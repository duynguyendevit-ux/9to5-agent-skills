#!/usr/bin/env python3
"""sql-forensics — reconstruct runnable Oracle SQL from Hibernate logs and assemble a
review packet for index analysis.

Sources, in priority order:
  --file <path>          read an existing log file
  (stdin)                piped logs, e.g.  klog app ns | sql-forensics --service app
  --pod <pod>            kubectl logs -n <ns> <pod> --tail <n>

The packet contains:
  report.md     grouped statements, runnable SQL, dbms_xplan template, next steps
  queries.sql   every reconstructed statement as a runnable Oracle statement

Read-only: no cluster writes, no database connection. Index work continues in the
9to5-oracle-index workflow; DDL is handed to 9to5-sql-migration.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime

BIND = re.compile(
    r"binding parameter \[(\d+)\] as \[([^\]]*)\] - (?:\[(.*)\]\s*$|(null)\s*$)"
)
HIBERNATE = re.compile(r"Hibernate:\s*(.+)$")
NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")
TABLES = re.compile(
    r"\b(?:from|join|update|into|delete\s+from)\s+([A-Za-z_][A-Za-z0-9_.$]*)",
    re.IGNORECASE,
)
NUMERIC_TYPES = {"INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT", "NUMERIC", "DECIMAL",
                 "NUMBER", "FLOAT", "REAL", "DOUBLE", "BINARY_FLOAT", "BINARY_DOUBLE"}
DATE_TYPES = {"DATE": "DATE", "TIMESTAMP": "TIMESTAMP", "TIMESTAMPTZ": "TIMESTAMP",
              "TIMESTAMP_WITH_TIMEZONE": "TIMESTAMP", "TIMESTAMP WITH TIME ZONE": "TIMESTAMP"}


def literal(value: str, jdbc_type: str) -> str:
    jt = (jdbc_type or "").upper()
    if value is None:
        return "NULL"
    if value.lower() in {"null", "none"}:
        return "NULL"
    if jt in NUMERIC_TYPES and NUMERIC.match(value.strip()):
        return value.strip()
    if jt in {"BOOLEAN", "BIT"} and value.strip().upper() in {"TRUE", "FALSE", "0", "1"}:
        return value.strip().upper()
    if jt in DATE_TYPES:
        return f"{DATE_TYPES[jt]} '{value.strip()}'"
    if jt in {"BINARY", "VARBINARY", "BLOB", "RAW"}:
        return f"/* {jt}: {len(value)} chars not inlined */"
    return "'" + value.replace("'", "''") + "'"


def parse(text: str) -> list[dict]:
    """Return statements: {sql, binds: {n: (type, value)}, occurrences of the raw block}"""
    statements: list[dict] = []
    current: dict | None = None
    pending: dict[int, tuple[str, str | None]] = {}

    def flush() -> None:
        nonlocal current, pending
        if current and pending:
            current["binds"] = dict(pending)
        if current is not None:
            statements.append(current)
        current = None
        pending = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = BIND.search(line)
        if match and (current is not None or pending):
            if current is None:
                continue
            index = int(match.group(1))
            if match.group(4) == "null":
                value = None
            else:
                value = match.group(3)
            pending[index] = (match.group(2), value)
            continue

        match = HIBERNATE.search(raw_line)
        if match:
            flush()
            current = {"sql": match.group(1).strip(), "raw": [match.group(1).strip()]}
            continue

        if current is not None and line and not re.match(r"^\d{4}-\d{2}-\d{2}", line):
            # multi-line SQL continuation, e.g. formatted statements
            if "?" in current["sql"] or not pending:
                current["sql"] += " " + line

    flush()
    return statements


def substitute(statement: dict) -> str | None:
    binds = statement.get("binds")
    if not binds:
        return None
    sql = statement["sql"]
    for n in sorted(binds):
        jdbc_type, value = binds[n]
        if "?" not in sql:
            break
        sql = sql.replace("?", literal(value, jdbc_type), 1)
    return sql


def normalize(sql: str) -> str:
    norm = re.sub(r"\s+", " ", sql).strip()
    norm = re.sub(r"in\s*\([\s?,]+\)", "in (...)", norm, flags=re.IGNORECASE)
    norm = re.sub(r"values\s*\([\s?,]+\)", "values (...)", norm, flags=re.IGNORECASE)
    return norm


def group(statements: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    for st in statements:
        norm = normalize(st["sql"])
        entry = groups.setdefault(norm, {"norm": norm, "count": 0, "sample": st})
        entry["count"] += 1
    return sorted(groups.values(), key=lambda e: (-e["count"], e["norm"]))


def render_report(service: str, source: str, groups: list[dict]) -> str:
    lines = [
        f"# SQL forensics — {service}",
        "",
        f"- source: {source}",
        f"- generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- statements captured: {sum(g['count'] for g in groups)} across {len(groups)} distinct shape(s)",
        "",
        "## Statement index",
        "",
        "| # | Seen | Tables | Shape |",
        "|---|---|---|---|",
    ]
    for i, g in enumerate(groups, 1):
        tables = sorted({t.upper() for t in TABLES.findall(g["norm"])})
        shape = g["norm"][:100].replace("|", "\\|")
        lines.append(f"| {i} | {g['count']} | {', '.join(tables) or '-'} | `{shape}` |")

    for i, g in enumerate(groups, 1):
        st = g["sample"]
        runnable = substitute(st)
        lines += ["", f"## {i}. {st['sql'][:120]}", ""]
        if runnable:
            lines += ["```sql", runnable, "```", ""]
        else:
            lines += ["```sql", st["sql"], "```", "",
                      "(no bind lines captured next to this statement — values unknown)", ""]
        binds = st.get("binds") or {}
        if binds:
            lines.append("Binds: " + ", ".join(
                f"{n}:{t}" for n, (t, _) in sorted(binds.items())))
        lines.append("")

    lines += [
        "## Next steps",
        "",
        "1. Collect the executed plan on a representative environment (read-only):",
        "",
        "```sql",
        "-- prefer the real cursor plan of a running session:",
        "SELECT * FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(sql_id => '<sql_id>', format => 'ALLSTATS LAST +BUFFERS'));",
        "-- EXPLAIN PLAN writes PLAN_TABLE rows; it is not a zero-write operation and",
        "-- may produce a different plan than the executed one.",
        "```",
        "",
        "2. Inspect access/filter predicates, Starts vs actual rows, and index-disabling",
        "   conversions for the critical statement above (9to5-oracle-index workflow).",
        "3. If an index is justified, ship it as a migration:",
        "   `V<YYYYMMDD>_<NN>__index_<short_description>.sql` (9to5-sql-migration).",
        "",
        "This packet contains no row data beyond bind values; strip sensitive values",
        "before attaching it to a ticket.",
    ]
    return "\n".join(lines) + "\n"


def render_queries(groups: list[dict]) -> str:
    chunks = ["-- reconstructed statements (best effort; verify before executing)",
              "-- generated by sql-forensics"]
    for i, g in enumerate(groups, 1):
        st = g["sample"]
        runnable = substitute(st) or st["sql"]
        chunks += ["", f"-- #{i} seen {g['count']}x", runnable.rstrip(";") + ";"]
    return "\n".join(chunks) + "\n"


def acquire(args: argparse.Namespace) -> tuple[str, str]:
    if args.file:
        with open(args.file, encoding="utf-8", errors="replace") as fh:
            return fh.read(), args.file
    if not sys.stdin.isatty():
        return sys.stdin.read(), "stdin"
    if args.pod:
        ns = args.namespace or "default"
        cmd = ["kubectl"]
        if args.context:
            cmd += ["--context", args.context]
        cmd += ["logs", "-n", ns, args.pod, f"--tail={args.tail}"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0:
            print(out.stderr.strip(), file=sys.stderr)
            sys.exit(1)
        return out.stdout, " ".join(cmd)
    print("no log source: pass --file, --pod, or pipe logs on stdin", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--service", required=True, help="service/app name for the report title")
    p.add_argument("--file", help="log file to parse")
    p.add_argument("--pod", help="pod name for kubectl logs")
    p.add_argument("--namespace", "-n", help="namespace for kubectl logs")
    p.add_argument("--context", help="kubectl context")
    p.add_argument("--tail", type=int, default=5000, help="kubectl logs tail (default 5000)")
    p.add_argument("--out", help="output directory (default ./sql-forensics/<ts>-<service>)")
    args = p.parse_args()

    text, source = acquire(args)
    groups = group(parse(text))
    if not groups:
        print("no Hibernate statements found in the log excerpt", file=sys.stderr)
        return 1

    out_dir = args.out or os.path.join(
        "sql-forensics", f"{datetime.now().strftime('%Y%m%d-%H%M')}-{args.service}")
    os.makedirs(out_dir, exist_ok=True)
    report = os.path.join(out_dir, "report.md")
    queries = os.path.join(out_dir, "queries.sql")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write(render_report(args.service, source, groups))
    with open(queries, "w", encoding="utf-8") as fh:
        fh.write(render_queries(groups))

    bound = sum(1 for g in groups if g["sample"].get("binds"))
    print(f"{sum(g['count'] for g in groups)} statement(s), {len(groups)} shape(s), "
          f"{bound}/{len(groups)} with binds -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
