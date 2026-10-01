---
name: 9to5-oracle-locking
description: Design and review work-claim queries and lock contention on Oracle — FOR UPDATE SKIP LOCKED claiming, batch refill semantics, NOWAIT versus waiting, lock waits and deadlock (ORA-00060) diagnosis, and transaction hygiene for outbox-style jobs. Use when writing or reviewing a claim query, investigating blocked sessions or deadlocks, judging SKIP LOCKED behaviour under concurrency, or checking foreign-key TM contention. Produces structural review and read-only diagnosis steps; index decisions go to 9to5-oracle-index and DDL to 9to5-sql-migration.
license: MIT
compatibility: Read-only. Diagnosis views (v$lock, v$session, DBA_WAITERS) need SELECT_CATALOG_ROLE or specific grants; without them, deliver the review and the exact queries to run.
metadata:
  version: "1.0.0"
---

# Oracle locking and work claiming

## Example output

Illustrative review; verdicts must come from the actual query and environment.

```text
Query: batch claim of PENDING outbox rows, one producer, oldest first.
Shape: ROWID subquery -> TOP-N candidates -> FOR UPDATE SKIP LOCKED.
Verdict: lock scope is the claimed rows only (good); refill is not guaranteed when
  candidate rows are already locked, because the TOP-N cut happens before the lock step.
Contention risk: claim batches per producer serialize on the hot status='PENDING' range
  only while rows stay unlocked; index viability decides whether the probe is cheap.
Observed? no lock waits collected in this review — hypothesis, not measurement.
Next evidence: run reference diagnosis queries during a concurrent load test;
  index shape belongs to 9to5-oracle-index.
```

## Scope and boundaries

- This skill reasons about locking **behaviour**, not performance. Index usability,
  buffered reads and plan shape belong to `9to5-oracle-index`; DDL changes ship through
  `9to5-sql-migration`.
- Claim review is structural unless measurements are supplied. Never present an
  expected lock profile as observed; label it *hypothesis* until a diagnosis query or
  load test proves it.
- No DML is executed here. Deadlock analysis reads traces; it does not reproduce them
  on production.
- The worked claim example lives in
  `9to5-oracle-index/references/worked-example-outbox.md`; this skill extends it with
  concurrency, contention and transaction lifecycle reasoning.

## Claim-query review workflow

1. **Identify the shape.** Read the actual SQL and its caller: who executes it, how often,
   in which transaction, and what happens between the SELECT and the COMMIT. A claim
   query is only as good as the transaction that surrounds it.
2. **Check the lock step.** Row-level locks from `FOR UPDATE` are held until commit or
   rollback. Confirm what else runs inside that window — a remote call, a Kafka send, or
   a slow downstream read inside the lock window converts row locks into an outage.
3. **Check refill semantics.** With the ROWID-subquery pattern, TOP-N candidates are
   chosen before `SKIP LOCKED`; already-locked candidates reduce the returned batch even
   when further eligible rows exist. Treat short batches as normal and loop, or move the
   limit after the lock if the workload allows it — measure the trade-off.
4. **Check fairness and ordering.** `ORDER BY created_at` plus TOP-N gives oldest-first
   batches; without an order, batches are arbitrary and starvation is possible. Retry
   timing (`next_attempt_at`) should exclude backed-off rows *inside* the index probe,
   not after the heap fetch.
5. **Check the alternative shapes.** `NOWAIT` fails fast and suits single-claimant jobs;
   plain `FOR UPDATE` serializes claimants and usually loses to `SKIP LOCKED` for
   multi-worker batches; optimistic `UPDATE ... WHERE status='PENDING'` with a token
   avoids locks but needs duplicate-proof state transitions. See
   [`references/claim-patterns.md`](references/claim-patterns.md).
6. **Check the contention surface.** For each claim shape, name the object of contention
   (rows in status range, index leaf blocks, sequence, foreign-key parent table) and the
   evidence that would confirm it (enq waits, blockers, deadlock trace). The
   foreign-key TM trap — DML on a parent table blocking children whose FK columns are
   unindexed — belongs in every schema review.
7. **Report** with the proof labels this collection uses: measured, hypothesis,
   unverified, plus one next action (diagnosis query, load test, index review, or
   "none — shape is sound").

## Transaction hygiene checklist

| Rule | Why |
|---|---|
| Commit between claim and side effects | A claim exists to move state; publishing inside the lock window multiplies lock duration by downstream latency. |
| One batch, one commit | Batching commits shrinks lock windows and speeds worker recovery after a crash. |
| Never call HTTP/gRPC/Kafka while holding row locks | Remote latency is unbounded; locks are not. Outbox exists exactly to avoid this. |
| Keep `FOR UPDATE` sets small and bound | Lock count grows with batch size; monitor both. |
| Avoid `FOR UPDATE` on rows a human will edit | UI think-time inside a transaction is an outage generator. |
| Index the FK columns that update parents | Prevents TM locks shared by unrelated children. |

## Diagnosis (read-only)

Run the queries in [`references/diagnosis-queries.md`](references/diagnosis-queries.md)
while the symptom exists. A finished incident leaves the alert log and trace files, not
the waits themselves — capture during, or read the deadlock trace after.

- Blocking chain and current waits: `v$session` with `blocking_session`.
- Enqueue details: `v$lock` filtered to blocked/requesting rows, joined to `dba_objects`.
- Waiter/holder pairs: `DBA_WAITERS` / `DBA_BLOCKERS` (catalog privileges may be needed).
- Deadlock: ORA-00060 trace file from `v$diag_info` (`Default Trace File`), or the
  alert log entry naming the trace.

## Safety

- Read-only against the database; no session kills, no `ALTER SYSTEM`, no DDL.
- A diagnosis query can be heavy on a busy instance; prefer targeted filters
  (`WHERE s.blocking_session IS NOT NULL`, specific `sid` or `object_id`) over full scans
  of `v$active_session_history`.
- Do not paste trace content into tickets without checking for bind values and
  business data.

## Handoffs

- Index shape for the claim predicate → `9to5-oracle-index`.
- New or changed indexes/DDL → `9to5-sql-migration`.
- Claim query seen in logs, before any locking discussion → `9to5-sql-forensics`.
- Live service symptom (stuck worker, long waits) → `9to5-k8s-service-debug` first, then
  this skill for the database side.

## Stop conditions

- No database access and no captured waits: deliver the structural review and the exact
  queries to run; do not invent a lock profile.
- Deadlock report without a trace: name the missing trace and how to get it; do not
  guess the deadlock graph from the error code alone.
- Claim rewrite would touch more than the query (state machine, outbox contract): stop
  at the review and hand the change to the owning service work.
