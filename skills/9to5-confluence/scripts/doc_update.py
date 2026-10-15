"""Scoped Confluence edits with immutable review bundles and one stable preview."""
import argparse
import contextlib
import difflib
import hashlib
import html
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import confluence as cf
import publication_checks as checks
import storage_tables as tables

DEFAULT_ROOT = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'opencode/doc-updates'

def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()

def write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('x', encoding='utf-8') as stream:
        stream.write(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    path.chmod(0o600)

def selected_column(headers, name):
    folded = [h.casefold() for h in headers]
    if len(set(folded)) != len(folded) or not isinstance(name, str) or name.casefold() not in folded:
        raise ValueError('Missing or ambiguous column')
    return folded.index(name.casefold())

def fragment(value):
    if not isinstance(value, str):
        raise ValueError('Replacement must be a string')
    node = tables._tree(value)
    for item in node.iter():
        if item.tag.rsplit('}', 1)[-1].lower() in ('script', 'iframe', 'object', 'embed', 'form', 'style', 'base', 'meta'):
            raise ValueError('Active markup is unsupported')
        for key, val in item.attrib.items():
            normalized = key.rsplit('}', 1)[-1].lower()
            if normalized.startswith('on') or (normalized in ('href', 'src') and re.match(r'\s*(javascript|data):', val, re.I)):
                raise ValueError('Active markup is unsupported')
    return value

def patch_body(source, operations):
    """Pure transformation: preserve every byte outside the selected ranges."""
    tables._tree(source)
    if not isinstance(operations, list) or not operations:
        raise ValueError('Provide a nonempty operations list')
    body, changes = source, []
    for op in operations:
        if not isinstance(op, dict):
            raise ValueError('Each operation must be an object')
        kind = op.get('op')
        if kind == 'replace':
            old, new = op.get('before'), op.get('after')
            if not isinstance(old, str) or not old or body.count(old) != 1:
                raise ValueError('Replace requires exactly one nonempty match')
            fragment(new)
            body = body.replace(old, new, 1)
            changes.append({'op': kind, 'before': old, 'after': new})
        elif kind == 'section':
            headings = list(re.finditer(r'<h([1-6])\b[^>]*>.*?</h\1>', body, re.S))
            direct = [n for n in tables._tree(body) if n.tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')]
            if len(headings) != len(direct):
                raise ValueError('Nested headings are unsupported')
            matches = [i for i, node in enumerate(direct) if tables._text(node) == op.get('heading')]
            if len(matches) != 1:
                raise ValueError('Section heading is missing or ambiguous')
            i = matches[0]
            start, end = headings[i].end(), len(body)
            for heading in headings[i + 1:]:
                if int(heading[1]) <= int(headings[i][1]):
                    end = heading.start()
                    break
            new = fragment(op.get('html'))
            old = body[start:end]
            body = body[:start] + new + body[end:]
            changes.append({'op': kind, 'heading': op['heading'], 'before': old, 'after': new})
        elif kind in ('cell', 'add_row'):
            match, headers, nodes, raw_rows = tables._selected(body, op.get('table_index', 0))
            key_index = selected_column(headers, op.get('key_column'))
            keys = [tables._text(row[key_index]) for row in nodes[1:]]
            if len(set(keys)) != len(keys):
                raise ValueError('Duplicate row keys')
            if kind == 'cell':
                found = [i for i, key in enumerate(keys, 1) if key == op.get('key')]
                if len(found) != 1:
                    raise ValueError('Row key is missing or ambiguous')
                ci = selected_column(headers, op.get('column'))
                row = raw_rows[found[0]]
                cell = list(tables.CELL.finditer(row.group()))[ci]
                if 'html' in op and 'value' in op:
                    raise ValueError('Choose value or html, not both')
                if 'html' not in op and not isinstance(op.get('value'), str):
                    raise ValueError('Cell value must be a string')
                new = fragment(op['html']) if 'html' in op else html.escape(op['value'])
                old = cell[2]
                start = match.start() + row.start() + cell.start(2)
                end = match.start() + row.start() + cell.end(2)
                body = body[:start] + new + body[end:]
                changes.append({'op': kind, 'key': op['key'], 'column': headers[ci], 'before': old, 'after': new})
            else:
                values = op.get('values')
                if not isinstance(values, dict) or set(values) != set(headers) or not all(isinstance(v, str) for v in values.values()):
                    raise ValueError('New row must provide every exact header')
                if not values[headers[key_index]].strip():
                    raise ValueError('New row key must be nonempty')
                if values[headers[key_index]] in keys:
                    raise ValueError('Row already exists')
                if len(nodes) < 2 or any(cell.tag != 'td' for cell in nodes[-1]):
                    raise ValueError('Append requires an existing data row')
                row = '<tr>' + ''.join('<td>' + html.escape(values[h]) + '</td>' for h in headers) + '</tr>'
                start = match.start() + raw_rows[-1].end()
                body = body[:start] + row + body[start:]
                changes.append({'op': kind, 'before': '', 'after': row})
        else:
            raise ValueError('Supported operations: replace, section, cell, add_row')
        tables._tree(body)
    # New attachments/uploads are outside this tool's scope.
    original = {n.get('{urn:ri}filename') for n in tables._tree(source).iter('{urn:ri}attachment')}
    current = {n.get('{urn:ri}filename') for n in tables._tree(body).iter('{urn:ri}attachment')}
    if not current.issubset(original):
        raise ValueError('New attachment references require a separate publication plan')
    if body == source:
        raise ValueError('No change; nothing to publish')
    return body, changes

def attachments(base, token, pid):
    result, start = [], 0
    while True:
        response = cf.api(base, token, 'GET', f'/rest/api/content/{pid}/child/attachment?expand=version&limit=100&start={start}')
        batch = response.get('results', [])
        result.extend(batch)
        if not response.get('_links', {}).get('next'):
            return sorted((a['id'], a['title'], a['version']['number']) for a in result)
        if not batch:
            raise ValueError('Incomplete attachment pagination')
        start += len(batch)

def bundle_path(root, name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}', name):
        raise ValueError('Invalid bundle name')
    path = root / name
    if path.is_symlink() or path.resolve().parent != root.resolve():
        raise ValueError('Bundle must stay inside review root')
    return path

def prepare(args):
    root = bundle_path(args.root, args.bundle)
    if root.exists():
        raise ValueError('Bundle exists; use a new name, retain previous evidence')
    operations = json.loads(args.patch_file.read_text())
    base, token = cf.resolve_url(None), cf.resolve_token()
    page = cf.resolve_page(base, token, args.page, 'body.storage,version,space,ancestors')
    source = page['body']['storage']['value']
    body, changes = patch_body(source, operations)
    inventory = attachments(base, token, page['id'])
    # Reject unsupported table layouts before the first possible write.
    checks.html_tables(body)
    root.mkdir(parents=True, mode=0o700)
    write(root, 'before.json', page)
    write(root, 'patch.json', operations)
    write(root, 'source.xhtml', source)
    write(root, 'proposed.xhtml', body)
    write(root, 'changes.json', changes)
    pretty = lambda value: re.sub(r'(?<=>)(?=<)', '\n', value).splitlines(True)
    diff = ''.join(difflib.unified_diff(pretty(source), pretty(body), fromfile='before', tofile='after'))
    write(root, 'changes.diff', diff)
    payload = {'id': page['id'], 'type': 'page', 'title': page['title'], 'version': {'number': page['version']['number'] + 1}, 'body': cf.body_payload(body, 'storage')}
    write(root, 'request.json', payload)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        cf.gate(SimpleNamespace(base=base, token=token, apply=False, approved=False), 'PUT', '/rest/api/content/' + page['id'], ['Scoped documentation update'], payload=payload)
    write(root, 'dry-run.txt', log.getvalue())
    files = ['source.xhtml', 'proposed.xhtml', 'patch.json', 'changes.json', 'changes.diff', 'request.json', 'dry-run.txt']
    contract = {'page_id': page['id'], 'title': page['title'], 'space': page['space']['key'], 'base_url': base,
                'expected_version': page['version']['number'], 'target_version': page['version']['number'] + 1,
                'ancestors': [a['id'] for a in page['ancestors']], 'attachments': inventory,
                'files': {name: sha((root / name).read_bytes()) for name in files}}
    write(root, 'contract.json', contract)
    # Stable /latest points to immutable bundles, not overwritten reviewed files.
    args.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = args.root / '.latest.tmp'
    temporary.write_text(args.bundle)
    temporary.chmod(0o600)
    temporary.replace(args.root / 'latest')
    print(json.dumps({'bundle': args.bundle, 'changes': changes, 'contract_sha256': sha((root / 'contract.json').read_bytes()), 'remote_writes': False}, ensure_ascii=False, indent=2))

class Hrefs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        href = dict(attrs).get('href')
        if tag == 'a' and href:
            self.items.append(href)
            self.links.append(dict(attrs))

def same_link(wanted, rendered, base_url):
    """Compare targets, retaining fragments, explicit resource IDs and multiplicity."""
    href = rendered['href']
    expected = urlsplit(urljoin(base_url.rstrip('/') + '/', wanted))
    actual = urlsplit(urljoin(base_url.rstrip('/') + '/', href))
    ids = parse_qs(expected.query, keep_blank_values=True).get('pageId', [])
    if expected.fragment != actual.fragment:
        return False
    if expected.path.endswith('/pages/viewpage.action') and len(ids) == 1:
        anchor = '<a ' + ' '.join(f'{k}="{html.escape(v, quote=True)}"' for k, v in rendered.items() if v is not None) + '></a>'
        # Only normalize a page link whose approved target is on this origin.
        approved = '<a href="' + html.escape(wanted, quote=True) + '"></a>'
        if checks.has_page_link(approved, ids[0], base_url=base_url):
            return checks.has_page_link(anchor, ids[0], base_url=base_url)
    # Other links retain the complete URL contract, including query and fragment.
    return expected == actual

def verify(page, contract, body):
    if (page['id'] != contract['page_id'] or page['title'] != contract['title'] or page['version']['number'] != contract['target_version']
            or page['space']['key'] != contract['space'] or [a['id'] for a in page['ancestors']] != contract['ancestors']):
        raise ValueError('Saved page identity/version/hierarchy mismatch')
    if not tables.storage_matches(body, page['body']['storage']['value']):
        raise ValueError('Saved body mismatch; do not repeat PUT')
    if checks.html_tables(body) != checks.html_tables(page['body']['view']['value']):
        raise ValueError('Server-view table mismatch; do not repeat PUT')
    wanted, rendered = Hrefs(), Hrefs()
    wanted.feed(body)
    rendered.feed(page['body']['view']['value'])
    remaining = list(rendered.links)
    for href in wanted.items:
        match = next((i for i, link in enumerate(remaining)
                      if same_link(href, link, contract['base_url'])), None)
        if match is None:
            raise ValueError('Missing rendered href; do not repeat PUT')
        remaining.pop(match)

def apply(args):
    root = bundle_path(args.root, args.bundle)
    if not args.apply or not args.approved:
        raise ValueError('Apply requires explicit --apply --approved for the reviewed plan')
    if sha((root / 'contract.json').read_bytes()) != args.contract_sha256:
        raise ValueError('Approval contract hash changed')
    contract = json.loads((root / 'contract.json').read_text())
    for name, digest in contract['files'].items():
        if name not in {'source.xhtml', 'proposed.xhtml', 'patch.json', 'changes.json', 'changes.diff', 'request.json', 'dry-run.txt'} or sha((root / name).read_bytes()) != digest:
            raise ValueError('Reviewed artifact changed')
    base, token = cf.resolve_url(None), cf.resolve_token()
    if base != contract['base_url']:
        raise ValueError('Endpoint differs from reviewed plan')
    body = (root / 'proposed.xhtml').read_text()
    page = cf.resolve_page(base, token, contract['page_id'], 'body.storage,body.view,version,space,ancestors')
    if (root / 'result.json').exists():
        verify(page, contract, body)
        if attachments(base, token, page['id']) != [tuple(item) for item in contract['attachments']]:
            raise ValueError('Attachment inventory changed since publication')
        print('Already published and verified; no repeated PUT.')
        return
    if (root / 'checkpoints').exists():
        raise ValueError('Partial/unknown previous apply: inspect status read-only; never retry automatically')
    if (page['version']['number'] != contract['expected_version'] or sha(page['body']['storage']['value']) != contract['files']['source.xhtml']
            or page['title'] != contract['title'] or page['space']['key'] != contract['space'] or [a['id'] for a in page['ancestors']] != contract['ancestors']):
        raise ValueError('Concurrent page edit; prepare a fresh scoped plan and review it')
    if attachments(base, token, page['id']) != [tuple(item) for item in contract['attachments']]:
        raise ValueError('Attachment inventory changed')
    write(root, 'approval.json', {'contract_sha256': args.contract_sha256, 'approved': True})
    payload = json.loads((root / 'request.json').read_text())
    if payload != {'id': contract['page_id'], 'type': 'page', 'title': contract['title'], 'version': {'number': contract['target_version']}, 'body': cf.body_payload(body, 'storage')}:
        raise ValueError('Request differs from approved body/identity/version')
    write(root, 'checkpoints/001-in-flight.json', {'page_id': page['id'], 'status': 'in-flight'})
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            response = cf.gate(SimpleNamespace(base=base, token=token, apply=True, approved=True), 'PUT', '/rest/api/content/' + page['id'], ['Apply approved scoped update'], payload=payload)
    except BaseException as error:
        write(root, 'checkpoints/002-unknown.json', {'status': 'outcome-unknown', 'failure_class': type(error).__name__})
        raise
    write(root, 'checkpoints/002-acknowledged.json', {'status': 'updated-unverified', 'response': response})
    write(root, 'applied-request.txt', log.getvalue())
    after = cf.resolve_page(base, token, page['id'], 'body.storage,body.view,version,space,ancestors')
    write(root, 'after.json', after)
    verify(after, contract, body)
    if attachments(base, token, page['id']) != [tuple(item) for item in contract['attachments']]:
        raise ValueError('Attachments changed; do not repeat PUT')
    write(root, 'result.json', {'status': 'verified-complete', 'page_id': page['id'], 'version': contract['target_version'], 'contract_sha256': args.contract_sha256,
                              'url': cf.page_url(after, base), 'coverage': 'Saved storage, server-view tables/hrefs, identity/hierarchy and attachments; no live-browser check'})
    print(f"Published {page['title']} v{contract['target_version']}; verified.")

def status(args):
    root = bundle_path(args.root, args.bundle)
    contract = json.loads((root / 'contract.json').read_text())
    base, token = cf.resolve_url(None), cf.resolve_token()
    if base != contract['base_url']:
        raise ValueError('Endpoint changed')
    page = cf.resolve_page(base, token, contract['page_id'], 'body.storage,body.view,version,space,ancestors')
    print(json.dumps({'live_version': page['version']['number'], 'target_version': contract['target_version'],
                      'target_body_matches': tables.storage_matches((root / 'proposed.xhtml').read_text(), page['body']['storage']['value']),
                      'checkpoints': [p.name for p in (root / 'checkpoints').glob('*.json')], 'remote_writes': False}, indent=2))

def serve(args):
    allowed = {'source.xhtml', 'proposed.xhtml', 'changes.diff', 'changes.json', 'contract.json', 'dry-run.txt'}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = unquote(urlsplit(self.path).path).strip('/')
            parts = path.split('/')
            name = parts[0] if path else 'latest'
            try:
                if name == 'latest':
                    name = (args.root / 'latest').read_text().strip()
                root = bundle_path(args.root, name)
                if len(parts) > 2:
                    raise ValueError('Invalid path')
                file = parts[1] if len(parts) == 2 else ''
                if file:
                    if file not in allowed:
                        raise ValueError('Not allowlisted')
                    data, mime = (root / file).read_bytes(), 'text/plain'
                else:
                    changes = json.loads((root / 'changes.json').read_text())
                    summary = '\n\n'.join(json.dumps(c, ensure_ascii=False, indent=2) for c in changes)
                    page = '<!doctype html><meta charset="utf-8"><title>Review</title><style>body{font:16px/1.6 system-ui;max-width:1100px;margin:32px auto;padding:0 20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Review</h1><p>' + html.escape(name) + '</p><pre>' + html.escape(summary) + '</pre>'
                    page += '<p>' + ' · '.join('<a href="/' + name + '/' + f + '">' + f + '</a>' for f in sorted(allowed)) + '</p><p>Contract: ' + sha((root / 'contract.json').read_bytes()) + '</p>'
                    data, mime = page.encode(), 'text/html'
            except (ValueError, OSError, json.JSONDecodeError):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime + '; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--page', required=True)
    prep.add_argument('--patch-file', type=Path, required=True)
    prep.add_argument('--bundle', required=True)
    push = commands.add_parser('apply')
    push.add_argument('--bundle', required=True)
    push.add_argument('--contract-sha256', required=True)
    push.add_argument('--apply', action='store_true')
    push.add_argument('--approved', action='store_true')
    inspect = commands.add_parser('status')
    inspect.add_argument('--bundle', required=True)
    preview = commands.add_parser('serve')
    preview.add_argument('--port', type=int, default=8792)
    args = parser.parse_args()
    try:
        {'prepare': prepare, 'apply': apply, 'status': status, 'serve': serve}[args.command](args)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'{type(error).__name__}: operation stopped; no automatic write retry.\n')

if __name__ == '__main__':
    main()
