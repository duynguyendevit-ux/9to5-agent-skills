---
name: 9to5-oracle-index
description: Decide and verify an Oracle index for a query shape — choose columns and order, read DBMS_XPLAN access/filter predicates, inspect index-disabling conversions, and weigh read gains against write costs. Use for slow queries, index usability, CREATE INDEX review, full scans, or composite column-order decisions. Hand DDL to 9to5-sql-migration.
license: MIT
metadata:
  version: "1.0.1"
---

# Oracle Index

## Example output

Illustrative structural review, with no fabricated measurements:

```text
Query: pending jobs for one producer, oldest first, top 100.
Candidate: (producer, status, created_at, next_attempt_at).
Expected benefit: trailing retry time may filter candidates before heap access.
Trade-off: wider index; retry updates require additional maintenance.
Ordering: inner sort may disappear; outer query ordering still needs plan verification.
Measured improvement: unknown — no executed plan collected.
Next evidence: representative binds, ALLSTATS LAST, buffers and concurrent claim behavior.
DDL: hand off through 9to5-sql-migration after evidence supports the change.
```

Choose candidate indexes from the query and workload, then prove the benefit with the
executed plan. Distinguish a possible access path from the optimizer's chosen path.

## Working rules

| Topic | Rule |
|---|---|
| Composite order | Equality prefixes followed by range/order columns are a useful starting point, not a universal optimizer law. Account for reuse, selectivity, sorting and write cost. |
| Missing leading column | A conventional range probe may be unavailable; Oracle may use skip scan, full index scan or another path. |
| Trailing predicates | May filter inside the index and sometimes contribute to access boundaries; inspect actual access/filter predicates rather than deriving them solely from column position. |
| Covering | All needed values must be obtainable without a heap lookup; also account for omitted all-null B-tree entries. |
| Ordering | A compatible ordered index path can avoid sorting, but joins, multiple probes, direction and final ordering can change this. Verify each query block. |
| Row limits | ROWNUM/FETCH FIRST can change estimates, transformations and chosen plans; early stopping depends on the access/filter/sort path. |
| Functions/conversions | Often prevent the intended range probe on the original column; matching function-based indexes or rewrites may help. Other index scan paths may still be possible. |
| Hints | Validate aliases, names, applicability and the hint report. Invalid hints are commonly ignored, not SQL identifier errors. |
| Write cost | Count affected indexes and measured DML overhead before adding one. |

Detailed examples: `references/index-design.md`. Actual-plan collection and interpretation:
`references/plan-reading.md`. Local outbox case: `references/worked-example-outbox.md`
(structural reasoning, not measured results).

## Workflow

1. Obtain the real SQL, bind datatypes/values and deployed Oracle version. Use
   `9to5-k8s-service-debug` for log-derived SQL when needed.
2. Inspect indexes, data distribution, statistics and the executed cursor plan.
3. Compare estimates with actual rows, including Starts for repeated operations.
   A discrepancy suggests a cardinality investigation, not proof that no index helps.
4. State which predicates narrow access, which filter, and where table lookups/sorts
   occur. Propose candidate orderings for the important workload, not only one query.
5. Measure before/after logical reads, elapsed time, returned rows and write costs on
   an appropriate environment. If no execution evidence exists, label expectations.
6. Ship DDL through `9to5-sql-migration`; do not execute it from this review workflow.

## Creating an index

Match schema naming and quoted identifier case. Check the database's identifier limit
(legacy schemas may require 30 bytes). Example migration for an **unquoted** table:

```sql
DECLARE
    v_exists NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_exists
    FROM user_indexes
    WHERE index_name = 'IX_OUTBOX_RECORD_CLAIM';

    IF v_exists = 0 THEN
        EXECUTE IMMEDIATE
            'CREATE INDEX ix_outbox_record_claim '
            || 'ON outbox_record (producer, status, created_at)';
    END IF;
END;
/
-- verify: SELECT column_position, column_name FROM user_ind_columns
-- WHERE index_name = 'IX_OUTBOX_RECORD_CLAIM' ORDER BY column_position;
```

A name-existence guard does not prove an existing definition matches. Verify columns,
order and status; stop on mismatch rather than silently accepting a different index.
Consider ONLINE only after checking Oracle edition/version, object restrictions,
resource cost and residual locking. Never drop/rebuild an index as an incidental fix.

## Execution boundary

Reading existing cursor plans is preferred. EXPLAIN PLAN writes plan rows but does not
execute the target statement; it is not a zero-write operation. Actual measurement
executes the statement: do not run production DML or locking SELECTs for diagnosis.
A SELECT projection of a locking query may choose a different plan; state that limit.
Statistics gathering changes optimizer metadata and requires an explicit operational
decision. Hand environment drift to `9to5-env-config-sync`.
