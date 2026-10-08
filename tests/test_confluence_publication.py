"""Offline regressions for semantic publication checks and focused-note contracts."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import unittest


ROOT = Path(os.environ.get("SKILLS_ROOT", Path(__file__).resolve().parents[1] / "skills"))


class PublicationChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "publication_checks", ROOT / "9to5-confluence/scripts/publication_checks.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def linked(self, view, **kwargs):
        return self.module.has_page_link(view, "123", base_url="https://example.invalid/wiki", **kwargs)

    def test_page_id_link_without_optional_resource_attribute(self):
        self.assertTrue(self.linked('<a href="/pages/viewpage.action?pageId=123">Details</a>'))

    def test_absolute_context_path_and_escaped_query(self):
        self.assertTrue(self.linked('<a href="https://example.invalid:443/wiki/pages/viewpage.action?x=1&amp;pageId=123#flow">Details</a>'))

    def test_friendly_route_using_known_target_metadata(self):
        self.assertTrue(self.linked('<a href="/display/ENG/AI+flow">Details</a>', space="ENG", title="AI flow"))
        self.assertTrue(self.linked('<a href="/display/ENG/AI%20flow">Details</a>', space="ENG", title="AI flow"))

    def test_friendly_route_with_resource_id(self):
        self.assertTrue(self.linked('<a href="/display/ENG/AI+flow" data-linked-resource-id="123">Details</a>'))

    def test_resource_id_does_not_override_explicit_wrong_target(self):
        self.assertFalse(self.linked('<a href="/pages/viewpage.action?pageId=456" data-linked-resource-id="123">Details</a>'))
        self.assertFalse(self.linked('<a href="/pages/viewpage.action?pageId=123" data-linked-resource-id="456">Details</a>'))

    def test_external_credentials_and_unsafe_scheme_links_fail(self):
        for href in ("https://other.invalid/pages/viewpage.action?pageId=123",
                     "//other.invalid/pages/viewpage.action?pageId=123",
                     "https://user:fixture@example.invalid/pages/viewpage.action?pageId=123",
                     "javascript:alert(123)", "http://example.invalid/pages/viewpage.action?pageId=123"):
            with self.subTest(href=href):
                self.assertFalse(self.linked(f'<a href="{href}" data-linked-resource-id="123">Details</a>'))

    def test_fragment_empty_missing_and_unresolved_anchors_fail(self):
        for view in ('<a>123</a>', '<a href="">123</a>', '<a href="#123">123</a>',
                     '<a class="unresolved" href="/pages/viewpage.action?pageId=123">Details</a>'):
            with self.subTest(view=view):
                self.assertFalse(self.linked(view))

    def test_duplicate_blank_prefix_and_wrong_endpoint_ids_fail(self):
        for href in ("/pages/viewpage.action?pageId=123&amp;pageId=456",
                     "/pages/viewpage.action?pageId=", "/pages/viewpage.action?pageId=1234",
                     "/download/attachments/123?pageId=123"):
            with self.subTest(href=href):
                self.assertFalse(self.linked(f'<a href="{href}">Details</a>'))

    def test_attachment_type_and_label_only_match_fail(self):
        self.assertFalse(self.linked('<a data-linked-resource-type="attachment" href="/pages/viewpage.action?pageId=123">Details</a>'))
        self.assertFalse(self.linked('<a href="/display/ENG/Other">Page 123 — AI flow</a>', space="ENG", title="AI flow"))
        self.assertFalse(self.linked('<a href="/display/OTHER/AI+flow">Details</a>', space="ENG", title="AI flow"))

    def test_bad_url_is_not_a_false_positive(self):
        self.assertFalse(self.linked('<a href="https://example.invalid:bad/pages/viewpage.action?pageId=123">Details</a>'))

    def test_raster_label_checked_against_approved_source_and_bytes(self):
        source = "sequenceDiagram\nSender->>Auth: userName and password\n"
        image = b"fixture-rendered-image"
        self.assertTrue(self.module.verify_diagram_label(
            "userName", source, image, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
            image_sha256=hashlib.sha256(image).hexdigest()))
        self.assertNotIn("userName", "<ac:image><ri:attachment ri:filename=\"flow.png\"/></ac:image>")

    def test_changed_source_image_or_missing_label_fail(self):
        source, image = "sequenceDiagram\nA->>B: userName\n", b"approved-image"
        hashes = {"source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                  "image_sha256": hashlib.sha256(image).hexdigest()}
        for label, code, data in [("userName", source + "changed", image),
                                  ("userName", source, b"changed-image"),
                                  ("absent-label", source, image), ("", source, image)]:
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.module.verify_diagram_label(label, code, data, **hashes)


class PublicationSkillContractsTests(unittest.TestCase):
    def test_offline_cases_and_metadata(self):
        for name in ["9to5-confluence", "9to5-confluence-doc"]:
            with self.subTest(skill=name):
                skill = ROOT / name
                text = (skill / "SKILL.md").read_text()
                self.assertIn(f"name: {name}\n", text)
                self.assertRegex(text, r'(?m)^\s+version: "\d+\.\d+\.\d+"$')
                self.assertLess(len(text.splitlines()), 500)
                cases = json.loads((skill / "evals/evals.json").read_text())
                self.assertEqual(cases["skill_name"], name)
                ids = [case["id"] for case in cases["evals"]]
                self.assertEqual(len(ids), len(set(ids)))
                for case in cases["evals"]:
                    self.assertIn("Offline simulation only", case["prompt"])
                    self.assertIn("do not run commands", case["prompt"])
                    self.assertEqual(case["files"], [])
                    self.assertTrue(case["expected_output"])
                    self.assertGreaterEqual(len(case["expectations"]), 3)

    def test_changed_reference_links_resolve(self):
        for name in ["9to5-confluence", "9to5-confluence-doc"]:
            files = [ROOT / name / "SKILL.md", *(ROOT / name / "references").glob("*.md")]
            for path in files:
                for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                    if "://" not in target and not target.startswith("#"):
                        self.assertTrue((path.parent / target.split("#", 1)[0]).is_file(), str(path) + ": " + target)


if __name__ == "__main__":
    unittest.main()
