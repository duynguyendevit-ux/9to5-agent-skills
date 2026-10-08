"""Filesystem contract checks for the bundled init template."""
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('SKILLS_ROOT', Path(__file__).resolve().parents[1] / 'skills'))
SCRIPT = ROOT / '9to5-spring-core/scripts/init_core.py'


class CoreInitTests(unittest.TestCase):
    def test_generated_binary_caches_excluded_but_template_dotfiles_retained(self):
        spec = importlib.util.spec_from_file_location('init_core', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ['.gradle', 'build', '.git', '__pycache__', 'node_modules']:
                cache = root / name / 'nested'
                cache.mkdir(parents=True)
                (cache / 'binary.bin').write_bytes(b'\xa0\xff')
            for name in ['.gitignore', '.env.example', 'build.gradle']:
                (root / name).write_text('template')
            self.assertEqual({p.relative_to(root).as_posix() for p in module.template_files(root)},
                             {'.gitignore', '.env.example', 'build.gradle'})

    def run_init(self, target, *extra):
        return subprocess.run(['python3', str(SCRIPT), '--output', str(target),
                               '--service-name', 'example-service', '--starter-version',
                               'fixture-1.0', *extra], capture_output=True, text=True)

    def test_preview_then_generate_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'service'
            self.assertEqual(self.run_init(target).returncode, 0)
            self.assertFalse(target.exists())
            self.assertEqual(self.run_init(target, '--apply').returncode, 0)
            files = {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()}
            self.assertEqual(len(files), 10)
            self.assertIn(b'fixture-1.0', files[Path('gradle.properties')])
            self.assertIn(b'${DB_WRITER_PASSWORD}', files[Path('src/main/resources/application.yml')])
            self.assertNotEqual(self.run_init(target, '--apply').returncode, 0)
            self.assertEqual(files, {p.relative_to(target): p.read_bytes() for p in target.rglob('*') if p.is_file()})

    def test_reject_injection_and_symlink_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / 'service'
            self.assertNotEqual(self.run_init(target, '--service-name', '../outside', '--apply').returncode, 0)
            self.assertFalse(target.exists())
            link = base / 'link'
            link.symlink_to(base, target_is_directory=True)
            self.assertNotEqual(self.run_init(link / 'service', '--apply').returncode, 0)
            self.assertFalse(target.exists())
