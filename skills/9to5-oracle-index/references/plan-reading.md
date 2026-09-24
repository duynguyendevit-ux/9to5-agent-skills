# Reading Oracle execution plans

## Estimated versus executed

EXPLAIN PLAN generates an estimate without executing the target SQL, but writes to a
plan table. Its bind context can differ from the service cursor. Prefer the real cursor
and actual statistics when available.

```sql
EXPLAIN PLAN FOR SELECT ...;
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY(NULL, NULL, 'BASIC +PREDICATE'));

-- Execute only an authorized read query, with representative binds and a full fetch.
SELECT /*+ GATHER_PLAN_STATISTICS */ ... FROM ... WHERE ...;
SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL, NULL, 'ALLSTATS LAST +PREDICATE'));
```

GATHER_PLAN_STATISTICS is a statement hint. STATISTICS_LEVEL=ALL can alternatively
collect statistics at session level; do not change instance settings for this workflow.
NULL sql_id means the last cursor in that session; clients may issue intervening SQL.
Capture sql_id and child_number explicitly when necessary:

```sql
SELECT sql_id, child_number, plan_hash_value, executions, buffer_gets, rows_processed
FROM v$sql
WHERE sql_text LIKE '%outbox_record%'
ORDER BY last_active_time DESC;

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:sql_id, :child_number, 'ALLSTATS LAST +PREDICATE'));
```

Missing row-source statistics can mean they were not collected; a missing cursor may
have aged out, be on another instance, or be inaccessible. Do not invent runtime counts.

## Read the work, not just the operation name

- E-Rows is an estimate; A-Rows reflects execution. Account for Starts when comparing
  repeated operations and check whether the application fully fetched the result.
- Cardinality errors can arise from skew, correlations, bind peeking, transformations
  and statistics. An index can still help; a mismatch does not prove "not an index issue".
- Read access and filter predicates at the exact operation where Oracle evaluates them.
- Compare Buffers, elapsed time, row counts and waits across representative executions.
  Do not sum nested cumulative figures blindly.

| Operation | What to inspect |
|---|---|
| INDEX UNIQUE/RANGE SCAN | Key bounds, candidates examined, filter predicates. |
| INDEX SKIP SCAN | Leading cardinality, cost, and any subsequent table lookups. |
| INDEX FULL SCAN | Ordered scan that may cover the query or supply order. |
| INDEX FAST FULL SCAN | Unordered multiblock scan; may avoid heap access. |
| TABLE ACCESS BY INDEX ROWID | Heap visits and filtering; may be batched. |
| TABLE ACCESS FULL | Fraction of table needed, physical layout, parallelism and cost. |
| SORT ORDER BY / STOPKEY / WINDOW operations | Top-N implementation, sort input and whether early stopping really occurs. |
| INLIST ITERATOR / CONCATENATION | Multiple probes/branches, deduplication and ordering consequences. |

## Hints

```sql
SELECT /*+ INDEX(t idx_orders_tenant) */ ... FROM orders t WHERE ...;
SELECT /*+ INDEX_SS(t idx_orders_tenant) */ ... FROM orders t WHERE ...;
SELECT /*+ INDEX_FFS(t idx_orders_tenant) */ ... FROM orders t WHERE ...;
SELECT /*+ NO_INDEX(t idx_orders_tenant) */ ... FROM orders t WHERE ...;
```

Match the query-block alias and index name. An invalid/nonexistent index name in an
INDEX hint is normally ignored/unresolved, not an ORA-00904 or ORA-01408 exception.
On versions supporting it, inspect `+HINT_REPORT` in DBMS_XPLAN output. An unchanged
plan does not prove a hint was ignored: it might already have selected that path.
Hints can override cost-based choices, but cannot make an inapplicable access path valid.

## Statistics and reporting

```sql
SELECT table_name, num_rows, last_analyzed, stale_stats
FROM user_tab_statistics WHERE table_name = :table_name;
```

Gathering statistics changes optimizer metadata. Plan it explicitly rather than
silently running DBMS_STATS on production. Use exact dictionary case for quoted names.

Report SQL/binds, environment, plan hash, before/after elapsed time and buffers,
returned rows, repeated-run variation, and DML trade-offs. Label hypothetical numbers
as examples and unexecuted reasoning as expectations.

Source: https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/influencing-the-optimizer.html
