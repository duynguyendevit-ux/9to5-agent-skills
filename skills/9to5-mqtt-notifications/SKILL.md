---
name: 9to5-mqtt-notifications
description: Design and review MQTT delivery of notification and refresh events in Platform services — the merchant gateway pattern, destination semantics, NotificationMessage payloads, QoS choice, client limits, environment configuration keys, and when MQTT is the wrong channel. Use when adding or debugging a refresh event to apps, touching a MessageGateway implementation, choosing QoS or retained messages, or deciding between MQTT and Kafka for a notification.
license: MIT
compatibility: Review needs the service checkout and, for live checks, cluster access through 9to5-k8s-service-debug. Broker URLs and credentials live only in per-environment service configs; never hardcode or print them.
metadata:
  version: "1.0.0"
---

# MQTT notifications — refresh events and the gateway pattern

## Example output

Illustrative review; destinations and payloads come from the actual service.

```text
Feature: notify the app that an event handle changed, so the UI re-fetches.
Channel: MQTT refresh via MessageMqttGateway (@Component("MQTT")) -> MqttTemplate.sendToTopic(body, destination, 0)
Payload: NotificationMessage protobuf (body + destinationList) from platform protos.
Verdict: QoS 0 is right for a refresh hint — a lost message heals on the next event or
  user action; no retained flag needed.
Config: broker URL resolves from the env config key (domain.internal.mqtt); destination
  chosen per message, not hardcoded.
Unverified: whether the receiver treats a refresh as state — it must re-fetch, not apply.
```

## Scope and boundaries

- Owns delivery of realtime hints to clients (app refresh, operator UI) over MQTT, and
  the gateway abstraction that routes a notification to one merchant/channel.
- Business events and state transfer stay on Kafka (`9to5-kafka`); push notifications to
  phones use their own merchant gateway. Choosing the wrong channel is the most common
  design error this skill exists to catch.
- Payload message definitions follow `9to5-grpc-contracts`; environment values for broker
  and destinations follow `9to5-env-config-sync`.

## Channel decision (do this first)

| Need | Channel |
|---|---|
| UI hint that something changed; loss is tolerable | MQTT refresh (this skill) |
| State that other services must process exactly once | Kafka + outbox (`9to5-kafka`) |
| Message reaching a phone that may be offline | Push merchant (FCM and friends) |
| Synchronous request/response | gRPC (`9to5-grpc-contracts`) |

A refresh event is a **hint, never state**: receivers re-fetch the truth from the API or
cache. If a consumer applies the payload as state, the design drifts into an unreliable
event-sourcing channel over QoS 0.

## Workflow

1. **Find the gateway.** Notification services route through a `MessageGateway`
   implementation selected by merchant; MQTT is one `@Component("<MERCHANT>")` among
   several. Read the implementation before changing anything — the interface contract is
   the fan-out point.
2. **Check the payload.** Messages are protobuf (`NotificationMessage` with a body and a
   destination list). Keep the body small and free of secrets; the client is a user
   device or UI, not a trusted service.
3. **Check destinations.** Destinations are per-message data, resolved from business
   context (user/device/session scopes), never hardcoded in code. Broker endpoints come
   from the environment config key convention (for example `domain.internal.mqtt`), with
   secure websocket fronts for browser clients supplied per environment.
4. **Choose QoS deliberately.** The house pattern sends refresh notifications at QoS 0 —
   fire-and-forget is correct when the receiver re-fetches anyway. Any move to QoS 1/2
   requires a stated business reason (dedup cost, ordering assumptions) and evidence
   that the broker and clients are configured to match.
5. **Decide retained/session behaviour explicitly.** Retained messages make sense for
   current-state topics; refresh hints usually do not retain. Clean-session behaviour
   decides whether a reconnecting client sees a burst — write the decision down per
   topic family.
6. **Understand client limits.** The MQTT client factory exposes connection options such
   as `maxInflight`; under broker outage, outbound queues fill and sends fail. Publishing
   is best-effort and must not fail the business transaction — send after commit, log
   failures, and let the next event heal the UI.
7. **Prove it manually when needed.** In dev, use an MQTT client (mqttx is installed) to
   subscribe to the destination and watch the refresh arrive; the EMQX broker is the
   environment's broker. Confirm the message shape matches the protobuf before blaming
   the UI.
8. **Report** with proof labels and one next action.

## Rules worth enforcing

| Rule | Reason |
|---|---|
| Refresh hints only; receivers re-fetch | QoS 0 cannot carry state guarantees |
| Publish after commit | MQTT failure must not roll back business state |
| Destinations are data, endpoints are config | Per-environment differences without code changes |
| Small protobuf payloads, no secrets/PII beyond UI need | Client-side exposure surface |
| QoS and retained decisions documented per topic family | Prevents accidental guarantees |
| Gateway per merchant, one interface | Adding a channel never forks the notification flow |

## Safety

- Never print broker URLs, credentials or full destination lists into notes or tickets;
  reference the config key, not the value.
- Live delivery debugging is read-only (subscribe, observe); publishing test messages to
  shared destinations needs an explicit decision.
- Payload bodies may contain user/device data — sanitize before attaching evidence.

## Handoffs

- Protobuf message changes → `9to5-grpc-contracts`.
- Broker keys, per-environment values → `9to5-env-config-sync`.
- Business event delivery (the durable path) → `9to5-kafka`.
- Live connectivity, pod logs, broker reachability → `9to5-k8s-service-debug`.
- Device error/refresh flows → inspect the selected service's own source-backed contracts.

## Stop conditions

- The request treats a refresh hint as durable state: stop and name the Kafka/outbox
  alternative; do not add QoS/retry complexity to an MQTT hint.
- Broker or destination values missing from config: report the missing key; never guess
  endpoints.
- A change would require every client to handle a new protocol behaviour (session,
  retained, QoS): list the client-side impact and stop at the recommendation.
