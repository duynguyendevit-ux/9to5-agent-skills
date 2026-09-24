# Kafka and long-running work queues

## Scope and evidence

Use this guide for import/export, reports, notifications, and other jobs whose execution
time or lifecycle differs from a short event handler. Separate traditional consumer
groups from share groups. The share-consumer details below are pinned to Kafka 4.2;
verify the deployed broker, client, and Spring integration before applying them.

The source article is useful architectural context, not the authority for API behavior:
https://zemit.substack.com/p/kafka-a-co-queue-that-va-ban-van

Technical claims were checked against Apache and AWS documentation on 2026-09-24.
This is documentation-based guidance, not a benchmark or a verified inventory of the
local cluster. Do not copy the article's sample code into production.

## Choose by required behavior

| Need | Candidate and trade-off |
|---|---|
| Independent subscribers, retained history, partition ordering, stream processing | Traditional Kafka consumer groups; job lifecycle remains application-owned. |
| Per-record acknowledgement and flexible sharing on an existing Kafka platform | Share groups; processing order is not guaranteed, and client/framework support must be checked. |
| Long jobs with progress, cancellation, checkpoints, or scheduling | Durable job store plus workers, optionally notified through Kafka or a queue; application owns claim/recovery logic. |
| Managed per-message delivery and visibility extension | SQS; reduces queue operations work but retains duplicates and application-level job state. |

Events describe facts; jobs describe intended work. Both can cause side effects, both
can require deduplication, and losing an event is not inherently less serious than
losing a job. Existing Kafka infrastructure is a legitimate cost consideration, not
proof that Kafka is either the right or wrong choice.

## Timeout and batching rules

| Mechanism | Meaning |
|---|---|
| `session.timeout.ms`, classic group protocol | Broker detects missing heartbeats, including process death and network failure. |
| `group.consumer.session.timeout.ms`, consumer protocol | Broker-controlled session timeout for the newer protocol. |
| `max.poll.interval.ms` | Bounds time between polls; detects lack of poll progress even when heartbeats continue. |
| `max.poll.records` | Limits records returned by a traditional consumer's poll; does not disable fetch buffering, producer batching, compression, or sequential writes. |

For example, a fifteen-minute poll interval and a forty-five-second session timeout do
not imply a fifteen-minute wait to detect an OOM-killed process. Missing-heartbeat
detection follows the session timeout; actual reassignment adds coordination time.
An alive consumer whose worker is stuck can continue heartbeating until the poll
interval expires. Static members stop heartbeating on poll timeout and reassignment
then waits for the session timeout. Do not promise exact failover latency from a single
configuration value.

For synchronous processing, budget the whole returned batch plus handler/commit overhead
against the poll interval. One record per poll reduces that batch budget but does not
make an arbitrarily long record safe. Async dispatch keeps polling responsive, but needs
backpressure, ownership tracking, and bounded in-flight work.

## Parallelism, ordering, and offsets

- One partition has at most one assigned consumer within a traditional consumer group.
  This limits active partition-owning consumers, not the total number of worker tasks.
- A consumer may dispatch multiple records to workers. This trades simpler ordering for
  offset tracking, rebalance handling, and possibly out-of-order effects.
- Commit the next offset after the completed prefix of delivered records for each
  partition. Do not commit past an unfinished or failed record without a durable,
  intentional handoff or failure disposition. Numeric offsets can contain gaps.
- A crash before commit can replay already completed work. Deduplicate by durable event
  or job identity; offset bookkeeping alone is not business idempotency.
- Adding partitions does not move old records. With hash-based key routing, changing
  the partition count can route a key's new records differently and break ordering
  across the transition.
- Keep consumer API calls on the owning thread; workers report results back. Handle
  revocation/loss explicitly and prevent stale workers from committing effects under
  an obsolete ownership claim.

Do not mark work successful in `finally`:

```java
try {
    runJob(record.value());
    reportSuccess(record); // owner thread later advances the safe commit position
} catch (Exception failure) {
    reportFailure(record, failure); // retry or durable failure disposition
} finally {
    releaseLocalResources();
}
```

This is control-flow pseudocode, not a complete consumer. Acknowledgement of a failed
attempt is valid only after the intended retry/failure handoff is durably recorded.
Inspect Spring acknowledgement and error-handler settings rather than equating Java
client defaults with the service's effective behavior. Auto commit is not proof that
jobs are already being lost; the polling/dispatch sequence determines the risk.

## Durable handoff pattern

```text
Kafka record containing eventId/jobId and parameters or an object reference
    -> database transaction: register job with a unique deduplication key
    -> commit database transaction
    -> acknowledge Kafka / advance the safe partition commit position

Job worker
    -> atomically claim eligible job with an ownership token and lease
    -> execute, checkpoint, renew lease, and check cancellation
    -> persist terminal status using the current ownership token
```

| Failure point | Required behavior |
|---|---|
| Registration fails before DB commit | Leave Kafka unacknowledged; retry delivery. |
| DB commit succeeds, Kafka acknowledgement fails | Redelivery finds the existing durable job; do not create a second job or reset its state. |
| Worker dies after claim | Lease/recovery logic makes work eligible again; resume from a durable checkpoint where possible. |
| Old worker continues after lease expiry | Ownership/fencing checks reject stale writes; external effects need their own idempotency support. |
| External effect succeeds, terminal status write fails | Retry must not repeat the effect; use a stable downstream idempotency key or reconciliation. |

The database transaction and Kafka acknowledgement are not one atomic operation here.
The intentional replay window is closed by deduplication, not by claiming exactly-once
execution. Store large input/output data outside the message and send references when
appropriate. Route schema changes through `9to5-sql-migration`.

Producer-side transactional outbox and consumer-side durable job registration solve
different failure windows. An outbox alone does not make downstream effects exactly once.

## Kafka 4.2 share groups

Kafka 4.2 made share groups production-ready and added `RENEW`. Multiple consumers can
acquire different records from one partition. Acknowledgements are per record:
`ACCEPT`, `RELEASE`, `REJECT`, and `RENEW`.

For long-running work:

1. Set `share.acknowledgement.mode=explicit` when using explicit acknowledgements.
2. Account for the acquisition lock: default duration is thirty seconds. Renewal is
   needed before expiry when processing exceeds the configured duration.
3. Keep polling and issue `RENEW` while processing continues. A local `acknowledge()`
   call is not yet a broker-confirmed renewal; acknowledgements are sent through poll
   or commit calls. Do not block the poll loop for a ten-minute export.
4. Explicit mode requires acknowledging all returned records before the next poll.
   Renew unfinished records and track them so redelivery after renewal does not launch
   the same local task again. Use topic/partition/offset identity, not offset alone.
5. Inspect commit result errors or acknowledgement callbacks. Treat renewal failure or
   ownership loss as a stale-worker condition. The share consumer is not thread-safe.
6. For strict delivery-count control, inspect `share.acquire.mode=record_limit` with
   `max.poll.records`; the default batch-optimized mode may exceed that record limit.
7. Do not interpret `REJECT` or a delivery-count limit as automatic routing to a DLQ.
   Design and verify the durable failure path separately.

Share groups do not guarantee processing order across consumers. Their acknowledgements
do not delete records from the topic; retention still applies. Traditional consumer
groups and share groups can independently consume the same topic, so adopting a share
group does not erase the log or globally remove replay capability. Distinguish replay
through another subscription from resetting an existing share group's delivery state.

Do not claim every service must upgrade its client simultaneously or that every non-Java
client is unsupported. Verify exact protocol compatibility and current client/framework
support. Broker readiness alone does not establish Spring Cloud Stream binder support.

## Queue semantics and operations

SQS Standard is at-least-once. Visibility extension reduces premature redelivery but
does not guarantee exclusive execution or exactly-once side effects. A stalled worker
can survive its lease. Scheduled renewal failures must be observed, not silently ignored.

Track job age, duration, attempts, expired leases, failure causes, and terminal outcomes
alongside Kafka lag and rebalance metrics. State whether lag is based on committed or
fetched position; neither directly measures job completion time. Workload cost can vary
for event processing as well as jobs.

Cancellation is application state checked before and during execution; removing a queue
message alone cannot stop a worker already executing it. Per-job priority, delay, TTL,
and lookup support vary by queue product; do not assume SQS supplies all of them.

## Authoritative references

- Consumer configuration (timeouts, static membership, poll record limits):
  https://kafka.apache.org/42/configuration/consumer-configs/
- Share-group production readiness and renewal release announcement:
  https://kafka.apache.org/blog/2026/02/17/apache-kafka-4.2.0-release-announcement/
- Share consumer acknowledgement, acquisition locks, renewal, and threading:
  https://kafka.apache.org/42/javadoc/org/apache/kafka/clients/consumer/KafkaShareConsumer.html
- SQS Standard delivery and idempotency:
  https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/standard-queues-at-least-once-delivery.html
