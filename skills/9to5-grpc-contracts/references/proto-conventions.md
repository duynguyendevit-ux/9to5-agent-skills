# Proto conventions and compatibility matrix

Grounded in the shared proto checkout (`common-core/files`) and consumer build files.
Recheck the checkout before relying on a specific package or version.

## Layout

```text
files/
├── domain/v1/<domain>/<message>.proto   # shared messages (imported)
└── service/<domain>/<x>_service.proto   # services + request/response wrappers
```

- Service protos declare `option java_package = "tech.source.protobuf.v1.service.<domain>"`.
- Domain messages appear in Java as `tech.source.common.protobuf.domain.v1.<domain>.*`
  (example in the wild: `...domain.v1.notifications.NotificationMessage` used by the
  notification-service MQTT gateway).
- Domains seen: category, core, device, diary, facility, notifications, worker, event,
  verification, flow, importfacility, mobilizationservice.
- `grpc-spring-boot-starter` (lognet) serves the server side; artifact versions come from
  `PLATFORM_PROTO_VERSION` / `COMMON_CORE_VERSION` in `gradle.properties`, with
  `DEBUG_*` flags switching to local project builds.

## Compatibility matrix

| Change | Wire-safe? | Notes |
|---|---|---|
| Add a field with a fresh number | Yes | Old readers ignore it; new readers default it |
| Add an RPC | Yes | Servers tolerate; clients must be deployed aware |
| Add an enum value | Mostly | `UNKNOWN`-tolerant consumers required |
| Rename a field | Yes (wire) / breaking (JSON, reflection, codegen names) | Treat renames as removals plus additions |
| Remove a field | Breaking for readers that still send it | `reserve` number and name |
| Change a field's type or number | Never | Silent corruption risk |
| Change `optional` to `repeated` or vice versa | Never on the same number | Reserve and introduce a new field |
| Move a message between files | Package-safe if java_package unchanged | Descriptor churn only |
| Change `java_package` | Yes on the wire; breaking for source | Coordinate as a release |

## Field-number hygiene

```proto
message FacilityInformation {
  reserved 4, 5;
  reserved "legacy_code", "old_name";
  // 6+ continue
}
```

- Reserve both number and name; reviewers reject reuse even if "clearly unused".
- Keep numbers dense only within a new message; never compact an existing one.
- `oneof` membership changes are removals plus additions; state which members existing
  senders may still emit.

## Style

- snake_case field names, CamelCase messages, `XxxService` for services, and
  `XxxRequest` / `XxxResponse` or the domain type as return.
- Keep wrappers minimal: no envelope duplication that Kafka headers or HTTP already carry.
- Comments on non-obvious fields; enums include an explicit unknown/zero value when the
  business distinguishes "not set" from a real value.

## Server and client patterns (from service checkouts)

- Server: `@GrpcService` implementation under `controller/grpc/<area>/` delegating to
  use-case services; business errors mapped to gRPC status + description.
- Client: thin clients under `repository/grpc/<area>/`; set a deadline per call; retry
  only idempotent methods; translate transport errors into domain errors before they
  reach use cases.
- Generated stubs are build artifacts — never committed, never hand-edited.

## Version flow

1. Proto change lands in the shared repository, published as a new artifact version.
2. Consuming services bump the version property in `gradle.properties`.
3. The cross-service bump (find every consumer, build each, commit) is `9to5-lib-bump`.
4. Rollout order: additive changes tolerate any order; removals require consumers to stop
   sending before producers drop handling — state it in the MR.

## Review checklist

1. Contract located; change classified (additive / breaking / cosmetic).
2. Numbers reserved where removed; no reuse or renumbering.
3. Semantic "must" rules stated for server-side validation.
4. java_package and path version intact.
5. Deadlines and retry policy on affected client calls.
6. Version bump path named (which property, which consumers).
7. Rollout order stated for anything non-additive.
