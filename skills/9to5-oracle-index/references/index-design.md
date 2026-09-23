# Index design

## Entries are a sorted list

An index is a sorted list of **entries**. Each entry holds the indexed column values
plus a pointer to the row. In Oracle the pointer is the `ROWID`; in InnoDB it is the
primary key. The list is structured as a B-tree for lookup, but at the leaf level it
is a contiguous sequence in key order.

From that list the engine does exactly two things:

| Operation | Meaning | Cost |
|---|---|---|
| **Seek** | Jump to a point and read a contiguous run of entries | Cheap |
| **Filter** | Read every entry in turn, compare, keep or discard | Expensive — you pay for the discarded rows too |

Seek is possible only while the rows you need are **adjacent**. Index `(shop_id,
created_at)` with `WHERE shop_id = 7`:

```
(6, 2026-01-05)
(6, 2026-02-11)
(7, 2026-01-01)  ┐
(7, 2026-01-02)  │  adjacent -> seek to the first entry, read the run, stop
(7, 2026-01-03)  │
(7, 2026-01-05)  ┘
(8, 2026-01-02)
```

The same index with `WHERE created_at = '2026-01-02'`:

```
(6, 2026-01-05)
(7, 2026-01-01)
(7, 2026-01-02)  <- match
(7, 2026-01-03)
(8, 2026-01-02)  <- match
(9, 2026-01-02)  <- match     matches are scattered -> no single entry point
```

Reading the whole **index** is still cheaper than reading the whole **table**, because
an entry is tens of bytes while a row is hundreds. The index does not become useless;
it drops from *seek* to *scan*. The gap between those two is where multi-second list
screens come from.

Oracle plan names for the three levels:

| Level | Plan operation |
|---|---|
| Seek | `INDEX UNIQUE SCAN`, `INDEX RANGE SCAN` |
| Scan the index only | `INDEX FULL SCAN`, `INDEX FAST FULL SCAN` |
| Scan the table | `TABLE ACCESS FULL` |

## Reading a query from left to right

For the proposed index, walk the query and write down where adjacency stops:

> Reading the index left to right, at which column do I lose adjacency?

- Everything up to that column is an **access predicate** (seek).
- Everything after it is a **filter predicate** — still useful if the column is part
  of the index, because the filter is then evaluated without touching the table.
- Any predicate on a **non-key** column forces `TABLE ACCESS BY INDEX ROWID` for each
  candidate row.

`DBMS_XPLAN` prints both lists when asked (`+PREDICATE`): `access(...)` and `filter(...)`.

## Column order

1. **Equality columns first**, in an order that maximizes prefix reuse across the
   queries that share this table. Reuse beats per-column selectivity: an index whose
   leading column only one query filters on is dead weight for the rest.
2. **Then one range or ordering column.** A range bound stops the seek. Columns after
   it cannot bound the scan; they filter.
3. **Then presence-only columns** — those needed so the query can be answered from the
   index alone (multi-column locators: `IN` lists, equality plus `IN`, etc.).

Two facts that surprise people:

- **Only one range column can bound the scan.** `WHERE a = 1 AND b > 5 AND c > 3` on
  `(a, b, c)`: `a` and `b` seek, `c` filters.
- **`IN` expands, `BETWEEN`/`>`, `<` bound.** An `IN` list is evaluated as several
  equality probes (`INLIST ITERATOR`), so it behaves like equality for access, not
  like a range.

## Ordering

An index whose key order matches `ORDER BY` and whose scan is a range scan gives the
rows in order — the plan shows no `SORT ORDER BY`. That is worth more than it looks:
combined with a row limit, the engine can stop after collecting the first batch
instead of sorting the whole match set.

When the `ORDER BY` columns and the `WHERE` columns disagree, choose:

- **Sort-serving index** (`WHERE` column later in the key): stops early, but walks every
  non-matching entry in order.
- **Filter-serving index** (`WHERE` column first): seeks, then sorts the match set.

Which wins depends on match density. A sparse predicate in front of a sort-serving
index is the classic slow screen: the engine walks a huge ordered run to collect a
small batch. Measure both; do not assume.

## Index-only access

If every column the query references is in the index, Oracle answers it from the index
and the plan contains **no** `TABLE ACCESS BY INDEX ROWID` step. This is a relation
between an index and one query, not a property of the index:

- Add one column to the `SELECT` list and the benefit disappears.
- `SELECT *` on a wide table forfeits it permanently. Selecting only the needed columns
  is part of the index design, not a style preference.

The two-step rewrite that keeps the benefit while still returning whole rows:

```sql
SELECT t.*
FROM   big_table t
JOIN  (SELECT rowid AS rid
       FROM   big_table
       WHERE  tenant_id = :t
         AND  created_at >= :from
       ORDER  BY created_at
       FETCH FIRST 200 ROWS ONLY) k
  ON   k.rid = t.ROWID;
```

The inner query can run entirely inside the index; the outer performs 200 lookups by
`ROWID`. `FETCH FIRST` is available from 12c; `ROWNUM <= 200` works everywhere.

## Query killers

| Killer | Effect | Fix |
|---|---|---|
| `TRUNC(col)`, `UPPER(col)`, any function on the column | Index on `col` is unusable | Rewrite as a range, or create a function-based index on the same expression |
| `VARCHAR2` column compared to a number | Column is converted, index unusable | Compare to a string literal |
| `LIKE '%text%'` | No fixed prefix, no seek | Prefix `LIKE 'text%'`; otherwise a text index or another store |
| `OR` across different columns | May become `CONCATENATION` of two scans, or a full scan | Two queries with `UNION ALL`, or an index per branch |
| `NOT`, `<>`, `IS NOT NULL` | Usually no access path | Range on the opposite condition if it exists |
| Stale statistics | Optimizer misprices plans it could get right | `DBMS_STATS.GATHER_TABLE_STATS(USER, 'T', CASCADE => TRUE)` |

On `IS NULL`: Oracle B-tree indexes can serve it, unlike some other engines. Confirm in
the plan instead of reasoning about it.

## Skip scan and other second-best paths

`INDEX SKIP SCAN` lets Oracle use an index whose leading column is missing from the
predicate, by iterating the distinct values of that leading column. It is a workaround,
not a design:

- It needs the leading column to have few distinct values. With high cardinality it
  degenerates to `INDEX FULL SCAN`.
- It needs the query's reference set to be satisfiable from the index.
- It is not a reason to accept the wrong column order in a new index.

## Indexes are paid on write

Each secondary index adds an entry on every insert and on every update of the indexed
columns (delete + insert). A table with a claim index and a cleanup index pays three
entries per insert and two entries per status transition. Before adding an index,
count the existing ones and say what the write path pays — a list screen that gets
faster while the ingest path gets slower is a trade, not a win.

## Coming from MySQL

The mechanics are the same; the names and tooling are not.

| MySQL 8.0 | Oracle 12c |
|---|---|
| `type: ALL` | `TABLE ACCESS FULL` |
| `ref` / `range` | `INDEX RANGE SCAN`, `INDEX UNIQUE SCAN` |
| `Using index` (covering) | no `TABLE ACCESS BY INDEX ROWID` step in the plan |
| skip scan | `INDEX SKIP SCAN` |
| `optimizer_trace` | `DBMS_XPLAN.DISPLAY_CURSOR`, `V$SQL_PLAN` |
| `FORCE INDEX` / `USE INDEX` | `/*+ INDEX(t idx) */`, `NO_INDEX`, `FULL(t)` |
| `ANALYZE TABLE` | `DBMS_STATS.GATHER_TABLE_STATS` |
| `LIMIT` | `ROWNUM <= n` / `FETCH FIRST n ROWS ONLY` |

Two differences worth remembering:

- **Index condition pushdown has no Oracle 12c equivalent.** MySQL can evaluate
  non-key predicates inside the index scan; Oracle needs the table for a non-key
  predicate. If a MySQL article relies on ICP, the Oracle answer is to move the column
  into the index.
- **Oracle's `INDEX` hint is not a cost override.** It selects among paths that exist
  and is ignored when none does, so the end state matches MySQL's `FORCE INDEX` on an
  impossible path, without MySQL's "make the full scan expensive" mechanism.
