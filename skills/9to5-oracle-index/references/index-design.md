# Oracle index design

## Sorted composite entries

An Oracle heap B-tree entry contains indexed values and ROWID. Entries are logically
ordered; leaf blocks need not be physically contiguous. For `(shop_id, created_at)`,
`shop_id = :id` identifies a contiguous key range, and a time predicate can narrow it.
For a time predicate alone, Oracle may consider a skip scan, full/fast-full index scan,
or table scan. Missing a leading predicate does not make the index universally unusable.

Start candidate design with equality columns, then the important range/order column,
then trailing columns useful for filtering or covering. Weigh prefix reuse, selectivity,
correlation and sort avoidance. Multiple ranges and IN lists need actual plan inspection;
do not assume every column after the first range is always only a filter. IN may become
multiple probes, which do not necessarily preserve the final requested ordering.

## Filtering and covering

Predicates on indexed values may be evaluated before a table lookup. Other heap column
values generally require table access unless another covering/index-join path supplies
them. Wide indexes trade fewer lookups for extra space and DML work.

Conventional B-tree indexes omit entries where every indexed column is null. Therefore
`IS NULL` and index-only COUNT(*) require attention to nullability and row coverage.
A composite index with a guaranteed non-null component can retain otherwise-null keys.

Oracle skip scan treats distinct leading values as logical subindexes. Low leading
cardinality often makes it attractive, but cost determines selection. It does **not**
require a covering index: a skip scan may be followed by TABLE ACCESS BY INDEX ROWID.
High cardinality increases work; it does not mechanically become INDEX FULL SCAN.

## Ordering and top-N

A compatible ordered index scan can avoid SORT ORDER BY and stop after enough qualifying
rows. Sparse eligibility predicates may still require many candidate reads. A filter-first
index followed by a sort may be cheaper than walking a large order-serving index.
ROWNUM/FETCH FIRST can change cardinality estimates, transformations and plan selection.

```sql
SELECT t.*
FROM big_table t
JOIN (
    SELECT ROWID AS rid, created_at, id
    FROM big_table
    WHERE tenant_id = :tenant_id AND created_at >= :from_time
    ORDER BY created_at, id
    FETCH FIRST 200 ROWS ONLY
) k ON k.rid = t.ROWID
ORDER BY k.created_at, k.id;
```

An index on `(tenant_id, created_at, id)` is a candidate for the inner query. The outer
query still needs table lookups and may sort; only its ORDER BY guarantees final order.
Use a unique tie-breaker for deterministic top-N. On older versions, place ORDER BY
inside an inline view and apply ROWNUM outside it; a same-block ROWNUM filter followed
by ORDER BY is not equivalent. Verify transformations in the real plan.

## Predicate pitfalls

| Shape | Investigation |
|---|---|
| TRUNC(timestamp) = :day | Half-open timestamp range or a matching function-based index; check timezone semantics. |
| UPPER(code) = :value | Match a function-based index and collation semantics if case-insensitive access is required. |
| VARCHAR2 compared to NUMBER | Inspect implicit column conversion; bind the intended datatype. |
| LIKE '%text%' | No fixed leading prefix for the usual range probe; evaluate text search or a scan. |
| OR across columns | Oracle may OR-expand; manual UNION ALL needs duplicate semantics preserved. |
| IS NULL / IS NOT NULL / <> | Check null coverage and selectivity; these are not universal index prohibitions. |

## Write trade-offs

Count relevant PK/unique/secondary indexes and which keys each DML changes. Insert,
delete and indexed-column updates maintain index entries; all-null key omission and
unchanged key values matter. More indexes can slow ingestion. Sequential and random
keys have different locality/contention trade-offs: measure workload waits and reads.

## MySQL comparisons

MySQL ICP evaluates eligible predicates using columns present in an index before fetching
the full row. It cannot read arbitrary non-indexed column values out of the index.
Oracle index filtering can similarly avoid some heap lookups. Do not transfer MySQL
EXPLAIN labels, hint behavior or InnoDB clustered-PK storage rules directly to Oracle.

Sources:
- https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/optimizer-access-paths.html
- https://dev.mysql.com/doc/refman/8.0/en/index-condition-pushdown-optimization.html
