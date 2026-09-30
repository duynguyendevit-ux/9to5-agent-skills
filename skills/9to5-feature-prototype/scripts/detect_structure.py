#!/usr/bin/env python3
"""Read-only, bounded directory inventory to orient a design prototype.

This does not establish runtime wiring or ownership. It never reads application
configuration, credentials or source file contents beyond declared build modules.
"""

import argparse
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


SKIP = {".git", ".gradle", ".idea", "build", "target", "node_modules", "out", ".kit"}
LAYERS = {"controller", "controllers", "usecase", "service", "services", "repository", "repositories", "entity", "model", "consumer", "producer", "worker", "configuration"}
MIGRATION_DIRS = ("admin/sql/oracle", "src/main/resources/db/migration")
EVENT_DIRS = ("src/main/resources/events",)
MAX_FILES = 2000
MAX_DEPTH = 16


def rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix() or "."


def build_modules(root: Path) -> tuple[list[str], list[str]]:
    """Read only conventional build metadata; ignore modules outside the root."""
    modules = []
    evidence = []
    for name in ("settings.gradle", "settings.gradle.kts"):
        file = root / name
        if not file.is_file() or file.is_symlink():
            continue
        evidence.append(name)
        text = file.read_text(encoding="utf-8", errors="replace")[:100_000]
        for match in re.finditer(r"(?m)^\s*include\s*(?:\(([^)]*)\)|([^\n]*))", text):
            for literal in re.findall(r"['\"](:[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)*)['\"]", match.group(1) or match.group(2) or ""):
                modules.append(literal.lstrip(":").replace(":", "/"))
    pom = root / "pom.xml"
    if pom.is_file() and not pom.is_symlink():
        evidence.append("pom.xml")
        try:
            tree = ET.fromstring(pom.read_bytes()[:1_000_000])
            for element in tree.iter():
                if element.tag.rsplit("}", 1)[-1] == "modules":
                    for module in element:
                        if module.tag.rsplit("}", 1)[-1] == "module" and module.text:
                            modules.append(module.text.strip())
        except ET.ParseError:
            pass
    safe = []
    for name in modules:
        path = Path(name)
        if not name or path.is_absolute() or ".." in path.parts or not (root / path).is_dir():
            continue
        if (root / path).is_symlink() or not (root / path).resolve().is_relative_to(root):
            continue
        safe.append(path.as_posix())
    return sorted(set(safe)), evidence


def inventory(root: Path) -> dict:
    modules, evidence = build_modules(root)
    found = {"layers": set(), "migrations": set(), "events": set(), "package_roots": set()}
    for module in [".", *modules]:
        base = root if module == "." else root / module
        for dirname in MIGRATION_DIRS:
            path = base / dirname
            if path.is_dir() and not path.is_symlink():
                found["migrations"].add(rel(root, path))
        for dirname in EVENT_DIRS:
            path = base / dirname
            if path.is_dir() and not path.is_symlink():
                found["events"].add(rel(root, path))
        for language in ("java", "kotlin"):
            source = base / "src/main" / language
            if not source.is_dir() or source.is_symlink():
                continue
            seen = 0
            for directory, dirs, files in os.walk(source, followlinks=False):
                here = Path(directory)
                depth = len(here.relative_to(source).parts)
                dirs[:] = sorted(d for d in dirs if d not in SKIP and not (here / d).is_symlink()) if depth < MAX_DEPTH else []
                parts = here.relative_to(source).parts
                for index, part in enumerate(parts):
                    if part.lower() in LAYERS:
                        found["layers"].add(rel(root, source.joinpath(*parts[:index + 1])))
                        if index:
                            found["package_roots"].add(".".join(parts[:index]))
                        break
                seen += len(files)
                if seen >= MAX_FILES:
                    break
    return {"root": str(root), "modules": modules, "evidence": evidence,
            **{key: sorted(values) for key, values in found.items()},
            "note": "Directory inventory only; inspect relevant source files to establish actual ownership and wiring."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="selected checkout root")
    args = parser.parse_args()
    if not args.root.is_dir():
        parser.error("--root must be an existing directory")
    print(json.dumps(inventory(args.root.resolve()), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
