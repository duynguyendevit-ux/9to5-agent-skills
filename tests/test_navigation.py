"""Offline navigation/catalog contracts; metadata owns the generated index."""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/update_catalog.py'
spec = importlib.util.spec_from_file_location('update_catalog', SCRIPT)
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)

def fixture(root):
    skill = root / 'skills/example-skill'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('---\nname: example-skill\ndescription: Explain a workflow. Use for example tasks.\nmetadata:\n  version: "1.0.0"\n---\n# Example\n')
    (root / 'README.md').write_text('# Title\n\nUser intro\n\n## Skills\n\n| Skill | Version | Purpose |\n| --- | --- | --- |\n| `example-skill` | 0.1.0 | Old description. |\n\n## License\n\nUser footer\n')

class NavigationTests(unittest.TestCase):
    def test_current_catalog_matches_all_skill_frontmatter(self):
        before, after = catalog.updated_readme(ROOT)
        self.assertEqual(before, after, 'Run python3 scripts/update_catalog.py')
        count = len(list((ROOT / 'skills').glob('*/SKILL.md')))
        self.assertEqual(catalog.catalog(ROOT).count('](skills/'), count)

    def test_legacy_table_migration_preserves_other_readme_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            before, after = catalog.updated_readme(root)
            self.assertTrue(after.startswith(before.split('## Skills')[0]))
            self.assertEqual(after.split('## License')[1], before.split('## License')[1])
            self.assertIn('](skills/example-skill/SKILL.md) | 1.0.0 | Explain a workflow.', after)
            (root / 'README.md').write_text(after)
            self.assertEqual(catalog.updated_readme(root), (after, after))

    def test_check_detects_drift_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            before = (root / 'README.md').read_bytes()
            run = subprocess.run([sys.executable, str(SCRIPT), '--root', str(root), '--check'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertEqual((root / 'README.md').read_bytes(), before)

    def test_invalid_metadata_and_ambiguous_markers_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            path = root / 'skills/example-skill/SKILL.md'
            original = path.read_text()
            for body in [original.replace('name: example-skill', 'name: other'),
                         original.replace('version: "1.0.0"', 'version: "bad"'),
                         original.replace('metadata:\n  version: "1.0.0"', 'metadata: null')]:
                path.write_text(body)
                with self.assertRaises(ValueError): catalog.catalog(root)
            path.write_text(original)
            (root / 'README.md').write_text(catalog.START + '\n' + catalog.START + '\n' + catalog.END)
            with self.assertRaises(ValueError): catalog.updated_readme(root)

    def test_root_map_is_short_and_concrete_markdown_links_resolve(self):
        self.assertLess(len((ROOT / 'AGENTS.md').read_text().splitlines()), 70)
        paths = [ROOT / 'AGENTS.md', ROOT / 'README.md', *sorted((ROOT / 'docs').glob('*.md'))]
        for path in paths:
            text = re.sub(r'```.*?```', '', path.read_text(), flags=re.S)
            for target in re.findall(r'\]\(([^\s)]+)\)', text):
                if target.startswith(('http://', 'https://', '#')): continue
                with self.subTest(path=path, target=target):
                    self.assertTrue((path.parent / target.split('#')[0]).is_file())

    def test_history_is_labeled_and_workflow_scopes_are_separate(self):
        self.assertIn('Historical snapshot', (ROOT / 'docs/verification-2026-09-24.md').read_text())
        routes = (ROOT / 'docs/workflows.md').read_text()
        for term in ['overall Jira release-version link', 'Change Jira version', 'Map tasks to services',
                     'Fixed version/tag/image column indexes', 'test_storage_tables.py']:
            self.assertIn(term, routes)
