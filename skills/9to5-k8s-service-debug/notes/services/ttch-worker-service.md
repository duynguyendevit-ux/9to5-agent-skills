# ttch-worker-service

- Namespaces: `dev-c7`, `dev-c7-ttdvkh`
- Repo: `null` in `config/apps.json` — no verified local checkout
- Type: scheduled / worker (polls event state)
- Port: `TODO(unverified)`

## Trigger

An event-handle worker loop. Each pass scans for due rows and logs a marker before running the query:

```
[EventHandleWorkerQuery] worker=<business>,cutoff=<timestamp>,limit=<n>
```

The `worker` value names the business flow; `cutoff` bounds `created_date_time` and `limit` caps the batch.

## Known business flows

Verified from the log-to-SQL binder in `config/helpers/rancher-log-alias.sh`, which infers the flow from the emitted SQL:

| Flow | Recognized by |
|------|---------------|
| `no-contact-60s` | SQL mentions `"no_verification_at"` and `"auto_calls"` |
| `no-final-verification-milestone` | SQL mentions `"event_elevate_level_histories"` and `"elevate_type"`, bound to `'NO_VERIFICATION_15_MINUTES'` |
| `dispatch-level-2` | `"event_level" < 2` |
| `dispatch-level-3` | `"event_level" < 3` |
| `device-state-expiration` | SQL mentions `"device_state_queues"` and `"expiration_at"` |

## Outputs

| Target | Detail |
|--------|--------|
| Oracle tables observed in queries | `event_elevate_level_histories`, `device_state_queues`; columns `event_level`, `elevate_type`, `expiration_at`, `created_date_time` |
| Kafka | `TODO(unverified)` — likely emits dispatch / notification events; confirm from producer config |

## Query shape

Scan queries filter `created_date_time <= :cutoff` and page with `offset :o rows fetch first :n rows only`. When binding worker metadata, the binder substitutes `offset 0` and the logged `limit`; the worker also injects `elevate_type = 'NO_VERIFICATION_15_MINUTES'` for the no-final-verification flow.

## Debug

```bash
kerror ttch-worker-service dev-c7
kfind  ttch-worker-service 'EventHandleWorkerQuery' dev-c7
ksql   ttch-worker-service dev-c7
```

## Failure modes

| Symptom | Log signature | Likely cause |
|---------|---------------|--------------|
| Flow never fires | no `[EventHandleWorkerQuery] worker=<flow>` line for the flow | worker disabled, cutoff clock skew, or scheduling stopped |
| Rows stay pending | `worker=<flow>` repeats with the same rows and `limit` never drains | query returns rows but the state update fails; check the following SQL for an update/rollback |
| Repeated dispatch | same event id dispatched on consecutive passes | idempotency/state flag not persisted |

## Open questions

- `TODO(unverified)` which repo builds this service. Lead: `~/Documents/service/ttch-woker-service` has remote `ttch-woker-service` but `rootProject.name = 'ttdvkh-worker-service'`, so it may be the TTDVKH worker rather than this app. Not recorded as the repo until confirmed.
- `TODO(unverified)` image source.
- `TODO(unverified)` Kafka topics produced.
- `TODO(unverified)` scheduler interval and `limit` config key.
