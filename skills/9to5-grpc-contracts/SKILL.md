---
name: 9to5-grpc-contracts
description: Design and review gRPC/protobuf contracts for Platform services — the proto3 layout in the shared proto repository (service definitions versus domain messages, versioned packages), java_package conventions, wire-compatibility rules, artifact version flow, and server/client patterns with the lognet starter. Use when adding or changing a proto, exposing a new gRPC API, reviewing a breaking change, or bumping a proto artifact version.
license: MIT
compatibility: Reading contracts needs the shared proto/common-core checkouts. Version bumps flow through gradle.properties and the library fan-out belongs to 9to5-lib-bump. No code generation or proto edits happen in a review.
metadata:
  version: "1.0.0"
---

# gRPC contracts — proto layout, compatibility, versions

## Example output

Illustrative review; names and versions come from the actual checkout.

```text
Service: FacilityService (files/service/facility/facility_service.proto)
Package: java_package tech.source.protobuf.v1.service.facility
Messages: FacilityInformationRequest/Response import domain messages from
  tech.source.common.protobuf.domain.v1.facility.*
Change: added optional field `enabled` to FacilityInformation (field 7).
Verdict: additive, compatible; field numbers 1-6 untouched; no reserved gaps needed.
Version flow: bump PLATFORM_PROTO_VERSION in consuming services via 9to5-lib-bump.
Unverified: whether any client persists serialized bytes long-term.
```

## Scope and boundaries

- Owns contract shape and compatibility. Generated code is never edited; if a proto
  change is needed, it lands in the shared proto repository and consumers pick it up
  through artifact versions.
- Event contracts on Kafka are `9to5-kafka` territory; MQTT payload messages
  (`NotificationMessage`) follow this skill for the message definition and
  `9to5-mqtt-notifications` for delivery.
- Starter API and response conventions → `9to5-spring-core`; library version fan-out →
  `9to5-lib-bump`.

## Proto layout in the shared repository

Verified shape (recheck before copying):

```text
files/
├── domain/v1/<domain>/<message>.proto       # domain messages, imported by services
└── service/<domain>/<x>_service.proto       # service + request/response wrappers
```

Conventions observed:

- `syntax = "proto3"`, paths carry the version (`v1`) and the domain (`facility`).
- Service protos declare `option java_package = "tech.source.protobuf.v1.service.<domain>"`.
- Domain messages resolve to `tech.source.common.protobuf.domain.v1.<domain>.*` in Java
  (e.g. `NotificationMessage` under `...domain.v1.notifications`).
- Request/response wrappers live next to the service RPC they serve; shared domain types
  are imported, not duplicated.

Full rule set and compatibility matrix:
[`references/proto-conventions.md`](references/proto-conventions.md).

## Review workflow

1. **Locate the contract.** Find the service proto under `files/service/<domain>/` and
   the domain messages it imports. A change that touches only wrappers is cheap; a change
   to a shared domain message fans out to every consumer.
2. **Classify the change.** Additive field (safe), new RPC (safe for servers, clients
   only if deployed together), new enum value (safe if consumers tolerate unknown),
   field removal or type change (breaking), renumbering (always forbidden). See the
   reference matrix.
3. **Check field-number hygiene.** Deleted fields are `reserved` by number and name;
   numbers are never reused; `oneof` changes are treated as removals plus additions.
4. **Check semantics, not just wire shape.** Proto3 has no required fields and no
   presence for scalars — a semantic "must" (e.g. non-empty facility_code) belongs in
   validation on the server, stated in the contract review.
5. **Follow the version flow.** Contract changes ship as a new artifact version; consuming
   services bump `PLATFORM_PROTO_VERSION` / `COMMON_CORE_VERSION` in `gradle.properties`
   (with the `DEBUG_*` project overrides available for local sibling builds). The fan-out
   across services is `9to5-lib-bump` work.
6. **Check the call site.** Servers implement `@GrpcService` under `controller/grpc/...`;
   clients live under `repository/grpc/...`. Every client call gets a deadline; retries
   only for idempotent methods; business failures mapped deliberately instead of leaking
   raw exception text.
7. **Report** with proof labels, the compatibility verdict, and one next action (bump
   version, add validation, or "compatible, ship").

## Rules worth enforcing

| Rule | Reason |
|---|---|
| Domain messages shared, wrappers local | Avoids duplicated schemas across services |
| Version in path and java_package | Mixed-version consumers stay explicable |
| Never renumber or reuse a field | Old bytes must stay decodable |
| `reserved` on delete, name included | Prevents silent reuse and confusion |
| Additive-first changes | Rollout order stays simple in k8s |
| Deadlines on every client call | A missing deadline is an outage waiting to happen |
| Semantic validation server-side | Proto3 presence is not business validation |

## Safety

- Generated code, descriptor files and version properties are derived artifacts; fix the
  contract, never the generated output.
- Do not change an existing contract to satisfy one consumer without checking other
  consumers of the shared message.
- Contract changes affecting released services are release-affecting: state the rollout
  order (producers first / consumers first) explicitly in the review.

## Handoffs

- Library/proto version fan-out across services → `9to5-lib-bump`.
- Kafka event schemas and topic contracts → `9to5-kafka`.
- MQTT payload messages and delivery → `9to5-mqtt-notifications`.
- New feature needing a brand-new contract → `9to5-feature-prototype` first, then this
  skill for the contract itself.

## Stop conditions

- Shared proto repository unavailable: review what is checked out and mark the fan-out
  unverified; never guess message shapes.
- A required change is breaking and rollout order is unknown: stop and produce the
  rollout question list (who deploys first, can old and new coexist, what tolerates
  unknown fields).
- The change is only needed because a consumer misuses a message: fix the consumer
  instead of widening the contract.
