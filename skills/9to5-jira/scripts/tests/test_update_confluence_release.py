import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "update_confluence_release.py"
SPEC = importlib.util.spec_from_file_location("update_confluence_release", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ReleaseScriptTest(unittest.TestCase):
    @staticmethod
    def release_body():
        return "<table><tr><td>1</td><td>svc</td>" + "".join(
            f"<td>old{i}</td>" for i in range(7)
        ) + "</tr></table>"

    def test_select_latest_tag_skips_hotfix_by_default(self):
        tags = ["hotfix-c7-ttch-v0.0.99", "c7-ttch-v0.0.10", "c7-ttch-v0.0.9"]
        self.assertEqual("c7-ttch-v0.0.10", MODULE.select_latest_tag(tags))
        self.assertEqual("hotfix-c7-ttch-v0.0.99", MODULE.select_latest_tag(tags, True))

    def test_parse_columns(self):
        self.assertEqual({0, 1, 2, 5}, MODULE.parse_columns("0-2,5"))
        with self.assertRaises(ValueError):
            MODULE.parse_columns("3-1")

    def test_parse_number_selection(self):
        self.assertEqual([0, 2], MODULE.parse_number_selection("1,3", 3))
        self.assertEqual([0, 1, 2], MODULE.parse_number_selection("a", 3))
        with self.assertRaises(ValueError):
            MODULE.parse_number_selection("4", 3)

    def test_increment_tag(self):
        self.assertEqual("c7-ttdvkh-v0.0.226", MODULE.increment_tag("c7-ttdvkh-v0.0.225"))
        self.assertEqual("c7-ttdvkh-alarm-v0.0.16", MODULE.increment_tag("c7-ttdvkh-alarm-v0.0.15"))
        with self.assertRaises(ValueError):
            MODULE.increment_tag("release")

    def test_service_change_filter(self):
        self.assertTrue(MODULE.service_has_develop_changes(1))
        self.assertFalse(MODULE.service_has_develop_changes(0))
        self.assertFalse(MODULE.service_has_develop_changes(None))

    def test_push_remote_tag_uses_resolved_commit(self):
        release = MODULE.Release(
            "svc",
            "v2",
            "http://git/svc/-/tags/v2",
            "registry/svc:v2",
            Path("/repo"),
            "origin/develop",
        )
        with patch.object(MODULE, "run_git", side_effect=["", "abc refs/tags/v2\n"]) as run_git:
            MODULE.push_remote_tag(release, "a" * 40)
        self.assertEqual(
            (Path("/repo"), "push", "origin", f"{'a' * 40}:refs/tags/v2"),
            run_git.call_args_list[0].args,
        )

    def test_profile_selects_ttdvkh_registry(self):
        args = MODULE.parse_args(["--profile", "c7-ttdvkh", "--dry-run"])
        path = MODULE.resolve_service_config(args)
        self.assertEqual("release-services-ttdvkh.json", path.name)

    def test_interactive_profile_picker(self):
        args = MODULE.parse_args(["--dry-run"])
        output = io.StringIO()
        selected = MODULE.choose_profile(
            args,
            input_fn=lambda _prompt: "2",
            output=output,
            interactive_terminal=True,
        )
        self.assertEqual("c7-ttdvkh", selected)
        self.assertIn("c7-ttch", output.getvalue())
        self.assertIn("c7-ttdvkh", output.getvalue())

    def test_tag_url_infers_profile(self):
        args = MODULE.parse_args(
            [
                "--tag-url",
                "http://git/c7-ttdvkh/ttch/ttch-migration/-/tags/c7-ttdvkh-v0.0.123",
                "--dry-run",
            ]
        )
        self.assertEqual("c7-ttdvkh", MODULE.choose_profile(args, interactive_terminal=False))

    def test_release_from_tag_url(self):
        registry = {
            "ttch-migration": {
                "repo": "/repo",
                "gitlab_project": "c7-ttdvkh/ttch/ttch-migration",
                "docker_image": "registry/migrations-admin",
            }
        }
        url = "http://git/c7-ttdvkh/ttch/ttch-migration/-/tags/c7-ttdvkh-v0.0.123"
        release = MODULE.release_from_tag_url(url, registry)
        self.assertEqual("ttch-migration", release.name)
        self.assertEqual("c7-ttdvkh-v0.0.123", release.tag)
        self.assertEqual("registry/migrations-admin:c7-ttdvkh-v0.0.123", release.docker_image)

    def test_update_row_preserves_current_version_and_other_body(self):
        cells = "".join(f"<td>v{i}</td>" for i in range(9))
        body = f"<p>before</p><table><tr>{cells}</tr><tr><td>1</td><td>svc</td>" + "".join(
            f"<td>old{i}</td>" for i in range(7)
        ) + "</tr></table><p>after</p>"
        release = MODULE.Release("svc", "v2", "http://git/svc/-/tags/v2", "registry/svc:v2")
        updated, current = MODULE.update_release_row(body, release, "#c0b6f2", set(range(9)))
        self.assertEqual("old2", current)
        self.assertIn("<p>before</p>", updated)
        self.assertIn("<p>after</p>", updated)
        MODULE.verify_release_row(updated, release, current, "#c0b6f2", set(range(9)))

    def test_dry_run_never_calls_put(self):
        class Client:
            instances = []

            def __init__(self, *_args, **_kwargs):
                self.requests = []
                self.instances.append(self)

            def get_page(self, page_id):
                return {
                    "id": page_id,
                    "title": "Release",
                    "space": {"key": "SPACE"},
                    "version": {"number": 3},
                    "body": {"storage": {"value": ReleaseScriptTest.release_body()}},
                }

            def request(self, *args, **kwargs):
                self.requests.append((args, kwargs))
                raise AssertionError("dry-run must not call request/PUT")

        with patch.object(MODULE, "ConfluenceClient", Client), patch.object(MODULE, "read_token", return_value="redacted"), redirect_stdout(io.StringIO()):
            result = MODULE.main(
                [
                    "--page-id",
                    "1",
                    "--release",
                    "svc|v2|http://git/svc/-/tags/v2|registry/svc:v2",
                    "--dry-run",
                ]
            )
        self.assertEqual(0, result)
        self.assertEqual([], Client.instances[0].requests)

    def test_page_id_and_display_url_resolution(self):
        class Client:
            def get_page(self, page_id):
                return {"id": page_id}

            def find_page(self, title, space):
                return {"title": title, "space": space}

            def find_daily_page(self, daily_date, services, space):
                return {"date": daily_date, "space": space}

        client = Client()
        self.assertEqual({"id": "123"}, MODULE.resolve_page(client, "https://x/pages/viewpage.action?pageId=123", None, None, "27.07.2026", ["svc"]))
        self.assertEqual(
            {"title": "255. 27.07.2026", "space": "C7GSAFEDA"},
            MODULE.resolve_page(client, "https://x/display/C7GSAFEDA/255.+27.07.2026", None, None, "27.07.2026", ["svc"]),
        )
        self.assertEqual(
            {"date": "27.07.2026", "space": None},
            MODULE.resolve_page(client, None, None, None, "27.07.2026", ["svc"]),
        )


if __name__ == "__main__":
    unittest.main()
