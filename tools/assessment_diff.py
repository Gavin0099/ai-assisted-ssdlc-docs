#!/usr/bin/env python3
"""Assessment Comparison and Diffing Engine (Phase S1-D3).

Provides deterministic, evaluative-free comparison between two SSDF assessment reports.
Strictly records state transitions and field changes without value judgements or compliance claims.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from tools.corpus_assessment_engine import (
    CorpusAssessmentBasis,
    CorpusAssessmentReport,
    CorpusTaskFinding,
    IdentifiedEvidence,
)

BASIS_PRIORITY: dict[str, int] = {
    "nist_normative": 1,
    "local_derived_guidance": 2,
    "reviewer_inference": 3,
}


def canonical_basis_tuple(
    bases: list[CorpusAssessmentBasis] | tuple[CorpusAssessmentBasis, ...],
) -> tuple[dict[str, Any], ...]:
    """Sorts basis entries deterministically by priority, rationale, task_id, and source."""
    sorted_bases = sorted(
        bases,
        key=lambda b: (
            BASIS_PRIORITY.get(b.type, 99),
            b.rationale,
            b.task_id or "",
            b.source or "",
        ),
    )
    return tuple(b.to_dict() for b in sorted_bases)


def canonical_evidence_tuple(
    evidences: list[IdentifiedEvidence] | tuple[IdentifiedEvidence, ...],
) -> tuple[dict[str, Any], ...]:
    """Sorts identified evidence deterministically by type and source_ref."""
    sorted_ev = sorted(
        evidences,
        key=lambda e: (e.type, e.source_ref),
    )
    return tuple(e.to_dict() for e in sorted_ev)


class DiffKind(str, Enum):
    """Categorization of difference between two assessment findings."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    MODIFIED = "MODIFIED"
    UNCHANGED = "UNCHANGED"


@dataclass(frozen=True)
class FieldDiff:
    """Represents a change in a single field between baseline and target."""

    field_name: str
    baseline_value: Any
    target_value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "baseline_value": self.baseline_value,
            "target_value": self.target_value,
        }


@dataclass(frozen=True)
class TaskFindingDiff:
    """Represents the difference in a single task assessment between baseline and target."""

    task_id: str
    diff_kind: DiffKind
    baseline_finding_id: str | None
    target_finding_id: str | None
    verdict_transition: tuple[str | None, str | None]
    changed_fields: tuple[FieldDiff, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "diff_kind": self.diff_kind.value,
            "baseline_finding_id": self.baseline_finding_id,
            "target_finding_id": self.target_finding_id,
            "verdict_transition": list(self.verdict_transition),
            "changed_fields": [f.to_dict() for f in self.changed_fields],
        }


@dataclass(frozen=True)
class AssessmentDiffRecord:
    """Immutable aggregate root representing the full deterministic diff between two assessments."""

    baseline_id: str
    target_id: str
    target_metadata_diff: tuple[FieldDiff, ...]
    task_diffs: tuple[TaskFindingDiff, ...]
    added_count: int
    removed_count: int
    modified_count: int
    unchanged_count: int
    claim_boundary: tuple[str, ...]
    provenance_verified: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "target_id": self.target_id,
            "provenance_verified": self.provenance_verified,
            "target_metadata_diff": [f.to_dict() for f in self.target_metadata_diff],
            "task_diffs": [td.to_dict() for td in self.task_diffs],
            "summary": {
                "added": self.added_count,
                "removed": self.removed_count,
                "modified": self.modified_count,
                "unchanged": self.unchanged_count,
                "total_tasks": len(self.task_diffs),
            },
            "claim_boundary": list(self.claim_boundary),
        }


class IAssessmentDiffEngine(Protocol):
    """Interface for comparing two assessment reports without evaluative sentiment."""

    def compare(
        self,
        baseline: CorpusAssessmentReport,
        target: CorpusAssessmentReport,
        provenance_verified: bool = True,
    ) -> AssessmentDiffRecord:
        """Determines differences between two assessment reports deterministically."""
        ...


class AssessmentDiffEngine:
    """Deterministic, sentiment-free diffing engine implementation."""

    def compare(
        self,
        baseline: CorpusAssessmentReport,
        target: CorpusAssessmentReport,
        provenance_verified: bool = True,
    ) -> AssessmentDiffRecord:
        # 1. Compare target metadata
        metadata_diffs: list[FieldDiff] = []
        for field in ("repo", "commit", "manifest_path", "manifest_digest", "corpus_digest", "target_type"):
            b_val = getattr(baseline.target, field, None)
            t_val = getattr(target.target, field, None)
            if b_val != t_val:
                metadata_diffs.append(
                    FieldDiff(field_name=field, baseline_value=b_val, target_value=t_val)
                )

        # 2. Compare task findings
        baseline_tasks: dict[str, CorpusTaskFinding] = {f.task_id: f for f in baseline.findings}
        target_tasks: dict[str, CorpusTaskFinding] = {f.task_id: f for f in target.findings}
        all_task_ids = sorted(set(baseline_tasks.keys()) | set(target_tasks.keys()))

        task_diffs: list[TaskFindingDiff] = []
        added_count = 0
        removed_count = 0
        modified_count = 0
        unchanged_count = 0

        for task_id in all_task_ids:
            b_finding = baseline_tasks.get(task_id)
            t_finding = target_tasks.get(task_id)

            if b_finding is None and t_finding is not None:
                # ADDED in target
                added_count += 1
                task_diffs.append(
                    TaskFindingDiff(
                        task_id=task_id,
                        diff_kind=DiffKind.ADDED,
                        baseline_finding_id=None,
                        target_finding_id=t_finding.finding_id,
                        verdict_transition=(None, t_finding.coverage_verdict),
                        changed_fields=(),
                    )
                )
            elif b_finding is not None and t_finding is None:
                # REMOVED from target
                removed_count += 1
                task_diffs.append(
                    TaskFindingDiff(
                        task_id=task_id,
                        diff_kind=DiffKind.REMOVED,
                        baseline_finding_id=b_finding.finding_id,
                        target_finding_id=None,
                        verdict_transition=(b_finding.coverage_verdict, None),
                        changed_fields=(),
                    )
                )
            elif b_finding is not None and t_finding is not None:
                # Compare fields between baseline and target findings
                field_diffs: list[FieldDiff] = []
                if b_finding.coverage_verdict != t_finding.coverage_verdict:
                    field_diffs.append(
                        FieldDiff(
                            field_name="coverage_verdict",
                            baseline_value=b_finding.coverage_verdict,
                            target_value=t_finding.coverage_verdict,
                        )
                    )
                if b_finding.company_source_ref != t_finding.company_source_ref:
                    field_diffs.append(
                        FieldDiff(
                            field_name="company_source_ref",
                            baseline_value=b_finding.company_source_ref,
                            target_value=t_finding.company_source_ref,
                        )
                    )
                if b_finding.company_statement != t_finding.company_statement:
                    field_diffs.append(
                        FieldDiff(
                            field_name="company_statement",
                            baseline_value=b_finding.company_statement,
                            target_value=t_finding.company_statement,
                        )
                    )
                if b_finding.review_queue_recommendation != t_finding.review_queue_recommendation:
                    field_diffs.append(
                        FieldDiff(
                            field_name="review_queue_recommendation",
                            baseline_value=b_finding.review_queue_recommendation,
                            target_value=t_finding.review_queue_recommendation,
                        )
                    )
                if b_finding.evidence_strength != t_finding.evidence_strength:
                    field_diffs.append(
                        FieldDiff(
                            field_name="evidence_strength",
                            baseline_value=b_finding.evidence_strength,
                            target_value=t_finding.evidence_strength,
                        )
                    )

                # Assessment rationale comparison
                if b_finding.assessment_rationale != t_finding.assessment_rationale:
                    field_diffs.append(
                        FieldDiff(
                            field_name="assessment_rationale",
                            baseline_value=list(b_finding.assessment_rationale),
                            target_value=list(t_finding.assessment_rationale),
                        )
                    )

                # Identified evidence comparison with canonical sorting
                b_ev = canonical_evidence_tuple(b_finding.identified_evidence)
                t_ev = canonical_evidence_tuple(t_finding.identified_evidence)
                if b_ev != t_ev:
                    field_diffs.append(
                        FieldDiff(
                            field_name="identified_evidence",
                            baseline_value=b_ev,
                            target_value=t_ev,
                        )
                    )

                # Basis comparison with canonical ordering to avoid serialization-order false positives
                b_bases = canonical_basis_tuple(b_finding.basis)
                t_bases = canonical_basis_tuple(t_finding.basis)
                if b_bases != t_bases:
                    field_diffs.append(
                        FieldDiff(
                            field_name="basis",
                            baseline_value=b_bases,
                            target_value=t_bases,
                        )
                    )

                # Cannot claim comparison with canonical sorting
                b_cc = tuple(sorted(b_finding.cannot_claim))
                t_cc = tuple(sorted(t_finding.cannot_claim))
                if b_cc != t_cc:
                    field_diffs.append(
                        FieldDiff(
                            field_name="cannot_claim",
                            baseline_value=b_finding.cannot_claim,
                            target_value=t_finding.cannot_claim,
                        )
                    )

                if field_diffs:
                    modified_count += 1
                    diff_kind = DiffKind.MODIFIED
                else:
                    unchanged_count += 1
                    diff_kind = DiffKind.UNCHANGED

                task_diffs.append(
                    TaskFindingDiff(
                        task_id=task_id,
                        diff_kind=diff_kind,
                        baseline_finding_id=b_finding.finding_id,
                        target_finding_id=t_finding.finding_id,
                        verdict_transition=(b_finding.coverage_verdict, t_finding.coverage_verdict),
                        changed_fields=tuple(field_diffs),
                    )
                )

        # 3. Merge and deduplicate claim boundaries
        merged_cb = sorted(set(baseline.claim_boundary) | set(target.claim_boundary))

        return AssessmentDiffRecord(
            baseline_id=baseline.id,
            target_id=target.id,
            target_metadata_diff=tuple(metadata_diffs),
            task_diffs=tuple(task_diffs),
            added_count=added_count,
            removed_count=removed_count,
            modified_count=modified_count,
            unchanged_count=unchanged_count,
            claim_boundary=tuple(merged_cb),
            provenance_verified=provenance_verified,
        )


class DeterministicDiffRenderer:
    """Renders AssessmentDiffRecord deterministically into Markdown or JSON without evaluative sentiment."""

    def render_json(self, record: AssessmentDiffRecord) -> str:
        return json.dumps(record.to_dict(), indent=2, sort_keys=True)

    def render_markdown(self, record: AssessmentDiffRecord) -> str:
        lines: list[str] = []
        lines.append(f"# Assessment Comparison Diff: `{record.baseline_id}` vs `{record.target_id}`")
        lines.append("")

        if not record.provenance_verified:
            lines.append("> [!WARNING]")
            lines.append("> **Provenance Verification: UNVERIFIED**")
            lines.append(
                "> This diff was generated without repository provenance verification (`--allow-unverified-provenance`)."
            )
            lines.append(
                "> Target repository commits, manifests, and corpus digests were NOT verified against real repositories."
            )
            lines.append("")

        # Claim boundary warning
        lines.append("> [!IMPORTANT]")
        lines.append("> **Claim Boundary Notice**:")
        lines.append("> Purely factual, deterministic comparison between assessment records without evaluative characterization.")
        lines.append("> Does not assert, verify, or certify any changes in security posture, control effectiveness, or adherence.")
        for cb in record.claim_boundary:
            lines.append(f"> - {cb}")
        lines.append("")

        # Summary section
        lines.append("## Comparison Summary")
        lines.append("")
        lines.append("| Added | Removed | Modified | Unchanged | Total Tasks |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        lines.append(
            f"| {record.added_count} | {record.removed_count} | {record.modified_count} | "
            f"{record.unchanged_count} | {len(record.task_diffs)} |"
        )
        lines.append("")

        # Target metadata changes
        if record.target_metadata_diff:
            lines.append("## Target Metadata Differences")
            lines.append("")
            lines.append("| Field | Baseline Value | Target Value |")
            lines.append("| :--- | :--- | :--- |")
            for fd in record.target_metadata_diff:
                b_display = f"`{fd.baseline_value}`" if fd.baseline_value is not None else "*(none)*"
                t_display = f"`{fd.target_value}`" if fd.target_value is not None else "*(none)*"
                lines.append(f"| `{fd.field_name}` | {b_display} | {t_display} |")
            lines.append("")
        else:
            lines.append("## Target Metadata Differences")
            lines.append("")
            lines.append("No differences in target metadata.")
            lines.append("")

        # Task comparison section
        lines.append("## Task Status Transitions")
        lines.append("")
        lines.append("| Task ID | Status | Baseline Verdict | Target Verdict | Changed Fields |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for td in record.task_diffs:
            b_v = f"`{td.verdict_transition[0]}`" if td.verdict_transition[0] else "*(none)*"
            t_v = f"`{td.verdict_transition[1]}`" if td.verdict_transition[1] else "*(none)*"
            if td.changed_fields:
                fields_str = ", ".join(f"`{f.field_name}`" for f in td.changed_fields)
            else:
                fields_str = "-"
            lines.append(f"| `{td.task_id}` | `{td.diff_kind.value}` | {b_v} | {t_v} | {fields_str} |")
        lines.append("")

        return "\n".join(lines).strip() + "\n"
