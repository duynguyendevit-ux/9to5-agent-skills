"""Validate metadata and offline review cases for daily Git/GitHub skills."""
import json
import os
from pathlib import Path
import re
import unittest


ROOT = Path(os.environ.get("SKILLS_ROOT", Path(__file__).resolve().parents[1] / "skills"))
SKILLS = (
    "9to5-git-publish", "9to5-github-audit", "9to5-github-settings",
    "9to5-debug-loop", "9to5-code-review", "9to5-handoff",
)


class DailySkillContractsTests(unittest.TestCase):
    def test_metadata_examples_and_size(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                text = (ROOT / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                frontmatter, body = text[4:].split("\n---\n", 1)
                self.assertIn(f"name: {name}\n", frontmatter)
                self.assertRegex(frontmatter, r"(?m)^description: .+")
                self.assertRegex(frontmatter, r'(?m)^\s+version: "\d+\.\d+\.\d+"$')
                self.assertIn("## Example output", body)
                self.assertIn("Illustrative", body)
                self.assertLess(len(text.splitlines()), 500)
                self.assertNotRegex(text, r"(?i)\bots\b|\bc7\b")

    def test_offline_cases_have_unique_ids_and_expectations(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                data = json.loads((ROOT / name / "evals/evals.json").read_text())
                self.assertEqual(name, data["skill_name"])
                self.assertGreaterEqual(len(data["evals"]), 2)
                ids = [case["id"] for case in data["evals"]]
                self.assertEqual(len(ids), len(set(ids)))
                for case in data["evals"]:
                    self.assertIn("Offline simulation only", case["prompt"])
                    self.assertIn("do not run commands", case["prompt"])
                    self.assertTrue(case["expected_output"])
                    self.assertGreaterEqual(len(case["expectations"]), 3)
                    self.assertEqual([], case["files"])

    def test_relative_markdown_links_resolve(self):
        for name in SKILLS:
            with self.subTest(skill=name):
                path = ROOT / name / "SKILL.md"
                targets = re.findall(r"\]\(([^)]+)\)", path.read_text())
                self.assertTrue(targets)
                for target in targets:
                    if "://" not in target and not target.startswith("#"):
                        self.assertTrue((path.parent / target.split("#", 1)[0]).is_file(), target)

    def test_handoff_is_explicitly_user_invoked(self):
        text = (ROOT / "9to5-handoff/SKILL.md").read_text()
        frontmatter = text[4:].split("\n---\n", 1)[0]
        self.assertRegex(frontmatter, r"(?m)^  opencode/autoinvoke: false$")


if __name__ == "__main__":
    unittest.main()
