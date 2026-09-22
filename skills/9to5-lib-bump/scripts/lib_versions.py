#!/usr/bin/env python3
"""Audit and bump shared-library versions across OTS/C7 service checkouts.

Reads <LIB>_VERSION properties from gradle.properties, reports drift between
services, suggests the next version from the library repository's git state, and
writes a bump with an explicit --apply.

Dry run by default. Never commits, never pushes, never builds.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = SKILL_DIR / "config"
VERSION_RE = re.compile(r"^([A-Z][A-Z0-9_]*_VERSION|checkstyleConventionVersion)=(.*)$")
DEBUG_RE = re.compile(r"^(DEBUG_[A-Z0-9_]+)=(.*)$")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"missing config file: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"{path} is not valid JSON: {exc}")


def expand(p: str) -> Path:
    return Path(p).expanduser()


def is_excluded(path: Path, exclude_paths: list[Path], patterns: list[str]) -> bool:
    text = str(path)
    if any(text == str(e) or text.startswith(str(e) + "/") for e in exclude_paths):
        return True
    return any(pat in text for pat in patterns)


def discover(roots_cfg: dict) -> dict[Path, dict]:
    """Return {checkout_dir: {property: version}} for real working checkouts."""
    include = [expand(p) for p in roots_cfg["include_roots"]]
    exclude = [expand(p) for p in roots_cfg["exclude_paths"]]
    patterns = roots_cfg["exclude_name_patterns"]

    found: dict[Path, dict] = {}
    for root in include:
        if not root.is_dir():
            continue
        for props in sorted(root.rglob("gradle.properties")):
            if is_excluded(props, exclude, patterns):
                continue
            checkout = props.parent
            if checkout in found:
                continue
            entries: dict[str, str] = {}
            debug: dict[str, str] = {}
            for line in props.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                m = VERSION_RE.match(line)
                if m:
                    entries[m.group(1)] = m.group(2).strip()
                    continue
                m = DEBUG_RE.match(line)
                if m:
                    debug[m.group(1)] = m.group(2).strip()
            if entries or debug:
                found[checkout] = {"versions": entries, "debug": debug}
    return found


def git_state(repo: Path) -> tuple[str, str] | None:
    try:
        branch = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short=8", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip()
        return branch, sha
    except Exception:
        return None


def cmd_list(args, checkouts, libraries) -> int:
    rows = []
    for checkout, data in sorted(checkouts.items()):
        version = data["versions"].get(args.property)
        if version:
            rows.append((checkout.name, version, checkout))
    if not rows:
        print(f"no checkout defines {args.property}")
        return 1
    print(f"{args.property} — {len(rows)} checkout(s)\n")
    print(f"{'service':<38} {'version':<34} path")
    print("-" * 110)
    for name, version, path in sorted(rows, key=lambda r: (r[1], r[0])):
        print(f"{name:<38} {version:<34} {path}")
    distinct = sorted({v for _, v, _ in rows})
    print(f"\ndistinct versions: {len(distinct)}")
    for v in distinct:
        holders = sorted(n for n, ver, _ in rows if ver == v)
        print(f"  {v:<34} {len(holders):2}  {', '.join(holders[:5])}{' ...' if len(holders) > 5 else ''}")
    return 0


def cmd_audit(args, checkouts, libraries) -> int:
    problems = 0

    print("=== debug flags left enabled (build resolves a local project, not Nexus) ===")
    hits = [(c, k, v) for c, d in checkouts.items() for k, v in d["debug"].items()
            if v.lower() == "true" and k in libraries["debug_flags"]]
    if hits:
        for checkout, key, _ in sorted(hits):
            print(f"  {checkout.name:<38} {key}=true  -> {libraries['debug_flags'][key]}")
        problems += len(hits)
    else:
        print("  none")

    print("\n=== duplicate checkouts (same service in two places) ===")
    by_name: dict[str, list[Path]] = defaultdict(list)
    for checkout in checkouts:
        by_name[checkout.name].append(checkout)
    dups = {n: ps for n, ps in by_name.items() if len(ps) > 1}
    if dups:
        for name, paths in sorted(dups.items()):
            versions = sorted({checkouts[p]["versions"].get(args.property, "-") for p in paths}
                              if args.property else set())
            print(f"  {name}")
            for p in sorted(paths):
                v = checkouts[p]["versions"].get(args.property, "") if args.property else ""
                print(f"      {p}{('  ' + v) if v else ''}")
            if args.property and len(versions) > 1:
                print("      ^ different versions — pick one checkout before bumping")
                problems += 1
    else:
        print("  none")

    print("\n=== drift for tracked libraries ===")
    for prop in sorted(libraries["libraries"]):
        versions = {c: d["versions"][prop] for c, d in checkouts.items() if prop in d["versions"]}
        if not versions:
            continue
        distinct = sorted(set(versions.values()))
        flag = "DRIFT" if len(distinct) > 1 else "uniform"
        print(f"  {prop:<32} {len(versions):2} checkouts, {len(distinct):2} versions  [{flag}]")
        if len(distinct) > 1:
            problems += 1
            for v in distinct:
                n = sum(1 for x in versions.values() if x == v)
                print(f"      {v:<34} {n}")

    print(f"\n{problems} issue(s) found")
    return 0


def cmd_suggest(args, checkouts, libraries) -> int:
    entry = libraries["libraries"].get(args.property)
    if not entry:
        sys.exit(f"{args.property} is not in the local library registry "
                 f"(see config/libraries.json; known: {', '.join(sorted(libraries['libraries']))})")
    repo = expand(entry["repo"])
    state = git_state(repo)
    if not state:
        sys.exit(f"cannot read git state of {repo}")
    branch, sha = state
    candidate = f"{branch}-{sha}-SNAPSHOT"
    print(f"property:  {args.property}")
    print(f"artifact:  {entry['artifact']}")
    print(f"library:   {repo}")
    print(f"git state: {branch} @ {sha}")
    print(f"candidate: {candidate}\n")

    holders = sorted((c.name, d["versions"][args.property], c)
                     for c, d in checkouts.items() if args.property in d["versions"])
    if not holders:
        print("no checkout defines this property")
        return 0
    stale = [h for h in holders if h[1] != candidate]
    print(f"{len(holders)} checkout(s) define it; {len(stale)} differ from the candidate\n")
    print(f"{'service':<38} {'current':<34} action")
    print("-" * 100)
    for name, version, _ in holders:
        action = "already current" if version == candidate else "bump"
        print(f"{name:<38} {version:<34} {action}")
    print("\nThe candidate assumes an unreleased build of the library branch. If the library was "
          "released with a tag, use that tag instead and say so in the commit.")
    return 0


def cmd_set(args, checkouts, libraries) -> int:
    if args.property not in libraries["libraries"] and args.property not in libraries["not_local"]:
        print(f"warning: {args.property} is not in config/libraries.json; proceeding anyway", file=sys.stderr)
    targets = sorted(c for c, d in checkouts.items() if args.property in d["versions"])
    if args.only:
        wanted = {x.strip() for x in args.only.split(",") if x.strip()}
        targets = [t for t in targets if t.name in wanted]
        missing = wanted - {t.name for t in targets}
        if missing:
            sys.exit(f"no checkout matched: {', '.join(sorted(missing))}")
    if not targets:
        sys.exit(f"no checkout defines {args.property}")

    print(f"{'APPLY' if args.apply else 'DRY RUN'} — {args.property} = {args.version}")
    print(f"{len(targets)} checkout(s)\n")
    changed = 0
    for checkout in targets:
        props = checkout / "gradle.properties"
        text = props.read_text(encoding="utf-8")
        new_text, n = re.subn(rf"^{re.escape(args.property)}=.*$",
                              f"{args.property}={args.version}", text, flags=re.MULTILINE)
        if n != 1:
            print(f"  {checkout.name:<38} SKIP (property not found as a full line)")
            continue
        old = checkouts[checkout]["versions"][args.property]
        if old == args.version:
            print(f"  {checkout.name:<38} already {args.version}")
            continue
        print(f"  {checkout.name:<38} {old} -> {args.version}")
        changed += 1
        if args.apply:
            props.write_text(new_text, encoding="utf-8")
    print(f"\n{changed} file(s) {'written' if args.apply else 'would change'}")
    if not args.apply and changed:
        print("re-run with --apply to write. Verify with ./gradlew build before committing.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="checkouts that define a property, grouped by version")
    p.add_argument("--property", required=True)

    p = sub.add_parser("audit", help="debug flags, duplicate checkouts, drift")
    p.add_argument("--property", help="also compare this property between duplicate checkouts")

    p = sub.add_parser("suggest", help="next version from the library repo's git state")
    p.add_argument("--property", required=True)

    p = sub.add_parser("set", help="write a version into every checkout that defines the property")
    p.add_argument("--property", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--only", help="comma-separated checkout directory names to limit the change")
    p.add_argument("--apply", action="store_true", help="write the change (default: dry run)")

    args = ap.parse_args()
    roots_cfg = load_json(CONFIG_DIR / "roots.json")
    libraries = load_json(CONFIG_DIR / "libraries.json")
    checkouts = discover(roots_cfg)

    handlers = {"list": cmd_list, "audit": cmd_audit, "suggest": cmd_suggest, "set": cmd_set}
    return handlers[args.cmd](args, checkouts, libraries)


if __name__ == "__main__":
    raise SystemExit(main())
