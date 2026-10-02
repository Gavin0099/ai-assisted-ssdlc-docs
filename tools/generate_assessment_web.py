"""Render a linked human assessment bundle as an offline, read-only HTML page.

Legacy mode reads human Markdown. Structured mode receives admitted context and
verified Markdown from the REPORT-4D adapter. Neither assesses company documents,
changes verdicts or projects a machine review queue.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'templates/s1-assessment-web.html'
ACTION_HEADER = ['ID', '類型', '哪裡有問題', '現在的問題', '要怎麼改', '怎樣算改完']
ACTION_FIELDS = ['問題編號與性質', '文件與位置', '規則依據與效力', '目前哪裡有問題', '要修改或補什麼', '完成確認方式', '適用條件與待確認事項', '對判定的影響與不能宣稱']
VERDICTS = {'COVERED', 'PARTIAL', 'MISSING', 'NOT_APPLICABLE', 'UNRESOLVED'}
STRENGTHS = {'strong', 'medium', 'weak'}
TOOL_VERSION = 'report-reader/0.2'


class ReportError(ValueError):
    """The supplied human report bundle cannot be rendered faithfully."""


def cells(line: str) -> list[str]:
    """Split a Markdown table row without splitting escaped/inline-code pipes."""
    parts, current, in_code, escaped = [], [], False, False
    for char in line.strip().strip('|'):
        if escaped:
            current.extend(('\\', char))
            escaped = False
        elif char == '\\':
            escaped = True
        elif char == '`':
            in_code = not in_code
            current.append(char)
        elif char == '|' and not in_code:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if escaped:
        current.append('\\')
    parts.append(''.join(current).strip())
    return parts


def plain(value: str) -> str:
    value = re.sub(r'\[([^]]+)\]\([^)]+\)', r'\1', value)
    value = re.sub(r'<br\s*/?>', ' ', value)
    value = re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]^_`{|}~\\])', r'\1', value)
    return html.unescape(value.replace('**', '').replace('`', ''))


def inline(value: str, technical_name: str = '', report_names: dict[str, str] | None = None) -> str:
    """Escape report text; only emit the small supported Markdown subset."""
    token = re.compile(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]^_`{|}~\\])|`([^`]+)`|\[([^]\n]+)\]\(([^)\n]+)\)|\*\*([^*\n]+)\*\*|<br\s*/?>|(&(?:#[0-9]+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);)')
    result, pos = [], 0
    for m in token.finditer(value):
        result.append(html.escape(value[pos:m.start()]))
        if m.group(1) is not None:
            result.append(html.escape(m.group(1)))
        elif m.group(2) is not None:
            result.append('<code>' + html.escape(m.group(2)) + '</code>')
        elif m.group(3) is not None:
            label, target = m.group(3), m.group(4).strip()
            scheme = urlsplit(target).scheme.lower()
            if scheme not in {'', 'https', 'http'} or target.startswith('//'):
                result.append(html.escape(label))
            else:
                path, _, fragment = target.partition('#')
                action = fragment if re.fullmatch(r'[a-z]+-\d+', fragment) and path in {'', technical_name} else ''
                if action:
                    target = '#' + action
                attrs = f' data-action="{html.escape(action, quote=True)}"' if action else ''
                if not fragment and report_names and path in report_names:
                    target = '#' + report_names[path]
                    attrs = f' data-panel="{report_names[path]}"'
                if scheme:
                    attrs += ' target="_blank" rel="noopener noreferrer"'
                result.append(f'<a href="{html.escape(target, quote=True)}"{attrs}>{html.escape(label)}</a>')
        elif m.group(5) is not None:
            result.append('<strong>' + inline(m.group(5), technical_name, report_names) + '</strong>')
        elif m.group(6) is not None:
            result.append(html.escape(html.unescape(m.group(6))))
        else:
            result.append('<br>')
        pos = m.end()
    result.append(html.escape(value[pos:]))
    return ''.join(result)


def markdown(value: str, technical_name: str = '', report_names: dict[str, str] | None = None) -> str:
    lines, out, i = value.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.startswith('<!--'):
            i += 1
            continue
        if line.startswith('```'):
            content = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                content.append(lines[i])
                i += 1
            out.append('<pre><code>' + html.escape('\n'.join(content)) + '</code></pre>')
            i += 1
            continue
        anchor = re.fullmatch(r'<a id="([a-zA-Z0-9_-]+)"></a>', line.strip())
        if anchor:
            out.append(f'<span id="{anchor.group(1)}" class="source-anchor"></span>')
            i += 1
            continue
        heading = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading:
            level = len(heading.group(1))
            if level != 1:
                out.append(f'<h{level}>' + inline(heading.group(2), technical_name, report_names) + f'</h{level}>')
            i += 1
            continue
        if line.startswith('|') and i + 1 < len(lines) and re.fullmatch(r'[\s|:\-]+', lines[i + 1]):
            header = cells(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                row = cells(lines[i])
                if len(row) != len(header):
                    raise ReportError('技術附錄表格的欄數不一致，請先修正 Markdown。')
                rows.append('<tr>' + ''.join('<td>' + inline(x, technical_name, report_names) + '</td>' for x in row) + '</tr>')
                i += 1
            out.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th scope="col">' + inline(x, technical_name, report_names) + '</th>' for x in header) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>')
            continue
        list_match = re.match(r'^(- |\d+\. )(.*)', line)
        if list_match:
            ordered = not line.startswith('- ')
            tag = 'ol' if ordered else 'ul'
            items = []
            while i < len(lines):
                match = re.match(r'^(\d+\. |\- )(.*)', lines[i])
                if not match or lines[i].startswith('- ') == ordered:
                    break
                items.append('<li>' + inline(match.group(2), technical_name, report_names) + '</li>')
                i += 1
            out.append('<' + tag + '>' + ''.join(items) + '</' + tag + '>')
            continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^(#{1,6} |\| |\||- |\d+\. |```|<a id=)', lines[i]):
            paragraph.append(lines[i])
            i += 1
        out.append('<p>' + inline(' '.join(paragraph), technical_name, report_names) + '</p>')
    return '\n'.join(out)


def status(text: str) -> str:
    match = re.search(r'STATUS:\s*([A-Z][A-Z _-]*?)(?=[`）*·]|$)', text, re.M)
    if not match:
        match = re.search(r'^\*\*(HUMAN REVIEW DRAFT|已接受且與指定 target 同步)｜產出日期 \d{4}-\d{2}-\d{2}\*\*$', text, re.M)
    if not match:
        raise ReportError('每份報告都必須明示 STATUS。')
    return match.group(1).strip()


def report_id(text: str) -> str:
    match = re.search(r'(?:Report ID:|報告識別：)\s*`([^`]+)`', text)
    if not match:
        match = re.search(r'^報告識別 ([A-Za-z0-9._-]+)。', text, re.M)
    if not match:
        raise ReportError('每份報告都必須明示 report-id／報告識別。')
    return match.group(1)


def product_scope(locator: str) -> list[str]:
    result = []
    if 'ISP' in locator or 'HUBISP' in locator or '兩產品' in locator:
        result.append('ISP Tool')
    if 'PciSd' in locator or 'DRVPCISD' in locator or '兩產品' in locator:
        result.append('PciSd')
    if 'CORP' in locator or '公司' in locator or 'docs/SSDLC-' in locator:
        result.append('公司／索引')
    return result or ['未分類']


def parse_actions(text: str, technical: str, technical_name: str = '') -> list[dict]:
    sections = re.split(r'^## ([ABC])\. .*$', text, flags=re.M)
    if sections[1::2] != ['A', 'B', 'C']:
        raise ReportError('工程師修正單須有固定 A／B／C 三節。')
    details = {}
    for m in re.finditer(r'^### ([A-Z]+-\d+)\s+[^\n]*\n(.*?)(?=^### |^## |\Z)', technical, re.M | re.S):
        if m.group(1) in details:
            raise ReportError('附錄 Action ID 重複：' + m.group(1))
        fields = {}
        for line in m.group(2).splitlines():
            if line.startswith('|'):
                row = cells(line)
                if len(row) == 2 and row[0] in ACTION_FIELDS:
                    if row[0] in fields:
                        raise ReportError('Action 附錄欄位重複：' + m.group(1) + ' / ' + row[0])
                    fields[row[0]] = row[1]
        details[m.group(1)] = fields
    result, seen = [], set()
    for group, content in zip(sections[1::2], sections[2::2]):
        table = False
        for line in content.splitlines():
            if line.startswith('|') and cells(line) == ACTION_HEADER:
                table = True
                continue
            if not table and line.startswith('|'):
                raise ReportError('工程師修正單須沿用六個固定欄位名稱及順序。')
            if not table or not line.startswith('|') or re.fullmatch(r'[\s|:\-]+', line):
                continue
            row = cells(line)
            if len(row) != 6:
                raise ReportError('工程師修正單必須恰有六欄。')
            m = re.fullmatch(r'\[([A-Z]+-\d+)\]\(([^#]+)#([a-z]+-\d+)\)', row[0])
            if not m or m.group(1).lower() != m.group(3) or (technical_name and m.group(2) != technical_name):
                raise ReportError('Action ID 須連到相同 ID 的附錄錨點。')
            identifier = m.group(1)
            if identifier in seen:
                raise ReportError('Action ID 重複：' + identifier)
            seen.add(identifier)
            fields = details.get(identifier, {})
            if list(fields) != ACTION_FIELDS:
                raise ReportError('Action 完整依據須保留八欄：' + identifier)
            if len(re.findall(r'<a id="' + re.escape(identifier.lower()) + r'"></a>', technical)) != 1:
                raise ReportError('Action 附錄必須有唯一且相符的錨點：' + identifier)
            priority_match = re.search(r'\bP[0-3]\b', plain(fields['問題編號與性質']))
            priority = priority_match.group(0) if priority_match else ''
            result.append({'id': identifier, 'group': group, 'cells': row, 'fields': fields, 'priority': priority, 'products': product_scope(plain(row[2])), 'search': plain(' '.join(row + list(fields.values())))})
    if set(details) != seen:
        raise ReportError('修正單與附錄的 Action ID 清單不一致。')
    return result


def parse_tasks(technical: str) -> list[dict]:
    tasks = []
    for m in re.finditer(r'^### ([A-Z]{2}\.\d+\.\d+)(?:\s+—\s+([^\n]+))?\n(.*?)(?=^### |^## |\Z)', technical, re.M | re.S):
        block = m.group(3)
        def field(token: str) -> str:
            lines = block.splitlines()
            for index, line in enumerate(lines):
                if not line.startswith('**') or token not in line.split('**', 2)[1]:
                    continue
                if '：**' in line:
                    return plain(line.split('：**', 1)[1].strip())
                if line.endswith('**'):
                    return plain(next((x for x in lines[index + 1:] if x.strip()), ''))
            raise ReportError('Task 欄位缺漏：' + m.group(1) + ' / ' + token)
        verdict = field('coverage_verdict').split('（')[0].strip()
        strength = re.split(r'[；;\s]', field('evidence_strength'))[0]
        if verdict not in VERDICTS or strength not in STRENGTHS:
            raise ReportError('Task 使用非既有 verdict／evidence strength：' + m.group(1))
        tasks.append({'id': m.group(1), 'question': m.group(2) or field('NIST Task Expectation'), 'verdict': verdict, 'strength': strength})
    if not tasks or len({t['id'] for t in tasks}) != len(tasks):
        raise ReportError('附錄須有不重複的 Task 評估紀錄。')
    return tasks


def technical_sections(value: str, filename: str, report_names: dict[str, str]) -> str:
    parts = re.split(r'^## (.+)$', value, flags=re.M)
    out = [markdown(parts[0], filename, report_names)]
    for heading, content in zip(parts[1::2], parts[2::2]):
        out.append('<details class="technical-section"><summary>' + inline(heading) + '</summary><div class="technical-body prose">' + markdown(content, filename, report_names) + '</div></details>')
    return ''.join(out)


def legacy_provenance(technical: str) -> dict[str, str]:
    """Read only the human report's declared scope, never incidental hashes."""
    visible, fenced = [], False
    for line in technical.splitlines():
        if line.startswith('```'):
            fenced = not fenced
        elif not fenced:
            visible.append(line)
    scopes = re.findall(r'^## 2\. 固定範圍與閱讀方法[ \t]*\n(.*?)(?=^## |\Z)',
                        '\n'.join(visible), re.M | re.S)
    if len(scopes) != 1:
        raise ReportError('技術附錄須有唯一的固定範圍與閱讀方法。')
    result = {}
    for label, key, width in [('固定 commit', 'target_commit', 40), ('Corpus digest', 'corpus_digest', 64)]:
        prefix = r'[ \t]*(?:- )?' + re.escape(label) + r'[ \t]*[:：]'
        lines = [line for line in scopes[0].splitlines() if re.match('^' + prefix, line)]
        if len(lines) != 1:
            raise ReportError('固定範圍須有唯一且明確標示的 ' + label + '。')
        match = re.fullmatch(prefix + r'[ \t]*`([0-9a-f]{' + str(width) + r'})`(?:[；;。].*)?[ \t]*', lines[0])
        if not match:
            raise ReportError('固定範圍的 ' + label + ' 格式不合法。')
        result[key] = match.group(1)
    return result


def render_bundle(summary_path: Path, actions_path: Path, technical_path: Path, metadata_path: Path, output: Path, *, projection=None, verified_documents: list[str] | None = None) -> str:
    paths = [p.resolve() for p in [summary_path, actions_path, technical_path, metadata_path]]
    if output.resolve() in paths or output.suffix.lower() != '.html':
        raise ReportError('輸出必須是獨立的 .html，不能覆寫來源報告。')
    if len({p.parent for p in (paths if projection is None else paths[:3])}) != 1:
        raise ReportError('四個來源必須屬於同一份報告的輸出目錄。')
    if projection is not None and (verified_documents is None or len(verified_documents) != 3):
        raise ReportError('結構化投影必須提供已驗證的三份 Markdown。')
    documents = verified_documents if projection is not None else [p.read_text(encoding='utf-8-sig') for p in paths[:3]]
    identifiers, statuses = [report_id(d) for d in documents], [status(d) for d in documents]
    if len(set(identifiers)) != 1 or len(set(statuses)) != 1:
        raise ReportError('三份報告的 report-id／STATUS 不一致。')
    metadata = json.loads(paths[3].read_text(encoding='utf-8-sig')) if projection is None else {
        'target_commit': projection.report_data.corpus.commit,
        'corpus_digest': projection.report_data.corpus.corpus_digest,
        'total_files': len(projection.report_data.corpus.files),
        'files': list(projection.report_data.corpus.files),
    }
    if not isinstance(metadata, dict):
        raise ReportError('metadata 必須是物件。')
    if not isinstance(metadata.get('target_commit'), str) or not isinstance(metadata.get('corpus_digest'), str) or not re.fullmatch(r'[0-9a-f]{40}', metadata['target_commit']) or not re.fullmatch(r'[0-9a-f]{64}', metadata['corpus_digest']):
        raise ReportError('metadata 缺少固定 commit／corpus digest。')
    if type(metadata.get('total_files')) is not int or metadata['total_files'] < 1 or not isinstance(metadata.get('files'), list) or len(metadata['files']) != metadata['total_files']:
        raise ReportError('metadata 文件份數與成員清單不一致。')
    if projection is None and legacy_provenance(documents[2]) != {
            key: metadata[key] for key in ('target_commit', 'corpus_digest')}:
        raise ReportError('技術附錄的固定 commit／corpus digest 與 metadata 不相符。')
    actions = parse_actions(documents[1], documents[2], paths[2].name)
    tasks = parse_tasks(documents[2])
    if projection is not None:
        recorded = {a.action_id: a for a in projection.report_data.data.actions}
        if set(recorded) != {a['id'] for a in actions}:
            raise ReportError('Markdown 與結構化 Action 清單不一致。')
        for a in actions:
            source = recorded[a['id']]
            if a['group'] != source.group:
                raise ReportError('Action 類別不一致。')
            a['priority'] = source.priority or ''
            a['products'] = list(source.scope_labels) or ['未記錄範圍標籤']
        recorded_tasks = {f.task_id: f for f in projection.report_data.assessment.report.findings if f.finding_type == 'task_finding'}
        if set(recorded_tasks) != {t['id'] for t in tasks} or any(
            (t['verdict'], t['strength']) != (recorded_tasks[t['id']].coverage_verdict, recorded_tasks[t['id']].evidence_strength) for t in tasks):
            raise ReportError('Markdown 與 assessment 的 Task 維度不一致。')
        for t in tasks:
            t['question'] = recorded_tasks[t['id']].company_statement
    counts = Counter(a['group'] for a in actions)
    products = sorted({product for a in actions for product in a['products']})
    report_names = dict(zip([p.name for p in paths[:3]], ['summary', 'actions', 'technical']))
    action_parts = re.split(r'^## ([ABC])\. .*$', documents[1], flags=re.M)
    group_content = dict(zip(action_parts[1::2], action_parts[2::2]))
    groups, details = [], []
    for group, label in [('A', '文件要修改'), ('B', '證據要補'), ('C', '改善建議')]:
        rows = []
        for a in [x for x in actions if x['group'] == group]:
            identifier = a['id'].lower()
            priority = f'<span class="priority">{a["priority"]}</span>' if a['priority'] else ''
            attrs = ' class="action-row" data-group="' + group + '" data-id="' + a['id'] + '"'
            row = f'<tr{attrs}><td data-label="ID"><button class="action-id" data-action="{identifier}">{a["id"]}</button>{priority}</td>'
            row += ''.join(f'<td data-label="{label}">' + inline(value, paths[2].name, report_names) + '</td>' for label, value in zip(ACTION_HEADER[1:], a['cells'][1:])) + '</tr>'
            rows.append(row)
            fields = ''.join('<div class="detail-field"><dt>' + html.escape(k) + '</dt><dd>' + inline(v, paths[2].name, report_names) + '</dd></div>' for k, v in a['fields'].items())
            details.append(f'<template id="detail-{identifier}"><dl class="detail-fields">{fields}</dl></template>')
        notes = '\n'.join(line for line in group_content[group].splitlines() if not line.startswith('|'))
        notes_html = markdown(notes, paths[2].name, report_names)
        table = '<div class="table-wrap action-table"><table><thead><tr>' + ''.join('<th scope="col">' + x + '</th>' for x in ACTION_HEADER) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>' if rows else ''
        if not rows and not notes_html:
            notes_html = '<p>本次未列。</p>'
        groups.append(f'<section class="action-group" data-group="{group}"><h3>{group}. {label}<span class="group-count">{len(rows)}</span></h3>{table}<div class="prose">{notes_html}</div></section>')
    task_rows = ''.join('<tr><td><code>' + t['id'] + '</code></td><td>' + html.escape(t['question']) + '</td><td><span class="verdict">' + t['verdict'] + '</span></td><td>' + t['strength'] + '</td></tr>' for t in tasks)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths} if projection is None else {
        **{p.name: hashlib.sha256(d.encode('utf-8')).hexdigest() for p, d in zip(paths[:3], documents)},
        paths[3].name: projection.report_data.data.corpus_metadata_ref.sha256,
        'report-data.json': projection.report_data.sha256,
        'assessment': projection.report_data.assessment.sha256,
    }
    data = {'reportId': identifiers[0], 'status': statuses[0], 'actions': actions, 'tasks': tasks, 'sourceHashes': hashes, 'targetCommit': metadata['target_commit'], 'corpusDigest': metadata['corpus_digest']}
    data['rendererVersion'] = TOOL_VERSION
    if projection is not None:
        data['acceptedRecord'] = projection.accepted
        data['syncState'] = projection.lifecycle.sync.state
    source_links = ' '.join('<a download href="' + html.escape(os.path.relpath(p, output.parent).replace('\\', '/'), quote=True) + '">' + label + '</a>' for p, label in zip(paths[:3], ['主管摘要', '工程師六欄修正單', '完整技術附錄']))
    provenance = ''.join('<div><dt>' + html.escape(name) + '</dt><dd><code>' + digest + '</code></dd></div>' for name, digest in hashes.items())
    title = next((plain(line[2:]) for line in documents[0].splitlines() if line.startswith('# ')), 'SSDLC 審閱報告')
    replacements = {
        'TITLE': html.escape(title), 'REPORT_ID': html.escape(identifiers[0]),
        'STATUS_LABEL': '人工審閱草稿' if statuses[0] == 'HUMAN REVIEW DRAFT' else html.escape(statuses[0]),
        'STATUS': html.escape(statuses[0]), 'COMMIT': metadata['target_commit'][:7],
        'TOTAL_FILES': str(metadata['total_files']), 'TOTAL_TASKS': str(len(tasks)),
        'TOTAL_ACTIONS': str(len(actions)), 'GROUP_A': str(counts['A']), 'GROUP_B': str(counts['B']), 'GROUP_C': str(counts['C']),
        'VERDICT_SUMMARY': html.escape(' · '.join(f'{value} × {n}' for value, n in Counter(t['verdict'] for t in tasks).items())),
        'STRENGTH_SUMMARY': html.escape(' · '.join(f'{value} × {n}' for value, n in Counter(t['strength'] for t in tasks).items())),
        'SUMMARY_HTML': markdown(documents[0], paths[2].name, report_names), 'ACTIONS_HTML': ''.join(groups),
        'ACTIONS_INTRO': markdown(action_parts[0], paths[2].name, report_names),
        'TECHNICAL_HTML': technical_sections(documents[2], paths[2].name, report_names),
        'TASK_ROWS': task_rows, 'DETAIL_TEMPLATES': ''.join(details),
        'PRODUCT_OPTIONS': ''.join('<option>' + html.escape(p) + '</option>' for p in products),
        'SOURCE_LINKS': source_links, 'PROVENANCE': provenance,
        'REPORT_DATA': json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'),
    }
    page = TEMPLATE.read_text(encoding='utf-8')
    if projection is not None:
        page = page.replace('白話問題', '公司文件重點')
        state = ('已提供綁定本版的接受紀錄' if projection.accepted else '人工結果尚未接受') + '；' + {
            'not_checked': '同步尚未核查', 'not_synced': '尚未同步 machine assessment', 'synced': '與指定 target 的同步紀錄已驗證'}[projection.lifecycle.sync.state]
        note = '<div class="boundary">' + html.escape(state) + '。本頁轉呈既有 Markdown；原文「只產生 Markdown」記錄的是 REPORT-4C 當時的停止點。本次新增 HTML 閱讀版，未更新判定或對外發布。範圍篩選僅使用已記錄標籤；未記錄時可使用 ID 或路徑搜尋。</div>'
        page = page.replace('<noscript>', note + '\n <noscript>', 1)
    script = re.search(r'<script id="reader-script">(.*?)</script>', page, re.S).group(1)
    digest = base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
    replacements['SCRIPT_HASH'] = digest
    def slot(match):
        name = match.group(1)
        if name not in replacements:
            raise ReportError('HTML 模板有未填的欄位：' + name)
        return replacements[name]
    # Only the original template has slots. Inserted report text is literal.
    return re.sub(r'@@([A-Z_]+)@@', slot, page)



def publish_page(output: Path, page: str) -> str:
    """Publish without replacing any existing version, including a raced file."""
    raw = page.encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    def existing():
        if output.is_symlink() or not output.is_file():
            raise ReportError('既有 HTML 必須是一般檔案；不跟隨 symbolic link。')
        if output.read_bytes() != raw:
            raise ReportError('既有 HTML 內容不同；請保留原版並使用新的報告版本目錄。')
        return 'unchanged'
    if output.exists() or output.is_symlink():
        return existing()
    with tempfile.NamedTemporaryFile(mode='wb', dir=output.parent, suffix='.tmp', delete=False) as f:
        temp = Path(f.name)
        f.write(raw)
    try:
        # A hard link publishes atomically without replacement on Windows/Linux.
        # If another writer wins the name, only an exact-byte no-op is allowed.
        try:
            os.link(temp, output)
        except FileExistsError:
            return existing()
        return 'created'
    finally:
        temp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['summary', 'actions', 'technical', 'metadata', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        page = render_bundle(args.summary, args.actions, args.technical, args.metadata, args.output)
        publish_page(args.output, page)
    except (ReportError, OSError, ValueError) as exc:
        parser.exit(2, '無法產出網頁：' + str(exc) + '\n')
    print('網頁閱讀版：' + str(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
