"""Offline regressions for write boundaries, selection and evidence preservation.

Run: python3 -m unittest discover -s tests -v
Optional SKILLS_ROOT points to canonical skills before synchronization.
"""
import contextlib
from datetime import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("SKILLS_ROOT", Path(__file__).resolve().parents[1] / "skills"))


def load(skill, script):
    spec = importlib.util.spec_from_file_location(script[:-3], ROOT / skill / "scripts" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConfluenceTests(unittest.TestCase):
    def setUp(self):
        self.module = load("9to5-confluence", "confluence.py")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        body = Path(self.temp.name) / "body.html"
        body.write_text("<p>" + "reviewed content " * 60 + "END-OF-BODY</p>")
        self.args = SimpleNamespace(base="https://example.invalid", token="fixture", page="123",
                                    expected_version=1, body_file=str(body), title=None,
                                    format="storage", apply=True, approved=True)

    def page(self, version):
        return {"id": "123", "title": "Fixture", "version": {"number": version}}

    def test_stale_body_never_sent(self):
        with patch.object(self.module, "resolve_page", return_value=self.page(2)), \
                patch.object(self.module, "api") as api:
            with self.assertRaisesRegex(SystemExit, "page changed"):
                self.module.cmd_update(self.args)
            api.assert_not_called()

    def test_matching_version_and_complete_preview(self):
        output = io.StringIO()
        with patch.object(self.module, "resolve_page", return_value=self.page(1)), \
                patch.object(self.module, "api", return_value={}) as api, \
                contextlib.redirect_stdout(output):
            self.module.cmd_update(self.args)
        self.assertEqual(api.call_args.kwargs["payload"]["version"]["number"], 2)
        self.assertIn("END-OF-BODY", output.getvalue())

    def test_dry_run_does_not_write(self):
        self.args.apply = False
        with patch.object(self.module, "resolve_page", return_value=self.page(1)), \
                patch.object(self.module, "api") as api, contextlib.redirect_stdout(io.StringIO()):
            self.module.cmd_update(self.args)
            api.assert_not_called()

    def test_unapproved_apply_does_not_write(self):
        self.args.approved = False
        with patch.object(self.module, "resolve_page", return_value=self.page(1)), \
                patch.object(self.module, "api") as api, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.module.cmd_update(self.args)
            api.assert_not_called()

    def test_cli_requires_expected_version(self):
        result = subprocess.run(["python3", str(ROOT / "9to5-confluence/scripts/confluence.py"),
                                 "update", "--page", "123", "--body-file", self.args.body_file],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--expected-version", result.stderr)


class ReleaseSyncTests(unittest.TestCase):
    def test_clone_rolls_release_into_current_including_link(self):
        module = load("9to5-release-confluence-sync", "sync_release_tags.py")
        header = '<tr><th>No</th><th>Service</th><th>Current version</th><th>Release Tag</th></tr>'
        release = '<a href="https://example.invalid/repo/-/tags/v1.2.3">v1.2.3</a>'
        for current in ('v1.2.2', ''):
            body = '<table>' + header + '<tr><td>1</td><td>api</td><td>' + current + '</td><td>' + release + '</td></tr></table>'
            actual = module.prepare_copied_release(body)
            self.assertEqual(actual.count(release), 2)
            self.assertEqual(module.prepare_copied_release(actual), actual)
        body = '<table>' + header + '<tr><td>1</td><td>api</td><td>v1.2.2</td><td></td></tr></table>'
        self.assertEqual(module.prepare_copied_release(body), body)

    def test_clone_resets_service_highlights_preserving_tags_and_headers(self):
        module = load("9to5-release-confluence-sync", "sync_release_tags.py")
        header = '<tr><th class="highlight-#abc">No</th><th>Service</th></tr>'
        row = ('<tr data-row="1"><td class="other highlight-#abc" data-highlight-colour="#abc">4</td>'
               '<td class="highlight-#abc">example-api</td>'
               '<td data-highlight-colour="#abc"><a href="/repo/-/tags/v1.2.3">v1.2.3</a></td></tr>')
        body = '<table>' + header + row + '</table>'
        cleaned = module.reset_copied_highlights(body)
        self.assertIn(header, cleaned)
        self.assertIn('class="other"', cleaned)
        self.assertIn('<a href="/repo/-/tags/v1.2.3">v1.2.3</a>', cleaned)
        self.assertNotIn('data-highlight-colour', cleaned)
        self.assertEqual(cleaned.count('highlight-'), 1)
        self.assertEqual(module.reset_copied_highlights(cleaned), cleaned)
        plan = {'template': {'body': {'storage': {'value': body}}}, 'title': 'new', 'parent': '10'}
        with patch.object(module, 'api', side_effect=[{'id': '20'}, {'id': '20'}]) as api:
            module.create_page('https://example.invalid', 'fixture', 'SPACE', plan)
        self.assertEqual(api.call_args_list[0].args[4]['body']['storage']['value'], cleaned)
        self.assertEqual(plan['template']['body']['storage']['value'], body)

    def test_stale_page_refuses_put(self):
        module = load("9to5-release-confluence-sync", "sync_release_tags.py")
        page = {"id": "123", "title": "Fixture", "version": {"number": 1}}
        with patch.object(module, "api", return_value={"version": {"number": 2}}) as api:
            with self.assertRaisesRegex(SystemExit, "page changed"):
                module.update_page("https://example.invalid", "fixture", page, "old body")
            self.assertEqual(api.call_count, 1)
            self.assertEqual(api.call_args.args[2], "GET")

    def test_put_keeps_original_version_boundary(self):
        module = load("9to5-release-confluence-sync", "sync_release_tags.py")
        page = {"id": "123", "title": "Fixture", "version": {"number": 4}}
        with patch.object(module, "api", side_effect=[{"version": {"number": 4}}, {}]) as api:
            module.update_page("https://example.invalid", "fixture", page, "reviewed body")
        self.assertEqual(api.call_args.args[2], "PUT")
        self.assertEqual(api.call_args.args[4]["version"]["number"], 5)


class ReleaseAuditTests(unittest.TestCase):
    def setUp(self):
        self.module = load("9to5-release-audit", "release_audit.py")

    def test_duplicate_service_fails_instead_of_losing_evidence(self):
        body = ("<table><tr><th>Service</th><th>Release Tag</th></tr>"
                "<tr><td>svc</td><td>v1</td></tr><tr><td>svc</td><td>v2</td></tr></table>")
        with self.assertRaisesRegex(SystemExit, "duplicate service"):
            self.module.extract_services(body)

    def test_links_survive_closing_anchor(self):
        parser = self.module.TableParser()
        parser.feed('<table><tr><td><a href="/one">one</a> <a href="/two">two</a></td></tr></table>')
        self.assertEqual(parser.tables[0][0][0]["links"], ["/one", "/two"])

    def test_blank_values_are_unknown_and_page_version_is_reported(self):
        old = {"source": {"page_id": "1", "page_version": 1}, "services": {"svc": {"release tag": ""}}}
        new = {"source": {"page_id": "1", "page_version": 2}, "services": {"svc": {"release tag": ""}}}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.module.compare(old, new)
        self.assertIn("UNKNOWN | svc", output.getvalue())
        self.assertIn("SOURCE_CHANGE | page_version: 1 -> 2", output.getvalue())
        self.assertNotIn("UNCHANGED_RECORD", output.getvalue())

    def test_cleared_tag_is_a_change(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.module.compare({"services": {"svc": {"release tag": "v1"}}},
                                {"services": {"svc": {"release tag": ""}}})
        self.assertIn("RECORDED_CHANGE", output.getvalue())


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.module = load("9to5-lib-bump", "lib_versions.py")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.checkouts = {}
        for parent in ("active", "stale"):
            path = Path(self.temp.name) / parent / "service"
            path.mkdir(parents=True)
            (path / "gradle.properties").write_text("LIB_VERSION=old\n")
            self.checkouts[path] = {"versions": {"LIB_VERSION": "old"}, "debug": {}}
        self.libraries = {"libraries": {"LIB_VERSION": {}}, "not_local": {}}

    def run_set(self, only):
        with contextlib.redirect_stdout(io.StringIO()):
            self.module.cmd_set(SimpleNamespace(property="LIB_VERSION", version="new", only=only,
                                                apply=True), self.checkouts, self.libraries)

    def test_ambiguous_and_empty_selection_refuse_all_writes(self):
        for selector in (None, "service", "", ","):
            with self.subTest(selector=selector), self.assertRaises(SystemExit):
                self.run_set(selector)
        for path in self.checkouts:
            self.assertEqual((path / "gradle.properties").read_text(), "LIB_VERSION=old\n")

    def test_path_selection_changes_only_intended_checkout(self):
        active, stale = self.checkouts
        self.run_set(str(active))
        self.assertEqual((active / "gradle.properties").read_text(), "LIB_VERSION=new\n")
        self.assertEqual((stale / "gradle.properties").read_text(), "LIB_VERSION=old\n")


class WorklogTests(unittest.TestCase):
    def test_duration_conversion(self):
        module = load("9to5-logwork", "duration_seconds.py")
        for value, expected in [("8", 28800), ("1.5h", 5400), ("1h30m", 5400), ("90m", 5400)]:
            with self.subTest(value=value):
                self.assertEqual(module.duration_seconds(value), expected)
        for value in ("0", "", "-1h", "NaN", "1h garbage", "0.00001h"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.duration_seconds(value)

    def test_resumed_codex_session_filters_local_record_date(self):
        module = load("9to5-logwork", "agent_activity.py")
        self.addCleanup(time.tzset)
        env = patch.dict(os.environ, {"TZ": "Asia/Ho_Chi_Minh"})
        env.start()
        self.addCleanup(env.stop)
        time.tzset()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "2026/09/22"
            folder.mkdir(parents=True)
            records = [{"type": "session_meta", "payload": {"cwd": "/fixture/project"}}]
            for timestamp, text in [("2026-09-22T16:30:00Z", "day one work"),
                                    ("2026-09-22T17:30:00Z", "day two work")]:
                records.append({"timestamp": timestamp, "type": "response_item", "payload": {
                    "type": "message", "role": "user", "content": [{"text": text}]}})
            (folder / "session.jsonl").write_text("\n".join(map(json.dumps, records)))
            with patch.object(module, "CODEX_DIR", directory):
                one = module.codex_activity(datetime(2026, 9, 22), datetime(2026, 9, 23))
                two = module.codex_activity(datetime(2026, 9, 23), datetime(2026, 9, 24))
            self.assertEqual(one["/fixture/project"]["prompts"], ["day one work"])
            self.assertEqual(two["/fixture/project"]["prompts"], ["day two work"])


class SkillSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("scripts", "config", "canonical", "mirror", "repo"):
            (self.root / name).mkdir()
        self.script = self.root / "scripts/skill_sync.sh"
        shutil.copyfile(ROOT / "9to5-skill-sync/scripts/skill_sync.sh", self.script)
        self.config = {"canonical": str(self.root / "canonical"), "mirrors": [str(self.root / "mirror")],
                       "repo": str(self.root / "repo"), "repo_skills_subdir": "skills",
                       "exclude_always": ["__pycache__", "*.pyc"],
                       "exclude_from_repo": ["endpoints.json", "cache.json", "debug/artifacts/*"],
                       "keep_empty_dirs": []}
        (self.root / "config/paths.json").write_text(json.dumps(self.config))
        for name in ("9to5-fixture", "third-party"):
            path = self.root / "canonical" / name
            path.mkdir()
            (path / "SKILL.md").write_text("fixture")

    def run_sync(self, *args):
        return subprocess.run(["bash", str(self.script), *args], capture_output=True, text=True)

    def test_invalid_scopes_never_copy(self):
        for args in [("--skill",), ("--skill=",), ("--skill", ""), ("--skill", "--apply"),
                     ("--skill", "third-party"), ("--skill=../9to5-fixture",)]:
            with self.subTest(args=args):
                self.assertEqual(self.run_sync("--apply", *args).returncode, 2)
        self.assertEqual(list((self.root / "mirror").iterdir()), [])

    def test_full_mirrors_filtered_repo_and_refresh(self):
        path = self.root / "canonical/9to5-fixture/config"
        path.mkdir()
        endpoint = path / "endpoints.json"
        endpoint.write_text('{"url":"https://example.invalid"}')
        endpoint.chmod(0o600)
        self.assertEqual(self.run_sync("--apply").returncode, 0)
        mirror = self.root / "mirror/9to5-fixture/config/endpoints.json"
        self.assertEqual(mirror.read_bytes(), endpoint.read_bytes())
        self.assertEqual(mirror.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / "repo/skills/9to5-fixture/config/endpoints.json").exists())
        self.assertFalse((self.root / "repo/skills/third-party").exists())
        endpoint.write_text('{"url":"https://changed.example.invalid"}')
        self.assertEqual(self.run_sync("--apply").returncode, 0)
        self.assertEqual(mirror.read_bytes(), endpoint.read_bytes())
        self.assertEqual(self.run_sync("--check").returncode, 0)

    def test_orphan_is_reported_not_deleted_and_apply_fails(self):
        orphan = self.root / "mirror/9to5-orphan"
        orphan.mkdir()
        result = self.run_sync("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("orphan skill", result.stderr)
        self.assertTrue(orphan.exists())


if __name__ == "__main__":
    unittest.main()
