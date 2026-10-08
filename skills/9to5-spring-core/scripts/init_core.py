#!/usr/bin/env python3
"""Render the bundled core service template without overwriting existing files."""
import argparse
import os
from pathlib import Path
import re


GENERATED_DIRECTORIES = {'.gradle', 'build', '.git', '__pycache__', 'node_modules', '.idea', '.venv'}


def template_files(root):
    """Enumerate text template inputs without traversing generated caches."""
    sources = []
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in GENERATED_DIRECTORIES)
        for name in files:
            if name == '.DS_Store':
                continue
            sources.append(Path(directory) / name)
    return sorted(sources)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--service-name', required=True)
    parser.add_argument('--starter-version', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', args.service_name):
        parser.error('service-name must be a lowercase service identifier')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.starter_version):
        parser.error('starter-version must be a concrete artifact version')
    root = args.output.expanduser().absolute()
    templates = Path(__file__).resolve().parents[1] / 'assets' / 'init-core'
    files = []
    for source in template_files(templates):
        if not source.is_file():
            continue
        relative = source.relative_to(templates)
        target = root / relative
        if target.exists() or target.is_symlink():
            parser.error(f'refusing to overwrite {target}')
        for parent in target.parents:
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                parser.error(f'unsafe destination parent: {parent}')
        body = source.read_text().replace('__SERVICE_NAME__', args.service_name)
        body = body.replace('__STARTER_VERSION__', args.starter_version)
        files.append((target, body))
    if not files:
        parser.error('bundled template is empty')
    for target, body in files:
        print(f'{"CREATE" if args.apply else "WOULD CREATE"} {target}')
        if args.apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x') as output:
                output.write(body)
    print(f'{len(files)} files; {"generated" if args.apply else "dry run; no writes"}')


if __name__ == '__main__':
    main()
