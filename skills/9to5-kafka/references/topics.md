# Kafka contracts and bindings — C7/TTDVKH

Two layers, deliberately separate:

| Layer | Lives in | Owns |
|-------|----------|------|
| Contract | `common/kafka-spring-boot-starter` | topic names, payload types, partition keys, binding definitions, the event catalog |
| Delivery | `common-outbox` | transactional write, retry, publish acknowledgement, cleanup |

An event contract change is not a delivery change. Decide which layer you are in before editing.

## Event catalog

```
kafka-spring-boot-starter/src/main/resources/events/
├── <domain>/consumer.properties
├── <domain>/producer.properties
└── <domain>/<sub-domain>/consumer.properties
    <domain>/<sub-domain>/producer.properties
```

30 files across domains such as `event/fire`, `event/diary`, `event/facility/fire`, `notification/message`, `verification`, `flow/mobilization`, `marker/managementinformation`, `external/integration/facility/sector/activity`.

The Java package mirrors the resource path: `...starter.events.<domain>.<subdomain>`. Keep them in step — the auto-configuration resolves functions by name.

### Consumer

```properties
spring.cloud.stream.bindings.fireEventConsumer-in-0.destination=${topic.fire.event}
spring.cloud.stream.bindings.fireEventConsumer-in-0.group=${spring.application.name}
spring.cloud.stream.bindings.fireEventConsumer-in-0.content-type=application/x-protobuf;charset=UTF-8
spring.cloud.stream.bindings.fireEventConsumer-in-0.consumer.batch-mode=true
spring.cloud.stream.bindings.fireEventConsumer-in-0.consumer.concurrency=3
```

### Producer

```properties
spring.cloud.stream.bindings.fireEventProducer-out-0.content-type=application/x-protobuf;charset=UTF-8
spring.cloud.stream.bindings.fireEventProducer-out-0.destination=${topic.fire.event}
spring.cloud.stream.bindings.fireEventProducer-out-0.producer.partition-count=20
spring.cloud.stream.bindings.fireEventProducer-out-0.producer.partition-key-expression=headers['fireEventId']
```

Conventions to preserve:

- Binding names are `<function><Consumer|Producer>-<in|out>-<index>`. A rename breaks a deployed binding — treat it as a contract change.
- `destination` is always a `${topic.<...>}` placeholder, never a literal topic. The literal lives in the service's configuration, per environment.
- Payloads are protobuf (`application/x-protobuf;charset=UTF-8`).
- `partition-count=20`; the partition key is a header expression, not the payload body. The header must be set by the producer.
- Consumer group defaults to `spring.application.name`. Subscribers in the same group share topic partitions; use separate groups when each service needs its own copy of the events.
- Consumers that need ordering per entity must use one partition key for that entity across all producers.

### Opting in and out

| Annotation | Effect |
|-----------|--------|
| `@ConditionalOnFunctionDefinition` | wire only when the service defines the function |
| `@IncludeEventsProducer` | enable producer autoconfiguration |
| `@ExcludeEventsConsumer` | skip a consumer the service does not want |

A service that consumes some events and not others uses `@ExcludeEventsConsumer` rather than deleting the properties file, so the catalog stays the single source of truth.

## Adding an event type

1. Add `producer.properties` and `consumer.properties` under the right `events/<domain>/` path, following an existing pair in the same domain.
2. Add the Java package with the function definition and the payload type; keep the package path aligned with the resource path.
3. Add the `${topic.<...>}` entry to every environment's service config (`ots-env-custom/service-configs/<env>/<service>/values.yaml` or `.env`) — a missing placeholder fails at startup, not at publish time.
4. Set the partition-key header required by the expression. Verify missing-key behavior for the deployed binder/client; it may reject the message or use another routing path. Constant keys cause hot partitions; a missing header does not universally mean partition zero.
5. Verify both sides: `JAVA_HOME=~/.jdks/corretto-17.0.19 ./gradlew build` in the starter (it versioning) and in each consumer.

## Topics in the outbox path

When a service publishes through the outbox instead of a direct producer binding:

- The outbox row stores the resolved topic. `outbox.topic` is the fallback; a blank resolved topic is rejected before the row is written.
- `aggregate_id` becomes the Kafka key, so per-entity ordering depends on it being stable and non-blank.
- The topic name in the row is what the publisher uses; changing `outbox.topic` does not rewrite existing rows.

Contract naming and delivery retry are independent: a topic typo shows up as publish failures with `last_error`, not as a contract error.

## Failure signatures

| Signature | Layer | Likely cause |
|-----------|-------|--------------|
| startup fails on an unresolved `${topic...}` | config | placeholder missing in that environment |
| no events, no errors, consumer idle | contract | wrong `destination`, wrong group, or the service excluded the consumer |
| independent service sees only part of a topic | contract | it shares a consumer group with another subscriber, so partitions are load-balanced |
| duplicate processing | delivery | redelivery after failure/rebalance, offset timing, producer retries, or application retry; shared group membership alone is not a duplicate mechanism |
| one partition hot, others idle | contract | constant/skewed keys or binder/partitioner configuration; inspect resolved keys and partitions |
| publish fails repeatedly, row stays `PENDING` | delivery | topic missing, broker unreachable, payload rejected — check `last_error` in `references/outbox-queries.sql` |
| payload missing a field after publish | contract | template or schema mismatch between producer and consumer versions |
