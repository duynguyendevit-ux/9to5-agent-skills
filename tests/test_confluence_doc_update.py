"""Offline scoped edits, approval binding and checkpoint/no-retry regressions."""
import contextlib
import copy
import importlib.util
import io
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(os.environ.get('SKILLS_ROOT', Path(__file__).resolve().parents[1] / 'skills'))

class ScopedUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scripts = ROOT / '9to5-confluence/scripts'
        sys.path.insert(0, str(scripts))
        try:
            spec = importlib.util.spec_from_file_location('doc_update_test', scripts / 'doc_update.py')
            cls.m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.m)
        finally:
            sys.path.pop(0)

    def table(self):
        return '<p>Keep</p><table class="wrapped"><colgroup><col /><col /><col /></colgroup><tbody><tr><th>source</th><th>type</th><th>description</th></tr><tr><td>alarm-service</td><td>service</td><td><p>Old</p></td></tr></tbody></table><p>Tail</p>'

    def cell(self, **kwargs):
        return dict(op='cell', table_index=0, key_column='SOURCE', key='alarm-service', column='Description', value='New & safe', **kwargs)

    def test_cell_preserves_other_bytes_lowercase_headers(self):
        original = self.table()
        body, changes = self.m.patch_body(original, [self.cell()])
        self.assertEqual(body, original.replace('<p>Old</p>', 'New &amp; safe'))
        self.assertEqual(changes[0]['before'], '<p>Old</p>')

    def test_section_preserves_heading_and_following_section(self):
        original = '<p>Start</p><h2>A</h2><p>Old</p><h3>Child</h3><p>X</p><h2>B</h2><p>Tail</p>'
        body, _ = self.m.patch_body(original, [{'op': 'section', 'heading': 'A', 'html': '<p>New</p>'}])
        self.assertEqual(body, '<p>Start</p><h2>A</h2><p>New</p><h2>B</h2><p>Tail</p>')

    def test_ambiguous_or_nested_heading_fails(self):
        for source in ['<h2>A</h2><h2>A</h2>', '<div><h2>A</h2></div>']:
            with self.assertRaises(ValueError):
                self.m.patch_body(source, [{'op': 'section', 'heading': 'A', 'html': '<p>New</p>'}])

    def test_replace_fails_for_multiple_or_empty_matches(self):
        for before in ['', 'Old']:
            with self.assertRaises(ValueError):
                self.m.patch_body('<p>Old Old</p>', [{'op': 'replace', 'before': before, 'after': 'New'}])

    def test_add_row_preserves_existing_rows(self):
        row = {'op': 'add_row', 'key_column': 'source', 'values': {'source': 'shared-lib', 'type': 'lib', 'description': 'Reusable'}}
        body, _ = self.m.patch_body(self.table(), [row])
        added = '<tr><td>shared-lib</td><td>lib</td><td>Reusable</td></tr>'
        self.assertEqual(body.replace(added, ''), self.table())
        with self.assertRaises(ValueError):
            self.m.patch_body(body, [row])

    def test_bad_markup_new_attachment_and_merged_cells_fail(self):
        for new in ['<script>alert(1)</script>', '<SCRIPT>alert(1)</SCRIPT>', '<p onclick="bad()">x</p>', '<a href="javascript:bad()">x</a>', '<a HREF="javascript:bad()">x</a>', '<ac:image><ri:attachment ri:filename="new.svg" /></ac:image>']:
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.m.patch_body('<p>Old</p>', [{'op': 'replace', 'before': '<p>Old</p>', 'after': new}])
        with self.assertRaises(ValueError):
            self.m.patch_body(self.table().replace('<td>service</td>', '<td colspan="2">service</td>'), [self.cell()])

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ['../escape', '/absolute', 'a/b', '..', '']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    self.m.bundle_path(Path(directory), name)

    def scenario(self, directory):
        root = Path(directory) / 'reviews'
        patch_file = Path(directory) / 'patch.json'
        patch_file.write_text(json.dumps([self.cell()]))
        page = {'id': '123', 'type': 'page', 'title': 'Fixture', 'version': {'number': 3}, 'space': {'key': 'EXAMPLE'},
                'ancestors': [{'id': '100'}], 'body': {'storage': {'value': self.table()}, 'view': {'value': self.table()}}}
        return root, patch_file, page

    def prepared(self, root, patch_file):
        self.m.prepare(SimpleNamespace(root=root, bundle='one', patch_file=patch_file, page='123'))
        digest = self.m.sha((root / 'one/contract.json').read_bytes())
        return SimpleNamespace(root=root, bundle='one', contract_sha256=digest, apply=True, approved=True)

    def test_prepare_and_apply_once_then_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            root, patch_file, page = self.scenario(directory)
            state = {'page': page}
            def send(args, method, path, summary, payload):
                self.assertEqual(path, '/rest/api/content/123')
                after = copy.deepcopy(state['page'])
                after['version'] = payload['version']
                after['body'] = {'storage': payload['body']['storage'], 'view': {'value': payload['body']['storage']['value']}}
                state['page'] = after
                return after
            with patch.object(self.m.cf, 'resolve_url', return_value='https://example.invalid'), patch.object(self.m.cf, 'resolve_token', return_value='fixture'), patch.object(self.m.cf, 'resolve_page', side_effect=lambda *a: copy.deepcopy(state['page'])), patch.object(self.m, 'attachments', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                # Dry-run gate must not perform a network call.
                with patch.object(self.m.cf, 'api', side_effect=AssertionError('network write')):
                    args = self.prepared(root, patch_file)
                with patch.object(self.m.cf, 'gate', side_effect=send) as gate:
                    self.m.apply(args)
                    self.m.apply(args)
                    self.assertEqual(gate.call_count, 1)
            self.assertTrue((root / 'one/result.json').exists())
            self.assertEqual((root / 'latest').read_text(), 'one')

    def verify_fixture(self, body, view=None):
        contract = {'page_id': '123', 'title': 'Fixture', 'target_version': 4,
                    'space': 'EXAMPLE', 'ancestors': ['100'], 'base_url': 'https://example.invalid'}
        page = {'id': '123', 'title': 'Fixture', 'version': {'number': 4},
                'space': {'key': 'EXAMPLE'}, 'ancestors': [{'id': '100'}],
                'body': {'storage': {'value': body}, 'view': {'value': body if view is None else view}}}
        return page, contract

    def test_outer_xml_whitespace_is_serialization_only(self):
        for outer in ['\n', '\r\n', ' \t\n']:
            body = '<p>Keep</p><pre> code\n</pre>'
            page, contract = self.verify_fixture(body)
            self.m.verify(page, contract, outer + body + outer)
            self.m.verify(self.verify_fixture(outer + body + outer)[0], contract, body)

    def test_interior_whitespace_and_content_remain_significant(self):
        for approved, saved in [('<p>Keep </p>', '<p>Keep</p>'),
                                ('<pre> code\n</pre>', '<pre>code</pre>'),
                                ('<p>A</p>\n<p>B</p>', '<p>A</p><p>B</p>'),
                                ('<p>Keep</p>', '<p>Changed</p>'),
                                ('<p>Keep</p>\u00a0', '<p>Keep</p>')]:
            page, contract = self.verify_fixture(saved)
            with self.subTest(approved=approved), self.assertRaises(ValueError):
                self.m.verify(page, contract, approved)

    def test_same_origin_page_link_spelling_can_change(self):
        for expected, rendered in [
            ('/pages/viewpage.action?pageId=456', 'https://example.invalid/pages/viewpage.action?pageId=456'),
            ('https://example.invalid/pages/viewpage.action?pageId=456', '/pages/viewpage.action?pageId=456'),
            ('/pages/viewpage.action?pageId=456#section', 'https://example.invalid/pages/viewpage.action?pageId=456#section'),
        ]:
            body = f'<p><a href="{expected}">Link</a></p>'
            page, contract = self.verify_fixture(body, f'<p><a href="{rendered}">Link</a></p>')
            with self.subTest(expected=expected):
                self.m.verify(page, contract, body)

    def test_page_link_rejects_wrong_target_origin_fragment_and_metadata(self):
        body = '<p><a href="/pages/viewpage.action?pageId=456#section">Link</a></p>'
        for attrs in [
            'href="https://other.invalid/pages/viewpage.action?pageId=456#section"',
            'href="https://user@example.invalid/pages/viewpage.action?pageId=456#section"',
            'href="/pages/viewpage.action?pageId=789#section"',
            'href="/pages/viewpage.action?pageId=456#other"',
            'href="/pages/viewpage.action?pageId=456#section" data-linked-resource-id="789"',
            'href="/pages/viewpage.action?pageId=456#section" data-linked-resource-type="attachment"',
            'href="/pages/viewpage.action?pageId=456#section" class="unresolved"',
        ]:
            page, contract = self.verify_fixture(body, '<p><a ' + attrs + '>Link</a></p>')
            with self.subTest(attrs=attrs), self.assertRaises(ValueError):
                self.m.verify(page, contract, body)

    def test_duplicate_links_cannot_share_one_rendered_occurrence(self):
        link = '<a href="/pages/viewpage.action?pageId=456">Link</a>'
        body = '<p>' + link + link + '</p>'
        page, contract = self.verify_fixture(body, '<p>' + link + '</p>')
        with self.assertRaises(ValueError):
            self.m.verify(page, contract, body)

    def test_other_links_keep_query_fragment_and_external_origin(self):
        for approved, rendered in [
            ('/download/file?version=1', '/download/file?version=2'),
            ('#section', '#other'),
            ('https://external.invalid/doc', 'https://other.invalid/doc'),
        ]:
            body = f'<a href="{approved}">Link</a>'
            page, contract = self.verify_fixture(body, f'<a href="{rendered}">Link</a>')
            with self.subTest(approved=approved), self.assertRaises(ValueError):
                self.m.verify(page, contract, body)

    def test_apply_with_normalized_storage_and_links_is_verified_noop_on_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            root, patch_file, page = self.scenario(directory)
            page['body']['storage']['value'] += '<p><a href="/pages/viewpage.action?pageId=456">Link</a></p>\n'
            def send(args, method, path, summary, payload):
                body = payload['body']['storage']['value'].rstrip('\n')
                page['version'] = payload['version']
                page['body'] = {'storage': {'value': body}, 'view': {'value': body.replace(
                    'href="/pages/', 'href="https://example.invalid/pages/')}}
                return copy.deepcopy(page)
            with patch.object(self.m.cf, 'resolve_url', return_value='https://example.invalid'), patch.object(self.m.cf, 'resolve_token', return_value='fixture'), patch.object(self.m.cf, 'resolve_page', side_effect=lambda *a: copy.deepcopy(page)), patch.object(self.m, 'attachments', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                args = self.prepared(root, patch_file)
                with patch.object(self.m.cf, 'gate', side_effect=send) as gate:
                    self.m.apply(args)
                    self.m.apply(args)
                    self.assertEqual(gate.call_count, 1)
            self.assertTrue((root / 'one/result.json').exists())

    def test_concurrent_version_and_hash_tamper_stop_before_put(self):
        for tamper in ['version', 'artifact', 'approval']:
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as directory:
                root, patch_file, page = self.scenario(directory)
                with patch.object(self.m.cf, 'resolve_url', return_value='https://example.invalid'), patch.object(self.m.cf, 'resolve_token', return_value='fixture'), patch.object(self.m.cf, 'resolve_page', return_value=page), patch.object(self.m, 'attachments', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                    args = self.prepared(root, patch_file)
                    if tamper == 'version':
                        page['version']['number'] = 4
                    elif tamper == 'artifact':
                        (root / 'one/proposed.xhtml').write_text('<p>Changed after review</p>')
                    else:
                        args.approved = False
                    with patch.object(self.m.cf, 'gate') as gate, self.assertRaises(ValueError):
                        self.m.apply(args)
                    gate.assert_not_called()

    def test_unknown_write_outcome_never_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            root, patch_file, page = self.scenario(directory)
            with patch.object(self.m.cf, 'resolve_url', return_value='https://example.invalid'), patch.object(self.m.cf, 'resolve_token', return_value='fixture'), patch.object(self.m.cf, 'resolve_page', return_value=page), patch.object(self.m, 'attachments', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                args = self.prepared(root, patch_file)
                with patch.object(self.m.cf, 'gate', side_effect=TimeoutError) as gate:
                    with self.assertRaises(TimeoutError):
                        self.m.apply(args)
                    with self.assertRaises(ValueError):
                        self.m.apply(args)
                    self.assertEqual(gate.call_count, 1)
            self.assertTrue((root / 'one/checkpoints/002-unknown.json').exists())

    def test_acknowledged_write_survives_failed_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root, patch_file, page = self.scenario(directory)
            def send(*args, **kwargs):
                page['version']['number'] = 4
                return copy.deepcopy(page)
            with patch.object(self.m.cf, 'resolve_url', return_value='https://example.invalid'), patch.object(self.m.cf, 'resolve_token', return_value='fixture'), patch.object(self.m.cf, 'resolve_page', return_value=page), patch.object(self.m, 'attachments', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                args = self.prepared(root, patch_file)
                with patch.object(self.m.cf, 'gate', side_effect=send) as gate:
                    with self.assertRaises(ValueError):
                        self.m.apply(args)
                    with self.assertRaises(ValueError):
                        self.m.apply(args)
                    self.assertEqual(gate.call_count, 1)
            acknowledged = json.loads((root / 'one/checkpoints/002-acknowledged.json').read_text())
            self.assertEqual(acknowledged['status'], 'updated-unverified')
            self.assertFalse((root / 'one/result.json').exists())

    def test_single_server_latest_and_pinned_bundle_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root, patch_file, page = self.scenario(directory)
            with patch.object(self.m.cf, 'resolve_url', return_value='https://example.invalid'), patch.object(self.m.cf, 'resolve_token', return_value='fixture'), patch.object(self.m.cf, 'resolve_page', return_value=page), patch.object(self.m, 'attachments', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
                self.prepared(root, patch_file)
                self.m.prepare(SimpleNamespace(root=root, bundle='two', patch_file=patch_file, page='123'))
            with patch.object(self.m, 'ThreadingHTTPServer') as server_factory:
                self.m.serve(SimpleNamespace(root=root, port=0))
                handler = server_factory.call_args.args[1]
            handler.log_message = lambda *args: None
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(server.server_port)
                with urlopen(base + '/latest') as response:
                    self.assertIn('<p>two</p>', response.read().decode())
                with urlopen(base + '/one') as response:
                    text = response.read().decode()
                    self.assertIn('<p>one</p>', text)
                    self.assertIn('&lt;p&gt;Old&lt;/p&gt;', text)
                with urlopen(base + '/one/proposed.xhtml') as response:
                    self.assertTrue(response.headers['Content-Type'].startswith('text/plain'))
                for path in ['/one/before.json', '/one/../contract.json', '/%2e%2e/contract.json', '/one/checkpoints/001.json']:
                    with self.subTest(path=path), self.assertRaises(HTTPError) as caught:
                        urlopen(base + path)
                    self.assertEqual(caught.exception.code, 404)
                    caught.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

if __name__ == '__main__':
    unittest.main()
