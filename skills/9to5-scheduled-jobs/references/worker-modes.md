# Worker modes — the two-mode milestone pipeline

Reference architecture: `worker-service` event-handle milestones, as recorded in the
vault (`Internal/Code/User/worker-service/PLATFORM Worker Service - Event Handle
Schedule Mode.md` and the cache-flow note). Recheck the checkout before relying on
details; this file generalizes the pattern.

## The shape

```text
Outbox DB -> Registration -> ZSET schedule:event-handle:due   (warm-up, always on)
                                  |
                 +----------------+-----------------+
                 v                                  v
      DB mode: 5 workers poll DB          REDIS mode: dispatcher reads ZSET
      by time window, process             -> publish Kafka -> consumer processes
      milestones directly
```

- **Warm-up always runs.** Registration writes the ZSET regardless of mode, so the
  alternate path is current the moment the switch flips.
- **Mode decides execution, not the definition of due.** Delays and business rules are
  shared; only discovery differs.
- **Runtime switch.** Env kill switch wins; otherwise the mode comes from a Redis key,
  with DB as the safe fallback when Redis is unreachable or the value is invalid.

## Generalizing the pattern

Any Platform service that owns per-entity delays (milestones, retries, expirations) can use
this architecture with the following invariants:

1. **One definition of due.** Due time is computed from entity state and configured
   delays by a single component; both execution modes consume that same computation.
2. **Derived structures are rebuildable.** Startup reconciliation can reconstruct the
   ZSET (or window cursors) from the database after data loss.
3. **Idempotent execution.** Every fired milestone is safe to process twice: state
   transitions are guarded by status checks; side effects (Kafka publish) go through the
   outbox.
4. **Disjoint discovery.** In DB mode, worker windows do not overlap; in REDIS mode, the
   dispatcher claims due entries (`ZRANGEBYSCORE` + remove/claim) so two dispatchers
   cannot pick the same item. Multi-replica deployments rely on this, not on luck.
5. **Safe fallback direction.** Any uncertainty (Redis down, invalid value, first start)
   resolves to DB mode; the aggressive/realtime path is never the default.

## Failure modes and the questions that expose them

| Failure mode | Question to ask | Expected answer |
|---|---|---|
| Double fire after replica restart | How does a second replica avoid picking the same due item? | Claim/remove or single-dispatcher election; not "it is unlikely" |
| Mode switched mid-flight | What happens to items already discovered by the old mode? | Idempotent execution makes overlap harmless; verify guards |
| Redis unavailable | Which mode runs? | DB, with lateness bounded by the poll interval |
| Backlog after outage | Old due items — fire late once, immediately, or skip? | Explicit policy, tested at the boundary |
| Clock drift / timezone | Which zone computes due times? | One configured zone (UTC in the reference), documented against business windows |
| Silent scheduler | What alerts when nothing fires? | Due-but-unfired age and fired-count metrics per interval |
| Delay override drift | Deployment values vs repo defaults | Recorded which is effective; differences explained (the reference snapshot found overrides faster than the documented business windows) |

## Minimal evidence set for a live diagnosis

- Effective mode: the runtime key's value plus the env kill switch.
- Oldest due-unfired item and its age.
- Fire counts per milestone per interval (log or metric).
- Dispatcher lag: due items vs published items.
- Recent restarts of the owning deployment (k8s events) aligned with gaps.

Collect through `9to5-k8s-service-debug`; this file defines what to collect, not how.
