---
name: 9to5-kafka
description: Work on OTS/C7 Kafka contracts, transactional outbox, and Kafka-versus-work-queue design. Add events and bindings, diagnose outbox backlog, and review long-running consumers, poll timeouts, offset commits, duplicate handling, and Kafka share groups. Use for Kafka topics, partition keys, consumer groups, protobuf events, outbox_record, payload_template, unpublished events, Kafka-backed import/export jobs, rebalance loops, max.poll.interval.ms, or Kafka 4.2 share-group adoption.
license: MIT
compatibility: Requires git checkouts of the kafka starter and common-outbox, JDK 17, and read access to the service Oracle schema for diagnosis (directly or through the 9to5-k8s-service-debug helper).
metadata:
  version: "1.1.2"
---

# Kafka Contracts, Outbox, and Work Queues

## Example output

Illustrative long-running consumer review; report actual deployed settings when available.

```text
Finding: synchronous export can exceed the configured poll interval.
Evidence: handler runs on the polling thread; observed export duration is 10 minutes.
Group type: traditional consumer group.
Design: register a deduplicated durable job, then acknowledge Kafka after DB commit.
Worker responsibility: lease, progress, retries, cancellation and idempotent effects.
Timeout distinction: missing heartbeats use session timeout; stalled polling uses max.poll.interval.ms.
Verification pending: crash between DB commit and Kafka acknowledgement; duplicate registration must be harmless.
```

Two layers. Decide which one you are in before editing anything.

| Layer | Where | Owns |
|-------|-------|------|
| Contract | `~/Documents/C777777777777/common/kafka-spring-boot-starter` | topic names, payload type, partition key, bindings, event catalog |
| Delivery | `~/Documents/C777777777777/web-establishment-registration/common-outbox` | transactional write, retry, acknowledgement, cleanup |

- `references/topics.md` — catalog layout, binding conventions, how to add an event type, contract failure signatures.
- `references/outbox-queries.sql` — read-only Oracle diagnosis queries for `outbox_record` and `payload_template`.
- `references/work-queues.md` — read before designing Kafka-backed jobs, diagnosing long-running consumers, or adopting share groups; includes verified corrections to the linked Kafka queue article.
- Library setup (dependency, config block, DDL, `append(...)` forms) is documented in `common-outbox/README.md`. Read it rather than re-deriving it; do not duplicate it here.

## Contract work

1. Find the domain under `src/main/resources/events/<domain>/`; match the existing `consumer.properties` / `producer.properties` pair in that domain.
2. Keep the Java package path aligned with the resource path.
3. `destination` is always a `${topic.<...>}` placeholder. The literal topic belongs in the environment config (`ots-env-custom/service-configs/<env>/<service>/`), so a new topic needs an entry there too — otherwise the service fails at startup, not at publish time.
4. Set and verify the partition-key header expected by the binding. A missing header may fail expression validation or invoke binder/partitioner-specific behavior; do not assume a fixed partition. A constant key concentrates traffic. Verify actual routing before claiming per-entity ordering.
5. Consumer group defaults to `spring.application.name`. Services with the same group that subscribe to the same topic load-balance its partitions rather than each receiving every event. Use separate groups for independent subscribers.
6. Build both sides before claiming done: `./gradlew build` in the starter and in each affected service (Gradle picks JDK 17 from `~/.gradle/gradle.properties`; override with `JAVA_HOME` only if needed).

Details and the annotation table (`@IncludeEventsProducer`, `@ExcludeEventsConsumer`) are in `references/topics.md`.

## Long-running consumers and work queues

1. Establish broker/client versions, group protocol, Spring binder/container acknowledgement mode, and the actual poll/worker threading model before proposing changes.
2. Separate transport acknowledgement from job completion. For durable handoff, register a deduplicated job in a database transaction, then acknowledge Kafka after that transaction succeeds. Workers manage execution, leases, progress, and retries.
3. Distinguish heartbeat failure (session timeout) from stalled polling (`max.poll.interval.ms`). Raising the poll interval does not make a dead pod undetectable for that duration.
4. Treat partition count as the active-consumer assignment ceiling in a traditional group, not an absolute worker-thread ceiling. Concurrent processing needs bounded capacity and safe offset tracking.
5. For Kafka 4.2 share groups, check explicit acknowledgement, acquisition-lock renewal, continued polling, acknowledgement errors, and framework support. An API change alone does not make ten-minute jobs safe.

Use `references/work-queues.md` for trade-offs, failure examples, and version-pinned sources. Keep idempotency and stale-worker protection explicit regardless of broker choice.

## Outbox diagnosis

Run the queries in `references/outbox-queries.sql`. Always scope to one `producer` — the table can be shared by several services in the same schema.

Order that gets to a cause fastest:

1. **Backlog by status** (query 1). `PENDING` growing with `PUBLISHED` flat means the publish worker is not draining. `PENDING` stable means records are being written and published normally.
2. **Due now versus total pending** (query 3). Pending rows all scheduled into the future means backoff is doing its job, not that the service is stuck.
3. **Failure reasons grouped** (query 4). One dominant `last_error` points at a single cause — a missing topic, an unreachable broker, or one malformed payload shape.
4. **Stuck records** (query 2) — high `attempt_count` with a recent `next_attempt_at` means the worker is alive and the publish keeps failing.
5. **Templates** (query 8) when `payload_template_code` is set: a `MISSING` or `INACTIVE` template row fails every event that uses it.
6. **Cleanup** (query 9) when the table grows without bound: a large candidate count with cleanup enabled means the cron is not running.
7. **Ordering** (query 6) when downstream reports out-of-order effects: the Kafka key is the aggregate type, not the aggregate id, and retries/concurrent sends do not guarantee commit order — treat a published row preceding a still-pending row for the same aggregate as a canary for the relevant contract, not automatic proof of a bug.

### Outbox configuration surface

Prefixes: `outbox`, `outbox.publish`, `outbox.cleanup`, `outbox.payload-template`. Defaults worth knowing when reading the queries: publish runs every 300 ms in batches of 100 with a 5 s retry backoff growing to 5 minutes; cleanup runs at 03:00 `Asia/Ho_Chi_Minh` with 7-day retention, batches of 500. Treat the library's `OutboxProperties` as the source of truth for exact defaults, and the service's `values.yaml` / `.env` for what is actually deployed.

## Traps

- **The append must be inside the business transaction.** Outside it, the business write and the outbox row commit separately and the event can be lost or duplicated.
- **`outbox_record` can be shared by several services in one schema.** Every query needs `producer`, or the numbers are meaningless. Cleanup and the publish worker only touch their own rows.
- **The library ships its own auto-configuration.** A service must not declare `OutboxModuleLoader`. A service whose base package is not `tech.app` needs the loader adapted, otherwise the feature repositories and entities are not scanned.
- **Oracle-specific claim.** Claiming uses `ROWID` with `FOR UPDATE SKIP LOCKED`; local H2 runs cannot claim batches. A local "worker does nothing" report is expected, not a bug.
- **Existing rows keep their stored topic.** Changing `outbox.topic` does not rewrite pending rows.
- **Do not change the DDL from this skill.** Table changes go through a migration (see `9to5-sql-migration`); the reference DDL lives in `common-outbox/files/`.

## Escalation

| Situation | Skill |
|-----------|-------|
| Need the runtime symptom (pod logs, lag observed live) | `9to5-k8s-service-debug` |
| Need a DDL or data fix for `outbox_record` / `payload_template` | `9to5-sql-migration` |
| Library version needs bumping across services | `9to5-lib-bump` |
| Environment variable or topic placeholder missing in a deployed env | `9to5-env-config-sync` |
