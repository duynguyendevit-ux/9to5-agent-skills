"""Offline auth, safe diagnostics and conditional CLI initialization regressions."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error


ROOT = Path(os.environ.get("SKILLS_ROOT", Path(__file__).resolve().parents[1] / "skills"))


def load(skill, script):
    spec = importlib.util.spec_from_file_location(script[:-3], ROOT / skill / "scripts" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.module = load("9to5-confluence-auth", "auth.py")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root)}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.config, self.overlay = self.module.default_paths()
        self.args = SimpleNamespace(config=None, overlay=None, endpoints=None,
                                    confluence_url=None, check=True, login_if_needed=True)

    def configured(self, token="fixture-pat"):
        self.config.parent.mkdir(parents=True, exist_ok=True)
        self.config.write_text('confluence_url: "https://example.invalid/wiki/"\n'
                               'token: "fixture-jira"\n'
                               f'confluence_token: "{token}" # comment is not part of PAT\n')

    def transport(self, data, status=200):
        response = Mock(status=status)
        response.read.return_value = json.dumps(data).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return Mock(open=Mock(return_value=response))

    def test_xdg_and_separate_confluence_pat(self):
        self.configured("fixture:hash#value")
        url, token, report = self.module.resolve()
        self.assertEqual(url, "https://example.invalid/wiki")
        self.assertEqual(token, "fixture:hash#value")
        self.assertEqual(report["token_source"], "zjira-config:confluence_token")
        self.assertNotIn(token, json.dumps(report))
        self.assertNotIn("example.invalid", json.dumps(report))

    def test_empty_overlay_does_not_mask_valid_fields(self):
        self.configured()
        self.overlay.parent.mkdir(parents=True)
        self.overlay.write_text(json.dumps({"confluence_token": " ", "token": 42}))
        self.assertEqual(self.module.resolve()[1], "fixture-pat")

    def test_overlay_precedes_yaml_and_environment_token(self):
        self.configured()
        self.overlay.parent.mkdir(parents=True)
        self.overlay.write_text(json.dumps({"confluence_token": "fixture-overlay"}))
        with patch.dict(os.environ, {"CONFLUENCE_TOKEN": "fixture-env"}):
            _, token, report = self.module.resolve()
        self.assertEqual(token, "fixture-overlay")
        self.assertEqual(report["token_source"], "release-sync-overlay:confluence_token")

    def test_url_precedence_and_token_fallbacks(self):
        self.configured()
        endpoints = self.root / "endpoints.json"
        endpoints.write_text('{"confluence_url":"https://endpoint.invalid"}')
        env = {"CONFLUENCE_URL": "https://env.invalid"}
        self.assertEqual(self.module.resolve(endpoints_path=endpoints, env=env)[0], "https://env.invalid")
        self.assertEqual(self.module.resolve(endpoints_path=endpoints, env=env,
                                            cli_url="https://cli.invalid")[0], "https://cli.invalid")
        self.assertEqual(self.module.resolve(endpoints_path=endpoints, env={})[0], "https://endpoint.invalid")
        self.config.write_text('token: fixture-jira\n')
        self.assertEqual(self.module.resolve(env={"CONFLUENCE_TOKEN": "fixture-env"})[1], "fixture-jira")
        self.config.unlink()
        self.assertEqual(self.module.resolve(env={"CONFLUENCE_TOKEN": "fixture-env"})[1], "fixture-env")

    def test_unsafe_url_and_multiline_header_are_rejected_safely(self):
        for url in ("https://user:fixture-secret@example.invalid", "file:///etc/config",
                    "https://example.invalid?token=fixture-secret", "https://example.invalid/#x",
                    "https://example.invalid:bad", "https://exa mple.invalid"):
            with self.subTest(url=url), self.assertRaises(self.module.ConfigError) as raised:
                self.module.resolve(cli_url=url)
            self.assertNotIn("fixture-secret", str(raised.exception))
        with self.assertRaises(self.module.ConfigError):
            self.module.resolve(env={"CONFLUENCE_TOKEN": "fixture\nheader"})

    def test_malformed_yaml_and_json_never_echo_values(self):
        self.configured()
        for path, text in ((self.config, 'confluence_token: [fixture-secret'),
                           (self.overlay, '{"token": "fixture-secret"')):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            report = self.module.run(self.args, interactive=True)
            self.assertEqual(report["status"], "config-error")
            self.assertFalse(report["login_needed"])
            self.assertNotIn("fixture-secret", json.dumps(report))
            path.unlink()
            self.configured()

    def test_nonmapping_config_blocks_initialization(self):
        self.config.parent.mkdir(parents=True)
        self.config.write_text('- fixture-secret\n')
        runner = Mock()
        report = self.module.run(self.args, interactive=True, login_runner=runner)
        self.assertEqual(report["status"], "config-error")
        runner.assert_not_called()

    def test_missing_noninteractive_reports_actual_command(self):
        runner = Mock()
        report = self.module.run(self.args, interactive=False, login_runner=runner)
        self.assertEqual(report["status"], "needs-interactive-login")
        self.assertEqual(report["login_command"], "zjira init")
        self.assertFalse(report["login_attempted"])
        runner.assert_not_called()

    def test_check_only_never_initializes(self):
        self.args.login_if_needed = False
        runner = Mock()
        report = self.module.run(self.args, interactive=True, login_runner=runner)
        self.assertEqual(report["status"], "missing-config")
        runner.assert_not_called()

    def test_configured_without_check_is_not_verified(self):
        self.configured()
        self.args.check = self.args.login_if_needed = False
        with patch.object(self.module, "check") as check:
            report = self.module.run(self.args)
        self.assertEqual(report["status"], "configured")
        self.assertFalse(report["verified"])
        check.assert_not_called()

    def test_authenticated_keeps_existing_credentials(self):
        self.configured()
        original = self.config.read_bytes()
        runner = Mock()
        with patch.object(self.module, "opener", return_value=self.transport({"type": "known"})):
            report = self.module.run(self.args, interactive=True, login_runner=runner)
        self.assertTrue(report["verified"])
        runner.assert_not_called()
        self.assertEqual(self.config.read_bytes(), original)

    def test_current_user_check_sends_get_and_withholds_identity(self):
        transport = self.transport({"type": "known", "username": "fixture-person"})
        report = self.module.check("https://example.invalid/wiki", "fixture-pat", transport)
        request = transport.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url, "https://example.invalid/wiki/rest/api/user/current")
        self.assertEqual(request.get_header("Authorization"), "Bearer fixture-pat")
        self.assertNotIn("fixture-person", json.dumps(report))

    def test_401_needs_login_but_403_redirect_and_server_errors_do_not(self):
        for code in (401, 403, 302, 500):
            with self.subTest(code=code):
                transport = Mock(open=Mock(side_effect=urllib.error.HTTPError(
                    "https://example.invalid", code, "fixture-secret", {}, io.BytesIO(b"fixture-secret"))))
                report = self.module.check("https://example.invalid", "fixture-pat", transport)
                self.assertEqual(report["login_needed"], code == 401)
                self.assertFalse(report["verified"])
                self.assertNotIn("fixture-secret", json.dumps(report))

    def test_anonymous_and_unknown_200_are_not_success(self):
        for data, login in (({"type": "anonymous"}, True), ({}, False), ([], False)):
            with self.subTest(data=data):
                report = self.module.check("https://example.invalid", "fixture-pat", self.transport(data))
                self.assertFalse(report["verified"])
                self.assertEqual(report["login_needed"], login)

    def test_forbidden_redirect_and_network_failures_never_initialize(self):
        self.configured()
        for status in ("forbidden", "redirect-blocked", "network-error", "invalid-response"):
            with self.subTest(status=status), patch.object(self.module, "check", return_value={
                    "status": status, "verified": False, "login_needed": False}):
                runner = Mock()
                report = self.module.run(self.args, interactive=True, login_runner=runner)
                self.assertEqual(report["status"], status)
                runner.assert_not_called()

    def test_network_error_and_invalid_response_do_not_trigger_login(self):
        transports = [Mock(open=Mock(side_effect=TimeoutError("fixture-secret"))),
                      self.transport({"type": "known"})]
        transports[1].open.return_value.read.return_value = b"fixture-secret-not-json"
        for transport in transports:
            report = self.module.check("https://example.invalid", "fixture-pat", transport)
            self.assertFalse(report["login_needed"])
            self.assertFalse(report["verified"])
            self.assertNotIn("fixture-secret", json.dumps(report))

    def test_redirect_handler_refuses_forwarding(self):
        self.assertIsNone(self.module.NoRedirect().redirect_request(
            Mock(), Mock(), 302, "redirect", {}, "https://login.invalid"))
        self.assertTrue(any(isinstance(handler, self.module.NoRedirect)
                            for handler in self.module.opener().handlers))

    def test_interactive_login_once_reloads_and_verifies(self):
        def login(command, **kwargs):
            self.assertEqual(command, ["/fixture/zjira", "init"])
            self.assertEqual(kwargs, {"check": False})
            self.configured()
            return SimpleNamespace(returncode=0)
        runner = Mock(side_effect=login)
        with patch.object(self.module.shutil, "which", return_value="/fixture/zjira"), \
                patch.object(self.module, "opener", return_value=self.transport({"type": "known"})):
            report = self.module.run(self.args, interactive=True, login_runner=runner)
        runner.assert_called_once()
        self.assertEqual(report["status"], "authenticated")
        self.assertTrue(report["login_attempted"])

    def test_expired_overlay_does_not_loop_or_claim_login_success(self):
        self.configured()
        self.overlay.parent.mkdir(parents=True)
        self.overlay.write_text('{"confluence_token":"fixture-expired"}')
        runner = Mock(return_value=SimpleNamespace(returncode=0))
        with patch.object(self.module.shutil, "which", return_value="/fixture/zjira"), \
                patch.object(self.module, "check", return_value={
                    "status": "unauthenticated", "verified": False, "login_needed": True}):
            report = self.module.run(self.args, interactive=True, login_runner=runner)
        runner.assert_called_once()
        self.assertEqual(report["status"], "unauthenticated")
        self.assertFalse(report["verified"])
        self.assertEqual(report["token_source"], "release-sync-overlay:confluence_token")

    def test_cli_failure_and_missing_binary_are_not_success(self):
        with patch.object(self.module.shutil, "which", return_value="/fixture/zjira"):
            report = self.module.run(self.args, interactive=True,
                                     login_runner=Mock(return_value=SimpleNamespace(returncode=1)))
        self.assertEqual(report["status"], "login-failed")
        with patch.object(self.module.shutil, "which", return_value=None):
            report = self.module.run(self.args, interactive=True)
        self.assertEqual(report["status"], "cli-missing")

    def test_custom_config_is_not_replaced_by_default_cli_setup(self):
        self.args.config = self.root / "custom.yaml"
        runner = Mock()
        report = self.module.run(self.args, interactive=True, login_runner=runner)
        self.assertEqual(report["status"], "custom-config-login-required")
        runner.assert_not_called()

    def test_cli_safe_exit_for_missing_and_malformed_config(self):
        script = ROOT / "9to5-confluence-auth/scripts/auth.py"
        for malformed in (False, True):
            if malformed:
                self.config.parent.mkdir(parents=True)
                self.config.write_text('token: [fixture-secret')
            result = subprocess.run([sys.executable, str(script), "--check", "--login-if-needed"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            report = json.loads(result.stdout)
            self.assertFalse(report["verified"])
            self.assertNotIn("fixture-secret", result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_rest_helper_uses_shared_resolver_and_safe_transport(self):
        self.configured()
        helper = load("9to5-confluence", "confluence.py")
        with patch.object(helper, "ZJIRA_CONFIG", self.config), \
                patch.object(helper, "SECRETS_PATH", self.overlay), \
                patch.object(helper, "ENDPOINTS_PATH", self.root / "absent.json"):
            self.assertEqual(helper.resolve_token(), "fixture-pat")
            self.assertEqual(helper.resolve_url(None), "https://example.invalid/wiki")
            self.config.write_text('confluence_url: "not-a-valid-url"\nconfluence_token: fixture-pat\n')
            self.assertEqual(helper.resolve_token("https://cli.invalid"), "fixture-pat")
        transport = Mock(open=Mock(side_effect=urllib.error.HTTPError(
            "https://example.invalid", 302, "fixture-secret", {}, io.BytesIO(b"fixture-secret"))))
        with patch.object(helper.AUTH, "opener", return_value=transport), \
                self.assertRaises(SystemExit) as raised:
            helper.api("https://example.invalid", "fixture-pat", "GET", "/rest/api/content")
        self.assertIn("HTTP 302", str(raised.exception))
        self.assertNotIn("fixture-secret", str(raised.exception))

    def test_skills_have_valid_offline_eval_contracts(self):
        for skill in ("9to5-confluence-auth", "9to5-confluence-doc"):
            data = json.loads((ROOT / skill / "evals/evals.json").read_text())
            self.assertEqual(data["skill_name"], skill)
            ids = [case["id"] for case in data["evals"]]
            self.assertEqual(len(ids), len(set(ids)))
            for case in data["evals"]:
                self.assertTrue(case["prompt"].startswith("Offline simulation only"))
                self.assertTrue(case["expected_output"])
                self.assertGreaterEqual(len(case["expectations"]), 3)


if __name__ == "__main__":
    unittest.main()
