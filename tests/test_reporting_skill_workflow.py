"""Exercise the installed-style helper CLI with independent synthetic inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from reporting_fixtures import AUXILIARY, reporting_bundle
from test_assessment_web import ACTIONS, SUMMARY, TECHNICAL

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / '.agents/skills/ssdlc-assessment-report/scripts/workflow.py'


class TestReportingSkillWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='report skill with spaces ')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bundle = reporting_bundle(self.base / 'data inputs')
        self.out = self.base / 'report outputs'

    def cli(self, *arguments, repo=REPO):
        return subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPT), '--reporting-repo', str(repo), *arguments],
                              cwd=self.base, capture_output=True, text=True, encoding='utf-8')

    def project(self, *, data='data inputs', out='report outputs', title='合成報告'):
        return self.cli('project', '--report-root', data, '--out-dir', out, '--date', '2026-10-02',
                        '--title', title, '--allow-auxiliary-source', AUXILIARY)

    def snapshot(self):
        return {p.relative_to(self.bundle.root).as_posix(): p.read_bytes()
                for p in self.bundle.root.rglob('*') if p.is_file()}

    def test_cli_outside_repo_with_spaces_produces_same_version_four_links(self):
        before = self.snapshot()
        result = self.project(title='合成 $() `literal` 報告')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data['stage'], 'complete')
        self.assertEqual(set(data['outputs']), {'html', 'summary', 'actions', 'technical'})
        for path in data['outputs'].values():
            self.assertTrue(Path(path).is_file())
            self.assertEqual(Path(path).parent, self.out / 'reading')
        self.assertEqual(data['markdown']['output_sha256'], data['html']['markdown_source_sha256'])
        self.assertFalse(data['accepted_record'])
        self.assertEqual(data['sync_state'], 'not_synced')
        self.assertFalse(data['published'])
        for name in data['markdown']['output_sha256']:
            self.assertEqual((self.out / 'markdown' / name).read_bytes(), (self.out / 'reading' / name).read_bytes())
        self.assertEqual(self.snapshot(), before)

    def test_repeat_returns_unchanged_and_equal_hashes(self):
        first = self.project()
        second = self.project()
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertEqual(second.returncode, 0, second.stdout)
        a, b = json.loads(first.stdout), json.loads(second.stdout)
        self.assertEqual(b['markdown']['status'], 'unchanged')
        self.assertEqual(b['html']['status'], 'unchanged')
        self.assertEqual(a['html']['output_sha256'], b['html']['output_sha256'])

    def test_invalid_data_fails_before_outputs_and_keeps_source_bytes(self):
        path = self.bundle.root / 'report-data.json'
        path.write_bytes(path.read_bytes() + b' ')
        before = self.snapshot()
        result = self.project()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['stage'], 'markdown')
        self.assertFalse(self.out.exists())
        self.assertEqual(before, self.snapshot())

    def test_html_failure_reports_partial_and_keeps_existing_output(self):
        reading = self.out / 'reading'
        reading.mkdir(parents=True)
        marker = reading / 'existing.txt'
        marker.write_text('keep existing', encoding='utf-8')
        result = self.project()
        self.assertNotEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual((data['status'], data['stage'], data['html_generated']), ('partial', 'html', False))
        self.assertEqual(len(list((self.out / 'markdown').glob('*.md'))), 3)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'keep existing')
        self.assertEqual(list(reading.glob('*.html')), [])

    def test_explicit_incomplete_reporting_repo_never_falls_back(self):
        wrong = self.base / 'wrong reporting repo'
        wrong.mkdir()
        result = self.cli('resources', repo=wrong)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('缺少共用資源', result.stderr)
        self.assertEqual(list(wrong.iterdir()), [])

    def test_unapproved_auxiliary_cannot_be_authorized_by_data(self):
        result = self.cli('project', '--report-root', 'data inputs', '--out-dir', 'report outputs',
                          '--date', '2026-10-02')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.out.exists())

    def test_report_id_is_taken_from_input_not_pilot(self):
        reporting_bundle(self.base / 'other data', report_id='another-synthetic')
        result = self.project(data='other data', out='other output')
        self.assertEqual(result.returncode, 0, result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data['report_id'], 'another-synthetic')
        self.assertEqual(Path(data['outputs']['html']).name, 'another-synthetic-report.html')

    def test_legacy_render_still_preserves_completed_human_markdown(self):
        legacy = self.base / 'legacy'
        legacy.mkdir()
        names = ('fixture-summary.md', 'fixture-actions.md', 'fixture-technical-review.md')
        for name, body in zip(names, (SUMMARY, ACTIONS, TECHNICAL)):
            (legacy / name).write_text(body, encoding='utf-8')
        before = [(legacy / name).read_bytes() for name in names]
        metadata = legacy / 'fixture-metadata.json'
        metadata.write_text(json.dumps({'target_commit': '1' * 40, 'corpus_digest': '2' * 64,
                           'total_files': 1, 'files': [{'relative_path': 'docs/policy.md', 'content_hash': '3' * 64}]}), encoding='utf-8')
        output = legacy / 'fixture-report.html'
        result = self.cli('render', '--summary', str(legacy / names[0]), '--actions', str(legacy / names[1]),
                          '--technical', str(legacy / names[2]), '--metadata', str(metadata), '--output', str(output))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(output.is_file())
        self.assertEqual([(legacy / name).read_bytes() for name in names], before)


if __name__ == '__main__':
    unittest.main()
