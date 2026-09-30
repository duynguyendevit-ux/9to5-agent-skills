---
name: 9to5-sql-forensics
description: Reconstruct runnable Oracle SQL from Hibernate log output with bound parameters and assemble an index-review packet. Use when a service log shows repeated or slow statements, when Hibernate SQL lines must become runnable statements before any index discussion, or when pod logs must be turned into a shareable query report. Produces report.md and queries.sql; reads logs only. Index conclusions belong to 9to5-oracle-index and DDL to 9to5-sql-migration.
license: MIT
compatibility: Requires Python 3; kubectl only for the live-pod path (a saved file or stdin works offline). No database connection is made and bind substitution is best-effort.
metadata:
  version: "1.0.0"
---

# SQL forensics — logs to runnable statements

## Example output

Illustrative packet from a synthetic log; counts, SQL and values come from the actual log.

```text
Command: sql_forensics.py --service order-worker --file outbox.log
Result:  6 statement(s), 6 shape(s), 6/6 with binds -> sql-forensics/20260928-1542-order-worker

report.md (excerpt):
| # | Seen | Tables | Shape |
| 1 | 1 | OUTBOX_RECORD | select count(*) from outbox_record where status=? and retry_at < ? |

  #1 select count(*) from outbox_record where status=? and retry_at < ?
  select count(*) from outbox_record where status='PENDING' and retry_at < TIMESTAMP '2026-09-28 08:59:00.0'
  Binds: 1:VARCHAR, 2:TIMESTAMP

queries.sql: every reconstructed statement, one per block, ready to paste into the
plan-collection step — not to execute against production data changes.
```

## Scope and boundaries

- Read-only: the script reads a log file, stdin, or `kubectl logs`; it never connects to
  a database and never executes anything. Reconstructed `UPDATE`/`DELETE` statements are
  review artifacts, not instructions.
- Bind substitution is best-effort: `?` is replaced in order with typed literals
  (numbers raw, strings quoted and escaped, null as `NULL`, timestamps as `TIMESTAMP
  '...'`). Verify the result before trusting it; interleaved log lines can corrupt a
  statement — mark those `TODO(unverified)`.
- Grouping by normalized shape (IN lists collapsed) is a navigation aid. It is not a plan,
  not a cardinality, and not evidence.
- Bind values can contain personal data (emails, device codes, tokens in payloads).
  Strip or mask them before attaching the packet anywhere.

## Workflow

1. **Acquire the right log slice.** Prefer the bound-SQL helper from
   `9to5-k8s-service-debug`: `ksql <app> [ns]` already walks `Hibernate:` lines and
   `binding parameter` lines. Alternatively:
   ```bash
   <this-skill>/scripts/sql_forensics.py --service <name> \
     --context <ctx> --namespace <ns> --pod <pod> --tail 5000
   ```
   or `--file <saved.log>`, or pipe stdin (`klog app ns | sql_forensics.py --service app`).
2. **Generate the packet** (default output `./sql-forensics/<ts>-<service>/`):
   `report.md` and `queries.sql`. Exit code 1 with "no Hibernate statements found" means
   the slice has no SQL — widen the tail or the filter, do not invent statements.
3. **Read the statement index first.** Note which shapes repeat and which tables they
   touch; repeated shapes with the same binds are the workload, single exotic shapes are
   usually noise.
4. **Collect plan evidence before proposing anything.** On a representative environment:
   ```sql
   SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(sql_id => '<sql_id>',
     format => 'ALLSTATS LAST +BUFFERS'));
   ```
   EXPLAIN PLAN writes `PLAN_TABLE` rows and can yield a different plan than the executed
   cursor — state that limit. Follow the evidence rules in `9to5-oracle-index`.
5. **Hand off.** Index candidates and plan evidence go through `9to5-oracle-index`;
   the DDL then ships via `9to5-sql-migration` as
   `V<YYYYMMDD>_<NN>__index_<short_description>.sql`. This skill stops at the review
   packet.
6. **Persist the packet** when it is part of an investigation: keep it under
   `debug/artifacts/<YYYYMMDD>-<app>-<slug>/` with the session notes
   (`9to5-k8s-service-debug` layout), not in the repository root.

## Safety

- No production DML, no locking `SELECT ... FOR UPDATE` copies, no statement execution
  from this workflow. Diagnosis happens on a representative environment or from plans,
  not by running the suspect statement against live data.
- The packet can contain query values and table names; internal hostnames and
  credentials never belong in it. Check before sharing with anyone outside the team.
- A reconstructed statement with unmatched `?` or truncated tail: fix the slice, do not
  guess the missing value.

## Handoffs

- Need the log slice, pod selection, or artifact layout → `9to5-k8s-service-debug`.
- Index decision, column order, plan interpretation → `9to5-oracle-index`.
- Migration script conventions and review → `9to5-sql-migration`.
- Retention symptom (unbounded result set feeding memory) → `9to5-heap-triage` for the
  heap side of the same incident.

## Stop conditions

- No Hibernate/bound-parameter lines in the slice: report the absence; the service may
  log SQL at another level or not use Hibernate.
- Database unreachable for plan collection: deliver the packet and list the exact plan
  queries to run later; label all index expectations as unverified.
- Statement cannot be reconstructed faithfully (interleaved logs, truncated values):
  keep the raw fragments and say so; never present a guessed statement as the executed
  one.
