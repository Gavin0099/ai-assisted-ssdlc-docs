from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from tools.corpus_assessment_engine import (
    CorpusAssessmentReport,
    CorpusAssessmentTarget,
)

BASIS_PRIORITY: dict[str, int] = {
    "nist_normative": 1,
    "local_derived_guidance": 2,
    "reviewer_inference": 3,
}


@dataclass(frozen=True)
class ReviewBasisRecord:
    """Immutable record of an assessment basis preserving attribution."""

    type: str
    rationale: str
    task_id: str | None = None
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"type": self.type}
        if self.task_id:
            d["task_id"] = self.task_id
        if self.source:
            d["source"] = self.source
        d["rationale"] = self.rationale
        return d


@dataclass(frozen=True)
class ReviewEvidenceRecord:
    """Immutable record of identified policy or process evidence."""

    type: str
    source_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "source_ref": self.source_ref}


@dataclass(frozen=True)
class ReadOnlyReviewFindingRecord:
    """Reviewer view for an individual scoped task finding.

    Invariants:
        Maintains all 6 core evaluation dimensions independently.
        No roll-up or lossy reduction into a single risk/status field is permitted.
    """

    task_id: str
    finding_id: str
    coverage_verdict: str
    evidence_strength: str
    review_queue_recommendation: str
    company_source_ref: str
    company_statement: str
    basis: tuple[ReviewBasisRecord, ...]
    assessment_rationale: tuple[str, ...]
    identified_evidence: tuple[ReviewEvidenceRecord, ...]
    cannot_claim: tuple[str, ...]
    finding_type: str = "task_finding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "finding_id": self.finding_id,
            "finding_type": self.finding_type,
            "coverage_verdict": self.coverage_verdict,
            "evidence_strength": self.evidence_strength,
            "review_queue_recommendation": self.review_queue_recommendation,
            "company_source_ref": self.company_source_ref,
            "company_statement": self.company_statement,
            "basis": [b.to_dict() for b in self.basis],
            "assessment_rationale": list(self.assessment_rationale),
            "identified_evidence": [e.to_dict() for e in self.identified_evidence],
            "cannot_claim": list(self.cannot_claim),
        }


@dataclass(frozen=True)
class ReadOnlyReviewObservationRecord:
    """Reviewer view for a non-normative reviewer observation."""

    finding_id: str
    company_source_ref: str
    observation: str
    basis: str
    review_queue_recommendation: str
    cannot_claim: tuple[str, ...]
    finding_type: str = "non_normative_observation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "finding_type": self.finding_type,
            "company_source_ref": self.company_source_ref,
            "observation": self.observation,
            "basis": self.basis,
            "review_queue_recommendation": self.review_queue_recommendation,
            "cannot_claim": list(self.cannot_claim),
        }


@dataclass(frozen=True)
class ReadOnlyReviewRecord:
    """Aggregate root representing a fully projected, deterministically ordered review record."""

    assessment_id: str
    baseline: str
    target: CorpusAssessmentTarget
    scope_tasks: tuple[str, ...]
    claim_boundary: tuple[str, ...]
    findings: tuple[ReadOnlyReviewFindingRecord, ...]
    observations: tuple[ReadOnlyReviewObservationRecord, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "assessment_id": self.assessment_id,
            "baseline": self.baseline,
            "target": {
                "type": self.target.target_type,
                "repo": self.target.repo,
                "commit": self.target.commit,
                "manifest_path": self.target.manifest_path,
                "manifest_digest": self.target.manifest_digest,
                "corpus_digest": self.target.corpus_digest,
            },
            "scope_tasks": list(self.scope_tasks),
            "claim_boundary": list(self.claim_boundary),
            "findings": [f.to_dict() for f in self.findings],
        }
        if self.observations:
            d["observations"] = [obs.to_dict() for obs in self.observations]
        return d


class IReadOnlyReviewProjector(Protocol):
    def project(self, report: CorpusAssessmentReport) -> ReadOnlyReviewRecord:
        """Projects a validated assessment report into a deterministically ordered review record."""
        ...


class IReviewReportRenderer(Protocol):
    def render_markdown(self, record: ReadOnlyReviewRecord) -> str:
        """Renders the review record to deterministic markdown format."""
        ...

    def render_dict(self, record: ReadOnlyReviewRecord) -> dict[str, Any]:
        """Renders the review record to a dictionary representation."""
        ...

    def render_json(self, record: ReadOnlyReviewRecord) -> str:
        """Renders the review record to deterministic JSON."""
        ...


class ReadOnlyReviewProjector:
    """Deterministic, non-evaluative review projector.

    Guarantees:
    1. Bit-for-bit reproducibility via deterministic ordering (task_id, finding_id).
    2. Zero evaluative inference: never changes verdicts or infers closure.
    3. Dimension preservation: keeps verdict, strength, recommendation, basis, cannot_claim, and source_ref separate.
    """

    def project(self, report: CorpusAssessmentReport) -> ReadOnlyReviewRecord:
        sorted_findings: list[ReadOnlyReviewFindingRecord] = []
        for finding in sorted(report.findings, key=lambda f: (f.task_id, f.finding_id)):
            sorted_basis = sorted(
                finding.basis,
                key=lambda b: (BASIS_PRIORITY.get(b.type, 99), b.rationale),
            )
            basis_records = tuple(
                ReviewBasisRecord(
                    type=b.type,
                    rationale=b.rationale,
                    task_id=b.task_id,
                    source=b.source,
                )
                for b in sorted_basis
            )

            sorted_evidence = sorted(
                finding.identified_evidence,
                key=lambda e: (e.source_ref, e.type),
            )
            evidence_records = tuple(
                ReviewEvidenceRecord(
                    type=e.type,
                    source_ref=e.source_ref,
                )
                for e in sorted_evidence
            )

            sorted_findings.append(
                ReadOnlyReviewFindingRecord(
                    task_id=finding.task_id,
                    finding_id=finding.finding_id,
                    coverage_verdict=finding.coverage_verdict,
                    evidence_strength=finding.evidence_strength,
                    review_queue_recommendation=finding.review_queue_recommendation,
                    company_source_ref=finding.company_source_ref,
                    company_statement=finding.company_statement,
                    basis=basis_records,
                    assessment_rationale=tuple(finding.assessment_rationale),
                    identified_evidence=evidence_records,
                    cannot_claim=tuple(finding.cannot_claim),
                    finding_type=finding.finding_type,
                )
            )

        sorted_observations: list[ReadOnlyReviewObservationRecord] = []
        for obs in sorted(report.observations, key=lambda o: o.finding_id):
            sorted_observations.append(
                ReadOnlyReviewObservationRecord(
                    finding_id=obs.finding_id,
                    company_source_ref=obs.company_source_ref,
                    observation=obs.observation,
                    basis=obs.basis,
                    review_queue_recommendation=obs.review_queue_recommendation,
                    cannot_claim=tuple(obs.cannot_claim),
                    finding_type=obs.finding_type,
                )
            )

        return ReadOnlyReviewRecord(
            assessment_id=report.id,
            baseline=report.baseline,
            target=report.target,
            scope_tasks=tuple(sorted(report.scope_tasks)),
            claim_boundary=tuple(report.claim_boundary),
            findings=tuple(sorted_findings),
            observations=tuple(sorted_observations),
        )


class DeterministicReviewReportRenderer:
    """Renders ReadOnlyReviewRecord into deterministic Markdown and JSON formats."""

    def render_dict(self, record: ReadOnlyReviewRecord) -> dict[str, Any]:
        return record.to_dict()

    def render_json(self, record: ReadOnlyReviewRecord) -> str:
        return json.dumps(self.render_dict(record), indent=2, sort_keys=True, ensure_ascii=False)

    def render_markdown(self, record: ReadOnlyReviewRecord) -> str:
        lines: list[str] = [
            f"# SSDF Direct Assessment Review Report: {record.assessment_id}",
            "",
            "## Report Metadata",
            "",
            f"- **Target Repository**: `{record.target.repo}`",
            f"- **Commit SHA**: `{record.target.commit}`",
            f"- **Baseline**: `{record.baseline}`",
            f"- **Target Manifest**: `{record.target.manifest_path}`",
            f"- **Manifest Digest**: `{record.target.manifest_digest}`",
            f"- **Corpus Digest**: `{record.target.corpus_digest}`",
            f"- **Total Scoped Tasks**: `{len(record.scope_tasks)}`",
            f"- **Total Findings**: `{len(record.findings)}`",
            f"- **Total Observations**: `{len(record.observations)}`",
            "",
            "## Claim Boundary & Non-Claims",
            "",
        ]

        for cb in record.claim_boundary:
            lines.append(f"> [!IMPORTANT]\n> {cb}")
            lines.append("")

        lines.extend([
            "## Findings Summary",
            "",
            "| Task ID | Finding ID | Verdict | Evidence Strength | Queue Recommendation | Source Reference |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for f in record.findings:
            lines.append(
                f"| `{f.task_id}` | `{f.finding_id}` | `{f.coverage_verdict}` | `{f.evidence_strength}` | `{f.review_queue_recommendation}` | `{f.company_source_ref}` |"
            )

        lines.extend(["", "## Detailed Task Findings", ""])

        for f in record.findings:
            lines.append(f"### {f.task_id}: {f.finding_id}")
            lines.append("")
            lines.append(f"- **Coverage Verdict**: `{f.coverage_verdict}`")
            lines.append(f"- **Evidence Strength**: `{f.evidence_strength}`")
            lines.append(f"- **Review Queue Recommendation**: `{f.review_queue_recommendation}`")
            lines.append(f"- **Company Source Ref**: `{f.company_source_ref}`")
            lines.append(f"- **Company Statement**:\n  > {f.company_statement}")
            lines.append("")

            lines.append("- **Basis**:")
            for b in f.basis:
                attribution = f" ({b.source})" if b.source else ""
                task_tag = f" [{b.task_id}]" if b.task_id else ""
                lines.append(f"  - `{b.type}`{task_tag}{attribution}: {b.rationale}")

            lines.append("")
            lines.append("- **Assessment Rationale**:")
            for r in f.assessment_rationale:
                lines.append(f"  - {r}")

            if f.identified_evidence:
                lines.append("")
                lines.append("- **Identified Evidence**:")
                for e in f.identified_evidence:
                    lines.append(f"  - `{e.type}`: `{e.source_ref}`")

            lines.append("")
            lines.append("- **Cannot Claim**:")
            for cc in f.cannot_claim:
                lines.append(f"  - {cc}")

            lines.append("")

        if record.observations:
            lines.extend(["## Non-Normative Observations", ""])
            for obs in record.observations:
                lines.append(f"### Observation: {obs.finding_id}")
                lines.append("")
                lines.append(f"- **Source Reference**: `{obs.company_source_ref}`")
                lines.append(f"- **Basis**: `{obs.basis}`")
                lines.append(f"- **Queue Recommendation**: `{obs.review_queue_recommendation}`")
                lines.append(f"- **Observation**: {obs.observation}")
                if obs.cannot_claim:
                    lines.append("- **Cannot Claim**:")
                    for cc in obs.cannot_claim:
                        lines.append(f"  - {cc}")
                lines.append("")

        return "\n".join(lines).strip() + "\n"
