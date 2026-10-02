"""REPORT-4C pure presentation of admitted records; no inference, I/O or clock.

Callers must supply a fully loaded lifecycle, explicit date, fixed templates and
navigation to admitted files. Original rationale and retained prose are never
parsed to invent actions, gaps, acceptance, scope labels or previous verdicts.
"""
from __future__ import annotations

from collections import Counter
from datetime import date as Date
from html import escape
import re
from string import Template
from typing import Mapping

from tools.review_lifecycle_contract import LoadedReviewLifecycle


class MarkdownProjectionError(ValueError):
    """No complete three-layer report can be emitted for this input."""


SECTIONS = {
    "summary": ("1. 結論", "2. 工程師要處理什麼", "3. 建議處理順序", "4. 詳細 NIST 判定"),
    "actions": ("A. 文件要修改", "B. 證據要補", "C. 改善建議"),
    "technical": ("1. Review 結論與宣稱邊界", "2. 固定範圍與閱讀方法", "3. 上次結果與問題追蹤",
                  "4. 工程師修正與補證的完整依據", "5. 各 Task 的評估紀錄", "6. 逐份文件與跨文件觀察",
                  "7. 來源指紋", "8. 驗證與停止點"),
}
SLOTS = {
    "summary": {"headline", "conclusion", "actions", "priority", "sources", "stop"},
    "actions": {"scope", "group_a", "group_b", "group_c", "stop"},
    "technical": {"review", "scope", "history", "actions", "tasks", "observations", "fingerprints", "validation"},
}
COMMON_SLOTS = {"title", "status", "date", "report_id", "navigation"}
TASK_LABELS = (
    "發現編號與類型（finding_id / finding_type）", "評估項目（Task / task_id）",
    "NIST 這題要求什麼（NIST Task Expectation）", "公司文件寫了什麼（Company Document Statements）",
    "文件中找到的相關內容（Identified Document Evidence）", "公司文件出處（Company Source / company_source_ref）",
    "影響覆蓋的缺口（Task Coverage Gap）", "可以再改善的地方（Improvement Opportunity）",
    "文件覆蓋判定（Coverage Verdict / coverage_verdict）", "實際執行的證據強度（Evidence Strength / evidence_strength）",
    "文件核准與來源狀態（Corpus Authority Context）", "為什麼這樣判（Assessment Rationale / assessment_rationale）",
    "判斷依據（Basis）", "建議如何安排人工審查（Review Queue Recommendation）",
    "這份結果不能證明什麼（Cannot Claim / cannot_claim）",
)
ACTION_COLUMNS = ("ID", "類型", "哪裡有問題", "現在的問題", "要怎麼改", "怎樣算改完")
AUTHORITY_NAMES = {"draft": "草稿", "under_review": "審核中", "unspecified": "讀過但未標示狀態", "approved": "文件標示 Approved"}


def text(value: object) -> str:
    """Keep recorded content as text, including hostile Markdown/HTML."""
    s = escape(str(value).replace("\r\n", "\n").replace("\r", "\n"), quote=False)
    return re.sub(r"([\\`*_\[\]{}|#~])", r"\\\1", s).replace("\n", "<br>")


def bullets(values) -> str:
    return "\n".join("- " + text(v) for v in values) or "本次未列。"


def table(columns, rows) -> str:
    return "\n".join(["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
                     + ["| " + " | ".join(row) + " |" for row in rows])


def distribution(values) -> str:
    counts = Counter(values)
    return "／".join(f"{text(key)} {counts[key]}" for key in sorted(counts)) or "本次未列"


def filenames(report_id: str) -> dict[str, str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", report_id) or report_id.endswith("."):
        raise MarkdownProjectionError("report_id is not a safe presentation filename")
    return {"summary": f"{report_id}-summary.md", "actions": f"{report_id}-actions.md", "technical": f"{report_id}-technical-review.md"}


def _link(label: str, href: str) -> str:
    # Application generates URL-encoded relative links to already admitted files.
    if not href or re.search(r"[\s():<>\\]", href) or href.startswith("/"):
        raise MarkdownProjectionError("expected an encoded relative presentation link")
    return f"[{text(label)}]({href})"


def _template(kind: str, raw: str, slots: dict[str, str]) -> str:
    if tuple(re.findall(r"^## (.+)$", raw, re.M)) != SECTIONS[kind]:
        raise MarkdownProjectionError(f"{kind}: fixed section layout changed")
    t = Template(raw)
    if not t.is_valid() or set(t.get_identifiers()) != COMMON_SLOTS | SLOTS[kind]:
        raise MarkdownProjectionError(f"{kind}: missing/unknown template slot")
    return t.substitute(slots).rstrip() + "\n"


def _basis(basis) -> str:
    parts = [basis.type]
    if basis.task_id is not None:
        parts.append(basis.task_id)
    if basis.source is not None:
        parts.append(basis.source)
    return text("；".join(parts) + "。" + basis.rationale)


def _items(items, empty: str) -> str:
    if items is None:
        raise MarkdownProjectionError("unorganized task supplement")
    return "\n".join("- " + text(item.text) + "；來源 " + text("／".join(item.source_refs))
                     + "；basis index（從 0 起） " + text(", ".join(map(str, item.basis_refs))) for item in items) or empty


def render_markdown(loaded: LoadedReviewLifecycle, *, date: str, title: str,
                    templates: Mapping[str, str], source_links: Mapping[str, str]) -> dict[str, str]:
    """Return three Markdown documents; admit incomplete data only in other tools.

    This is presentation of existing judgments, not a new corpus read/review.
    Unavailable prior human verdicts stay unavailable. Machine history is shown
    with its own provenance, never reused as a Previous/Reassessed human result.
    """
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise MarkdownProjectionError("explicit canonical date required")
    try:
        Date.fromisoformat(date)
    except ValueError as e:
        raise MarkdownProjectionError("invalid date") from e
    if not title.strip() or "\n" in title or "\r" in title:
        raise MarkdownProjectionError("single-line title required")
    rd = loaded.report_data
    if not rd.validation.complete:
        raise MarkdownProjectionError("incomplete report data: " + "; ".join(rd.validation.incomplete))
    report, data = rd.assessment.report, rd.data
    names = filenames(data.report_id)
    if set(templates) != set(names):
        raise MarkdownProjectionError("three fixed templates required")
    status = "已接受且與指定 target 同步" if loaded.accepted and loaded.lifecycle.sync.state == "synced" else "HUMAN REVIEW DRAFT"
    acceptance = "人工報告已接受（結構化紀錄綁定本版；未核實決策者權限）" if loaded.accepted else "未提供綁定本版的接受紀錄"
    sync = {"not_checked": "尚未核查同步", "not_synced": "與指定 target 未同步", "synced": "與指定 target 同步紀錄已驗證"}[loaded.lifecycle.sync.state]
    stop = f"人工接受狀態 {acceptance}；machine 狀態 {sync}。本次只產生 Markdown，沒有修改 assessment、queue 或公司文件，也沒有產生新 HTML 或對外發布。"
    boundary = bullets(report.claim_boundary)
    scope = f"參考基準 {text(report.baseline)}。固定 repository {text(report.target.repo)}，commit {text(report.target.commit)}。\n\n只限納入的 {len(rd.corpus.files)} 份文件及 {len(report.findings)} 個 Task。"
    authority = "／".join(f"{AUTHORITY_NAMES[state]} {sum(a.state == state for a in data.source_authority)}" for state in AUTHORITY_NAMES)
    authority += "。只投影已記錄的文件狀態；未查驗核准者身分、權限或組織核准系統。"
    nav = "／".join(_link(label, names[kind]) for kind, label in (("summary", "主管摘要"), ("actions", "工程師六欄修正單"), ("technical", "完整技術附錄")))
    common = dict(title=text(title), status=status, date=date, report_id=text(data.report_id), navigation=nav)
    actions = sorted(data.actions, key=lambda a: (a.group, a.action_id))
    action_counts = Counter(a.group for a in actions)
    action_summary = "\n".join(f"- **{group} {label}** {action_counts[group]} 項。" for group, label in (("A", "文件要修改"), ("B", "證據要補"), ("C", "改善建議")))
    priority = "\n".join(f"- {text(a.action_id)}（{text(a.priority)}） {text(a.priority_reason)}" for a in actions if a.priority in ("P0", "P1")) or "本次未記錄 P0／P1 項目；處理順序不由 Coverage Verdict 自動換算。"
    folders = Counter("/".join(path.split("/")[:3 if path.startswith("docs/03-products/") else 2]) if "/" in path else "根目錄" for path, _, _ in rd.corpus.files)
    scope_table = table(("文件資料夾（只作閱讀分組）", "份數"), [[text(folder), str(count)] for folder, count in sorted(folders.items())] + [["合計", str(len(rd.corpus.files))]])
    headline = f"本次 {len(rd.corpus.files)} 份文件、{len(report.findings)} 題的文件覆蓋為 {distribution(f.coverage_verdict for f in report.findings)}；實際執行證據為 {distribution(f.evidence_strength for f in report.findings)}。"
    summary_scope = f"本次呈現 {len(rd.corpus.files)} 份固定文件及 {len(report.findings)} 個 Task 的既有結果。參考基準 {text(report.baseline)}；完整來源版本見技術附錄。"
    coverage_note = "COVERED 表示在本次範圍內，文件已涵蓋該題要求；不代表實際執行完成。" if any(f.coverage_verdict == "COVERED" for f in report.findings) else "本次只呈現文件覆蓋結果，不代表實際執行完成。"
    conclusion = summary_scope + "\n\n" + scope_table + f"\n\n- **文件覆蓋** {distribution(f.coverage_verdict for f in report.findings)}。\n- **實際執行證據** {distribution(f.evidence_strength for f in report.findings)}。\n- **文件核准狀態** {authority}\n\n" + coverage_note + "下列原始範圍與宣稱限制仍適用。\n\n" + boundary
    sources = "\n".join("- " + _link(label, href) for label, href in sorted(source_links.items())) or "本次未提供其他閱讀來源。"
    primary_sources = "\n".join("- " + _link(label, source_links[label]) for label in ("report-data", "corpus metadata", "review lifecycle") if label in source_links)
    summary = _template("summary", templates["summary"], {**common, "headline": headline, "conclusion": conclusion, "actions": action_summary + "\n\n直接工作入口 " + _link("工程師六欄修正單", names["actions"]) + "。", "priority": priority, "sources": _link("完整技術附錄", names["technical"]) + "保存逐題理由、修法與完整限制。\n\n" + primary_sources, "stop": stop})
    groups = {}
    for group in "ABC":
        rows = []
        for a in actions:
            if a.group != group:
                continue
            details = dict(a.details)
            rows.append([_link(a.action_id, names["technical"] + "#" + a.action_id.lower()), text(a.kind),
                         text("\n".join(loc.display_text for loc in a.locations)), text(details["目前哪裡有問題"]),
                         text(details["要修改或補什麼"]), text(details["完成確認方式"])])
        groups[group] = table(ACTION_COLUMNS, rows) if rows else "本次未列。"
    action_doc = _template("actions", templates["actions"], {**common, "scope": scope, "group_a": groups["A"], "group_b": groups["B"], "group_c": groups["C"], "stop": stop})
    detail_blocks = []
    for a in actions:
        d = dict(a.details)
        nature = f"{a.action_id}／{a.group}／{a.kind}；" + (f"{a.priority}。{a.priority_reason}" if a.priority else "未記錄 priority，不推填。")
        rows = [["問題編號與性質", text(nature)], ["文件與位置", text("\n".join(f"{loc.display_text}（{loc.source_scope}；{loc.source_ref}）" for loc in a.locations))]]
        rows.extend([key, text(d[key])] for key in ("規則依據與效力", "目前哪裡有問題", "要修改或補什麼", "完成確認方式", "適用條件與待確認事項", "對判定的影響與不能宣稱"))
        tracking = text(a.tracking.statement) if a.tracking else "未提供結構化追蹤紀錄。"
        if a.tracking:
            tracking += "\n\n" + bullets(f"{ref.path}；SHA-256 {ref.sha256}" for ref in a.tracking.evidence_refs)
        detail_blocks.append(f'<a id="{a.action_id.lower()}"></a>\n### {text(a.action_id)} — {text(a.kind)}\n\n' + table(("欄位", "說明"), rows)
                             + "\n\n修訂句 " + text(d["修訂句"]) + "\n\n已記錄的 basis（依原順序）\n\n" + "\n".join("- " + _basis(b) for b in a.basis)
                             + "\n\nfinding refs " + text("／".join(a.finding_refs) or "未記錄關係，不推論 NIST 對應")
                             + "；scope labels " + text("／".join(a.scope_labels) or "未記錄標籤，不由檔名推填") + "。\n\n追蹤紀錄 " + tracking)
    supplements = {s.finding_id: s for s in data.task_supplements}
    task_blocks = []
    for f in sorted(report.findings, key=lambda f: (f.task_id, f.finding_id)):
        s = supplements[f.finding_id]
        normative = "\n".join("- " + _basis(b) for b in f.basis if b.type == "nist_normative") or "未記錄 normative basis，不自行補入。"
        values = (text(f"{f.finding_id}／{f.finding_type}"), text(f.task_id), normative, text(f.company_statement),
                  bullets(f"{e.type}；{e.source_ref}" for e in f.identified_evidence), text(f.company_source_ref) + "\n\n補充文件引用\n\n" + bullets(s.document_refs),
                  _items(s.gap_items, "已整理；本次範圍內未記錄 coverage gap。"), _items(s.improvement_items, "已整理；本次未列改善建議。"),
                  text(f.coverage_verdict), text(f.evidence_strength) + "；理由依原文保存於 Assessment Rationale，不由文件狀態換算。",
                  authority, bullets(f.assessment_rationale), "\n".join(f"- index {i}：{_basis(b)}" for i, b in enumerate(f.basis)),
                  text(f.review_queue_recommendation) + "；獨立理由保留在 Assessment Rationale，不由 verdict 自動換算。", bullets(f.cannot_claim))
        task_blocks.append(f"### {text(f.task_id)}\n\n" + "\n\n".join(f"**{label}**\n\n{value}" for label, value in zip(TASK_LABELS, values)))
    history = "未提供結構化的上一版人工 Task verdict；原報告與歷史文字保留於來源連結。本次沿用所引用 assessment，不重新判定。\n\n"
    if loaded.machine_baseline is None:
        history += "未提供歷史 machine baseline。"
    else:
        old = loaded.machine_baseline.report
        history += "**歷史 machine baseline（獨立來源）**\n\n" + table(("Assessment", "Commit", "Corpus digest", "Verdict 分布"), [
            [text(old.id), text(old.target.commit), text(old.target.corpus_digest), distribution(f.coverage_verdict for f in old.findings)],
            [text(report.id), text(report.target.commit), text(report.target.corpus_digest), distribution(f.coverage_verdict for f in report.findings)]])
        history += "\n\n這是兩個 assessment 的來源對照，不冒充同一 corpus 的 Previous／Reassessed Verdict。"
    history += "\n\n" + table(("Stable ID", "本輪追蹤紀錄", "來源"), [[_link(a.action_id, "#" + a.action_id.lower()), text(a.tracking.statement if a.tracking else "未記錄"), text("／".join(r.path for r in a.tracking.evidence_refs) if a.tracking else "未記錄")] for a in actions])
    observations = "本次產生器沒有重讀公司文件，也不從保留的 Markdown 推論新結論。逐份文件及跨文件的既有分析保留於下列原始來源。\n\n" + sources
    for o in sorted(report.observations, key=lambda o: o.finding_id):
        observations += f"\n\n### {text(o.finding_id)}\n\n" + bullets((o.finding_type, o.company_source_ref, o.observation, o.basis, o.review_queue_recommendation)) + "\n\n" + bullets(o.cannot_claim)
    fingerprints = table(("Corpus path", "Bytes", "SHA-256"), [[text(path), str(size), digest] for path, digest, size in sorted(rd.corpus.files)])
    fingerprints += "\n\nAuxiliary source（不加入 coverage、corpus digest 或 authority 統計）\n\n" + table(("Source", "Artifact", "SHA-256"), [[text(a.source_ref), text(a.artifact_ref.path), a.artifact_ref.sha256] for a in data.auxiliary_sources]) if data.auxiliary_sources else "\n\n本次未列 auxiliary source。"
    fingerprints += f"\n\nManifest digest {report.target.manifest_digest}。\n\nCorpus digest {report.target.corpus_digest}。\n\nReport-data SHA-256 {rd.sha256}。\n\nAssessment SHA-256 {rd.assessment.sha256}。"
    fingerprints += "\n\n逐份文件核准與來源狀態（只保存已記錄資料）\n\n" + table(("Corpus path", "State", "Raw status", "Status source", "Approval reference"), [[text(a.path), text(a.state), text(a.raw_status or "未記錄"), text(a.status_source_ref.path if hasattr(a.status_source_ref, "path") else a.status_source_ref or "未記錄"), text(a.approval_ref.path if a.approval_ref else "未提供")] for a in sorted(data.source_authority, key=lambda a: a.path)])
    technical = _template("technical", templates["technical"], {**common, "review": stop + "\n\n" + (text(loaded.lifecycle.review_recommendation.opinion + "。" + loaded.lifecycle.review_recommendation.reason) if loaded.lifecycle.review_recommendation else "未提供獨立 Review Recommendation。") + "\n\n" + boundary,
        "scope": scope + "\n\n" + authority + "\n\nTask 清單 " + text("／".join(report.scope_tasks)) + "。\n\n本次閱讀方式為結構化資料投影；既有審閱方法與詳細文字見 retained sources。原 assessment 的分支名稱未結構化保存，不從檔名推填。\n\nNIST SSDF 看要做什麼；OWASP SAMM 看成熟到哪；ISO／IEC 看管理與標準化。本次沒有新增 SAMM 或 ISO 評估。",
        "history": history, "actions": "\n\n".join(detail_blocks) or "本次未列。", "tasks": "\n\n".join(task_blocks), "observations": observations, "fingerprints": fingerprints,
        "validation": "入口已執行 REPORT-4A 的 ArtifactRef／SHA-256、版本關係與 cross-reference admission，report data 整理完整。三層均由同一份已載入資料產生；固定模板保留章節、六欄及逐題欄位。\n\n此檢查不證明 Git／quote-span、semantic reasoning、真實執行、核准身分或權限。新檔的測試與連結核對結果由外部執行紀錄保存，本文不自行宣稱測試已通過。\n\n" + stop})
    return {names["summary"]: summary, names["actions"]: action_doc, names["technical"]: technical}
