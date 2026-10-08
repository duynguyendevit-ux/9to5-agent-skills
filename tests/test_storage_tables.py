"""Offline column geometry, protected-field and serialization regressions."""
import importlib.util
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get('SKILLS_ROOT', Path(__file__).resolve().parents[1] / 'skills'))
spec = importlib.util.spec_from_file_location('storage_tables', ROOT / '9to5-confluence/scripts/storage_tables.py')
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)

def tree(body):
    return ET.fromstring('<root xmlns:ac="urn:ac" xmlns:ri="urn:ri">' + body + '</root>')

def fixture(colgroup=True):
    cols = '<colgroup><col style="width: 20%;" /><col style="width: 30%;" /><col style="width: 50%;" /></colgroup>' if colgroup else ''
    return ('<p>Protected intro</p><table data-layout="wide">' + cols +
            '<tbody><tr><th>Service</th><th>Test</th><th>ENV</th></tr>'
            '<tr><td><p>api</p></td><td class="highlight-#abc" data-highlight-colour="#abc"><p>Passed</p></td>'
            '<td><ac:structured-macro ac:name="code" ac:macro-id="one"><ac:plain-text-body><![CDATA[fixture-private]]></ac:plain-text-body></ac:structured-macro></td></tr>'
            '<tr><td><p>worker</p></td><td><p>Pending</p></td><td><p>Existing</p></td></tr></tbody></table><p>Protected outro</p>')

class StorageTableTests(unittest.TestCase):
    def test_column_added_with_colgroup_and_existing_values_preserved(self):
        body = fixture()
        result = tables.insert_column(body, 'DEV CHECK', 'Test')
        rows = tree(result).findall('.//tr')
        self.assertEqual([''.join(c.itertext()) for c in rows[0]], ['Service', 'Test', 'DEV CHECK', 'ENV'])
        self.assertTrue(all(len(row) == 4 for row in rows))
        self.assertEqual(''.join(rows[1][2].itertext()), '')
        self.assertEqual(rows[1][2].attrib, rows[1][1].attrib)
        self.assertIn('fixture-private', result)
        self.assertEqual([c.get('style') for c in tree(result).findall('.//col')],
                         ['width: 18.4%;', 'width: 27.6%;', 'width: 8%;', 'width: 46%;'])
        self.assertTrue(result.startswith('<p>Protected intro</p>'))
        self.assertTrue(result.endswith('<p>Protected outro</p>'))

    def test_no_colgroup_is_not_invented(self):
        result = tables.insert_column(fixture(False), 'DEV CHECK', 'Test')
        self.assertEqual(tree(result).findall('.//colgroup'), [])

    def test_existing_column_is_noop_and_preserves_its_result(self):
        result = tables.insert_column(fixture(), 'DEV CHECK', 'Test')
        result = tables.replace_cell(result, 'api', 'DEV CHECK', '<p>Verified</p>')
        self.assertEqual(tables.insert_column(result, 'DEV CHECK', 'Test'), result)

    def test_existing_column_elsewhere_is_not_relocated(self):
        result = tables.insert_column(fixture(), 'DEV CHECK', 'Service')
        with self.assertRaises(ValueError): tables.insert_column(result, 'DEV CHECK', 'Test')

    def test_known_missing_colgroup_repaired_before_next_column(self):
        broken = tables.insert_column(fixture(False), 'DEV CHECK', 'Test')
        group = '<colgroup><col style="width: 20%;" /><col style="width: 30%;" /><col style="width: 50%;" /></colgroup>'
        broken = broken.replace('<tbody>', group + '<tbody>')
        with self.assertRaises(ValueError): tables.insert_column(broken, 'Jira task', 'Test')
        repaired = tables.repair_colgroup(broken, 'DEV CHECK')
        self.assertEqual(len(tree(repaired).findall('.//col')), 4)
        self.assertEqual(tables.repair_colgroup(repaired, 'DEV CHECK'), repaired)
        added = tables.insert_column(repaired, 'Jira task', 'Test')
        self.assertEqual(len(tree(added).findall('.//col')), 5)
        self.assertEqual(len(tree(added).findall('.//tr')[0]), 5)

    def test_repair_requires_a_single_missing_named_column(self):
        body = fixture().replace('<col style="width: 30%;" />', '').replace('<col style="width: 50%;" />', '')
        with self.assertRaises(ValueError): tables.repair_colgroup(body, 'Test')
        with self.assertRaises(ValueError): tables.repair_colgroup(fixture(), 'Absent')

    def test_replace_one_cell_preserves_all_other_bytes(self):
        body = fixture()
        result = tables.replace_cell(body, 'api', 'Test', '<p>Reviewed</p>')
        self.assertEqual(result, body.replace('<p>Passed</p>', '<p>Reviewed</p>'))

    def test_duplicate_or_missing_service_and_column_fail(self):
        for body, service, column in [(fixture(), 'absent', 'Test'), (fixture(), 'api', 'Absent'),
                                      (fixture().replace('worker', 'api'), 'api', 'Test')]:
            with self.subTest(service=service, column=column), self.assertRaises(ValueError):
                tables.replace_cell(body, service, column, '<p>new</p>')

    def test_duplicate_headers_and_merged_cells_fail(self):
        for body in [fixture().replace('<th>ENV</th>', '<th>Test</th>'),
                     fixture().replace('<td><p>api', '<td colspan="2"><p>api'),
                     fixture().replace('<td><p>api', '<td rowspan="2"><p>api')]:
            with self.assertRaises(ValueError): tables.insert_column(body, 'DEV CHECK', 'Test')

    def test_multiple_table_selection_preserves_the_other_table(self):
        first = fixture(False)
        result = tables.replace_cell(first + fixture(), 'api', 'Test', '<p>Second</p>', table_index=1)
        self.assertTrue(result.startswith(first))
        for index in [-1, 2, True]:
            with self.assertRaises(ValueError): tables.insert_column(first, 'X', 'Test', table_index=index)

    def test_nested_tables_and_bad_inner_markup_fail(self):
        nested = fixture().replace('<p>Existing</p>', '<table><tr><td>Nested</td></tr></table>')
        with self.assertRaises(ValueError): tables.insert_column(nested, 'X', 'Test')
        with self.assertRaisesRegex(ValueError, 'content withheld'):
            tables.replace_cell(fixture(), 'api', 'Test', '<p>broken')

    def test_column_name_is_escaped(self):
        result = tables.insert_column(fixture(), 'Jira <task>', 'Test')
        self.assertIn('Jira &lt;task&gt;', result)

    def test_invalid_widths_and_styles_fail(self):
        for width in ['NaN', 'Infinity', 'bad', 0, 100, -1]:
            with self.subTest(width=width), self.assertRaises(ValueError):
                tables.insert_column(fixture(), 'X', 'Test', width=width)
        for body in [fixture().replace('width: 20%;', 'width: 20px;'),
                     fixture().replace('width: 20%;', 'width: ..%;'),
                     fixture().replace('width: 20%;', 'width: 20%; color: red;')]:
            with self.assertRaises(ValueError): tables.insert_column(body, 'X', 'Test')

    def test_numeric_formatting_and_tiny_rounding_are_equivalent(self):
        approved = fixture().replace('width: 20%;', 'width: 21.789462%;')
        saved = approved.replace('width: 21.789462%;', 'width: 21.789461%;').replace('width: 30%;', 'width: 30.0%;')
        self.assertTrue(tables.storage_matches(approved, saved))

    def test_real_layout_text_href_and_macro_changes_are_significant(self):
        approved = fixture().replace('<p>Passed</p>', '<p><a href="https://example.invalid/one">Passed</a></p>')
        for saved in [approved.replace('width: 20%;', 'width: 21%;'),
                      approved.replace('fixture-private', 'changed-value'),
                      approved.replace('/one', '/two'), approved.replace('ac:name="code"', 'ac:name="jira"'),
                      approved.replace('highlight-#abc', 'highlight-#def')]:
            with self.subTest(saved_length=len(saved)):
                self.assertFalse(tables.storage_matches(approved, saved))

    def test_macro_ids_may_regenerate_but_other_ids_remain_significant(self):
        self.assertTrue(tables.storage_matches(fixture(), fixture().replace('ac:macro-id="one"', 'ac:macro-id="two"')))
        body = fixture().replace('<p>Protected intro</p>', '<p ac:macro-id="one">Protected intro</p>')
        self.assertFalse(tables.storage_matches(body, body.replace('ac:macro-id="one"', 'ac:macro-id="two"', 1)))

    def test_width_tolerance_is_bounded(self):
        for value in ['NaN', 'Infinity', '-1', '0.01', 'bad']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                tables.storage_matches(fixture(), fixture(), width_tolerance=value)
