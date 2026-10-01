# Claim patterns and their trade-offs

Structural reasoning for Oracle work-claiming. Numbers are never claimed here; run
`9to5-oracle-index` plan checks and concurrent load tests for measurements.

## Pattern A — ROWID subquery + TOP-N + SKIP LOCKED

The house pattern (see `9to5-oracle-index/references/worked-example-outbox.md`):

```sql
SELECT outbox.*
FROM outbox_record outbox
WHERE outbox.ROWID IN (
    SELECT candidate_rowid
    FROM (
        SELECT candidate.ROWID AS candidate_rowid
        FROM outbox_record candidate
        WHERE candidate.producer = :producer
          AND candidate.status = 'PENDING'
          AND (candidate.next_attempt_at IS NULL OR candidate.next_attempt_at <= :now)
        ORDER BY candidate.created_at
    )
    WHERE ROWNUM <= :batchSize
)
ORDER BY outbox.created_at
FOR UPDATE SKIP LOCKED;
```

Properties to reason about, not assume:

- **Candidate cut happens before locking.** If the first N candidates are locked by other
  workers, the claim returns fewer than N rows even when eligible rows exist later in the
  order. Workers must loop until short/empty, and designs must not assume full batches.
- **Lock scope is the outer rows only.** The inner query takes no locks; the locking step
  waits on nothing (SKIP LOCKED) and holds rows until commit.
- **Ordering has two parts.** Inner order picks candidates; outer order defines the
  returned sequence. Only the real plan shows whether sorts disappear.
- **Retry eligibility belongs in the index.** When `next_attempt_at` is only a heap
  filter, candidates cost visits even when rejected; the trailing composite candidate
  (`producer, status, created_at, next_attempt_at`) is the measured alternative.
- **Stuck rows do not age out.** `created_at <= cutoff` excludes newer rows; nothing here
  rescues rows whose worker died. Monitor the oldest PENDING age per producer.

## Pattern B — NOWAIT single claimant

```sql
SELECT ... WHERE ... FOR UPDATE NOWAIT;
```

- Fails immediately when any candidate row is already locked; good for exactly-one
  worker or a lock-probe/leader-election check.
- In multi-worker pools it turns contention into a `ORA-00054` retry loop; only use it
  when the caller treats the error as "someone else is on it".

## Pattern C — direct FETCH FIRST + SKIP LOCKED

```sql
SELECT ... WHERE status = 'PENDING'
ORDER BY created_at
FETCH FIRST :batchSize ROWS ONLY
FOR UPDATE SKIP LOCKED;
```

- No ROWID indirection; simpler shape, but the optimizer's top-N and the lock step
  interact: verify with the actual plan that the order is stable and the row limit still
  yields a usable batch under concurrency.
- Often fine at small scale; prove it before adopting it for a hot producer range.

## Pattern D — optimistic claim (no row locks held)

```sql
UPDATE outbox_record SET status = 'PROCESSING', claim_token = :token, claimed_at = :now
WHERE id = :id AND status = 'PENDING';
-- commit, then process, then UPDATE ... WHERE id = :id AND claim_token = :token;
```

- Contention becomes short write locks instead of long read locks; throughput scales
  better when processing time is long.
- Requires duplicate-safe state transitions and a claim token in the schema, plus
  reclamation for tokens whose worker died (timeout sweep).
- The `UPDATE ... WHERE status='PENDING'` guard is the claim; never re-select then update
  without the status predicate.

## Choosing between them

| Situation | First choice |
|---|---|
| Many workers, long processing per row, same producer | D (optimistic) or A with generous looping |
| Short processing, batch semantics acceptable | A |
| One claimant, want fast failure | B |
| Simple low-volume queue, plan verified | C |
| Human-in-the-loop editing on claimed rows | avoid claiming entirely; lock on submission only |

## Monitoring that belongs with any claim design

- Oldest PENDING age per producer (stuck worker early warning).
- Claimed-but-unfinished age (leaked claims or crashed workers).
- Short-batch frequency, if full batches are part of the contract.
- Blocked-session count during peak, per claim object (rows vs FK parents).
