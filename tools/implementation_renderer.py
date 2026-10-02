"""Pure S2 projection of admitted records; no inference, source content or clock."""
from __future__ import annotations

import json

from tools.assessment_markdown import text, table
from tools.implementation_verification import verify_verification_record

UNVERIFIED_WARNING = (
    "UNVERIFIED PROVENANCE — Repository identity evidence is unavailable for at least one side. "
    "Both pinned snapshots passed integrity validation; overall provenance is not fully verified."
)


def _payload(record):
    verify_verification_record(record)
    identity = record.policy_assessment_identity
    # Never asdict(record): private context contains complete source snapshots.
    return {
        "warning": None if record.provenance_verified else UNVERIFIED_WARNING,
        "verification_id": record.verification_id,
        "policy_assessment_identity": {
            "assessment_id": identity.assessment_id,
            "target_source_type": identity.target_source_type,
            "target_repo": identity.target_repo,
            "target_commit": identity.target_commit,
            "target_manifest_digest": identity.target_manifest_digest,
            "target_corpus_digest": identity.target_corpus_digest,
        },
        **{name: getattr(record, name) for name in (
            "policy_snapshot_integrity_verified", "policy_unverified_reason_codes",
            "product_target_source_type", "product_target_repo", "product_target_commit",
            "product_manifest_digest", "product_corpus_digest",
            "product_snapshot_integrity_verified", "product_unverified_reason_codes",
            "expectation_set_digest", "ruleset_digest")},
        "policy_repository_identity_status": record.policy_repository_identity_status.value,
        "product_repository_identity_status": record.product_repository_identity_status.value,
        "policy_provenance_verified": record.policy_provenance_verified,
        "product_provenance_verified": record.product_provenance_verified,
        "provenance_verified": record.provenance_verified,
        "verified_items": [
            {
                "expectation_id": item.expectation_id,
                "expectation_digest": item.expectation_digest,
                "task_id": item.task_id,
                "rule_id": item.rule_id,
                "rule_digest": item.rule_digest,
                "verdict": item.verdict.value,
                "evidence_refs": [
                    {"repo_path": ref.repo_path, "content_digest": ref.content_digest,
                     "locator": {"kind": ref.locator.kind, "value": ref.locator.value},
                     "resolved_node_paths": ref.resolved_node_paths,
                     "matched_snippet": ref.matched_snippet}
                    for ref in item.evidence_refs
                ],
                "discrepancy_details": item.discrepancy_details,
                "applicability_reason": item.applicability_reason,
                "explanation": item.explanation,
            }
            for item in record.verified_items
        ],
        "claim_boundary": record.claim_boundary,
    }


def _display(value):
    if value is None:
        return "—"
    if type(value) is bool:
        return "true" if value else "false"
    if isinstance(value, (tuple, list)):
        return "／".join(_display(v) for v in value) or "—"
    # Preserve control characters as visible escapes instead of terminal controls.
    value = "".join(f"\\u{ord(c):04x}" if ord(c) < 32 and c != "\n" else c for c in str(value))
    return text(value)


class DeterministicImplementationRenderer:
    def render_json(self, record) -> str:
        # Fixed insertion order keeps the warning first; no wall clock or machine path.
        return json.dumps(_payload(record), ensure_ascii=False, indent=2, allow_nan=False) + "\n"

    def render_markdown(self, record) -> str:
        data = _payload(record)
        lines = []
        if data["warning"]:
            lines.extend(["> [!WARNING]", "> " + _display(data["warning"]), ""])
        lines.extend(["# S2 靜態實作憑證驗證", "", "驗證編號 " + _display(data["verification_id"]), "",
                      "這份報告保留每條規則的結果。未合成 Task 判定、優先級、審查決策或執行成效。", "",
                      "## 來源與完整性", ""])
        rows = []
        for side in ("policy", "product"):
            for field in ("snapshot_integrity_verified", "repository_identity_status",
                          "unverified_reason_codes", "provenance_verified"):
                key = side + "_" + field
                rows.append([key, _display(data[key])])
        rows.append(["provenance_verified", _display(data["provenance_verified"])])
        lines.extend([table(("欄位", "狀態"), rows), "", "## 固定版本與指紋", ""])
        rows = [["policy." + key, _display(value)]
                for key, value in data["policy_assessment_identity"].items()]
        rows.extend([key, _display(data[key])] for key in (
            "product_target_source_type", "product_target_repo", "product_target_commit",
            "product_manifest_digest", "product_corpus_digest", "expectation_set_digest", "ruleset_digest"))
        lines.extend([table(("欄位", "值"), rows), "", "## 每條規則的結果", ""])
        for item in data["verified_items"]:
            lines.extend(["### " + _display(item["task_id"]) + "／" + _display(item["expectation_id"])
                          + "／" + _display(item["rule_id"]), ""])
            rows = [[key, _display(item[key])] for key in (
                "verdict", "expectation_digest", "rule_digest", "discrepancy_details",
                "applicability_reason", "explanation")]
            lines.extend([table(("欄位", "值"), rows), ""])
            if item["evidence_refs"]:
                rows = [[_display(ref["repo_path"]), _display(ref["content_digest"]),
                         _display(ref["locator"]["kind"]), _display(ref["locator"]["value"]),
                         _display(json.dumps(ref["resolved_node_paths"], ensure_ascii=False,
                                             separators=(",", ":")))] for ref in item["evidence_refs"]]
                lines.extend([table(("檔案", "SHA-256", "Locator", "Expression", "Concrete nodes"), rows), ""])
            else:
                lines.extend(["本項沒有 evidence refs。", ""])
        lines.extend(["## 不能從這份結果宣稱什麼", ""])
        lines.extend("- " + _display(claim) for claim in data["claim_boundary"])
        return "\n".join(lines) + "\n"
