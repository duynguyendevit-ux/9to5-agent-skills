---
name: 9to5-oracle-index
description: Decide and verify an Oracle index for a query shape — pick the access columns and their order, read the execution plan (DBMS_XPLAN) to separate access from filter, spot the rewrites that disable an index, weigh the write cost against the read gain, then hand the DDL to 9to5-sql-migration. Use when a query is slow, when asked whether an index can be used, when reviewing a CREATE INDEX statement, when a plan shows TABLE ACCESS FULL, or when arguing about composite index column order.
license: MIT
metadata:
  version: "1.0.0"
---

# Oracle Index

Decide the index from the query, then prove it with the plan. An index that exists
is not an index that is used, and an index that is used is not an index that helps.

## The only question

For a given query and a given index:

> How far can the engine **seek**, and from which column does it fall back to
> reading every entry and comparing?

Index entries are a sorted list. Seek is possible only while the rows you want are
**adjacent** in that list. `(a, b, c)` serves seek for `a`, `(a, b)`, `(a, b, c)` —
never for `b` or `c` alone. That is the leftmost prefix rule, and it is a
consequence of adjacency, not a rule Oracle invented.

Everything else in this skill is a corollary. Detail:
`references/index-design.md`.

## Rules

| Rule | Why |
|---|---|
| Equality columns first, then at most one range column | The range stops the seek; later columns become filters |
| Column order follows prefix reuse, not per-column selectivity | A reused leading prefix serves more queries than a high-cardinality first column |
| A predicate on a key column can filter inside the index; a predicate on any other column needs the table | Non-key predicates force `TABLE ACCESS BY INDEX ROWID` per row |
| Index-only access requires every referenced column to be in the index | One extra column in `SELECT` costs the whole benefit — `SELECT *` forfeits it |
| `ORDER BY` is free when the index order matches and the scan is a range scan | Plan shows no `SORT ORDER BY`; the limit can then stop early |
| `ROWNUM`/`FETCH FIRST` does not change the plan | It caps damage. On a sparse predicate the scan may still cover most of the table |
| A hint selects among paths that already exist; it never creates one | If no index path is possible, the hint is ignored silently |
| Every index is paid on write | Count the indexes on the table before adding one |

## Query killers

Any of these turns a seek into a scan; fix the query before adding an index.

- **Function on the indexed column** — `TRUNC(created_at) = :d`, `UPPER(code) = :c`.
  Needs a matching function-based index, or rewrite to a range.
- **Implicit conversion** — comparing a `VARCHAR2` column to a number converts the
  column and drops the index.
- **Leading wildcard** — `LIKE '%text%'` cannot seek. Only a prefix `LIKE 'text%'` can.
- **`OR` across different columns** — may split into `CONCATENATION` of two scans, or
  fall to a full scan. `OR` on one column is usually an `INLIST ITERATOR`.
- **`IS NULL`** — Oracle B-tree indexes can serve it; confirm in the plan rather than
  assuming either way.
- **Wrong statistics** — gather table statistics before blaming the optimizer:
  `DBMS_STATS.GATHER_TABLE_STATS(USER, 'TABLE_NAME', CASCADE => TRUE)`.

## Workflow

1. **Get the real statement and the real bind values.** Estimated plans mislead;
   skewed data misleads more. If the query comes from a service log, take the bound
   values with it (`9to5-k8s-service-debug` extracts them from Hibernate logs).
2. **Get the plan with real numbers** — see `references/plan-reading.md`. Compare
   `E-Rows` against `A-Rows`; a large gap means a statistics problem, not an index problem.
3. **Name the operation.** `TABLE ACCESS FULL`, `TABLE ACCESS BY INDEX ROWID`,
   `INDEX RANGE SCAN`, `INDEX SKIP SCAN`, `INDEX FULL SCAN`, `SORT ORDER BY`,
   `COUNT STOPKEY`.
4. **Read the access predicates, then the filter predicates.** For each column of the
   proposed index decide: does it *seek* or does it *filter*? Write the seek horizon
   down before proposing anything.
5. **Propose the column order** — equalities, then the ordering/range column, then
   columns that only need to be present for index-only access.
6. **Weigh write cost**: each added index is an extra entry on every insert and on
   every update that touches an indexed column.
7. **Verify by plan, not by intuition**: run before and after, compare estimated and
   actual rows, and state the measured numbers.
8. **Hand the DDL to `9to5-sql-migration`** — indexes ship as migration scripts, not
   as ad-hoc DDL. See "Creating the index" below.

## Creating the index

Follow the target schema's existing style. In this codebase indexes are named
`idx_<table>__<columns>` or `ix_<table>_<purpose>`, lowercase, within the schema's
identifier limit (30 chars on the legacy schemas).

Rerunnable migration form:

```sql
DECLARE
    v_exists NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_exists
    FROM   user_indexes
    WHERE  index_name = 'IDX_OUTBOX_RECORD__CLAIM';

    IF v_exists = 0 THEN
        EXECUTE IMMEDIATE
            'CREATE INDEX idx_outbox_record__claim '
            || 'ON outbox_record (producer, status, created_at) ONLINE';
    END IF;
END;
/

-- verify:
-- SELECT column_position, column_name
-- FROM   user_ind_columns
-- WHERE  index_name = 'IDX_OUTBOX_RECORD__CLAIM'
-- ORDER  BY column_position;
```

- `ONLINE` keeps the table open to DML while the index builds; still a DBA-level
  decision on a large table.
- A new index gathers statistics by default, so the optimizer sees it without a
  separate gather.
- Never drop or rebuild an index as a side effect of this skill. Report it.
- Confirm the column order against the query **before** writing the migration;
  reordering the columns of an existing index is a drop and recreate, which is a
  different, more expensive ticket.

## Worked example

The outbox claim and cleanup queries and their two indexes, with the reasoning and
the measured trade-offs: `references/worked-example-outbox.md`.

## Safety

- Read-only by default. `EXPLAIN PLAN` and `DBMS_XPLAN` do not change data.
- Never run a row-locking form (`FOR UPDATE`) of a production query just to measure
  it; measure a `SELECT` projection of the same shape instead.
- Index DDL is a schema change: it goes through `9to5-sql-migration` and the release
  pipeline, with the lock and volume implications stated.

## Handoffs

| Situation | Skill |
|---|---|
| Need the real SQL and bind values from a running service | `9to5-k8s-service-debug` |
| Shipping the `CREATE INDEX` / `DROP INDEX` script | `9to5-sql-migration` |
| Deciding whether a config or environment value is the real cause | `9to5-env-config-sync` |
