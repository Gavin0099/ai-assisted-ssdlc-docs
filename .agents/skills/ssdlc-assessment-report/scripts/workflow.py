"""Locate resources and route fixed structured or legacy report generation.

This helper does not assess, alter source Markdown, or copy competing templates.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


RESOURCES = {
    'rubric': 'docs/specs/s1-assessment-reporting-rubric.md',
    'presentation_contract': 'docs/specs/s1-report-presentation-contract.md',
    'target_manifest_contract': 'docs/specs/s1-target-manifest-spec.md',
    'corpus_assessment_contract': 'docs/specs/s1-corpus-assessment-spec.md',
    'manifest_schema': 'schemas/target-manifest.schema.yaml',
    'summary_template': 'templates/s1-assessment-summary.md',
    'actions_template': 'templates/s1-assessment-actions.md',
    'technical_template': 'templates/s1-assessment-technical-review.md',
    'web_template': 'templates/s1-assessment-web.html',
    'manifest_validator': 'tools/validate_target_manifest.py',
    'corpus_resolver': 'tools/repo_corpus_resolver.py',
    'web_renderer': 'tools/generate_assessment_web.py',
    'report_data_contract': 'docs/specs/s1-minimal-report-data-contract.md',
    'markdown_projection': 'docs/specs/s1-markdown-projection.md',
    'html_projection': 'docs/specs/s1-html-projection.md',
    'markdown_generator': 'tools/generate_assessment_markdown.py',
    'html_generator': 'tools/generate_assessment_html.py',
}


def missing_resources(root: Path) -> list[str]:
    return [relative for relative in RESOURCES.values() if not (root / relative).is_file()]


def reporting_root(explicit: Path | None) -> Path:
    if explicit is not None:
        root = explicit.expanduser().resolve()
        missing = missing_resources(root)
        if missing:
            raise ValueError('指定 reporting repo 缺少共用資源：' + ', '.join(missing))
        return root
    candidates = [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]
    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if not missing_resources(candidate):
            return candidate
    raise ValueError('找不到 ai-assisted-ssdlc-docs 的共用資源；請明示 --reporting-repo。')


def run_stage(root: Path, module: str, arguments: list[str]) -> tuple[int, dict]:
    result = subprocess.run([sys.executable, '-X', 'utf8', '-m', module, *arguments],
                            cwd=root, capture_output=True, text=True, encoding='utf-8', check=False)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return result.returncode or 1, {'error': result.stderr.strip() or result.stdout.strip() or '產出工具沒有回傳 JSON。'}
    if not isinstance(payload, dict):
        return 1, {'error': '產出工具回傳非物件。'}
    if result.returncode or payload.get('status') not in {'created', 'unchanged'}:
        return result.returncode or 1, payload
    return 0, payload


def project(root: Path, args) -> int:
    """Delegate to existing admission/I/O boundaries; do not analyze or accept."""
    data_root = args.report_root.expanduser().resolve()
    output = args.out_dir.expanduser().absolute()
    md, reading = output / 'markdown', output / 'reading'
    common = ['--report-root', str(data_root), '--lifecycle', args.lifecycle,
              '--date', args.date, '--title', args.title]
    for source in args.allow_auxiliary_source:
        common.extend(['--allow-auxiliary-source', source])
    code, markdown = run_stage(root, 'tools.generate_assessment_markdown', [*common, '--out-dir', str(md)])
    if code:
        print(json.dumps({'status': 'failed', 'stage': 'markdown', 'detail': markdown}, ensure_ascii=False))
        return code
    code, html = run_stage(root, 'tools.generate_assessment_html', [*common, '--markdown-dir', str(md), '--out-dir', str(reading)])
    if code:
        print(json.dumps({'status': 'partial', 'stage': 'html', 'markdown': markdown,
                          'detail': html, 'html_generated': False}, ensure_ascii=False))
        return code
    if markdown.get('output_sha256') != html.get('markdown_source_sha256'):
        print(json.dumps({'status': 'failed', 'stage': 'binding', 'error': 'Markdown 與 HTML 來源指紋不一致。'}, ensure_ascii=False))
        return 1
    report_id = html['report_id']
    outputs = {kind: str(reading / (report_id + suffix)) for kind, suffix in (
        ('html', '-report.html'), ('summary', '-summary.md'), ('actions', '-actions.md'), ('technical', '-technical-review.md'))}
    print(json.dumps({'status': 'report_only', 'stage': 'complete', 'report_id': report_id,
                      'outputs': outputs, 'markdown': markdown, 'html': html,
                      'accepted_record': html['accepted_record'], 'sync_state': html['sync_state'],
                      'published': False}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reporting-repo', type=Path, help='Canonical ai-assisted-ssdlc-docs root, not the target SSDLC repository')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('resources', help='Print canonical resource paths without writing files')
    structured = commands.add_parser('project', help='Validate recorded data, then generate three Markdown files and offline HTML')
    structured.add_argument('--report-root', type=Path, required=True)
    structured.add_argument('--lifecycle', default='review-lifecycle.json')
    structured.add_argument('--out-dir', type=Path, required=True, help='separate output parent; creates markdown/ and reading/')
    structured.add_argument('--date', required=True, help='explicit YYYY-MM-DD, never default to today')
    structured.add_argument('--title', default='SSDLC 文件評估')
    structured.add_argument('--allow-auxiliary-source', action='append', default=[])
    renderer = commands.add_parser('render', help='Render a completed human report bundle with the existing renderer')
    for name in ['summary', 'actions', 'technical', 'metadata', 'output']:
        renderer.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = reporting_root(args.reporting_repo)
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    if args.command == 'resources':
        print(json.dumps({'reporting_repo': str(root), 'resources': {key: str(root / relative) for key, relative in RESOURCES.items()}}, ensure_ascii=False, indent=2))
        return 0
    if args.command == 'project':
        try:
            return project(root, args)
        except OSError as exc:
            parser.exit(2, '無法執行共用 projection：' + str(exc) + '\n')
    paths = {name: getattr(args, name).expanduser().resolve() for name in ['summary', 'actions', 'technical', 'metadata', 'output']}
    if paths['output'].parent != paths['summary'].parent:
        parser.exit(2, 'HTML 必須放在三層報告的同一版本目錄，保留原始來源連結。\n')
    command = [sys.executable, '-X', 'utf8', str(root / RESOURCES['web_renderer'])]
    for name in ['summary', 'actions', 'technical', 'metadata', 'output']:
        # Resolve before changing cwd; retain argument boundaries for spaces.
        command.extend(['--' + name, str(paths[name])])
    try:
        return subprocess.run(command, cwd=root, check=False).returncode
    except OSError as exc:
        parser.exit(2, '無法執行共用 renderer：' + str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
