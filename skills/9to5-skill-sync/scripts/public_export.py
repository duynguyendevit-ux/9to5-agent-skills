#!/usr/bin/env python3
"""Render a private export staging tree using a machine-local disclosure policy."""
import argparse
import fnmatch
import json
from pathlib import Path, PurePosixPath
import re
import sys


def relative(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value:
        raise ValueError('Unsafe export path; value withheld')
    return path


def load_policy(path):
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Export policy must be an object')
    for key in ('replacements', 'path_replacements'):
        for pair in data.get(key, []):
            if not isinstance(pair, list) or len(pair) != 2 or not all(isinstance(x, str) for x in pair) or not pair[0]:
                raise ValueError('Invalid export replacement')
    for pattern in data.get('deny_patterns', []):
        re.compile(pattern)
    for pattern, replacement in data.get('regex_replacements', []):
        re.compile(pattern)
        if not isinstance(replacement, str):
            raise ValueError('Invalid regex replacement')
    for name, body in data.get('overrides', {}).items():
        relative(name)
        if not isinstance(body, str):
            raise ValueError('Export override must contain text')
    for pattern in data.get('omit', []):
        relative(pattern)
    return data


def transform(text, policy, *, path=False):
    for before, after in policy.get('path_replacements' if path else 'replacements', []):
        text = text.replace(before, after)
    if not path:
        for pattern, replacement in policy.get('regex_replacements', []):
            text = re.sub(pattern, replacement, text)
    return text


def render(root, policy, *, namespace=''):
    """Validate every output before replacing files in an isolated staging tree."""
    outputs = {}
    sources = []
    for file in sorted(root.rglob('*')):
        if not file.is_file() and not file.is_symlink():
            continue
        rel = file.relative_to(root).as_posix()
        key = namespace + '/' + rel if namespace else rel
        sources.append(file)
        if any(fnmatch.fnmatchcase(key, pattern) for pattern in policy.get('omit', [])):
            continue
        override = policy.get('overrides', {}).get(key)
        if file.is_symlink() and override is None:
            raise ValueError('Symlinked export inputs require an explicit synthetic override or omission')
        target = str(relative(transform(rel, policy, path=True)))
        if any(re.search(pattern, target) for pattern in policy.get('deny_patterns', [])):
            raise ValueError('Public export filename contains a forbidden identifier')
        if target in outputs:
            raise ValueError('Export path collision; values withheld')
        data = override.encode('utf-8') if override is not None else file.read_bytes()
        try:
            text = transform(data.decode('utf-8'), policy)
        except UnicodeDecodeError:
            # Binary assets are preserved, not decoded using a lossy fallback.
            text = None
        if text is not None:
            if any(re.search(pattern, text) for pattern in policy.get('deny_patterns', [])):
                raise ValueError('Public export contains a forbidden identifier; content withheld')
            data = text.encode('utf-8')
        outputs[target] = (data, file.stat().st_mode & 0o777)
    # These are disposable copies, never the canonical directory or working tree.
    for file in sources:
        file.unlink()
    for name, (data, mode) in outputs.items():
        file = root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        file.chmod(mode)
    return len(outputs)


def check(root, policy):
    failures = []
    for file in sorted(root.rglob('*')):
        if '.git' in file.relative_to(root).parts or not file.is_file():
            continue
        try:
            text = file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if any(re.search(pattern, text) for pattern in policy.get('deny_patterns', [])):
            failures.append(file.relative_to(root).as_posix())
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--namespace', default='')
    parser.add_argument('--check', action='store_true', help='scan only, do not transform')
    parser.add_argument('--staging', action='store_true', help='confirm root is a disposable copied tree')
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        if args.check:
            failures = check(args.root, policy)
            if failures:
                print('Public export screening failed: ' + str(len(failures)) + ' file(s)', file=sys.stderr)
                return 1
        else:
            if not args.staging:
                raise ValueError('Rendering requires an isolated staging tree and --staging')
            render(args.root, policy, namespace=args.namespace)
    except (ValueError, OSError, re.error):
        print('Public export failed; inspect local policy and staging inputs; values withheld', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
