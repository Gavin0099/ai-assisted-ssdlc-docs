#!/usr/bin/env python3
"""Review Queue Action Projection Layer (Phase S1-D4).

Projects assessment findings and non-normative observations deterministically into
reviewer action views and queue action candidates.
Strictly read-only; never mutates or overwrites human-maintained review queue files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from tools.corpus_assessment_engine import (
    CorpusAssessmentReport,
    CorpusObservation,
    CorpusTaskFinding,
)


class ReviewQueueProjectionError(ValueError):
    """Raised when queue projection encounters unsupported recommendations or invalid data."""

    pass


class ActionPriority(str, Enum):
    """Categorization of queue action urgency projected from assessment recommendations."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


PRIORITY_WEIGHT: dict[ActionPriority, int] = {
    ActionPriority.HIGH: 1,
    ActionPriority.MEDIUM: 2,
    ActionPriority.LOW: 3,
}

TASK_RECOMMENDATION_MAPPING: dict[str, tuple[ActionPriority, str]] = {
    "needs_changes": (
        ActionPriority.HIGH,
        "Open review queue item: policy or evidence revision required for {task_id}.",
    ),
    "rejected": (
        ActionPriority.HIGH,
        "Open review queue item: rejected evidence or statement requires replacement for {task_id}.",
    ),
    "accepted_with_review_due": (
        ActionPriority.MEDIUM,
        "Schedule due review: accepted with periodic review obligation for {task_id}.",
    ),
    "pending": (
        ActionPriority.MEDIUM,
        "Track pending review: awaiting human reviewer assessment for {task_id}.",
    ),
    "deferred": (
        ActionPriority.LOW,
        "Log deferred item: review postponed for {task_id}.",
    ),
    "accepted": (
        ActionPriority.LOW,
        "Retain record: findings accepted without immediate queue action for {task_id}.",
    ),
}

# Retain RECOMMENDATION_MAPPING for backwards compatibility
RECOMMENDATION_MAPPING = TASK_RECOMMENDATION_MAPPING

OBSERVATION_RECOMMENDATION_MAPPING: dict[str, tuple[ActionPriority, str]] = {
    "needs_changes": (
        ActionPriority.HIGH,
        "Open review queue item: review observation finding {finding_id} for necessary adjustments.",
    ),
    "rejected": (
        ActionPriority.HIGH,
        "Open review queue item: rejected observation statement requires replacement for {finding_id}.",
    ),
    "accepted_with_review_due": (
        ActionPriority.MEDIUM,
        "Schedule due review: observation accepted with periodic review obligation for {finding_id}.",
    ),
    "pending": (
        ActionPriority.MEDIUM,
        "Track pending review: awaiting human reviewer assessment for observation {finding_id}.",
    ),
    "deferred": (
        ActionPriority.LOW,
        "Log deferred item: observation review postponed for {finding_id}.",
    ),
    "accepted": (
        ActionPriority.LOW,
        "Retain record: observation accepted without immediate queue action for {finding_id}.",
    ),
}


@dataclass(frozen=True)
class ReviewQueueActionItem:
    """Represents a deterministic action candidate projected from a task finding or observation."""

    source_kind: str  # "task_finding" | "non_normative_observation"
    finding_id: str
    review_queue_recommendation: str
    action_priority: ActionPriority
    suggested_action: str
    company_source_ref: str
    basis_summary: str
    cannot_claim: tuple[str, ...]
    task_id: str | None = None
    coverage_verdict: str | None = None
    evidence_strength: str | None = None
    observation_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "source_kind": self.source_kind,
            "finding_id": self.finding_id,
            "review_queue_recommendation": self.review_queue_recommendation,
            "action_priority": self.action_priority.value,
            "suggested_action": self.suggested_action,
            "company_source_ref": self.company_source_ref,
            "basis_summary": self.basis_summary,
            "cannot_claim": list(self.cannot_claim),
        }
        if self.task_id is not None:
            d["task_id"] = self.task_id
        if self.coverage_verdict is not None:
            d["coverage_verdict"] = self.coverage_verdict
        if self.evidence_strength is not None:
            d["evidence_strength"] = self.evidence_strength
        if self.observation_text is not None:
            d["observation_text"] = self.observation_text
        return d


@dataclass(frozen=True)
class ReviewQueueProjectionRecord:
    """Aggregate root for the review queue action view."""

    assessment_id: str
    target_repo: str
    target_commit: str
    action_items: tuple[ReviewQueueActionItem, ...]
    needs_action_count: int
    informational_count: int
    claim_boundary: tuple[str, ...]
    provenance_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "target_repo": self.target_repo,
            "target_commit": self.target_commit,
            "provenance_verified": self.provenance_verified,
            "summary": {
                "needs_action_count": self.needs_action_count,
                "informational_count": self.informational_count,
                "total_action_items": len(self.action_items),
            },
            "action_items": [item.to_dict() for item in self.action_items],
            "claim_boundary": list(self.claim_boundary),
        }


class IReviewQueueProjector(Protocol):
    """Interface for projecting assessment recommendations into review queue actions."""

    def project_queue(
        self,
        report: CorpusAssessmentReport,
        provenance_verified: bool = False,
    ) -> ReviewQueueProjectionRecord:
        """Projects assessment recommendations into deterministic review queue action items."""
        ...


class ReviewQueueProjector:
    """Deterministic, read-only implementation of review queue action projection."""

    def project_queue(
        self,
        report: CorpusAssessmentReport,
        provenance_verified: bool = False,
    ) -> ReviewQueueProjectionRecord:
        items: list[ReviewQueueActionItem] = []
        needs_action_count = 0
        informational_count = 0

        # Project task findings
        for finding in report.findings:
            rec = finding.review_queue_recommendation
            if rec not in TASK_RECOMMENDATION_MAPPING:
                raise ReviewQueueProjectionError(
                    f"Unsupported review queue recommendation '{rec}' for task finding '{finding.finding_id}'. "
                    f"Cannot infer queue action priority."
                )

            priority, action_template = TASK_RECOMMENDATION_MAPPING[rec]
            suggested_action = action_template.format(task_id=finding.task_id, finding_id=finding.finding_id)

            if priority in (ActionPriority.HIGH, ActionPriority.MEDIUM):
                needs_action_count += 1
            else:
                informational_count += 1

            basis_summary = "; ".join(b.rationale for b in finding.basis if b.rationale)

            items.append(
                ReviewQueueActionItem(
                    source_kind="task_finding",
                    task_id=finding.task_id,
                    finding_id=finding.finding_id,
                    coverage_verdict=finding.coverage_verdict,
                    review_queue_recommendation=rec,
                    action_priority=priority,
                    suggested_action=suggested_action,
                    company_source_ref=finding.company_source_ref,
                    evidence_strength=finding.evidence_strength,
                    basis_summary=basis_summary,
                    cannot_claim=tuple(finding.cannot_claim),
                )
            )

        # Project non-normative observations
        for obs in report.observations:
            rec = obs.review_queue_recommendation
            if rec not in OBSERVATION_RECOMMENDATION_MAPPING:
                raise ReviewQueueProjectionError(
                    f"Unsupported review queue recommendation '{rec}' for observation '{obs.finding_id}'. "
                    f"Cannot infer queue action priority."
                )

            priority, action_template = OBSERVATION_RECOMMENDATION_MAPPING[rec]
            suggested_action = action_template.format(finding_id=obs.finding_id)

            if priority in (ActionPriority.HIGH, ActionPriority.MEDIUM):
                needs_action_count += 1
            else:
                informational_count += 1

            items.append(
                ReviewQueueActionItem(
                    source_kind="non_normative_observation",
                    task_id=None,
                    finding_id=obs.finding_id,
                    coverage_verdict=None,
                    review_queue_recommendation=rec,
                    action_priority=priority,
                    suggested_action=suggested_action,
                    company_source_ref=obs.company_source_ref,
                    evidence_strength=None,
                    basis_summary=obs.basis,
                    cannot_claim=tuple(obs.cannot_claim),
                    observation_text=obs.observation,
                )
            )

        # Deterministic sorting: priority weight -> source_kind rank -> sort_key -> finding_id
        items.sort(
            key=lambda x: (
                PRIORITY_WEIGHT.get(x.action_priority, 99),
                0 if x.source_kind == "task_finding" else 1,
                x.task_id or x.finding_id,
                x.finding_id,
            )
        )

        return ReviewQueueProjectionRecord(
            assessment_id=report.id,
            target_repo=report.target.repo,
            target_commit=report.target.commit,
            action_items=tuple(items),
            needs_action_count=needs_action_count,
            informational_count=informational_count,
            claim_boundary=tuple(report.claim_boundary),
            provenance_verified=provenance_verified,
        )


class DeterministicQueueActionRenderer:
    """Renders ReviewQueueProjectionRecord deterministically into Markdown or JSON."""

    def render_json(self, record: ReviewQueueProjectionRecord) -> str:
        return json.dumps(record.to_dict(), indent=2, sort_keys=True)

    def render_markdown(self, record: ReviewQueueProjectionRecord) -> str:
        lines: list[str] = []
        lines.append(f"# Review Queue Action Projection: `{record.assessment_id}`")
        lines.append("")
        lines.append(f"- **Target Repository**: `{record.target_repo}`")
        lines.append(f"- **Target Commit**: `{record.target_commit}`")
        lines.append("")

        if not record.provenance_verified:
            lines.append("> [!WARNING]")
            lines.append("> **Provenance Verification: UNVERIFIED**")
            lines.append(
                "> This review queue action projection was generated without repository provenance verification (`--allow-unverified-provenance`)."
            )
            lines.append(
                "> Target repository commits, manifests, and corpus digests were NOT verified against real repositories."
            )
            lines.append("")

        # Claim boundary notice - multiline preservation pattern
        lines.append("> [!IMPORTANT]")
        lines.append("> **Claim Boundary Notice**:")
        lines.append(
            "> Purely deterministic projection of assessment recommendations into reviewer action view."
        )
        lines.append(
            "> Read-only view; does not modify review queue, resolve items, or certify compliance."
        )
        for cb in record.claim_boundary:
            cb_clean = cb.strip()
            if not cb_clean:
                continue
            for idx, line in enumerate(cb_clean.splitlines()):
                if idx == 0:
                    lines.append(f"> - {line}" if line else "> -")
                else:
                    lines.append(f">   {line}" if line else ">")
        lines.append("")

        # Summary Section
        lines.append("## Action Summary")
        lines.append("")
        lines.append("| Needs Action (High/Medium) | Informational (Low) | Total Action Items |")
        lines.append("| :--- | :--- | :--- |")
        lines.append(
            f"| {record.needs_action_count} | {record.informational_count} | {len(record.action_items)} |"
        )
        lines.append("")

        # Action Items Table
        lines.append("## Projected Action Items")
        lines.append("")
        lines.append(
            "| Kind | Target / ID | Priority | Recommendation | Coverage | Suggested Action | Source Ref |"
        )
        lines.append(
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        )
        for item in record.action_items:
            escaped_action = item.suggested_action.replace("|", "\\|")
            escaped_ref = item.company_source_ref.replace("|", "\\|")
            if item.source_kind == "task_finding":
                target_str = f"`{item.task_id}` ({item.finding_id})"
                coverage_str = f"`{item.coverage_verdict}`"
            else:
                target_str = f"`{item.finding_id}`"
                coverage_str = "—"

            lines.append(
                f"| `{item.source_kind}` | {target_str} | **{item.action_priority.value}** | "
                f"`{item.review_queue_recommendation}` | {coverage_str} | {escaped_action} | `{escaped_ref}` |"
            )
        lines.append("")

        # Detailed Action Item Cards
        lines.append("## Action Item Details")
        lines.append("")
        for item in record.action_items:
            if item.source_kind == "task_finding":
                lines.append(f"### [Task] `{item.task_id}` — {item.finding_id} ({item.action_priority.value})")
                lines.append("")
                lines.append(f"- **Source Kind**: `{item.source_kind}`")
                lines.append(f"- **Suggested Action**: {item.suggested_action}")
                lines.append(f"- **Recommendation**: `{item.review_queue_recommendation}`")
                lines.append(f"- **Coverage Verdict**: `{item.coverage_verdict}`")
                lines.append(f"- **Evidence Strength**: `{item.evidence_strength}`")
                lines.append(f"- **Company Source Ref**: `{item.company_source_ref}`")
                if item.basis_summary:
                    lines.append(f"- **Basis Rationale**: {item.basis_summary}")
            else:
                lines.append(f"### [Observation] {item.finding_id} ({item.action_priority.value})")
                lines.append("")
                lines.append(f"- **Source Kind**: `{item.source_kind}`")
                lines.append(f"- **Suggested Action**: {item.suggested_action}")
                lines.append(f"- **Recommendation**: `{item.review_queue_recommendation}`")
                if item.observation_text:
                    lines.append(f"- **Observation**: {item.observation_text}")
                lines.append(f"- **Company Source Ref**: `{item.company_source_ref}`")
                if item.basis_summary:
                    lines.append(f"- **Basis**: `{item.basis_summary}`")

            if item.cannot_claim:
                lines.append("- **Cannot Claim Boundary**:")
                for cc in item.cannot_claim:
                    lines.append(f"  - {cc}")
            lines.append("")

        return "\n".join(lines)
