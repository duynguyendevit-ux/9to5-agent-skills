"""Offline source-link construction regressions; no Git or network requests."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(os.environ.get('SKILLS_ROOT',Path(__file__).resolve().parents[1]/'skills'))
spec=importlib.util.spec_from_file_location('source_links',ROOT/'9to5-release-confluence-sync/scripts/source_links.py')
links=importlib.util.module_from_spec(spec);spec.loader.exec_module(links)


class SourceLinksTests(unittest.TestCase):
    def test_one_overall_jira_version_note_without_task_links(self):
        value=links.release_version_note('https://example.invalid/jira/','DEMO','12345','Release_15/01/2030')
        self.assertEqual(value.count('<a '),1)
        self.assertIn('https://example.invalid/jira/projects/DEMO/versions/12345',value)
        self.assertIn('>Release_15/01/2030</a>',value)
        self.assertNotIn('/browse/',value)

    def test_jira_name_escaped_and_untrusted_id_project_rejected(self):
        value=links.release_version_note('https://example.invalid','DEMO',12345,'A & <B>')
        self.assertIn('A &amp; &lt;B&gt;',value)
        for project,id in [('DEMO/other','123'),('demo','123'),('DEMO','123?token=x'),('DEMO','0')]:
            with self.subTest(project=project,id=id),self.assertRaises(ValueError):
                links.release_version_note('https://example.invalid',project,id,'Release')

    def test_jira_note_rejects_credential_bases_and_control_names(self):
        for base,name in [('https://user:fixture@example.invalid','Release'),
                          ('https://example.invalid?token=fixture','Release'),
                          ('https://example.invalid',''),('https://example.invalid','Release\nInjected')]:
            with self.subTest(base=base),self.assertRaises(ValueError):
                links.release_version_note(base,'DEMO','12345',name)

    def test_develop_uses_same_nested_repository(self):
        root,branch=links.source_urls('https://example.invalid','product/platform/worker','develop')
        self.assertEqual(root,'https://example.invalid/product/platform/worker')
        self.assertEqual(branch,root+'/-/tree/develop')

    def test_context_path_and_branch_slash_encoding(self):
        root,branch=links.source_urls('https://example.invalid/gitlab/','group/repo','feature/EX-1')
        self.assertEqual(root,'https://example.invalid/gitlab/group/repo')
        self.assertEqual(branch,root+'/-/tree/feature%2FEX-1')

    def test_runtime_label_does_not_define_repo(self):
        service,branch=links.source_cells('worker-service','https://example.invalid','group/worker-repo','develop')
        self.assertIn('/group/worker-repo"',service)
        self.assertIn('>worker-service</a>',service)
        self.assertIn('/group/worker-repo/-/tree/develop"',branch)

    def test_labels_are_html_escaped(self):
        service,_=links.source_cells('A & <B>','https://example.invalid','group/repo','develop')
        self.assertIn('A &amp; &lt;B&gt;',service)

    def test_token_urls_and_non_web_bases_rejected(self):
        for base in ['ssh://git@example.invalid','https://user:fixture@example.invalid',
                     'https://example.invalid?token=fixture','https://example.invalid#fixture',
                     'https://example.invalid:99999','https://example.invalid/\n']:
            with self.subTest(base=base),self.assertRaises(ValueError):
                links.source_urls(base,'group/repo','develop')

    def test_untrusted_repository_paths_rejected(self):
        for path in ['repo','group/../repo','/group/repo','group/repo?token=x','group/repo/-/tree/develop','group//repo']:
            with self.subTest(path=path),self.assertRaises(ValueError):
                links.source_urls('https://example.invalid',path,'develop')

    def test_bad_branch_names_rejected(self):
        for branch in ['','-develop','has space','a..b','a\\b','a?b','/develop','develop/','a.lock','a@{x']:
            with self.subTest(branch=branch),self.assertRaises(ValueError):
                links.source_urls('https://example.invalid','group/repo',branch)


if __name__=='__main__':
    unittest.main()
