# Gateway pattern and delivery facts

Grounded in the notification-service checkout and the worker refresh flows recorded in
the vault (`TTCH Worker Service - EventHandle Cache Flows.md`). Recheck before relying on
a specific destination or config key.

## Gateway pattern

```java
@Component("MQTT")
public class MessageMqttGateway implements MessageGateway {
    MqttTemplate mqttTemplate;

    public MessageResults pushMessage(NotificationMessage message) {
        return new MessageResults(message.getDestinationList().stream()
            .map(destination -> {
                mqttTemplate.sendToTopic(message.getBody(), destination, 0);
                return MessageResult.ofSuccess(destination);
            })
            .toList());
    }
}
```

- One `MessageGateway` implementation per merchant/channel; Spring selects by qualifier
  (`@Component("MQTT")`, and a merchant enum carries the same code).
- `pushMessage` returns per-destination results — partial failures are visible, not
  swallowed.
- `MqttTemplate` and the Paho client factory come from the shared microservice starter
  (`tech.outsource.core.starter.integration.mqtt`), so connection options
  (`maxInflight` etc.) are starter/config concerns, not per-service code.

## Payload and destination facts

- Payload type: protobuf `NotificationMessage` (domain message from the shared protos)
  with `body` plus `destinationList`.
- QoS used for refresh delivery: `0` (literal in the gateway call). Loss is acceptable
  because the message is a hint.
- Destination comes from the message/business context, not constants in code.
- Broker configuration appears in service YAML as internal-domain placeholders
  (for example `domain.internal.mqtt`) resolved per environment; browser clients get a
  secure websocket front per environment. Values stay in environment configs — never
  copy them into skills, notes or tickets.

## Refresh flow in practice (worker side)

- State changes write cache/DB at `AFTER_COMMIT` time and trigger a refresh event so open
  UIs re-fetch (diary/event-handle flows do this via `sendRefreshEventMqttV2`).
- The refresh is additive to the durable path: the same state change also flows to
  downstream systems over Kafka (C7 sync) with outbox guarantees. MQTT and Kafka are not
  alternatives for the same guarantee level.

## QoS cheat sheet

| QoS | Guarantee | Use here when |
|---|---|---|
| 0 | At most once, fire-and-forget | Refresh hints (house default) |
| 1 | At least once, possible duplicates | A consumer that dedups and genuinely needs delivery |
| 2 | Exactly once, highest cost | Almost never for notifications; justify in writing |

Retained messages persist the last payload on a topic; useful for current-state topics
(dashboards), misleading for "something changed" hints. Decide per topic family and
document it where the topic is defined.

## Manual verification (dev)

- `mqttx` (installed locally) subscribes to the destination topic and prints payloads;
  `emqx` is the broker stack in the environment. Confirm shape against the protobuf
  definition before escalating to UI bugs.
- For app-side flows, the secure websocket front per environment is what the client uses;
  a working CLI subscription does not prove the wss endpoint or auth works.

## Failure modes to look for

| Symptom | Likely cause | First check |
|---|---|---|
| UI not refreshing, broker healthy | Publish failure swallowed or wrong destination | Gateway logs; destination value from context |
| Some users refresh, others do not | Destination scoping bug | Destination list construction |
| Refresh storm after reconnect | Session/retained policy unexpected | Topic family decision record |
| Business transaction failing on MQTT error | Publish wired into the transaction | Move publish after commit |
| Sends failing under broker outage | Outbound queue/inflight saturation | Client factory limits, broker health |
