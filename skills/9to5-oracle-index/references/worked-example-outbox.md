# Worked example: outbox claim and cleanup

Real code, not an illustration. Sources:

- DDL: `common-outbox/files/outbox-oracle.sql` (reference DDL applied by the product
  migration repo)
- Queries: `common-outbox/java/src/main/java/tech/features/outbox/repository/OutboxRepository.java`

Nothing in this file was measured against a cluster. The reasoning is structural,
derived from the DDL and the query text; every number must come from `DBMS_XPLAN` on
the real schema before it is quoted as fact.

## The queries

**Claim** — one producer, oldest pending first, batched, locked without waiting:

```sql
SELECT outbox.*
FROM   outbox_record outbox
WHERE  outbox.ROWID IN (
         SELECT candidate_rowid
         FROM   (SELECT candidate.ROWID AS candidate_rowid
                 FROM   outbox_record candidate
                 WHERE  candidate.producer = :producer
                   AND  candidate.status = 'PENDING'
                   AND  candidate.created_at <= :cutoff
                   AND  (candidate.next_attempt_at IS NULL
                         OR candidate.next_attempt_at <= :now)
                 ORDER  BY candidate.created_at)
         WHERE  ROWNUM <= :batchSize)
ORDER  BY outbox.created_at
FOR UPDATE SKIP LOCKED;
```

**Cleanup** — same shape, published rows only, ordered by publication:

```sql
... WHERE producer = :producer
      AND status = 'PUBLISHED'
      AND published_at < :cutoff
    ORDER BY published_at
    ... ROWNUM <= :batchSize ... FOR UPDATE SKIP LOCKED
```

Plus two monitoring queries on the same table, both filtered by `producer` and `status`:

```sql
SELECT COUNT(*) FROM outbox_record WHERE producer = :p AND status = :s;
SELECT MIN(created_at) FROM outbox_record WHERE producer = :p AND status = :s;
```

## The indexes

```sql
CREATE INDEX ix_outbox_record_claim   ON outbox_record (producer, status, created_at);
CREATE INDEX ix_outbox_record_cleanup ON outbox_record (producer, status, published_at);
```

## Seek horizon

For `ix_outbox_record_claim` against the claim query:

| Column | Predicate | Role |
|---|---|---|
| `producer` | `= :producer` | Access — seek |
| `status` | `= 'PENDING'` | Access — seek; splits the producer run in two |
| `created_at` | `<= :cutoff` | Access — range bound, **and** the `ORDER BY` column |
| `next_attempt_at` | `IS NULL OR <= :now` | **Not in the index** → filter, and because it is a non-key column the test needs the table row |
| `outbox_id`, `payload`, … | `SELECT outbox.*` | Not in the index → table access for the surviving batch only |

The scan starts at the oldest `(producer, PENDING)` entry and walks forward in
`created_at` order. Because the index supplies that order, the plan has no
`SORT ORDER BY`, and `ROWNUM <= :batchSize` stops the walk after the batch is
collected rather than after the whole run is read.

## Pros

1. **The batch is collected in index order.** `ORDER BY created_at` is satisfied by the
   key order, so the engine reads the first eligible entries and stops. Without the
   index that becomes a `SORT ORDER BY` over every pending row of the producer.
2. **The producer is the leading column.** The table is shared by several services and
   instances, so each service's backlog is physically separated; one service's volume
   cannot widen another's scan.
3. **The cutoff bounds the scan.** `created_at <= :cutoff` caps how far forward the run
   can go, and it lets a stuck record older than the cutoff drop out of the walk.
4. **Both monitoring queries are answered from the same index.** `COUNT(*)` and
   `MIN(created_at)` filter on `producer` and `status`, both key columns, so the plan
   can satisfy them without touching the table.
5. **The two workloads are separated by the key tail.** Claim orders by `created_at`,
   cleanup by `published_at`. Two indexes mean the cleanup walk never steps through
   pending entries, and vice versa.

## Cons

1. **Every write pays twice.** An insert creates three index entries (primary key plus
   both secondary indexes). A successful publish updates `status`, `published_at`, and
   `next_attempt_at`, moving the entry in both secondary indexes. On a high event rate
   this is a throughput cost on the ingest path, not a rounding error.
2. **Eligibility is a filter, and a non-key filter needs the table.** `next_attempt_at`
   is not in the index, so each candidate row needs a `TABLE ACCESS BY INDEX ROWID`
   before it can be rejected. `ROWNUM` counts rows **after** that filter, so a backlog
   with many future-dated `next_attempt_at` entries makes the walk read far more rows
   than the batch returns.
3. **`status` carries almost no discrimination.** Two values: it divides the producer
   run, nothing more. All selectivity comes from `producer` and the `created_at` bound.
4. **A stuck backlog stays in the scan forever.** The DDL states that `PENDING` rows are
   never deleted. Records that exhaust retries remain in the claim run, and every pass
   pays for them. No index fixes a queue that is never drained.
5. **It serves only this access path.** Queries by `aggregate_id`, `event_type`, or
   `payload_template_code` get no help; those need their own index and their own
   justification.
6. **`FOR UPDATE SKIP LOCKED` still costs work per locked row.** Rows already claimed by
   another worker are skipped after being examined, so concurrency itself slightly
   widens the walk.

## What would change the design

If measurement shows the `next_attempt_at` filter dominating — high `A-Rows` on the
`TABLE ACCESS BY INDEX ROWID` step relative to `INDEX RANGE SCAN` — the candidate index
to test is:

```sql
CREATE INDEX ix_outbox_record_claim ON outbox_record (producer, status, created_at, next_attempt_at);
```

Making `next_attempt_at` a trailing **key** column keeps the `created_at` order and the
range bound intact, while moving the eligibility test from the table to the index entry.
Only the surviving batch is then fetched by `ROWID`. Cost: wider entries and one more
column on every index maintenance. Decide by plan, before and after.

If the backlog is the problem rather than the plan — millions of never-drained
`PENDING` rows — the fix is upstream (retry policy, dead-letter handling), not an index.

## The way to create them

Migration script, matching the repository conventions (see `9to5-sql-migration` for the
file naming and location rules). Both indexes are guarded and rerunnable:

```sql
DECLARE
    v_exists NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_exists
    FROM   user_indexes
    WHERE  index_name = 'IX_OUTBOX_RECORD_CLAIM';

    IF v_exists = 0 THEN
        EXECUTE IMMEDIATE
            'CREATE INDEX ix_outbox_record_claim '
            || 'ON outbox_record (producer, status, created_at) ONLINE';
    END IF;

    SELECT COUNT(*) INTO v_exists
    FROM   user_indexes
    WHERE  index_name = 'IX_OUTBOX_RECORD_CLEANUP';

    IF v_exists = 0 THEN
        EXECUTE IMMEDIATE
            'CREATE INDEX ix_outbox_record_cleanup '
            || 'ON outbox_record (producer, status, published_at) ONLINE';
    END IF;
END;
/

-- verify: both indexes, in column order
-- SELECT index_name, column_position, column_name
-- FROM   user_ind_columns
-- WHERE  index_name IN ('IX_OUTBOX_RECORD_CLAIM', 'IX_OUTBOX_RECORD_CLEANUP')
-- ORDER  BY index_name, column_position;
```

Notes:

- `ONLINE` lets DML continue while the index builds. On a large table this is still a
  DBA decision about load and space; state it, do not decide it silently.
- A newly created index gathers statistics by default, so no separate gather is needed.
- Existing deployments get the index through the migration pipeline, never by ad-hoc DDL
  on a running database.
- Changing the column order later means drop and recreate: a different, more expensive
  change with its own approval.

## How to verify the claim query

```sql
-- 1. run the real statement with real binds, statistics collected
SELECT /*+ GATHER_PLAN_STATISTICS */ outbox.*
FROM   outbox_record outbox
WHERE  ... ;                            -- same predicate and order, your producer and cutoff

-- 2. read the plan that ran
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL, NULL, 'ALLSTATS LAST +PREDICATE'));
```

Check, in this order:

| Question | Where to look |
|---|---|
| Did it seek, or scan? | `INDEX RANGE SCAN` vs `TABLE ACCESS FULL` |
| Is the order free? | absence of `SORT ORDER BY` |
| Did it stop early? | `COUNT STOPKEY` above the scan, `A-Rows` near the batch size |
| How many candidates were rejected? | `A-Rows` on `TABLE ACCESS BY INDEX ROWID` vs on `INDEX RANGE SCAN` |
| Was the estimate right? | `E-Rows` vs `A-Rows`; a large gap means statistics, not index |
