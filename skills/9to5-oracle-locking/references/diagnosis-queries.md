# Read-only lock diagnosis queries

Run during the symptom. Read-only; no kills, no DDL. Privileges vary — `v$` views need
`SELECT_CATALOG_ROLE` or specific grants, `DBA_*` views additionally a DBA role. If a
query is not permitted, hand the statement to the DBA rather than requesting broader
access.

## 1. Blocking chain

```sql
SELECT s.sid,
       s.serial#,
       s.username,
       s.status,
       s.sql_id,
       s.event,
       s.seconds_in_wait,
       s.blocking_session,
       s.blocking_session_status,
       bs.username   AS blocker_user,
       bs.sql_id     AS blocker_sql_id,
       bs.event      AS blocker_event,
       bs.seconds_in_wait AS blocker_seconds
FROM v$session s
LEFT JOIN v$session bs ON bs.sid = s.blocking_session
WHERE s.blocking_session IS NOT NULL
   OR s.blocking_session_status = 'VALID'
ORDER BY s.seconds_in_wait DESC;
```

Read: the longest `seconds_in_wait` chain is the incident. Follow `blocking_session`
until null; the root session runs the statement everyone waits on.

## 2. Enqueue detail for current waits

```sql
SELECT l.sid,
       l.type,
       l.id1,
       l.id2,
       l.lmode,
       l.request,
       l.ctime,
       l.block,
       s.username,
       s.sql_id,
       o.owner,
       o.object_name
FROM v$lock l
JOIN v$session s ON s.sid = l.sid
LEFT JOIN dba_objects o
       ON o.object_id = l.id1
      AND l.type IN ('TM', 'TX')
WHERE l.block = 1
   OR l.request > 0
ORDER BY l.block DESC, l.ctime DESC;
```

- `type = 'TX'` with `request = 6` is row-lock contention on the same rows.
- `type = 'TM'` points at table-level locks — check whether FK columns on child tables
  are indexed before blaming the application.
- `ctime` is how long the current mode has been held; the holder's `seconds_in_wait` is 0.

## 3. Waiter and holder pairs

```sql
-- Who is waiting on whom (DBA_WAITERS shows waiter -> holder).
SELECT waiting_session, holding_session, lock_type, mode_held, mode_requested, lock_id1, lock_id2
FROM dba_waiters
ORDER BY waiting_session;

-- Sessions holding a lock someone waits on.
SELECT blocking_session, sid, serial#, username
FROM dba_blockers;
```

## 4. Foreign-key TM contention check (schema-level)

```sql
SELECT c.table_name AS child_table,
       c.constraint_name,
       cc.column_name,
       CASE WHEN i.index_name IS NULL THEN 'MISSING INDEX' ELSE i.index_name END AS index_state
FROM user_constraints c
JOIN user_cons_columns cc
  ON cc.owner = c.owner AND cc.constraint_name = c.constraint_name
LEFT JOIN user_ind_columns i
  ON i.table_name = c.table_name
 AND i.column_name = cc.column_name
 AND i.column_position = 1
WHERE c.constraint_type = 'R'
ORDER BY index_state DESC, child_table, cc.position;
```

A child foreign key whose columns are not the leading columns of any index makes parent
DML take a full-table TM lock on the child; the fix is an index, reviewed as always via
`9to5-oracle-index` and shipped via `9to5-sql-migration`.

## 5. Deadlock trail (after ORA-00060)

```sql
SELECT value AS default_trace_file FROM v$diag_info WHERE name = 'Default Trace File';
-- Then read the trace; it contains the Deadlock graph:
--   grep -n -A40 "Deadlock" <trace-file>
```

Also check the alert log for the ORA-00060 entry and deadlock details; the trace has the
two sessions' current SQL and the rows/resource each waited for. Report the cycle, not a
single statement.

## 6. Waits over time (when the incident is still live)

```sql
SELECT event, COUNT(*) AS sessions, MAX(seconds_in_wait) AS max_wait_s
FROM v$session
WHERE state = 'WAITING'
  AND wait_class <> 'Idle'
GROUP BY event
ORDER BY sessions DESC;
```

`enq: TX - row lock contention` at the top confirms the row-lock reading from section 1;
`db file sequential read` at the top is an I/O story, not a locking one — do not confuse
the two.

## Notes

- All statements above are safe to run read-only, but section 2 benefits from a
  `WHERE o.owner = :schema` filter on busy instances.
- `v$active_session_history`/ASH is richer but sampled and heavy; use it to locate the
  window, then confirm with the live views above or the deadlock trace.
- Record the output as a debug artifact (`debug/artifacts/<date>-<app>-<slug>/`) per
  `9to5-k8s-service-debug` when the incident is service-related.
