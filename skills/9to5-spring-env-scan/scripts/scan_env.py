#!/usr/bin/env python3
"""Offline, value-free Java/Spring environment inventory (Python 3.10+)."""
import argparse
from collections import defaultdict, namedtuple
import fnmatch
import json
import os
from pathlib import Path
import re
import sys

try:
    import yaml
except ImportError:
    yaml = None

SKIP = {'.git', '.gradle', '.idea', '.venv', 'venv', 'build', 'target',
        'node_modules', 'vendor', '__pycache__', 'out'}
ENV = re.compile(r'^[A-Z_][A-Z0-9_]*$')
KEY = re.compile(r'^[A-Za-z_][A-Za-z0-9_.\[\]-]*$')
Token = namedtuple('Token', 'text start end string')
LEX = re.compile(r'//[^\n]*|/\*.*?\*/|""".*?"""|"(?:\\.|[^"\\])*"|'
                 r"'(?:\\.|[^'\\])*'|[A-Za-z_$][\w$]*|\d+|[^\s]", re.S)


def decode_literal(value, java=False):
    """Decode Java/properties escapes without evaluating expressions."""
    def replace(match):
        escape = match.group(1)
        if escape.startswith('u') and re.fullmatch(r'u+[0-9a-fA-F]{4}', escape):
            return chr(int(escape.lstrip('u'), 16))
        if java and re.fullmatch(r'[0-7]{1,3}', escape):
            return chr(int(escape, 8))
        return {'n': '\n', 'r': '\r', 't': '\t', 'f': '\f', 'b': '\b'}.get(escape, escape)
    pattern = r'\\(u+[0-9a-fA-F]{4}|[0-3][0-7]{0,2}|[4-7][0-7]?|.)' if java else r'\\(u+[0-9a-fA-F]{4}|.)'
    return re.sub(pattern, replace, value)


def tokenize(text):
    result = []
    for match in LEX.finditer(text):
        raw = match.group()
        if raw.startswith(('//', '/*')):
            continue
        string = raw.startswith('"')
        if string:
            raw = decode_literal(raw[3:-3] if raw.startswith('"""') else raw[1:-1], java=True)
        result.append(Token(raw, match.start(), match.end(), string))
    return result


def matching(tokens, index, opening='(', closing=')'):
    depth = 0
    for i in range(index, len(tokens)):
        if tokens[i].string:
            continue
        if tokens[i].text == opening:
            depth += 1
        elif tokens[i].text == closing:
            depth -= 1
            if depth == 0:
                return i
    return None


def annotation_name(tokens, index):
    """Read a qualified annotation name, not the following declaration's words."""
    names = []
    if index < len(tokens) and re.fullmatch(r'[A-Za-z_$][\w$]*', tokens[index].text):
        names.append(tokens[index].text)
        index += 1
        while index + 1 < len(tokens) and tokens[index].text == '.':
            names.extend(('.', tokens[index + 1].text))
            index += 2
    return ''.join(names), index


def kebab(name):
    name = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1-\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', name).replace('_', '-').lower()


def canonical(key):
    # Compare relaxed field names within each path segment, not across dots.
    return '.'.join(part.replace('-', '').replace('_', '').lower() for part in key.split('.'))


def placeholders(text):
    """Yield (key, fallback_present, offset); support recursive fallback syntax."""
    pos = 0
    while True:
        start = text.find('${', pos)
        if start < 0:
            return
        i, depth, colon = start + 2, 1, None
        while i < len(text) and depth:
            if text.startswith('${', i):
                depth += 1
                i += 2
                continue
            if text[i] == '}':
                depth -= 1
            elif text[i] == ':' and depth == 1 and colon is None:
                colon = i
            i += 1
        if depth:
            yield None, False, start
            return
        end = i - 1
        key = text[start + 2:colon if colon is not None else end]
        yield key if KEY.fullmatch(key) else None, colon is not None, start
        if colon is not None:
            for nested, default, offset in placeholders(text[colon + 1:end]):
                yield nested, default, colon + 1 + offset
        pos = i


class Scan:
    def __init__(self, root):
        self.root = root
        self.props = defaultdict(list)
        self.variables = defaultdict(list)
        self.edges = defaultdict(set)
        self.warnings = []
        self.files = []
        self.classes = []
        self.bindings = []

    def location(self, path, line, kind, **extra):
        return dict(file=path.relative_to(self.root).as_posix(), line=line, kind=kind, **extra)

    def warn(self, code, location):
        item = dict(code=code, **location)
        if item not in self.warnings:
            self.warnings.append(item)

    def prop(self, key, location):
        if KEY.fullmatch(key):
            if location not in self.props[key]:
                self.props[key].append(location)
        else:
            self.warn('unsupported_property_key', location)

    def references(self, value, location, owner=None):
        for key, fallback, _ in placeholders(value):
            if key is None:
                self.warn('dynamic_or_malformed_placeholder', location)
                continue
            evidence = dict(location, default='has_default' if fallback else 'no_default')
            if ENV.fullmatch(key):
                if evidence not in self.variables[key]:
                    self.variables[key].append(evidence)
            else:
                self.prop(key, dict(evidence, kind='property_reference' if location['kind'] == 'config'
                                    else location['kind']))
            if owner and KEY.fullmatch(owner):
                self.edges[owner].add(key)

    def config_value(self, key, value, location):
        self.prop(key, location)
        if isinstance(value, str):
            self.references(value, location, key)
        if key == 'spring.config.import' or key.startswith('spring.config.import['):
            self.warn('config_import_not_resolved', location)

    def scan_yaml(self, path, text):
        try:
            docs = list(yaml.compose_all(text, Loader=yaml.SafeLoader))
        except (yaml.YAMLError, RecursionError) as error:
            mark = getattr(error, 'problem_mark', None)
            self.warn('invalid_yaml', self.location(path, mark.line + 1 if mark else 1, 'config'))
            return
        for number, doc in enumerate(docs, 1):
            visits = 0
            def visit(node, key, ancestors):
                nonlocal visits
                loc = self.location(path, node.start_mark.line + 1, 'config', document=number)
                visits += 1
                if visits > 50000:
                    self.warn('yaml_expansion_limit', self.location(path, 1, 'config'))
                    return
                if len(ancestors) > 100:
                    self.warn('yaml_depth_limit', loc)
                    return
                if id(node) in ancestors:
                    self.warn('recursive_yaml_alias', loc)
                    return
                ancestors = ancestors | {id(node)}
                if isinstance(node, yaml.MappingNode):
                    seen = set()
                    for name, value in node.value:
                        if not isinstance(name, yaml.ScalarNode):
                            self.warn('complex_yaml_key', loc)
                            continue
                        if name.tag == 'tag:yaml.org,2002:merge':
                            merges = value.value if isinstance(value, yaml.SequenceNode) else [value]
                            for merged in merges:
                                visit(merged, key, ancestors)
                            continue
                        if name.value in seen:
                            self.warn('duplicate_yaml_key', loc)
                        seen.add(name.value)
                        visit(value, f'{key}.{name.value}' if key else name.value, ancestors)
                elif isinstance(node, yaml.SequenceNode):
                    for index, child in enumerate(node.value):
                        visit(child, f'{key}[{index}]', ancestors)
                elif isinstance(node, yaml.ScalarNode) and key:
                    self.config_value(key, node.value, loc)
            if doc is not None:
                visit(doc, '', set())

    def scan_properties(self, path, text):
        pending, start, document = '', 1, 1
        for line, raw in enumerate(text.splitlines(), 1):
            if not pending:
                start = line
                if raw.strip() in ('#---', '!---'):
                    document += 1
                if not raw.strip() or raw.lstrip().startswith(('#', '!')):
                    continue
            pending += raw.lstrip() if pending else raw.lstrip()
            trailing = len(pending) - len(pending.rstrip('\\'))
            if trailing % 2:
                pending = pending[:-1]
                continue
            entry, pending = pending, ''
            separator = re.search(r'(?<!\\)(?:\\\\)*([:=\s])', entry)
            if separator:
                split = separator.end(1) - 1
                key = decode_literal(entry[:split])
                value = re.sub(r'^\s*[:=]?\s*', '', entry[split:])
            else:
                key, value = decode_literal(entry), ''
            self.config_value(key, decode_literal(value),
                              self.location(path, start, 'config', document=document))
        if pending:
            self.warn('unfinished_properties_continuation', self.location(path, start, 'config'))

    def scan_java(self, path, text):
        tokens = tokenize(text)
        line = lambda i: text.count('\n', 0, tokens[i].start) + 1
        loc = lambda i, kind, **extra: self.location(path, line(i), kind, **extra)
        annotations = []
        for i, token in enumerate(tokens):
            if token.string:
                continue
            if token.text == '@':
                name, j = annotation_name(tokens, i + 1)
                if name.split('.')[-1] == 'ConfigurationProperties' and (j >= len(tokens) or tokens[j].text != '('):
                    annotations.append((j - 1, '', loc(i, '@ConfigurationProperties')))
                if j < len(tokens) and tokens[j].text == '(':
                    end = matching(tokens, j)
                    if end is None:
                        self.warn('unbalanced_java_annotation', loc(i, 'java'))
                        continue
                    simple = name.split('.')[-1]
                    args = tokens[j + 1:end]
                    if simple == 'Value':
                        if len(args) == 1 and args[0].string:
                            self.references(args[0].text, loc(i, '@Value'))
                            if '#{' in args[0].text:
                                self.warn('spel_not_evaluated', loc(i, '@Value'))
                        else:
                            self.warn('dynamic_value_annotation', loc(i, '@Value'))
                    if simple == 'ConfigurationProperties':
                        prefix = '' if not args or not any(not a.string and a.text in ('prefix', 'value') for a in args) else None
                        if len(args) == 1 and args[0].string:
                            prefix = args[0].text
                        for a in range(len(args) - 2):
                            if args[a].text in ('prefix', 'value') and args[a + 1].text == '=' and args[a + 2].string:
                                if a + 3 == len(args) or args[a + 3].text == ',':
                                    prefix = args[a + 2].text
                        if prefix is None or (prefix and not KEY.fullmatch(prefix)):
                            self.warn('dynamic_configuration_prefix', loc(i, '@ConfigurationProperties'))
                        else:
                            annotations.append((end, prefix, loc(i, '@ConfigurationProperties')))
            if i + 2 >= len(tokens) or tokens[i + 1].text != '(':
                continue
            method = token.text
            if method not in ('getenv', 'getProperty', 'getRequiredProperty', 'containsProperty'):
                continue
            if i < 2 or tokens[i - 1].text != '.':
                continue
            system = tokens[i - 2].text == 'System'
            if method == 'getenv' and not system:
                continue
            end = matching(tokens, i + 1)
            args = tokens[i + 2:end] if end is not None else []
            evidence = loc(i, 'System.getenv' if method == 'getenv' else
                           'System.getProperty' if system else method,
                           confidence='literal' if system else 'heuristic_receiver')
            if not args or not args[0].string or (len(args) > 1 and args[1].text != ','):
                self.warn('dynamic_lookup_argument', evidence)
                continue
            key = args[0].text
            if method == 'getenv':
                if KEY.fullmatch(key):
                    self.variables[key].append(evidence)
                else:
                    self.warn('unsupported_environment_name', evidence)
            else:
                self.prop(key, evidence)
                if not system and ENV.fullmatch(key):
                    self.variables[key].append(evidence)
        classes = self.java_classes(tokens, loc)
        for cls in classes:
            for field in cls['fields']:
                if 'start' in field:
                    field['line'] = text.count('\n', 0, field['start']) + 1
        self.classes.extend(classes)
        for end, prefix, evidence in annotations:
            # Only attach to the following declaration, never a later unrelated class.
            tail = tokens[end + 1:]
            boundary = next((j for j, t in enumerate(tail) if not t.string and t.text in ('{', ';')), len(tail))
            header = tail[:boundary]
            cls = next((c for c in classes if end < c['index'] < end + 1 + boundary), None)
            if cls:
                self.bindings.append((prefix, cls, evidence))
            else:
                clean, cursor = [], 0
                while cursor < len(header):
                    if header[cursor].text == '@' and not header[cursor].string:
                        _, cursor = annotation_name(header, cursor + 1)
                        if cursor < len(header) and header[cursor].text == '(':
                            annotation_end = matching(header, cursor)
                            cursor = len(header) if annotation_end is None else annotation_end + 1
                    else:
                        clean.append(header[cursor])
                        cursor += 1
                header = clean
                paren = next((j for j, t in enumerate(header) if t.text == '('), None)
                if paren is not None and paren >= 2:
                    # Factory method: the token before its name is the simple return type.
                    self.bindings.append((prefix, header[paren - 2].text, evidence))
                else:
                    self.warn('unsupported_configuration_declaration', evidence)

    def java_classes(self, tokens, loc):
        classes = []
        for i, token in enumerate(tokens):
            if token.string or token.text not in ('class', 'record') or i + 1 >= len(tokens):
                continue
            if i and tokens[i - 1].text == '.':  # Foo.class
                continue
            j = i + 2
            components = []
            if token.text == 'record' and j < len(tokens) and tokens[j].text == '(':
                end = matching(tokens, j)
                if end is None:
                    continue
                components = self.fields(tokens[j + 1:end], ',', loc, record=True)
                j = end + 1
            while j < len(tokens) and tokens[j].text not in ('{', ';'):
                j += 1
            if j == len(tokens) or tokens[j].text != '{':
                continue
            end = matching(tokens, j, '{', '}')
            if end is None:
                self.warn('unbalanced_java_class', loc(i, 'java'))
                continue
            fields = self.fields(tokens[j + 1:end], ';', loc)
            header = [t.text for t in tokens[i + 2:j]]
            classes.append(dict(name=tokens[i + 1].text, index=i, fields=components + fields,
                                inherited='extends' in header, location=loc(i, 'config_class')))
        return classes

    def fields(self, tokens, separator, loc, record=False):
        # Walk declaration-level tokens, skipping methods, nested classes and initializers.
        fields, segment, i, angle, initialized = [], [], 0, 0, False
        while i < len(tokens):
            token = tokens[i]
            if not token.string and token.text == '@':
                _, i = annotation_name(tokens, i + 1)
                if i < len(tokens) and tokens[i].text == '(':
                    end = matching(tokens, i)
                    i = len(tokens) if end is None else end + 1
                continue
            if not token.string and token.text == '{':
                end = matching(tokens, i, '{', '}')
                if '=' not in [t.text for t in segment]:
                    segment = []
                    angle, initialized = 0, False
                i = len(tokens) if end is None else end + 1
                continue
            if not token.string and token.text == '=':
                initialized = True
            if not token.string and token.text == '<' and not initialized:
                angle += 1
            if not token.string and token.text == '>' and not initialized:
                angle = max(0, angle - 1)
            if not token.string and token.text == separator and not angle:
                self.field_segment(segment, fields)
                segment = []
                initialized = False
            else:
                segment.append(token)
            i += 1
        if record:
            self.field_segment(segment, fields)
        return fields

    @staticmethod
    def field_segment(segment, fields):
        words = [t.text if not t.string else '' for t in segment]
        if not words or 'static' in words:
            return
        before = segment[:words.index('=')] if '=' in words else segment
        if any(t.text == '(' and not t.string for t in before):
            return
        if any(t.text in ('class', 'record', 'interface', 'enum') for t in before):
            return
        # Multiple declarations are intentionally rejected rather than inventing keys.
        depth, parens, initialized = 0, 0, False
        for t in segment:
            if t.string:
                continue
            if t.text == '=': initialized = True
            elif t.text == '<' and not initialized: depth += 1
            elif t.text == '>' and not initialized: depth -= 1
            elif t.text == '(': parens += 1
            elif t.text == ')': parens -= 1
            elif t.text == ',' and depth == 0 and parens == 0:
                fields.append(dict(unsupported=True))
                return
        identifiers = [t for t in before if not t.string and re.fullmatch(r'[A-Za-z_$][\w$]*', t.text)
                       and t.text not in ('public', 'private', 'protected', 'final', 'transient', 'volatile')]
        if len(identifiers) >= 2:
            generic = next((i for i, t in enumerate(before) if t.text == '<'), None)
            type_tokens = before[:generic] if generic is not None else before[:before.index(identifiers[-1])]
            types = [t.text for t in type_tokens if not t.string and re.fullmatch(r'[A-Za-z_$][\w$]*', t.text)
                     and t.text not in ('public', 'private', 'protected', 'final', 'transient', 'volatile')]
            fields.append(dict(name=identifiers[-1].text, type=types[-1] if types else identifiers[0].text,
                               start=identifiers[-1].start,
                               collection=any(t.text in ('<', '[') for t in before)))

    def expand_bindings(self):
        by_name = defaultdict(list)
        for cls in self.classes:
            by_name[cls['name']].append(cls)
        simple_types = {'String', 'boolean', 'Boolean', 'byte', 'Byte', 'short', 'Short',
                        'int', 'Integer', 'long', 'Long', 'float', 'Float', 'double', 'Double',
                        'char', 'Character', 'Duration', 'DataSize', 'URI', 'URL', 'Path',
                        'BigDecimal', 'BigInteger', 'Charset', 'InetAddress'}
        def expand(prefix, cls, evidence, ancestors):
            if len(ancestors) > 100:
                self.warn('config_type_depth_limit', evidence)
                return
            if id(cls) in ancestors:
                self.warn('recursive_config_type', evidence)
                return
            if cls['inherited']:
                self.warn('inherited_config_fields_not_scanned', evidence)
            for field in cls['fields']:
                if field.get('unsupported'):
                    self.warn('multiple_config_field_declaration', evidence)
                    continue
                key = f'{prefix}.{kebab(field["name"])}' if prefix else kebab(field['name'])
                shape = 'collection' if field['collection'] else 'object' if field['type'] in by_name else 'scalar'
                location = dict(cls['location'], line=field['line'], kind='config_binding',
                                confidence='heuristic_binding', binding_shape=shape)
                self.prop(key, location)
                if field['collection']:
                    self.warn('collection_config_not_expanded', location)
                elif field['type'] in by_name:
                    candidates = by_name[field['type']]
                    if len(candidates) == 1:
                        expand(key, candidates[0], evidence, ancestors | {id(cls)})
                    else:
                        self.warn('ambiguous_config_type', location)
                elif field['type'] not in simple_types:
                    self.warn('external_or_unsupported_config_type', location)
        for prefix, cls, evidence in self.bindings:
            if isinstance(cls, str):
                candidates = by_name[cls]
                if len(candidates) != 1:
                    self.warn('unresolved_factory_config_type', evidence)
                    continue
                cls = candidates[0]
            expand(prefix, cls, evidence, set())

    def report(self, include_tests):
        self.expand_bindings()
        # Link relaxed Java binding keys to config keys without losing declaration spelling.
        groups = defaultdict(set)
        for key in set(self.props) | set(self.edges):
            groups[canonical(key)].add(key)
        resolved = {}
        def env_for(key):
            visited, pending, result = set(), [key], set()
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                if current in self.variables:
                    result.add(current)
                for equivalent in groups.get(canonical(current), set()):
                    pending.extend(self.edges.get(equivalent, set()))
            return result
        for key in self.props:
            resolved[key] = env_for(key)
        props = []
        inferred = defaultdict(set)
        for key, occurrences in sorted(self.props.items()):
            equivalents = groups[canonical(key)]
            evidence = []
            for name in sorted(equivalents):
                for item in self.props.get(name, []):
                    if item not in evidence:
                        evidence.append(item)
            props.append(dict(name=key, variables=sorted(resolved[key]), evidence=evidence))
            spring = any(e['kind'] != 'System.getProperty' and e.get('binding_shape') not in ('collection', 'object')
                         for e in evidence)
            if spring and not ENV.fullmatch(key) and re.fullmatch(r'[a-zA-Z0-9.-]+', key):
                candidate = key.replace('.', '_').replace('-', '').upper()
                inferred[candidate].add(key)
        variables = [dict(name=name, properties=sorted(k for k in self.props if name in resolved[k]),
                          evidence=items) for name, items in sorted(self.variables.items())]
        return dict(schema_version=1, coverage=dict(files=self.files, include_tests=include_tests,
                    profiles='inventory_only', values='withheld', analysis='static_heuristic'),
                    variables=variables, properties=props,
                    inferred_variables=[dict(name=k, properties=sorted(v), confidence='spring_candidate')
                                        for k, v in sorted(inferred.items())],
                    warnings=sorted(self.warnings, key=lambda w: (w['file'], w['line'], w['code'])))


def markdown(report):
    def cell(text):
        return str(text).replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ').replace('\r', ' ').replace('`', "'")
    def locations(items):
        return ', '.join(sorted({f"{e['file']}:{e['line']} ({e['kind']})" for e in items}))
    lines = ['# Spring environment inventory', '',
             f"Explicit variables: {len(report['variables'])}; inferred candidates: {len(report['inferred_variables'])}; warnings: {len(report['warnings'])}.",
             'Static source inventory; profiles not evaluated; values withheld.', '',
             '## Explicit variables', '', '| Variable | Properties | Direct evidence / default presence |', '| --- | --- | --- |']
    for var in report['variables']:
        evidence = ', '.join(f"{e['file']}:{e['line']} ({e['kind']}, {e.get('default', 'not_assessed')})" for e in var['evidence'])
        lines.append('| ' + ' | '.join(map(cell, (var['name'], ', '.join(var['properties']), evidence))) + ' |')
    lines += ['', '## Properties and Java consumers', '', '| Property | Explicit variables | Evidence |', '| --- | --- | --- |']
    for prop in report['properties']:
        lines.append('| ' + ' | '.join(map(cell, (prop['name'], ', '.join(prop['variables']), locations(prop['evidence'])))) + ' |')
    lines += ['', '## Inferred Spring override candidates', '', '| Candidate (not proven) | Properties |', '| --- | --- |']
    for var in report['inferred_variables']:
        lines.append('| ' + ' | '.join(map(cell, (var['name'], ', '.join(var['properties'])))) + ' |')
    lines += ['', '## Coverage', '', f"Scanned files: {len(report['coverage']['files'])}; include tests: {report['coverage']['include_tests']}. All profile documents are inventoried separately.",
              'No dependency/runtime sources, computed names, getter call-site tracing or binding verification.', '', '## Warnings', '']
    lines += [f"- {cell(w['code'])}: {cell(w['file'])}:{w['line']}" for w in report['warnings']] or ['None within supported scope.']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='repository to scan read-only')
    parser.add_argument('--format', choices=('json', 'markdown', 'env'), default='markdown')
    parser.add_argument('--include-tests', action='store_true')
    parser.add_argument('--config', action='append', default=[], help='extra config relative to root (repeatable)')
    parser.add_argument('--exclude', action='append', default=[], help='exclude root-relative glob (repeatable)')
    args = parser.parse_args(argv)
    if yaml is None:
        parser.error('PyYAML required: python3 -m pip install PyYAML')
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        parser.error('root must be an existing directory')
    extras = set()
    for raw in args.config:
        path = root / raw
        if '..' in path.parts or not path.is_relative_to(root) or path.is_symlink() or not path.is_file():
            parser.error('custom config must be a regular file inside root')
        if any(parent.is_symlink() for parent in path.parents if parent != root):
            parser.error('custom config symlink parents are outside scan scope')
        if path.suffix not in ('.yaml', '.yml', '.properties'):
            parser.error('custom config must be YAML or properties')
        extras.add(path)
    scan = Scan(root)
    def excluded(path):
        rel = path.relative_to(root)
        return any(fnmatch.fnmatch(rel.as_posix(), pattern) for pattern in args.exclude)
    paths = {p for p in extras if not excluded(p)}
    def walk_error(error):
        path = Path(error.filename) if error.filename else root
        scan.warn('unreadable_directory', scan.location(path, 1, 'directory'))
    for base, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.')
                         and (args.include_tests or d not in ('test', 'tests'))
                         and not (Path(base) / d).is_symlink() and not excluded(Path(base) / d))
        for name in sorted(files):
            path = Path(base) / name
            if path.is_symlink() or excluded(path):
                continue
            if path.suffix == '.java' or re.fullmatch(r'(application|bootstrap)[^/]*\.(yaml|yml|properties)', name):
                paths.add(path)
    for path in sorted(paths):
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            scan.warn('unreadable_source', scan.location(path, 1, 'file'))
            continue
        scan.files.append(path.relative_to(root).as_posix())
        if path.suffix == '.java':
            scan.scan_java(path, text)
        elif path.suffix == '.properties':
            scan.scan_properties(path, text)
        else:
            scan.scan_yaml(path, text)
    report = scan.report(args.include_tests)
    if not scan.files:
        report['warnings'].append(dict(code='no_supported_files', file='.', line=1, kind='coverage'))
    if args.format == 'json':
        print(json.dumps(report, indent=2, ensure_ascii=True))
    elif args.format == 'env':
        print('# Names only; not a dotenv file. Inferred candidates omitted.')
        print('# Coverage: static, profiles not evaluated; warnings=' + str(len(report['warnings'])))
        for item in report['variables']:
            print(item['name'])
    else:
        print(markdown(report), end='')
    return 1 if report['warnings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
