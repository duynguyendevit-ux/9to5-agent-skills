# Worked example: outbox claim and cleanup

Reference sources: `common-outbox/files/outbox-oracle.sql` and
`common-outbox/java/src/main/java/tech/features/outbox/repository/OutboxRepository.java`.
Recheck the target checkout before relying on this shape. This analysis is structural;
no database measurements or executed plans are recorded here.

## Claim shape

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
          AND candidate.created_at <= :cutoff
          AND (candidate.next_attempt_at IS NULL
               OR candidate.next_attempt_at <= :now)
        ORDER BY candidate.created_at
    )
    WHERE ROWNUM <= :batchSize
)
ORDER BY outbox.created_at
FOR UPDATE SKIP LOCKED;
```

Cleanup uses producer/status=`PUBLISHED`, `published_at < :cutoff`, and publication
ordering. Candidate indexes in the reference DDL are:

```sql
CREATE INDEX ix_outbox_record_claim
    ON outbox_record (producer, status, created_at);
CREATE INDEX ix_outbox_record_cleanup
    ON outbox_record (producer, status, published_at);
```

## Expected benefits to verify

- Producer/status equality predicates can delimit a key range, and the timestamp can
  bound it. Status can be highly selective if pending rows are rare; two distinct
  values do not imply low usefulness.
- The claim index may supply the inner timestamp order. The outer ROWID lookup/query
  block may still sort. An index definition alone does not prove the absence of sorts.
- `created_at <= cutoff` excludes newer rows; older stuck rows remain eligible for that
  predicate. It does not age them out. Retry timing may separately exclude them.
- A top-N operation can stop after enough eligible candidates, but may inspect many
  rejected rows before reaching the batch size. Inspect the real plan and buffers.
- Producer/status COUNT and MIN queries may use covering access when row coverage and
  nullability permit it; verify actual plan choice.

## Costs and concurrency

The original claim index lacks next_attempt_at, so that eligibility predicate normally
needs a heap lookup for each candidate. Index maintenance also affects inserts, status
changes, publication timestamps and deletion. Quantify workload costs rather than
assuming a fixed performance penalty.

The inner query limits candidates before the outer locking step. If selected candidates
are already locked, SKIP LOCKED can return fewer rows than the requested batch even
when additional eligible rows exist beyond that candidate set. Do not describe this
shape as guaranteed to refill a full batch. Test concurrent claim behavior separately
from nonlocking SELECT performance.

## Alternative to measure

```sql
CREATE INDEX ix_outbox_claim_candidate
    ON outbox_record (producer, status, created_at, next_attempt_at);
```

The trailing retry timestamp can allow index filtering without heap visits for rejected
candidates, while retaining a timestamp-ordered candidate path. It widens the index and
adds maintenance when retry timing changes. Compare buffers, heap visits and DML impact;
do not infer rejected-row counts from a simple ratio of cumulative A-Rows.

Use a distinct candidate index name for evaluation in an approved environment. Merely
guarding CREATE INDEX by the old name would skip creation and leave the old definition.
The decision to replace an existing index needs an explicit migration and rollback plan.

## Shipping and verification

Use `9to5-sql-migration` and the guarded DDL pattern in SKILL.md. Verify index columns,
order, validity and exact quoted identifier case; a name match is insufficient. Decide
ONLINE support and resource/locking costs for the actual Oracle edition/version.

Prefer an existing cursor with collected statistics. If authorized measurement uses a
nonlocking SELECT variant, state that removing FOR UPDATE can change the plan. Record:

| Question | Evidence |
|---|---|
| Which keys narrow access? | Access predicates and chosen index operations |
| Does either query block sort? | SORT/WINDOW operations in the actual plan |
| How much work finds a batch? | Buffers, rows, Starts, full-fetch elapsed time |
| How many rows are actually claimed? | Separate concurrent-worker evidence |
| Are estimates reliable? | E-Rows versus A-Rows adjusted for Starts and fetch completeness |
| Does the index help ingestion? | Insert/update latency and contention before/after |

A never-drained backlog may need retry, failure disposition or capacity changes in
addition to an index. Fix the demonstrated bottleneck rather than assigning all queue
behavior to the access path.
