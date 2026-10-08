---
name: 9to5-scheduled-jobs
description: Design and review scheduled work and milestone pipelines in Platform services — DB polling versus Redis ZSET scheduling, dispatcher-to-Kafka handoffs, runtime mode switches, timezone and delay configuration, catch-up and missed-fire handling, and multi-replica safety. Use when adding or reviewing a scheduled worker, tuning milestone delays, introducing a runtime processing-mode switch, or diagnosing workers that did not run, ran late, or ran twice.
license: MIT
compatibility: Review is read-only; live diagnosis of a cluster worker goes through 9to5-k8s-service-debug. The reference architecture is the worker-service two-mode milestone pipeline as recorded in the vault.
metadata:
  version: "1.0.0"
---

# Scheduled jobs and milestone pipelines

## Example output

Illustrative review; delays and flags must come from the actual deployment.

```text
Pipeline: event-handle milestones (Level 2 20s, No verification 60s, Level 3 90s,
  No final verification 2m default / deployment override, Auto complete 30m default).
Modes: DB mode = 5 workers polling by time window; REDIS mode = ZSET due queue ->
  dispatcher -> Kafka -> consumer. Warm-up writes the ZSET in both modes.
Findings: runtime switch falls back to DB when Redis is unreachable (safe);
  milestone clock is UTC while business windows are documented in local time — confirm.
Open: multi-replica ownership of a due milestone is not stated — verify single-dispatch
  guarantee or idempotent consumption before scaling replicas.
```

## Scope and boundaries

- This skill owns **when work runs and who runs it**: schedule contract, mechanism
  choice, mode switching, catch-up, duplicate safety.
- Cache keys, TTLs and cache consistency around the schedule → `9to5-redis-design`.
- Event publication contracts and outbox mechanics → `9to5-kafka`.
- Process configuration values and their per-environment differences →
  `9to5-env-config-sync`; runtime proof of what actually runs → `9to5-k8s-service-debug`.

## Review workflow

1. **Write the schedule contract first.** For every milestone or job, name the trigger
   (delay after an event, fixed cron, queue arrival), the expected work, the acceptable
   lateness, and the behaviour on a missed window. A scheduler without a written lateness
   budget cannot be verified later.
2. **Choose the mechanism deliberately.** DB polling is simplest and survives Redis
   outages; ZSET scheduling gives precise due times and cheap ordering; Kafka dispatch
   decouples execution. The house two-mode design supports both behind a runtime switch,
   with the trade-offs below. See [`references/worker-modes.md`](references/worker-modes.md).
3. **Check the mode-resolution order.** Kill switch first, runtime key second, safe
   fallback on Redis errors, configured default when the value is invalid. Switching modes
   must not require a restart; both modes must share the same delays and business rules so
   a switch changes *how* work is found, not *what* is due.
4. **Check the warm-up path.** Whatever mechanism runs, an independent warm-up keeps the
   alternate structure current (registration writing the ZSET in both modes). Reconciliation
   on startup must be able to rebuild the scheduler state from the database.
5. **Check multi-replica safety.** For each job, state how N replicas avoid double
   execution: partitioned windows (disjoint time slices), claim with locks, single-leader
   dispatcher, or idempotent execution downstream. "It didn't double-run in dev" is not a
   guarantee.
6. **Check time and clock assumptions.** Milestone arithmetic uses one timezone (UTC in
   the reference) while business windows are described in local time; document the
   mapping and check DST behaviour for anything expressed in local hours.
7. **Check catch-up and staleness.** After a pause, deployment, or mode switch, what
   happens to due-in-the-past entries: fire immediately, fire late once, or skip with a
   record? Choose explicitly and test the boundary (exactly-due, just-missed window).
8. **Check observability.** At minimum — due-but-unfired age, fired count per interval,
   duplicate-fire detector, mode currently effective, and the age of the oldest pending
   item. Without these, a silent scheduler is indistinguishable from an idle system.
9. **Report** with proof labels and one next action.

## Mechanism trade-offs (short form)

| Mechanism | Strength | Cost / risk |
|---|---|---|
| DB polling windows | Survives Redis outages; easy to reason about | Lateness bounded by poll interval; scans can be heavy; window overlaps need care |
| ZSET due queue | Precise due times; cheap ordering; drains naturally | Redis becomes critical path; warm-up and reconciliation are mandatory |
| Dispatcher to Kafka | Decouples discovery from execution; natural backpressure control | At-least-once delivery; consumers must be idempotent; lag monitoring required |
| Fixed cron only | Simple for coarse schedules | No per-entity delays; missed windows need explicit catch-up |

## Rules worth enforcing

- Delay values are configuration, not constants in code; defaults live with the service,
  deployments may override — record which is active.
- A runtime switch has a kill switch (env) that wins, and a safe fallback when the switch
  store is unreachable.
- Every job that touches business state is idempotent or claimed; at-least-once is the
  default assumption for dispatch mechanisms.
- Warm-up/reconciliation exists for every derived schedule structure; derived state must
  be rebuildable from the source of truth.
- Milestone documentation states the timezone and the delay source next to the number.

## Safety

- Read-only review. Changing delays or switching modes in a live environment is an
  operational action with blast radius — it requires explicit approval and an owner,
  never a drive-by edit.
- When diagnosis requires firing behaviour evidence, prefer logs and metrics over
  manually triggering jobs in production.
- Do not paste full deployment manifests into notes; cite variable names and effective
  values, not secret content.

## Handoffs

- Key/TTL and cache-consistency aspects of the scheduler structures → `9to5-redis-design`.
- Topic and consumer-group contracts for dispatched work → `9to5-kafka`.
- Per-environment flag differences → `9to5-env-config-sync`.
- Live worker evidence (did not run, ran late, restarted mid-fire) →
  `9to5-k8s-service-debug`.
- Deadlocks or blocking when the scheduled job claims rows → `9to5-oracle-locking`.

## Stop conditions

- Schedule contract (trigger, lateness budget, missed-window behaviour) not stated:
  stop at the review question list; a scheduler cannot be verified without the contract.
- Multi-replica ownership unknown and the service runs more than one replica: report the
  duplicate-execution risk as unverified and block a "looks fine" verdict.
- Mode switch requested without a safe fallback path: refuse; fallback first, then switch.
