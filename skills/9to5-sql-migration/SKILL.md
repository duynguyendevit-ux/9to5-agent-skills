---
name: 9to5-sql-migration
description: Write and review Oracle migration scripts for the C7/TTDVKH schemas (admin/sql/oracle, V<YYYYMMDD>_<NN>__<type>_<description>.sql). Use when the user asks to add or alter Oracle tables, columns, indexes, constraints, or seed/data fixes, mentions a migration/DDL/script file, or asks to review a migration before release.
license: MIT
metadata:
  version: "1.0.0"
---

# Oracle SQL Migration

Write Flyway-style Oracle scripts that match the existing repository conventions.

## Locations

- C7: `~/Documents/C777777777777/ttch-migration/admin/sql/oracle/`
- TTDVKH migrations live in the matching `migrations` repositories (`~/Documents/migration/...`).
- Confirm with `git rev-parse --show-toplevel` before editing; never assume.

## Naming

`V<YYYYMMDD>_<NN>__<type>_<snake_case_description>.sql`

- `YYYYMMDD` = today (`date +%Y%m%d`), `NN` = next free counter for that date (`ls V<date>_*`).
- Type prefixes observed in the repo: `ddl_` (create/structural), `uml_` (alter/add/update), `dml_` (data).
  Check the newest files first and follow what they use.
- Description is lowercase snake_case, short but specific
  (`V20260918_02__ddl_create_index_event_diaries_eh_input_source_type.sql`).

## Script rules

- One logical change per file. Keep the SQL readable; no unrelated edits.
- Oracle identifiers are case-sensitive when quoted — match existing style
  (`CREATE INDEX "idx_event_diaries__eh_input_source_type" ON "event_diaries" (...)`).
- Index and constraint names must stay within the schema's identifier limit
  (30 chars on the legacy Oracle schemas) — shorten rather than truncate silently.
- Make the script rerunnable where practical: guard with `USER_TABLES` /
  `USER_TAB_COLUMNS` / `USER_INDEXES` checks, or state clearly in a comment that it
  is one-shot.
- Never add `DROP`, `TRUNCATE`, or unconditional `DELETE` unless the ticket
  explicitly asks for it; call out data-loss risk in the plan.
- End with a verification query as a comment (`-- verify: SELECT ...`).
- No credentials, no connection strings, no environment-specific schema names.

## Workflow

1. Read the 3-5 newest migrations in the target directory to match style.
2. Grep the affected tables/columns so the change fits the current schema
   (`grep -rn "TABLE_NAME" admin/sql/oracle | tail`).
3. Write the file with the correct version and type prefix.
4. Show the full SQL to the user. Do not execute it and do not run Flyway; the
   release pipeline applies migrations.

## Review checklist

| Check | Fail looks like |
|-------|-----------------|
| Version/counter unique for the date | two `V20260918_01__` files |
| Correct type prefix for the change | `ddl_` for an ALTER TABLE |
| Identifier length ≤ limit | 34-char index name on the legacy schema |
| Rerunnable or documented one-shot | raw `CREATE TABLE` with an existing guard |
| No accidental data loss | `DROP`/`DELETE` without ticket approval |
| Verification query present | no `-- verify:` line |
| No secrets / env-specific values | hardcoded schema or password |
