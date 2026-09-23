# Reading the plan

## Two plans, two purposes

| Command | Gives | Use for |
|---|---|---|
| `EXPLAIN PLAN` + `DBMS_XPLAN.DISPLAY` | The plan for a statement without running it | First look, no side effects |
| `GATHER_PLAN_STATISTICS` + `DBMS_XPLAN.DISPLAY_CURSOR(..., 'ALLSTATS LAST')` | The plan that actually ran, with real row counts | Any judgement about performance |

Estimated rows alone will mislead you on skewed data. Always finish with the real one.

```sql
EXPLAIN PLAN FOR
SELECT ... ;

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY(NULL, NULL, 'BASIC +PREDICATE'));
```

```sql
SELECT /*+ GATHER_PLAN_STATISTICS */
       ...
FROM   ...
WHERE  ... ;

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(NULL, NULL, 'ALLSTATS LAST +PREDICATE'));
```

Notes:

- `DISPLAY_CURSOR` with a `NULL` `sql_id` reads the last statement executed **in that
  session**. Do not run anything else in between, or capture the `SQL_ID` from `V$SQL`
  and pass it explicitly.
- Real row counts need `STATISTICS_LEVEL => ALL` or a session with
  `GATHER_PLAN_STATISTICS`. The session-level setting is enough; do not change
  instance parameters for a diagnosis.
- For a statement that already ran in a service, look it up instead of re-running it:

```sql
SELECT sql_id, child_number, plan_hash_value, executions, buffer_gets, rows_processed
FROM   v$sql
WHERE  sql_text LIKE '%outbox_record%'
ORDER  BY last_active_time DESC;

SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR('<sql_id>', NULL, 'ALLSTATS LAST +PREDICATE'));
```

Rows may be aged out of `V$SQL`; if the plan is missing, the statement ran too long ago.

## Reading the output

Read top-down, indent by indent. For each line note:

1. **The operation** — seek, scan, or sort.
2. **`E-Rows` vs `A-Rows`** — a large gap means the optimizer's estimate is wrong.
   That is a statistics or predicate-shape problem, and no index fixes it.
3. **`access(...)` and `filter(...)`** — which columns seek, which merely filter.
4. **`Buffers`** — logical reads. The number that correlates with elapsed time when
   the data is cached, and the honest one to quote.

## Plan operations

| Operation | Meaning | Verdict |
|---|---|---|
| `INDEX UNIQUE SCAN` | Direct seek to one entry | Best case |
| `INDEX RANGE SCAN` | Seek plus a contiguous run | Good; check how wide the run is |
| `INDEX SKIP SCAN` | Iterates a leading column that the predicate omits | Workaround; watch `A-Rows` |
| `INDEX FULL SCAN` | Reads the whole index in order | Acceptable only when the order is wanted |
| `INDEX FAST FULL SCAN` | Reads the whole index, multiblock, unordered | A smaller `TABLE ACCESS FULL` |
| `TABLE ACCESS BY INDEX ROWID` | One table lookup per candidate row | Expected per row; watch the row count |
| `TABLE ACCESS FULL` | Whole table | Fine for a large share of the table, wrong for a selective predicate |
| `SORT ORDER BY` | The database sorts the result | Check whether an index could have ordered it |
| `COUNT STOPKEY` | Early stop from `ROWNUM` / `FETCH FIRST` | Only helps if the rows arrive in the needed order |
| `INLIST ITERATOR` | `IN` list evaluated as several probes | Behave like equality for access |
| `CONCATENATION` | Two scans, one per branch of an `OR` | Sometimes fine; a full scan in disguise otherwise |
| `FILTER` | Row-by-row test, often a subquery | Watch for a nested loop over a large driving set |

## Hints

Hints choose among paths that already exist. Add one, then read the plan; if the plan
is unchanged, the hint was ignored — often because no path was possible, and
occasionally because the table alias does not match.

```sql
SELECT /*+ INDEX(t idx_orders_tenant) */ ... FROM orders t WHERE ...;
SELECT /*+ INDEX_SS(t idx_orders_tenant) */ ...;   -- allow skip scan
SELECT /*+ INDEX_FFS(t idx_orders_tenant) */ ...;  -- index fast full scan
SELECT /*+ NO_INDEX(t idx_orders_tenant) */ ...;   -- remove a candidate
SELECT /*+ FULL(t) */ ...;                         -- forbid index paths
```

Rules:

- The alias inside the hint must match the alias in `FROM`, or the hint silently does
  nothing.
- A wrong index **name** is an error (`ORA-00904`/`ORA-01408` family, `key doesn't
  exist`); a hint that cannot be obeyed is not.
- Scope a hint to its purpose when it matters: `INDEX(t idx)`, `INDEX_SS(t idx)`,
  `USE_NL`, `LEADING`. Blanket hints outlive their reason and turn into folklore.
- Prefer the least forceful lever that works: `NO_INDEX` to remove a bad candidate
  rather than `INDEX` to pin a good one.
- A hint left in production code needs a comment saying what it fixes and what would
  let you remove it. Otherwise it is a bug with a schedule.

## Statistics

Before adding an index, check whether the optimizer is simply misinformed:

```sql
SELECT table_name, num_rows, last_analyzed, stale_stats
FROM   user_tab_statistics
WHERE  table_name = 'OUTBOX_RECORD';
```

```sql
BEGIN
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'OUTBOX_RECORD', CASCADE => TRUE);
END;
/
```

`CASCADE => TRUE` gathers the index statistics with the table. Gathering statistics on
a production schema is an operational action: state that you want it rather than
running it silently.

## Reporting

State measured numbers, not adjectives:

```
Query:    claim batch (producer = 'notification-service', status = 'PENDING')
Before:   TABLE ACCESS FULL, A-Rows 512000, Buffers 41,997, Elapsed 1.9 s
Index:    (producer, status, created_at)
After:    INDEX RANGE SCAN, A-Rows 200 (E-Rows 200), Buffers 63, Elapsed 4 ms
Write:    +1 index entry per insert, +2 per publish transition
Verified: DISPLAY_CURSOR ALLSTATS LAST, 3 runs, plans stable
```

If you did not measure it, say so. "Should be faster" is not a result.
