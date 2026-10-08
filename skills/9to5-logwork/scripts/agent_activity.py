#!/usr/bin/env python3
"""Agent activity digest for Jira worklog descriptions.

Reads local agent session history for given dates and prints a compact digest:
  - opencode : ~/.local/share/opencode/opencode.db (sqlite)
  - codex    : ~/.codex/sessions/YYYY/MM/DD/*.jsonl
  - claude   : ~/.claude/projects/<slug>/*.jsonl

Usage:
  agent_activity.py --date 2026-09-22
  agent_activity.py --date 2026-09-21 --date 2026-09-22
  agent_activity.py --from 2026-09-01 --to 2026-09-22
  agent_activity.py --date 2026-09-22 --json

Output is intentionally small: project + up to 3 user prompts + edited file names.
Synthesize the Vietnamese worklog description from this, never copy it verbatim.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta

HOME = os.path.expanduser("~")
OPENCODE_DB = os.path.join(HOME, ".local/share/opencode/opencode.db")
CODEX_DIR = os.path.join(HOME, ".codex/sessions")
CLAUDE_DIR = os.path.join(HOME, ".claude/projects")

MAX_PROMPTS = 3
MAX_PROMPT_LEN = 140
MAX_FILES = 6

SKIP_PROMPT = re.compile(
    r"^(<|/resume|Caveat:|\[Request interrupted|Copyright|Analyze this codebase|"
    r"You are |I'll |This session is being continued|# )"
)
SKIP_CWD = re.compile(r"^/tmp/")
TOOL_EDIT = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def day_bounds(d: date):
    start = datetime(d.year, d.month, d.day)
    end = start + timedelta(days=1)
    return start, end


def clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_PROMPT_LEN:
        text = text[: MAX_PROMPT_LEN - 1] + "…"
    return text


def good_prompt(text: str) -> bool:
    if len(text.strip()) < 3:
        return False
    if SKIP_PROMPT.match(text.strip()):
        return False
    # drop huge injected boilerplate blocks
    if text.count("\n") > 20 and len(text) > 2000:
        return False
    return True


# ---------------------------------------------------------------- opencode

def opencode_activity(start: datetime, end: datetime):
    if not os.path.exists(OPENCODE_DB):
        return {}
    s_ms = int(start.timestamp() * 1000)
    e_ms = int(end.timestamp() * 1000)
    out: dict[str, dict] = {}
    try:
        con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True)
        tables = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        # schema v2: session_v2 + session_message {type, data}
        if {"session_v2", "session_message"} <= tables:
            rows = con.execute(
                """
                SELECT s.id, coalesce(s.title,''), s.directory, sm.type, sm.data
                FROM session_v2 s
                JOIN session_message sm ON sm.session_id = s.id
                WHERE sm.time_created >= ? AND sm.time_created < ?
                  AND sm.type IN ('user','assistant')
                ORDER BY s.id, sm.seq
                """,
                (s_ms, e_ms),
            ).fetchall()
            for sid, title, directory, mtype, mdata in rows:
                if SKIP_CWD.match(directory or ""):
                    continue
                try:
                    msg = json.loads(mdata)
                except json.JSONDecodeError:
                    continue
                entry = out.setdefault(
                    directory,
                    {"agent": "opencode", "sessions": {}, "prompts": [], "files": []},
                )
                entry["sessions"][sid] = title
                if mtype == "user":
                    text = msg.get("text") or ""
                    if (
                        good_prompt(text)
                        and len(entry["prompts"]) < MAX_PROMPTS
                        and clean(text) not in entry["prompts"]
                    ):
                        entry["prompts"].append(clean(text))
                else:
                    for c in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                        if not isinstance(c, dict) or c.get("type") != "tool":
                            continue
                        if c.get("name") not in ("edit", "write", "multiedit", "apply_patch", "patch"):
                            continue
                        if len(entry["files"]) >= MAX_FILES:
                            continue
                        inp = (c.get("state") or {}).get("input") or {}
                        fp = inp.get("filePath") or inp.get("path") or inp.get("file_path")
                        if fp:
                            base = os.path.basename(fp)
                            if base not in entry["files"]:
                                entry["files"].append(base)
        else:
            # legacy schema: session + message + part
            rows = con.execute(
                """
                SELECT s.id, s.title, s.directory, p.data
                FROM session s
                JOIN message m ON m.session_id = s.id
                JOIN part p ON p.message_id = m.id
                WHERE json_extract(m.data, '$.role') = 'user'
                  AND p.time_created >= ? AND p.time_created < ?
                ORDER BY s.id, p.time_created
                """,
                (s_ms, e_ms),
            ).fetchall()
            for sid, title, directory, pdata in rows:
                if SKIP_CWD.match(directory or ""):
                    continue
                try:
                    part = json.loads(pdata)
                except json.JSONDecodeError:
                    continue
                if part.get("type") != "text":
                    continue
                text = part.get("text") or ""
                if not good_prompt(text):
                    continue
                entry = out.setdefault(
                    directory,
                    {"agent": "opencode", "sessions": {}, "prompts": [], "files": []},
                )
                entry["sessions"][sid] = title
                if len(entry["prompts"]) < MAX_PROMPTS and clean(text) not in entry["prompts"]:
                    entry["prompts"].append(clean(text))
        con.close()
    except sqlite3.Error as exc:
        print(f"[warn] opencode db: {exc}", file=sys.stderr)
        return out
    return out


# ------------------------------------------------------------------- codex

def codex_activity(start: datetime, end: datetime):
    out: dict[str, dict] = {}
    # Resumed sessions remain in their creation-day directory. Inspect each record,
    # not the directory date; start/end use the local timezone like other collectors.
    pattern = os.path.join(CODEX_DIR, "**", "*.jsonl")
    for path in sorted(glob.glob(pattern, recursive=True)):
        cwd, prompts, tools = None, [], []
        try:
            with open(path, encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rtype = rec.get("type")
                    payload = rec.get("payload") or {}
                    if rtype == "session_meta":
                        cwd = payload.get("cwd") or cwd
                    elif rtype == "response_item":
                        try:
                            when = datetime.fromisoformat(rec.get("timestamp", "").replace("Z", "+00:00"))
                            when = when.astimezone().replace(tzinfo=None)
                        except (ValueError, TypeError):
                            continue
                        if not (start <= when < end):
                            continue
                        ptype = payload.get("type")
                        if ptype == "message" and payload.get("role") == "user":
                            text = " ".join(
                                c.get("text", "")
                                for c in payload.get("content", [])
                                if isinstance(c, dict)
                            )
                            if good_prompt(text) and len(prompts) < MAX_PROMPTS:
                                prompts.append(clean(text))
                        elif ptype in ("function_call", "custom_tool_call"):
                            name = payload.get("name")
                            if name and name not in tools:
                                tools.append(name)
        except OSError:
            continue
        if not cwd or SKIP_CWD.match(cwd) or (not prompts and not tools):
            continue
        entry = out.setdefault(
            cwd, {"agent": "codex", "prompts": [], "files": [], "tools": [], "sessions": 0}
        )
        entry["sessions"] += 1
        for p in prompts:
            if p not in entry["prompts"] and len(entry["prompts"]) < MAX_PROMPTS:
                entry["prompts"].append(p)
        for t in tools:
            if t not in entry["tools"]:
                entry["tools"].append(t)
    return out


# ------------------------------------------------------------------ claude

def claude_activity(start: datetime, end: datetime):
    out: dict[str, dict] = {}
    cutoff = start.timestamp() - 86400
    for path in glob.glob(os.path.join(CLAUDE_DIR, "*", "*.jsonl")):
        try:
            if os.path.getmtime(path) < cutoff:
                continue
        except OSError:
            continue
        cwd, prompts, files = None, [], []
        try:
            for line in open(path, encoding="utf-8", errors="replace"):
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = rec.get("timestamp")
                if not ts:
                    continue
                try:
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().replace(tzinfo=None)
                except ValueError:
                    continue
                if not (start <= when < end):
                    continue
                if rec.get("cwd"):
                    cwd = rec["cwd"]
                if rec.get("isMeta"):
                    continue
                rtype = rec.get("type")
                msg = rec.get("message") or {}
                if rtype == "user" and msg.get("role") == "user":
                    content = msg.get("content")
                    texts = []
                    if isinstance(content, str):
                        texts = [content]
                    elif isinstance(content, list):
                        texts = [
                            c.get("text", "")
                            for c in content
                            if isinstance(c, dict) and c.get("type") == "text"
                        ]
                    for text in texts:
                        if good_prompt(text) and len(prompts) < MAX_PROMPTS:
                            prompts.append(clean(text))
                elif rtype == "assistant":
                    for c in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                        if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") in TOOL_EDIT:
                            fp = (c.get("input") or {}).get("file_path")
                            if fp:
                                base = os.path.basename(fp)
                                if base not in files:
                                    files.append(base)
        except OSError:
            continue
        if not cwd or SKIP_CWD.match(cwd) or (not prompts and not files):
            continue
        entry = out.setdefault(
            cwd, {"agent": "claude", "prompts": [], "files": [], "sessions": 0}
        )
        entry["sessions"] += 1
        for p in prompts:
            if p not in entry["prompts"] and len(entry["prompts"]) < MAX_PROMPTS:
                entry["prompts"].append(p)
        for f in files[: MAX_FILES - len(entry["files"])]:
            if f not in entry["files"]:
                entry["files"].append(f)
    return out


# ------------------------------------------------------------------ render

def project_name(directory: str) -> str:
    parts = [p for p in directory.rstrip("/").split("/") if p and p not in ("home", os.path.basename(HOME))]
    if not parts:
        return directory
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return parts[-1]


def render_date(d: date, as_json: bool):
    start, end = day_bounds(d)
    groups = []
    for collector in (opencode_activity, codex_activity, claude_activity):
        for directory, data in collector(start, end).items():
            data["directory"] = directory
            groups.append(data)

    if as_json:
        return {"date": d.isoformat(), "projects": groups}

    lines = [f"### {d.isoformat()}"]
    if not groups:
        lines.append("- (no agent activity found)")
        return "\n".join(lines)

    order = {"opencode": 0, "codex": 1, "claude": 2}
    groups.sort(key=lambda g: (order.get(g["agent"], 9), g["directory"]))
    for g in groups:
        sessions = g.get("sessions")
        count = len(sessions) if isinstance(sessions, dict) else sessions
        header = f"- [{g['agent']}] {project_name(g['directory'])} ({count} session(s))"
        titles = list(sessions.values()) if isinstance(sessions, dict) else []
        if titles:
            header += f" — {clean(titles[0])}"
        lines.append(header)
        for p in g.get("prompts", []):
            lines.append(f"    · {p}")
        if g.get("files"):
            lines.append("    · edits: " + ", ".join(g["files"]))
        if g.get("tools"):
            lines.append("    · tools: " + ", ".join(g["tools"][:8]))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Agent activity digest")
    ap.add_argument("--date", action="append", default=[], help="YYYY-MM-DD (repeatable)")
    ap.add_argument("--from", dest="date_from", help="start date YYYY-MM-DD")
    ap.add_argument("--to", dest="date_to", help="end date YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    dates: list[date] = []
    if args.date_from and args.date_to:
        cur = date.fromisoformat(args.date_from)
        last = date.fromisoformat(args.date_to)
        while cur <= last:
            if cur.weekday() < 5:
                dates.append(cur)
            cur += timedelta(days=1)
    for ds in args.date:
        dates.append(date.fromisoformat(ds))
    if not dates:
        ap.error("provide --date or --from/--to")

    seen = set()
    payload = []
    for d in dates:
        if d in seen:
            continue
        seen.add(d)
        payload.append(render_date(d, args.json))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(payload))


if __name__ == "__main__":
    main()
