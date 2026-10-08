"""Offline regressions for masked PAT login and private dotfile writes."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
import urllib.error
import warnings
from unittest.mock import Mock, patch

ROOT = Path(os.environ.get('SKILLS_ROOT', Path(__file__).resolve().parents[1] / 'skills'))
SCRIPTS = ROOT / '9to5-confluence-auth/scripts'
spec = importlib.util.spec_from_file_location('access_setup', SCRIPTS / 'access.py')
module = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SCRIPTS))
spec.loader.exec_module(module)
sys.path.pop(0)


class AccessSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / 'release-sync.json'

    def args(self, command='login'):
        return SimpleNamespace(config=self.file, endpoints=None, command=command,
                               service='gitlab', replace=False)

    def test_atomic_private_merge(self):
        module.save(self.file, {}, {'jira_token': 'fixture-old', 'nested': {'keep': True}})
        before = module.load(self.file)
        module.save(self.file, before, {'gitlab_token': 'fixture-new'})
        actual = module.load(self.file)
        self.assertEqual(actual['jira_token'], 'fixture-old')
        self.assertEqual(actual['nested'], {'keep': True})
        self.assertEqual(self.file.stat().st_mode & 0o777, 0o600)

    def test_concurrent_write_rejected(self):
        module.save(self.file, {}, {'keep': 'yes'})
        with self.assertRaises(module.auth.ConfigError):
            module.save(self.file, {}, {'gitlab_token': 'fixture'})
        self.assertEqual(module.load(self.file), {'keep': 'yes'})

    def test_malformed_config_is_preserved(self):
        self.file.write_text('{invalid fixture secret')
        with self.assertRaises(module.auth.ConfigError) as exc:
            module.load(self.file)
        self.assertNotIn('fixture secret', str(exc.exception))
        self.assertEqual(self.file.read_text(), '{invalid fixture secret')

    def test_symlink_write_rejected(self):
        target = self.file.with_name('target.json'); target.write_text('{}')
        self.file.symlink_to(target)
        with self.assertRaises(module.auth.ConfigError):
            module.save(self.file, {}, {'gitlab_token': 'fixture'})
        self.assertEqual(target.read_text(), '{}')

    def test_noninteractive_refuses_token_prompt(self):
        with patch.object(module.sys.stdin, 'isatty', return_value=False):
            with self.assertRaises(module.auth.ConfigError):
                module.terminal()

    def test_working_login_never_prompts(self):
        with patch.object(module, 'resolve', return_value=('https://example.invalid', 'fixture')), \
             patch.object(module, 'check', return_value={'status': 'authenticated', 'verified': True}), \
             patch.object(module.getpass, 'getpass') as prompt:
            result = module.run(self.args())
            prompt.assert_not_called()
            self.assertTrue(result['services']['gitlab']['verified'])
            self.assertFalse(self.file.exists())

    def test_failed_new_token_not_saved_or_printed(self):
        with patch.object(module, 'resolve', return_value=('https://example.invalid', None)), \
             patch.object(module, 'terminal'), \
             patch.object(module.getpass, 'getpass', return_value='fixture-secret'), \
             patch.object(module, 'check', side_effect=[{'status': 'missing-config', 'verified': False},
                                                       {'status': 'unauthenticated', 'verified': False}]):
            result = module.run(self.args())
            self.assertFalse(self.file.exists())
            self.assertNotIn('fixture-secret', json.dumps(result))

    def test_successful_login_saves_service_specific_keys(self):
        with patch.object(module, 'resolve', return_value=('https://example.invalid', None)), \
             patch.object(module, 'terminal'), \
             patch.object(module.getpass, 'getpass', return_value='fixture-secret'), \
             patch.object(module, 'check', side_effect=[{'status': 'missing-config', 'verified': False},
                                                       {'status': 'authenticated', 'verified': True}]):
            result = module.run(self.args())
            self.assertEqual(module.load(self.file), {'gitlab_url': 'https://example.invalid', 'gitlab_token': 'fixture-secret'})
            self.assertNotIn('fixture-secret', json.dumps(result))

    def test_gitlab_does_not_borrow_jira_pat(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(module.auth, 'read_mapping', return_value={'token': 'jira-fixture', 'gitlab_url': 'https://example.invalid'}):
            self.assertEqual(module.resolve('gitlab', self.file), ('https://example.invalid', None))

    def test_forbidden_does_not_prompt(self):
        with patch.object(module, 'resolve', return_value=('https://example.invalid', 'fixture')), \
             patch.object(module, 'check', return_value={'status': 'forbidden', 'verified': False}), \
             patch.object(module.getpass, 'getpass') as prompt:
            module.run(self.args()); prompt.assert_not_called()

    def test_redirect_network_and_invalid_response_do_not_prompt(self):
        for status in ['redirect-blocked', 'network-error', 'invalid-response']:
            with self.subTest(status=status), \
                 patch.object(module, 'resolve', return_value=('https://example.invalid', 'fixture')), \
                 patch.object(module, 'check', return_value={'status': status, 'verified': False}), \
                 patch.object(module.getpass, 'getpass') as prompt:
                module.run(self.args()); prompt.assert_not_called()

    def test_configure_only_missing_keys_and_preserves_credentials(self):
        module.save(self.file, {}, {'jira_token': 'fixture-secret', 'jira_task': 'EX-1'})
        args = self.args('configure'); args.keys = ['jira_task', 'confluence_space']
        with patch.object(module, 'terminal'), patch('builtins.input', return_value='SPACE') as prompt:
            result = module.run(args)
        prompt.assert_called_once()
        self.assertEqual(result['saved_keys'], ['confluence_space'])
        self.assertEqual(module.load(self.file)['jira_token'], 'fixture-secret')
        self.assertEqual(module.load(self.file)['jira_task'], 'EX-1')

    def test_replace_task_preserves_pat(self):
        module.save(self.file, {}, {'jira_token': 'fixture-secret', 'jira_task': 'EX-1'})
        args = self.args('configure'); args.keys = ['jira_task']; args.replace = True
        with patch.object(module, 'terminal'), patch('builtins.input', return_value='EX-2'):
            module.run(args)
        self.assertEqual(module.load(self.file), {'jira_token': 'fixture-secret', 'jira_task': 'EX-2'})

    def test_validate_public_fields(self):
        self.assertEqual(module.validate_public('git_ssh_base', 'ssh://git@example.invalid:22/'),
                         'ssh://git@example.invalid:22')
        for key, value in [('git_ssh_base', 'ssh://git:fixture-secret@example.invalid'),
                           ('git_ssh_base', 'ssh://git@example.invalid:70000'),
                           ('git_ssh_base', 'ssh://git@example.invalid/path'),
                           ('jira_task', 'invalid fixture'), ('confluence_space', 'has spaces')]:
            with self.subTest(key=key, value=value), self.assertRaises(module.auth.ConfigError) as exc:
                module.validate_public(key, value)
            self.assertNotIn('fixture-secret', str(exc.exception))

    def test_echoing_getpass_fallback_aborts_without_saving(self):
        def unsafe(*args):
            warnings.warn('fixture-warning', module.getpass.GetPassWarning)
            return 'fixture-secret'
        with patch.object(module, 'resolve', return_value=('https://example.invalid', None)), \
             patch.object(module, 'terminal'), patch.object(module.getpass, 'getpass', side_effect=unsafe), \
             patch.object(module, 'check', return_value={'status': 'missing-config', 'verified': False}), \
             self.assertRaises(module.getpass.GetPassWarning):
            module.run(self.args())
        self.assertFalse(self.file.exists())

    def transport(self, data):
        response = Mock(status=200)
        response.read.return_value = json.dumps(data).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return Mock(open=Mock(return_value=response))

    def test_service_specific_headers_paths_and_known_identity(self):
        for service, identity, path, header in [
                ('gitlab', {'id': 1}, '/api/v4/user', 'Private-token'),
                ('jira', {'key': 'user'}, '/rest/api/2/myself', 'Authorization')]:
            transport = self.transport(identity)
            with patch.object(module.auth, 'opener', return_value=transport):
                result = module.check(service, 'https://example.invalid', 'fixture-secret')
            request = transport.open.call_args.args[0]
            self.assertTrue(request.full_url.endswith(path))
            self.assertEqual(request.get_header(header),
                             'fixture-secret' if service == 'gitlab' else 'Bearer fixture-secret')
            self.assertTrue(result['verified'])
            self.assertNotIn('fixture-secret', json.dumps(result))

    def test_unknown_identity_cannot_be_authenticated(self):
        for service in ['gitlab', 'jira']:
            with patch.object(module.auth, 'opener', return_value=self.transport({})):
                self.assertFalse(module.check(service, 'https://example.invalid', 'fixture')['verified'])

    def test_http_status_and_redirect_handler(self):
        for service in ['gitlab', 'jira']:
            for code, status in [(401, 'unauthenticated'), (403, 'forbidden'), (302, 'redirect-blocked')]:
                transport = Mock(open=Mock(side_effect=urllib.error.HTTPError(
                    'https://example.invalid', code, 'fixture-secret', {}, io.BytesIO(b'fixture-secret'))))
                with patch.object(module.auth, 'opener', return_value=transport):
                    result = module.check(service, 'https://example.invalid', 'fixture-secret')
                self.assertEqual(result['status'], status)
                self.assertNotIn('fixture-secret', json.dumps(result))
        self.assertIsNone(module.auth.NoRedirect().redirect_request(
            Mock(), Mock(), 302, 'redirect', {}, 'https://other.invalid'))

    def test_empty_pat_is_not_saved(self):
        with patch.object(module, 'resolve', return_value=('https://example.invalid', None)), \
             patch.object(module, 'terminal'), patch.object(module.getpass, 'getpass', return_value=''), \
             patch.object(module, 'check', return_value={'status': 'missing-config', 'verified': False}), \
             self.assertRaises(module.auth.ConfigError):
            module.run(self.args())
        self.assertFalse(self.file.exists())

    def test_jira_legacy_token_fallback_and_service_token_priority(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(module.auth, 'read_mapping', return_value={'token': 'legacy-fixture', 'jira_url': 'https://example.invalid'}):
            self.assertEqual(module.resolve('jira', self.file), ('https://example.invalid', 'legacy-fixture'))
            module.save(self.file, {}, {'jira_token': 'new-fixture'})
            self.assertEqual(module.resolve('jira', self.file), ('https://example.invalid', 'new-fixture'))

    def test_cli_missing_config_no_network_no_secret_output(self):
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': self.temp.name}, clear=True):
            result = subprocess.run([sys.executable, str(SCRIPTS / 'access.py'), 'status', 'all'],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(set(report['services']), {'confluence', 'jira', 'gitlab'})
        self.assertTrue(all(x['status'] == 'missing-config' for x in report['services'].values()))
        self.assertNotIn('Traceback', result.stderr)

    def test_cli_noninteractive_login_does_not_read_pat(self):
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': self.temp.name}, clear=True):
            result = subprocess.run([sys.executable, str(SCRIPTS / 'access.py'), 'login', 'gitlab'],
                                    input='fixture-secret', capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Interactive terminal required', result.stdout)
        self.assertNotIn('fixture-secret', result.stdout + result.stderr)
        self.assertFalse((Path(self.temp.name) / 'opencode/release-sync.json').exists())


if __name__ == '__main__':
    unittest.main()
