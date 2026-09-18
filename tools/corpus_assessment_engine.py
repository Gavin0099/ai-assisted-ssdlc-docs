from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from tools.repo_corpus_resolver import CorpusSnapshot

COMMIT_HEX_REGEX = re.compile(r"^[0-9a-f]{40}$")
DIGEST_HEX_REGEX = re.compile(r"^[0-9a-f]{64}$")


class CorpusAssessmentError(Exception):
    """Base exception for corpus assessment errors."""


class SourceRefNotFoundError(CorpusAssessmentError):
    """Raised when a company_source_ref points to a file not present in the corpus."""


class CorpusDigestMismatchError(CorpusAssessmentError):
    """Raised when the declared corpus_digest does not match the actual snapshot digest."""


@dataclass(frozen=True)
class CorpusAssessmentTarget:
    repo: str
    commit: str
    manifest_path: str
    manifest_digest: str
    corpus_digest: str
    target_type: str = "repository_corpus"

    def __post_init__(self) -> None:
        if not self.repo or not self.repo.strip():
            raise CorpusAssessmentError("Target repo must be a non-empty string.")
        if not COMMIT_HEX_REGEX.match(self.commit):
            raise CorpusAssessmentError(f"Target commit must be a 40-character hex SHA: {self.commit!r}")
        if not self.manifest_path or not self.manifest_path.strip():
            raise CorpusAssessmentError("Target manifest_path must be a non-empty string.")
        if not DIGEST_HEX_REGEX.match(self.manifest_digest):
            raise CorpusAssessmentError(f"Target manifest_digest must be a 64-character hex SHA-256: {self.manifest_digest!r}")
        if not DIGEST_HEX_REGEX.match(self.corpus_digest):
            raise CorpusAssessmentError(f"Target corpus_digest must be a 64-character hex SHA-256: {self.corpus_digest!r}")


@dataclass(frozen=True)
class CorpusAssessmentBasis:
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
class IdentifiedEvidence:
    type: str
    source_ref: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "source_ref": self.source_ref}


@dataclass(frozen=True)
class CorpusTaskFinding:
    finding_id: str
    task_id: str
    company_source_ref: str
    company_statement: str
    coverage_verdict: str
    basis: list[CorpusAssessmentBasis]
    assessment_rationale: list[str]
    identified_evidence: list[IdentifiedEvidence]
    evidence_strength: str
    review_queue_recommendation: str
    cannot_claim: list[str]
    finding_type: str = "task_finding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "finding_type": self.finding_type,
            "task_id": self.task_id,
            "company_source_ref": self.company_source_ref,
            "company_statement": self.company_statement,
            "coverage_verdict": self.coverage_verdict,
            "basis": [b.to_dict() for b in self.basis],
            "assessment_rationale": list(self.assessment_rationale),
            "identified_evidence": [e.to_dict() for e in self.identified_evidence],
            "evidence_strength": self.evidence_strength,
            "review_queue_recommendation": self.review_queue_recommendation,
            "cannot_claim": list(self.cannot_claim),
        }


@dataclass(frozen=True)
class CorpusAssessmentReport:
    id: str
    baseline: str
    target: CorpusAssessmentTarget
    scope_tasks: list[str]
    claim_boundary: list[str]
    findings: list[CorpusTaskFinding]

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment": {
                "id": self.id,
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
            },
            "results": [f.to_dict() for f in self.findings],
        }

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), sort_keys=False, allow_unicode=True)


class ICorpusSourceRefValidator(Protocol):
    def validate_source_ref(
        self,
        snapshot: CorpusSnapshot,
        source_ref: str,
        coverage_verdict: str | None = None,
    ) -> None:
        """Validate that a source_ref points to an existing file in the corpus snapshot."""
        ...


class ICorpusAssessmentEngine(Protocol):
    def evaluate(
        self,
        snapshot: CorpusSnapshot,
        target: CorpusAssessmentTarget,
        scope_tasks: list[str],
    ) -> CorpusAssessmentReport:
        """Evaluate the corpus snapshot against SSDF scope tasks."""
        ...


class StrictCorpusSourceRefValidator:
    """Validates that company_source_ref paths strictly exist within the corpus snapshot."""

    def validate_source_ref(
        self,
        snapshot: CorpusSnapshot,
        source_ref: str,
        coverage_verdict: str | None = None,
    ) -> None:
        if not source_ref or not source_ref.strip():
            raise SourceRefNotFoundError("Empty company_source_ref is not allowed.")

        # Sentinel check: <corpus>#unmentioned is strictly allowed ONLY for MISSING or UNRESOLVED
        if source_ref.startswith("<corpus>"):
            if coverage_verdict is not None and coverage_verdict not in ("MISSING", "UNRESOLVED"):
                raise CorpusAssessmentError(
                    f"Sentinel '<corpus>#unmentioned' is not permitted for coverage_verdict {coverage_verdict!r}; "
                    "verdicts with claimed or partial coverage must reference an actual corpus file."
                )
            return

        # Extract file path before anchor '#'
        file_path = source_ref.split("#", 1)[0].strip()
        # Normalize slashes
        file_path = file_path.replace("\\", "/")

        snapshot_paths = set(snapshot.paths())
        if file_path not in snapshot_paths:
            raise SourceRefNotFoundError(
                f"Source reference path {file_path!r} not found in materialized corpus snapshot. "
                f"Available paths: {sorted(snapshot_paths)}"
            )


def validate_corpus_assessment_provenance(
    snapshot: CorpusSnapshot,
    target: CorpusAssessmentTarget,
) -> None:
    """Ensure that the target provenance perfectly matches the materialized snapshot."""
    if snapshot.target_commit != target.commit:
        raise CorpusAssessmentError(
            f"Snapshot commit {snapshot.target_commit} does not match target commit {target.commit}"
        )
    if snapshot.corpus_digest != target.corpus_digest:
        raise CorpusDigestMismatchError(
            f"Snapshot corpus_digest {snapshot.corpus_digest} does not match target corpus_digest {target.corpus_digest}"
        )


def validate_report_against_snapshot(
    report: CorpusAssessmentReport,
    snapshot: CorpusSnapshot,
    source_ref_validator: ICorpusSourceRefValidator | None = None,
) -> None:
    """Validates the entire assessment report against the given materialized corpus snapshot."""
    validate_corpus_assessment_provenance(snapshot, report.target)

    if not report.findings:
        raise CorpusAssessmentError("Corpus assessment report must contain at least one finding.")

    validator = source_ref_validator or StrictCorpusSourceRefValidator()
    for finding in report.findings:
        validator.validate_source_ref(
            snapshot,
            finding.company_source_ref,
            coverage_verdict=finding.coverage_verdict,
        )


def parse_corpus_assessment_dict(data: dict[str, Any]) -> CorpusAssessmentReport:
    """Parses a dictionary into a validated CorpusAssessmentReport domain object."""
    if not isinstance(data, dict):
        raise CorpusAssessmentError("Assessment data must be a dictionary.")

    hdr = data.get("assessment")
    if not isinstance(hdr, dict):
        raise CorpusAssessmentError("Missing or invalid 'assessment' header mapping.")

    target_raw = hdr.get("target")
    if not isinstance(target_raw, dict):
        raise CorpusAssessmentError("assessment.target must be a mapping for repository corpus assessment.")

    target = CorpusAssessmentTarget(
        repo=str(target_raw.get("repo", "")),
        commit=str(target_raw.get("commit", "")),
        manifest_path=str(target_raw.get("manifest_path", "")),
        manifest_digest=str(target_raw.get("manifest_digest", "")),
        corpus_digest=str(target_raw.get("corpus_digest", "")),
        target_type=str(target_raw.get("type", "repository_corpus")),
    )

    results_raw = data.get("results")
    if not isinstance(results_raw, list):
        raise CorpusAssessmentError("Assessment results must be a list of findings.")

    findings: list[CorpusTaskFinding] = []
    for item in results_raw:
        if not isinstance(item, dict):
            raise CorpusAssessmentError("Each finding in results must be a mapping.")

        basis_items: list[CorpusAssessmentBasis] = []
        for b in item.get("basis", []):
            if isinstance(b, dict):
                basis_items.append(
                    CorpusAssessmentBasis(
                        type=str(b.get("type", "")),
                        rationale=str(b.get("rationale", "")),
                        task_id=b.get("task_id"),
                        source=b.get("source"),
                    )
                )

        evidence_items: list[IdentifiedEvidence] = []
        for e in item.get("identified_evidence", []):
            if isinstance(e, dict):
                evidence_items.append(
                    IdentifiedEvidence(
                        type=str(e.get("type", "")),
                        source_ref=str(e.get("source_ref", "")),
                    )
                )

        finding = CorpusTaskFinding(
            finding_id=str(item.get("finding_id", "")),
            finding_type=str(item.get("finding_type", "task_finding")),
            task_id=str(item.get("task_id", "")),
            company_source_ref=str(item.get("company_source_ref", "")),
            company_statement=str(item.get("company_statement", "")),
            coverage_verdict=str(item.get("coverage_verdict", "")),
            basis=basis_items,
            assessment_rationale=list(item.get("assessment_rationale", [])),
            identified_evidence=evidence_items,
            evidence_strength=str(item.get("evidence_strength", "")),
            review_queue_recommendation=str(item.get("review_queue_recommendation", "")),
            cannot_claim=list(item.get("cannot_claim", [])),
        )
        findings.append(finding)

    return CorpusAssessmentReport(
        id=str(hdr.get("id", "")),
        baseline=str(hdr.get("baseline", "")),
        target=target,
        scope_tasks=list(hdr.get("scope_tasks", [])),
        claim_boundary=list(hdr.get("claim_boundary", [])),
        findings=findings,
    )
