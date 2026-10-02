"""REPORT-3B lifecycle admission; no queue projection, renderer or sync writer.

Structured records establish the declared decisions and exact content bindings.
They do not authenticate a human, prove authority, or prove an operation ran.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.report_data_contract import (
    ArtifactRef, ArtifactStore, AssessmentDocument, LoadedReportData,
    _choice, _digest, _fail, _object, _text, decode_json,
    load_assessment_bytes, load_report_data, parse_artifact_ref,
)


@dataclass(frozen=True)
class ReviewRecommendation:
    opinion: str
    reason: str


@dataclass(frozen=True)
class SyncRecord:
    state: str
    target_ref: ArtifactRef | None
    decision_ref: ArtifactRef | None
    verification_ref: ArtifactRef | None


@dataclass(frozen=True)
class ReviewLifecycle:
    report_data_ref: ArtifactRef
    machine_baseline_ref: ArtifactRef | None
    review_recommendation: ReviewRecommendation | None
    acceptance_ref: ArtifactRef | None
    sync: SyncRecord


@dataclass(frozen=True)
class AcceptanceDecision:
    decision: str
    report_data_sha256: str
    assessment_sha256: str
    evidence_ref: ArtifactRef


@dataclass(frozen=True)
class SyncDecision:
    decision: str
    report_data_sha256: str
    assessment_sha256: str
    target_sha256: str
    evidence_ref: ArtifactRef


@dataclass(frozen=True)
class SyncVerification:
    result: str
    report_data_sha256: str
    assessment_sha256: str
    target_sha256: str
    evidence_ref: ArtifactRef


@dataclass(frozen=True)
class LoadedReviewLifecycle:
    lifecycle: ReviewLifecycle
    report_data: LoadedReportData
    machine_baseline: AssessmentDocument | None
    target: AssessmentDocument | None
    acceptance: AcceptanceDecision | None
    sync_decision: SyncDecision | None
    sync_verification: SyncVerification | None

    @property
    def accepted(self) -> bool:
        return self.acceptance is not None


def _optional_ref(value: Any) -> ArtifactRef | None:
    return None if value is None else parse_artifact_ref(value)


def parse_review_lifecycle(value: Any) -> ReviewLifecycle:
    """Pure strict structural parser. Recommendation never implies acceptance."""
    v = _object(value, "review_lifecycle", {"report_data_ref", "machine_baseline_ref", "review_recommendation", "acceptance_ref", "sync"})
    recommendation = None
    if v["review_recommendation"] is not None:
        r = _object(v["review_recommendation"], "review_recommendation", {"opinion", "reason"})
        recommendation = ReviewRecommendation(_text(r["opinion"], "opinion"), _text(r["reason"], "reason"))
    s = _object(v["sync"], "sync", {"state", "target_ref", "decision_ref", "verification_ref"})
    state = _choice(s["state"], {"not_checked", "not_synced", "synced"}, "sync.state")
    target, decision, verification = (_optional_ref(s[key]) for key in ["target_ref", "decision_ref", "verification_ref"])
    if (state == "not_checked" and any(x is not None for x in (target, decision, verification))
            or state != "not_checked" and (target is None or verification is None)
            or state == "synced" and decision is None):
        _fail("sync.state", "state and required references are inconsistent")
    return ReviewLifecycle(parse_artifact_ref(v["report_data_ref"]), _optional_ref(v["machine_baseline_ref"]),
                           recommendation, _optional_ref(v["acceptance_ref"]), SyncRecord(state, target, decision, verification))


def parse_acceptance_decision(value: Any) -> AcceptanceDecision:
    v = _object(value, "acceptance_decision", {"decision", "report_data_sha256", "assessment_sha256", "evidence_ref"})
    return AcceptanceDecision(_choice(v["decision"], {"accepted"}, "acceptance.decision"),
                              _digest(v["report_data_sha256"], "report_data_sha256"),
                              _digest(v["assessment_sha256"], "assessment_sha256"), parse_artifact_ref(v["evidence_ref"]))


def parse_sync_decision(value: Any) -> SyncDecision:
    v = _object(value, "sync_decision", {"decision", "report_data_sha256", "assessment_sha256", "target_sha256", "evidence_ref"})
    return SyncDecision(_choice(v["decision"], {"synchronize"}, "sync.decision"),
                        _digest(v["report_data_sha256"], "report_data_sha256"),
                        _digest(v["assessment_sha256"], "assessment_sha256"),
                        _digest(v["target_sha256"], "target_sha256"), parse_artifact_ref(v["evidence_ref"]))


def parse_sync_verification(value: Any) -> SyncVerification:
    v = _object(value, "sync_verification", {"result", "report_data_sha256", "assessment_sha256", "target_sha256", "evidence_ref"})
    return SyncVerification(_choice(v["result"], {"matched", "not_synced"}, "sync.result"),
                            _digest(v["report_data_sha256"], "report_data_sha256"),
                            _digest(v["assessment_sha256"], "assessment_sha256"),
                            _digest(v["target_sha256"], "target_sha256"), parse_artifact_ref(v["evidence_ref"]))


def validate_decision_binding(record: AcceptanceDecision | SyncDecision | SyncVerification,
                              report: LoadedReportData, target: AssessmentDocument | None = None) -> None:
    """Pure comparisons of already loaded records; no textual decision inference."""
    if record.report_data_sha256 != report.sha256 or record.assessment_sha256 != report.assessment.sha256:
        _fail("decision.binding", "report data or selected assessment fingerprint mismatch")
    if isinstance(record, (SyncDecision, SyncVerification)):
        if target is None or record.target_sha256 != target.sha256:
            _fail("decision.binding", "target fingerprint mismatch")


def validate_sync_content(state: str, verification: SyncVerification,
                          selected: AssessmentDocument, target: AssessmentDocument) -> None:
    """Verify the result against all original dimensions, not just verdicts.

    The documented sync can change assessment ID/navigation path only. Arrays
    keep original order (including basis indexes); no semantic normalization.
    Equal contents alone never cause a sync decision or accepted state.
    """
    matched = selected.comparison == target.comparison
    if (state == "synced" and (verification.result != "matched" or not matched)
            or state == "not_synced" and (verification.result != "not_synced" or matched)):
        _fail("sync.verification", "declared state/result contradict the actual compared contents")


def load_review_lifecycle(relative_path: str, report_root: Path, *,
                          authorized_auxiliary_sources: frozenset[str] = frozenset()) -> LoadedReviewLifecycle:
    """Full read-only lifecycle admission. Any non-null invalid proof raises."""
    store = ArtifactStore(report_root)
    path, raw = store.read_path(relative_path)
    lifecycle = parse_review_lifecycle(decode_json(raw, "review_lifecycle"))
    report_path, _ = store.read_ref(lifecycle.report_data_ref, path)
    report = load_report_data(report_path.relative_to(store.root).as_posix(), store.root,
                              authorized_auxiliary_sources=authorized_auxiliary_sources)
    if report.sha256 != lifecycle.report_data_ref.sha256:
        _fail("report_data.binding", "report changed during loading")
    baseline = None
    if lifecycle.machine_baseline_ref is not None:
        _, baseline_raw = store.read_ref(lifecycle.machine_baseline_ref, path)
        baseline = load_assessment_bytes(baseline_raw)
    acceptance = None
    if lifecycle.acceptance_ref is not None:
        record_path, record_raw = store.read_ref(lifecycle.acceptance_ref, path)
        acceptance = parse_acceptance_decision(decode_json(record_raw, "acceptance_decision"))
        validate_decision_binding(acceptance, report)
        store.read_ref(acceptance.evidence_ref, record_path)
    target = None
    decision = None
    verification = None
    sync = lifecycle.sync
    if sync.state != "not_checked":
        _, target_raw = store.read_ref(sync.target_ref, path)
        target = load_assessment_bytes(target_raw)
        if sync.decision_ref is not None:
            decision_path, decision_raw = store.read_ref(sync.decision_ref, path)
            decision = parse_sync_decision(decode_json(decision_raw, "sync_decision"))
            validate_decision_binding(decision, report, target)
            store.read_ref(decision.evidence_ref, decision_path)
        verification_path, verification_raw = store.read_ref(sync.verification_ref, path)
        verification = parse_sync_verification(decode_json(verification_raw, "sync_verification"))
        validate_decision_binding(verification, report, target)
        store.read_ref(verification.evidence_ref, verification_path)
        validate_sync_content(sync.state, verification, report.assessment, target)
    return LoadedReviewLifecycle(lifecycle, report, baseline, target, acceptance, decision, verification)
