"""Reader contract tests using a small, independently authored report bundle.

These check faithful presentation and failure boundaries, not assessment quality.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.generate_assessment_web import ReportError, render_bundle


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/generate_assessment_web.py'
HEADER = '**STATUS: HUMAN REVIEW DRAFT** · Report ID: `fixture`\n'
SUMMARY = '# Fixture 摘要\n\n' + HEADER + '''
## 1. 結論
來源版本 `1111111`；本次一題 PARTIAL，執行證據 medium。
## 2. 工程師要處理什麼
[修正單](fixture-actions.md)
## 3. 建議處理順序
先確認來源，再改引用並回查真實紀錄。
## 4. 詳細 NIST 判定
[附錄](fixture-technical-review.md)
'''
ACTIONS = '# Fixture 修正單\n\n' + HEADER + '''
這是相對於草稿的修訂；來源版本 `1111111`。
## A. 文件要修改
| ID | 類型 | 哪裡有問題 | 現在的問題 | 要怎麼改 | 怎樣算改完 |
| --- | --- | --- | --- | --- | --- |
| [E-01](fixture-technical-review.md#e-01) | 引用問題 | ISP 0001 §2 | 引用退役編號 | 對照已核實新編號 | 點開正確文件 |
保留本類的條件說明。
## B. 證據要補
| ID | 類型 | 哪裡有問題 | 現在的問題 | 要怎麼改 | 怎樣算改完 |
| --- | --- | --- | --- | --- | --- |
| [E-02](fixture-technical-review.md#e-02) | 執行證據待補 | PciSd 0007 §2 | 沒有受控引用 | 回查真實 run | 能追到同一版本 |
## C. 改善建議
本次未列。不能靠改善降級。
'''
DETAIL_ONE = '''<a id="e-01"></a>
### E-01 — 引用問題
| 欄位 | 說明 |
| --- | --- |
| 問題編號與性質 | E-01；A；P1；文件引用問題 |
| 文件與位置 | docs/ISP-0001.md §2 |
| 規則依據與效力 | 公司草稿明列現行文件引用要求 |
| 目前哪裡有問題 | 指向退役 ID |
| 要修改或補什麼 | 改成已核實的現行 ID |
| 完成確認方式 | 點開對應文件 |
| 適用條件與待確認事項 | 新編號待文件 owner 核對 |
| 對判定的影響與不能宣稱 | 不因列為 A 就自動改 Task verdict |
'''
DETAIL_TWO = '''<a id="e-02"></a>
### E-02 — 執行證據待補
| 欄位 | 說明 |
| --- | --- |
| 問題編號與性質 | E-02；B；執行證據待補 |
| 文件與位置 | docs/PciSd-0007.md §2 |
| 規則依據與效力 | 公司草稿需要受控測試引用 |
| 目前哪裡有問題 | 未在本次範圍找到引用 |
| 要修改或補什麼 | 回查既有 run，不補造結果 |
| 完成確認方式 | 版本與真實結果可互相追溯 |
| 適用條件與待確認事項 | 外部紀錄待查 |
| 對判定的影響與不能宣稱 | 未找到不能推成從未執行 |
'''
TASK = '''## Task 判定
### PW.4.4 — 文件是否定義元件管理？
**文件覆蓋（coverage_verdict）：** `PARTIAL`
**執行證據（evidence_strength）：** `medium`；另有待補項。
**不能宣稱：** 不代表已核准或已落實。
'''
PROVENANCE = '## 2. 固定範圍與閱讀方法\n\n- 固定 commit：`' + '1' * 40 + '`；來源版本已固定。\nCorpus digest：`' + '2' * 64 + '`  \n'
TECHNICAL = '# Fixture 附錄\n\n' + HEADER + '\n' + PROVENANCE + '\n## 修正依據\n' + DETAIL_ONE + DETAIL_TWO + TASK


class WebReaderContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.paths = [self.base / ('fixture-' + name) for name in ['summary.md', 'actions.md', 'technical-review.md', 'metadata.json']]
        self.output = self.base / 'fixture-report.html'
        self.write(0, SUMMARY)
        self.write(1, ACTIONS)
        self.write(2, TECHNICAL)
        self.write(3, json.dumps({'target_commit': '1' * 40, 'corpus_digest': '2' * 64, 'total_files': 1, 'files': [{'relative_path': 'docs/policy.md', 'content_hash': '3' * 64}]}))

    def write(self, index, text):
        self.paths[index].write_text(text, encoding='utf-8')

    def render(self):
        return render_bundle(*self.paths, self.output)

    def data(self, page):
        return json.loads(re.search(r'<script type="application/json" id="report-data">(.*?)</script>', page, re.S)[1])

    def cli(self):
        command = [sys.executable, '-X', 'utf8', str(SCRIPT)]
        for name, path in zip(['summary', 'actions', 'technical', 'metadata', 'output'], self.paths + [self.output]):
            command.extend(['--' + name, str(path)])
        return subprocess.run(command, capture_output=True, encoding='utf-8')

    def test_render_preserves_independent_verdict_strength_actions_and_limits(self):
        page = self.render()
        data = self.data(page)
        self.assertEqual(data['tasks'], [{'id': 'PW.4.4', 'question': '文件是否定義元件管理？', 'verdict': 'PARTIAL', 'strength': 'medium'}])
        self.assertEqual([(a['id'], a['group'], a['priority']) for a in data['actions']], [('E-01', 'A', 'P1'), ('E-02', 'B', '')])
        self.assertEqual(data['status'], 'HUMAN REVIEW DRAFT')
        self.assertIn('未找到不能推成從未執行', page)
        self.assertIn('這是相對於草稿的修訂', page)
        self.assertIn('保留本類的條件說明', page)
        self.assertIn('不能靠改善降級', page)
        self.assertIn('href="#actions" data-panel="actions"', page)
        self.assertIn('href="#technical" data-panel="technical"', page)

    def test_generation_is_deterministic_offline_and_preserves_sources(self):
        before = [p.read_bytes() for p in self.paths]
        page = self.render()
        self.assertEqual(page, self.render())
        self.assertNotRegex(page, r'<(?:script|link)[^>]+(?:src|href)="https?://')
        self.assertIn("connect-src 'none'", page)
        self.assertIn('script-src \'sha256-', page)
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(self.output.read_text(encoding='utf-8'), page)
        self.assertEqual([p.read_bytes() for p in self.paths], before)
        self.assertEqual(self.data(page)['sourceHashes']['fixture-summary.md'], hashlib.sha256(before[0]).hexdigest())

    def test_report_text_matching_template_slots_remains_literal(self):
        literal = 'LITERAL @@DETAIL_TEMPLATES@@ @@SCRIPT_HASH@@ @@UNRECOGNIZED@@ END'
        self.write(0, SUMMARY + '\n' + literal)
        page = self.render()
        self.assertIn(literal, page)
        self.assertEqual(page.count('<template id="detail-e-01">'), 1)

    def test_zero_actions_is_allowed_without_inventing_findings(self):
        self.write(1, '# 修正單\n' + HEADER + '\n## A. 文件要修改\n本次未列。\n## B. 證據要補\n本次未列。\n## C. 改善建議\n本次未列。\n')
        self.write(2, '# 附錄\n' + HEADER + '\n' + PROVENANCE + '\n' + TASK)
        page = self.render()
        self.assertEqual(self.data(page)['actions'], [])
        self.assertNotIn('class="action-row"', page)
        self.assertIn('本次未列', page)

    def test_mismatched_report_id_or_status_rejected(self):
        for changed in [ACTIONS.replace('`fixture`', '`different`'), ACTIONS.replace('HUMAN REVIEW DRAFT', 'ACCEPTED')]:
            with self.subTest(text=changed[:70]):
                self.write(1, changed)
                with self.assertRaisesRegex(ReportError, 'report-id／STATUS 不一致'):
                    self.render()

    def test_metadata_binding_counts_and_types_rejected(self):
        original = json.loads(self.paths[3].read_text(encoding='utf-8'))
        mutations = [dict(original, target_commit='4' * 40), dict(original, corpus_digest='4' * 64), dict(original, total_files=0), dict(original, total_files=2), dict(original, files=None), dict(original, target_commit=123), []]
        for mutation in mutations:
            with self.subTest(metadata=mutation):
                self.write(3, json.dumps(mutation))
                with self.assertRaises(ReportError):
                    self.render()

    def test_unrelated_history_hashes_cannot_satisfy_metadata_binding(self):
        self.assertEqual(self.cli().returncode, 0)
        original_output = self.output.read_bytes()
        original_metadata = json.loads(self.paths[3].read_text(encoding='utf-8'))
        self.write(2, TECHNICAL + '\n## 3. 歷史來源\n固定 commit：`' + '4' * 40 + '`\nCorpus digest：`' + '5' * 64 + '`\n## 7. 來源指紋\n| history.md | `' + '5' * 64 + '` |\n')
        for key, value in [('target_commit', '4' * 40), ('corpus_digest', '5' * 64)]:
            with self.subTest(key=key):
                self.write(3, json.dumps(dict(original_metadata, **{key: value})))
                sources = [p.read_bytes() for p in self.paths]
                with self.assertRaisesRegex(ReportError, '與 metadata 不相符'):
                    self.render()
                result = self.cli()
                self.assertEqual(result.returncode, 2)
                self.assertIn('與 metadata 不相符', result.stderr)
                self.assertEqual(self.output.read_bytes(), original_output)
                self.assertEqual([p.read_bytes() for p in self.paths], sources)

    def test_legacy_provenance_requires_unique_labeled_scope_values(self):
        scope_line = '- 固定 commit：`' + '1' * 40 + '`；來源版本已固定。\n'
        digest_line = 'Corpus digest：`' + '2' * 64 + '`  \n'
        invalid = [
            TECHNICAL.replace('## 2. 固定範圍與閱讀方法', '## 2. 其他範圍'),
            TECHNICAL + '\n' + PROVENANCE,
            TECHNICAL.replace(scope_line, '1' * 40 + '\n'),
            TECHNICAL.replace(digest_line, '2' * 64 + '\n'),
            TECHNICAL.replace(scope_line, scope_line * 2),
            TECHNICAL.replace(digest_line, digest_line + 'Corpus digest：`bad`\n'),
            TECHNICAL.replace(scope_line, '```\n' + scope_line + '```\n'),
        ]
        for changed in invalid:
            with self.subTest(scope=changed[:200]):
                self.write(2, changed)
                with self.assertRaises(ReportError):
                    self.render()

    def test_labeled_scope_is_authoritative_over_history_and_fingerprints(self):
        self.write(2, TECHNICAL + '\n## 3. 歷史來源\n固定 commit：`' + '4' * 40 + '`\nCorpus digest：`' + '5' * 64 + '`\n## 7. 來源指紋\n| history.md | `' + '5' * 64 + '` |\n')
        page = self.render()
        self.assertEqual(self.data(page)['targetCommit'], '1' * 40)
        self.assertEqual(self.data(page)['corpusDigest'], '2' * 64)
        self.assertIn('4' * 40, page)
        self.assertIn('5' * 64, page)

    def test_duplicate_action_or_detail_rejected(self):
        row = next(line for line in ACTIONS.splitlines() if line.startswith('| [E-01]'))
        self.write(1, ACTIONS.replace(row, row + '\n' + row))
        with self.assertRaisesRegex(ReportError, 'Action ID 重複'):
            self.render()
        self.write(1, ACTIONS)
        self.write(2, TECHNICAL.replace(DETAIL_ONE, DETAIL_ONE + DETAIL_ONE))
        with self.assertRaisesRegex(ReportError, '附錄 Action ID 重複'):
            self.render()

    def test_wrong_column_names_or_column_count_rejected(self):
        for changed in [ACTIONS.replace('哪裡有問題', '來源'), ACTIONS.replace('| 點開正確文件 |', '| 多一欄 | 點開正確文件 |')]:
            with self.subTest(text=changed):
                self.write(1, changed)
                with self.assertRaises(ReportError):
                    self.render()

    def test_missing_or_duplicate_detail_field_rejected(self):
        line = '| 完成確認方式 | 點開對應文件 |\n'
        for replacement in ['', line + line]:
            with self.subTest(replacement=replacement):
                self.write(2, TECHNICAL.replace(line, replacement))
                with self.assertRaises(ReportError):
                    self.render()

    def test_wrong_link_target_missing_anchor_or_orphan_detail_rejected(self):
        for changed in [ACTIONS.replace('fixture-technical-review.md#e-01', 'old-technical.md#e-01'), ACTIONS.replace('#e-01)', '#e-02)')]:
            with self.subTest(link=changed):
                self.write(1, changed)
                with self.assertRaises(ReportError):
                    self.render()
        self.write(1, ACTIONS)
        self.write(2, TECHNICAL.replace('<a id="e-01"></a>', ''))
        with self.assertRaisesRegex(ReportError, '錨點'):
            self.render()
        self.write(2, TECHNICAL)
        self.write(1, ACTIONS.replace(next(line for line in ACTIONS.splitlines() if line.startswith('| [E-02]')), ''))
        with self.assertRaisesRegex(ReportError, 'Action ID 清單不一致'):
            self.render()

    def test_unknown_or_missing_task_dimension_rejected(self):
        for changed in [TECHNICAL.replace('`PARTIAL`', '`PASS`'), TECHNICAL.replace('`medium`', '`verified`'), TECHNICAL.replace('**執行證據（evidence_strength）：** `medium`；另有待補項。', ''), TECHNICAL + TASK]:
            with self.subTest(text=changed[-200:]):
                self.write(2, changed)
                with self.assertRaises(ReportError):
                    self.render()

    def test_raw_html_and_unsafe_links_are_text_not_executable(self):
        hostile = '</script><script>alert(1)</script><img src=x onerror=alert(2)> [壞連結](javascript:alert) [遠端](//example.invalid/path)'
        self.write(0, SUMMARY + '\n' + hostile)
        self.write(1, ACTIONS.replace('引用退役編號', hostile))
        page = self.render()
        self.assertNotIn('<script>alert(1)', page)
        self.assertNotIn('<img src=x', page)
        self.assertNotIn('href="javascript:', page)
        self.assertNotIn('href="//', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('\\u003c/script\\u003e', page)
        self.assertEqual(self.data(page)['actions'][0]['cells'][3], hostile)


    def test_supported_legacy_priorities_are_preserved(self):
        for priority in ('P0', 'P1', 'P2', 'P3'):
            with self.subTest(priority=priority):
                self.write(2, TECHNICAL.replace('E-01；A；P1；', 'E-01；A；' + priority + '；'))
                page = self.render()
                self.assertEqual(self.data(page)['actions'][0]['priority'], priority)
                self.assertIn('<span class="priority">' + priority + '</span>', page)

    def test_valid_changed_legacy_report_preserves_existing_html(self):
        self.assertEqual(self.cli().returncode, 0)
        first = self.output.read_bytes()
        self.assertEqual(self.cli().returncode, 0)
        self.assertEqual(self.output.read_bytes(), first)
        self.write(0, SUMMARY + '\n合法的新說明。\n')
        sources = [p.read_bytes() for p in self.paths]
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('既有 HTML 內容不同', result.stderr)
        self.assertEqual(self.output.read_bytes(), first)
        self.assertEqual([p.read_bytes() for p in self.paths], sources)
        self.assertEqual(list(self.base.glob('*.tmp')), [])

    def test_legacy_publication_race_cannot_replace_existing_output(self):
        from tools import generate_assessment_web as application
        import os
        original = os.link
        def concurrent_winner(source, destination):
            Path(destination).write_bytes(b'CONCURRENT VERSION')
            return original(source, destination)
        with patch.object(application.os, 'link', concurrent_winner):
            with self.assertRaisesRegex(ReportError, '既有 HTML 內容不同'):
                application.publish_page(self.output, self.render())
        self.assertEqual(self.output.read_bytes(), b'CONCURRENT VERSION')
        self.assertEqual(list(self.base.glob('*.tmp')), [])

    def test_invalid_bundle_cli_keeps_existing_output_and_sources(self):
        self.write(1, ACTIONS.replace('HUMAN REVIEW DRAFT', 'ACCEPTED'))
        before = [p.read_bytes() for p in self.paths]
        self.output.write_text('existing report', encoding='utf-8')
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn('不一致', result.stderr)
        self.assertEqual(self.output.read_text(encoding='utf-8'), 'existing report')
        self.assertEqual([p.read_bytes() for p in self.paths], before)
        self.assertEqual(list(self.base.glob('*.tmp')), [])

    def test_output_must_not_overwrite_input_or_use_non_html_suffix(self):
        for output in [self.paths[0], self.base / 'report.md']:
            with self.subTest(output=output):
                with self.assertRaisesRegex(ReportError, '獨立的 .html'):
                    render_bundle(*self.paths, output)

    def test_inputs_from_different_bundles_rejected(self):
        other = self.base / 'older'
        other.mkdir()
        misplaced = other / self.paths[0].name
        misplaced.write_text(SUMMARY, encoding='utf-8')
        with self.assertRaisesRegex(ReportError, '同一份報告'):
            render_bundle(misplaced, *self.paths[1:], self.output)


if __name__ == '__main__':
    unittest.main()
