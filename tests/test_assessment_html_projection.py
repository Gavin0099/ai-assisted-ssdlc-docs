"""Read-only HTML fidelity and failure fixtures; no assessment quality claims.

Expected counts/states come from independent synthetic fixtures and REPORT-3B.
Escaping examples are independent literal strings, not production algorithms.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
import unittest

from tools.assessment_markdown import MarkdownProjectionError
from tools.generate_assessment_html import generate
from tools.generate_assessment_markdown import generate as markdown_generate
from tools.generate_assessment_web import cells, inline
from tools.report_data_contract import ReportContractError
from reporting_fixtures import AUXILIARY, reporting_bundle

ROOT = Path(__file__).resolve().parents[1]
ALLOW = frozenset({AUXILIARY})


class VisibleText(HTMLParser):
    def __init__(self, value):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.feed(value)

    def handle_data(self, data):
        self.parts.append(data)


class EscapedMarkdownTests(unittest.TestCase):
    def test_literal_escaped_punctuation_and_entities(self):
        value = r'C\# HP\_OCI \`fmt\_helper.h\` &amp; &lt;script&gt;'
        rendered = inline(value)
        self.assertEqual(''.join(VisibleText(rendered).parts), 'C# HP_OCI `fmt_helper.h` & <script>')
        self.assertNotIn('<script>', rendered)
        self.assertNotIn('<code>', rendered)

    def test_escaped_pipe_keeps_column_and_inline_meaning(self):
        row = cells(r'| A\|B | C\# |')
        self.assertEqual(row, [r'A\|B', r'C\#'])
        self.assertEqual(''.join(VisibleText(inline(row[0])).parts), 'A|B')

    def test_encoded_html_is_visible_text_not_markup(self):
        page = inline('&lt;img src=x onerror=alert(1)&gt;')
        self.assertEqual(''.join(VisibleText(page).parts), '<img src=x onerror=alert(1)>')
        self.assertNotIn('<img', page)


class HTMLProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.data = self.base / 'data'
        self.bundle = reporting_bundle(self.data)
        self.md, self.out = self.base / 'markdown', self.base / 'web'
        markdown_generate(self.data, 'review-lifecycle.json', self.md,
                          date='2026-10-02', title='公司 SSDLC Pilot', authorized_auxiliary_sources=ALLOW)

    def generate(self, **kwargs):
        return generate(self.data, 'review-lifecycle.json', self.md, kwargs.pop('out_dir', self.out),
                        date='2026-10-02', title='公司 SSDLC Pilot',
                        authorized_auxiliary_sources=kwargs.pop('allow', ALLOW), **kwargs)

    def test_reviewed_dimensions_actions_and_empty_scope_are_preserved(self):
        result = self.generate()
        page = (self.out / 'synthetic-report-report.html').read_text(encoding='utf-8')
        data = json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>', page, re.S)[1])
        self.assertEqual(len(data['tasks']), 1)
        self.assertEqual({(t['verdict'], t['strength']) for t in data['tasks']}, {('COVERED', 'weak')})
        self.assertEqual(len(data['actions']), 3)
        self.assertEqual(sum(a['group'] == 'A' for a in data['actions']), 2)
        self.assertEqual(sum(a['group'] == 'B' for a in data['actions']), 1)
        self.assertEqual(next(a['priority'] for a in data['actions'] if a['id'] == 'E-05'), 'P1')
        self.assertEqual(data['status'], 'HUMAN REVIEW DRAFT')
        self.assertFalse(data['acceptedRecord'])
        self.assertEqual(data['syncState'], 'not_synced')
        self.assertFalse(result['accepted_record'])
        self.assertFalse(result['published'])
        self.assertIn('1 份文件', page)
        self.assertIn('本次未列', page)
        self.assertEqual(next(a['products'] for a in data['actions'] if a['id'] == 'E-05'), ['未記錄範圍標籤'])
        self.assertIn(AUXILIARY, page)
        self.assertEqual(page.count('<template id="detail-'), 3)
        self.assertEqual(page.count('<div class="detail-field">'), 3 * 8)
        self.assertIn('人工結果尚未接受', page)
        self.assertIn('尚未同步 machine assessment', page)
        self.assertNotRegex(page, r'<(?:script|link)[^>]+(?:src|href)="https?://')
        self.assertIn("connect-src 'none'", page)
        self.assertNotIn('@@', page)

    def test_deterministic_bundle_and_exact_markdown_bytes_no_source_writes(self):
        before = {p.relative_to(self.base).as_posix(): p.read_bytes() for root in (self.data, self.md) for p in root.rglob('*') if p.is_file()}
        first = self.generate()
        second = self.generate()
        self.assertEqual(second['status'], 'unchanged')
        self.assertEqual(first['output_sha256'], second['output_sha256'])
        for path, raw in before.items():
            self.assertEqual((self.base / path).read_bytes(), raw)
        for name in first['markdown_source_sha256']:
            self.assertEqual((self.md / name).read_bytes(), (self.out / name).read_bytes())

    def test_edited_markdown_cannot_be_rendered_under_recorded_identity(self):
        path = self.md / 'synthetic-report-summary.md'
        path.write_bytes(path.read_bytes().replace(b'COVERED 1', b'PARTIAL 1'))
        with self.assertRaisesRegex(ReportContractError, 'digest mismatch'):
            self.generate()
        self.assertFalse(self.out.exists())

    def test_unapproved_auxiliary_source_is_rejected(self):
        with self.assertRaises(ReportContractError):
            self.generate(allow=frozenset())
        self.assertFalse(self.out.exists())

    def test_output_cannot_replace_input(self):
        for target in (self.data, self.md, self.md / 'child', self.base):
            with self.subTest(target=target), self.assertRaisesRegex(MarkdownProjectionError, 'disjoint'):
                self.generate(out_dir=target)

    def test_existing_other_bundle_is_preserved(self):
        self.out.mkdir()
        marker = self.out / 'other.html'
        marker.write_text('existing', encoding='utf-8')
        with self.assertRaises(MarkdownProjectionError):
            self.generate()
        self.assertEqual(marker.read_text(encoding='utf-8'), 'existing')

    def test_relocation_with_broken_relative_source_links_is_rejected(self):
        with self.assertRaisesRegex(MarkdownProjectionError, 'same relative source links'):
            self.generate(out_dir=self.base / 'deeper' / 'web')
        self.assertFalse((self.base / 'deeper').exists())

    def test_literal_title_slots_do_not_become_template_content(self):
        title = 'Literal @@SCRIPT_HASH@@ @@DETAIL_TEMPLATES@@ @@UNKNOWN@@ value'
        md = self.base / 'literal-markdown'
        out = self.base / 'literal-web'
        markdown_generate(self.data, 'review-lifecycle.json', md, date='2026-10-02', title=title,
                          authorized_auxiliary_sources=ALLOW)
        generate(self.data, 'review-lifecycle.json', md, out, date='2026-10-02', title=title,
                 authorized_auxiliary_sources=ALLOW)
        page = (out / 'synthetic-report-report.html').read_text(encoding='utf-8')
        self.assertIn('<title>' + title + ' — 主管摘要</title>', page)
        self.assertEqual(page.count('<template id="detail-e-05">'), 1)


if __name__ == '__main__':
    unittest.main()
