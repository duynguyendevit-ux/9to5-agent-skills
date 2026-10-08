#!/usr/bin/env python3
"""Generate/check the README skill catalog from frontmatter (no remote access)."""
import argparse
from pathlib import Path
import re
import sys

import yaml

START = '<!-- skill-catalog:start -->'
END = '<!-- skill-catalog:end -->'

def catalog(root):
    rows = ['| Skill | Version | Purpose |', '| --- | --- | --- |']
    paths = sorted((root / 'skills').glob('*/SKILL.md'))
    if not paths:
        raise ValueError('No skill entry points found')
    for path in paths:
        text = path.read_text(encoding='utf-8')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.S)
        if not match:
            raise ValueError(f'{path.parent.name}: missing frontmatter')
        data = yaml.safe_load(match[1])
        if not isinstance(data, dict) or data.get('name') != path.parent.name:
            raise ValueError(f'{path.parent.name}: frontmatter name mismatch')
        metadata = data.get('metadata')
        if not isinstance(metadata, dict):
            raise ValueError(f'{path.parent.name}: missing metadata')
        version = str(metadata.get('version', ''))
        if not re.fullmatch(r'\d+\.\d+\.\d+', version):
            raise ValueError(f'{path.parent.name}: invalid version')
        description = data.get('description')
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f'{path.parent.name}: missing description')
        purpose = re.split(r'\.\s+(?=[A-Z])', ' '.join(description.split()), maxsplit=1)[0]
        purpose = purpose.replace('|', '&#124;').replace('<', '&lt;').replace('>', '&gt;')
        name = path.parent.name
        rows.append(f'| [`{name}`](skills/{name}/SKILL.md) | {version} | {purpose.rstrip(".")}. |')
    return START + '\n' + '\n'.join(rows) + '\n' + END

def updated_readme(root):
    path = root / 'README.md'
    text = path.read_text(encoding='utf-8')
    block = catalog(root)
    if START in text or END in text:
        if text.count(START) != 1 or text.count(END) != 1 or text.index(START) > text.index(END):
            raise ValueError('README catalog markers are ambiguous')
        return text, text[:text.index(START)] + block + text[text.index(END) + len(END):]
    section = re.search(r'(?m)^## Skills\s*$', text)
    if not section:
        raise ValueError('README Skills section not found')
    next_section = re.search(r'(?m)^## ', text[section.end():])
    end = section.end() + next_section.start() if next_section else len(text)
    content = text[section.end():end]
    table = re.search(r'(?m)^\| Skill \| Version \| Purpose \|\n(?:\|[^\n]*\|\n?)+', content)
    if not table:
        raise ValueError('README legacy catalog table not found')
    begin = section.end() + table.start()
    finish = section.end() + table.end()
    suffix = text[finish:]
    return text, text[:begin] + block + '\n' + suffix

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='exit nonzero on drift, without writing')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        before, after = updated_readme(args.root)
    except (ValueError, OSError, yaml.YAMLError) as exc:
        print(f'Catalog check failed: {type(exc).__name__}; inspect metadata/markers', file=sys.stderr)
        return 2
    if before != after:
        if args.check:
            print('Skill catalog drift: run python3 scripts/update_catalog.py', file=sys.stderr)
            return 1
        (args.root / 'README.md').write_text(after, encoding='utf-8')
        print('README skill catalog regenerated from frontmatter')
    else:
        print('Skill catalog matches frontmatter')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
