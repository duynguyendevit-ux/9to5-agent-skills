"""Synthetic disclosure-policy tests; no organization-specific values."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(os.environ.get('SKILLS_ROOT', Path(__file__).resolve().parents[1] / 'skills'))
spec = importlib.util.spec_from_file_location('public_export', ROOT / '9to5-skill-sync/scripts/public_export.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicExportTests(unittest.TestCase):
    def test_text_filenames_overrides_omissions_and_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'internal-example.md').write_text('INTERNAL_NAME')
            (root / 'internal-example.md').chmod(0o755)
            (root / 'projects.json').write_text('private inventory')
            (root / 'private.md').write_text('private note')
            policy = {'replacements': [['INTERNAL_NAME', 'Product']],
                      'path_replacements': [['internal-example', 'product']],
                      'overrides': {'9to5-example/projects.json': '{"projects":{}}\n'},
                      'omit': ['9to5-example/private.md'], 'deny_patterns': ['INTERNAL_NAME']}
            module.render(root, policy, namespace='9to5-example')
            self.assertEqual((root / 'product.md').read_text(), 'Product')
            self.assertEqual((root / 'product.md').stat().st_mode & 0o777, 0o755)
            self.assertEqual((root / 'projects.json').read_text(), '{"projects":{}}\n')
            self.assertFalse((root / 'private.md').exists())
            self.assertFalse((root / 'internal-example.md').exists())

    def test_identity_export_preserves_binary_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'image.bin').write_bytes(b'\xff\xa0\x00')
            module.render(root, {})
            self.assertEqual((root / 'image.bin').read_bytes(), b'\xff\xa0\x00')

    def test_explicit_synthetic_override_does_not_read_or_modify_symlink_target(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / 'private.json'
            target.write_text('private inventory')
            root = base / 'stage'
            root.mkdir()
            (root / 'projects.json').symlink_to(target)
            module.render(root, {'overrides': {'9to5-example/projects.json': '{"projects":{}}'}},
                          namespace='9to5-example')
            self.assertEqual(target.read_text(), 'private inventory')
            self.assertFalse((root / 'projects.json').is_symlink())
            self.assertEqual((root / 'projects.json').read_text(), '{"projects":{}}')

    def test_collision_unsafe_path_symlink_and_forbidden_output_leave_input_intact(self):
        for variant in ['collision', 'unsafe', 'symlink', 'forbidden']:
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'one.md').write_text('INTERNAL_NAME')
                policy = {}
                if variant == 'collision':
                    (root / 'two.md').write_text('second')
                    policy = {'path_replacements': [['two.md', 'one.md']]}
                elif variant == 'unsafe':
                    policy = {'path_replacements': [['one.md', '../outside.md']]}
                elif variant == 'symlink':
                    (root / 'link.md').symlink_to(root / 'one.md')
                else:
                    policy = {'deny_patterns': ['INTERNAL_NAME']}
                with self.assertRaises(ValueError): module.render(root, policy)
                self.assertEqual((root / 'one.md').read_text(), 'INTERNAL_NAME')

    def test_check_reports_only_file_paths_and_skips_git_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'one.md').write_text('INTERNAL_NAME')
            (root / '.git').mkdir()
            (root / '.git/config').write_text('INTERNAL_NAME')
            self.assertEqual(module.check(root, {'deny_patterns': ['INTERNAL_NAME']}), ['one.md'])

    def test_missing_policy_does_not_mean_identity_when_explicitly_configured(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(OSError): module.load_policy(Path(directory) / 'absent.json')
        self.assertEqual(module.load_policy(None), {})
