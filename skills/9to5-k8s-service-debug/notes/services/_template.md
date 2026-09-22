# <app-name>

- Namespaces: `dev-c7`, `dev-c7-ttdvkh` (copy verbatim from `config/apps.json`; a service can run in both)
- Repo: `<repo from config/apps.json>` — if `repo` is `null` there is no verified checkout; write `null in registry` and do not guess a path
- Type: `rest` | `grpc` | `kafka-consumer` | `kafka-producer` | `cron` | `mqtt`
- Port:
- Image / deploy source:

## Trigger

What starts work in this service. Kafka topic + group, REST path, gRPC method, cron expression, MQTT topic, or scheduled poll.

## Inputs

| Source | Detail |
|--------|--------|
| | |

## Outputs

| Target | Detail |
|--------|--------|
| Oracle tables | |
| Redis keys | |
| Kafka topics | |
| External calls | |

## Dependencies

Upstream services/topics that must be healthy, and downstream consumers that break if this service stalls.

## Config

Config keys read at runtime (`app.module.exts`, feature flags, timeouts). Point at `ots-env-custom/service-configs/<env>/<app>/` for values; do not paste values.

## Failure modes

| Symptom | Log signature | Likely cause |
|---------|---------------|--------------|
| | | |

## Open questions

- `TODO(unverified)` items to confirm on the next session.
