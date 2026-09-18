import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

ROOT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import yaml

from tools.corpus_assessment_engine import (
    CorpusAssessmentError,
    CorpusAssessmentReport,
    CorpusAssessmentTarget,
    ICorpusSourceRefValidator,
    StrictCorpusSourceRefValidator,
    parse_corpus_assessment_dict,
    validate_report_against_snapshot,
)
from tools.repo_corpus_resolver import IRepoCorpusResolver, RepoCorpusResolver
from tools.validate_ssdf_assessment import (
    DEFAULT_EVIDENCE_SCHEMA,
    DEFAULT_REVIEW_QUEUE_SCHEMA,
    DEFAULT_TASKS_REF,
    validate_ssdf_assessment,
)
from tools.validate_target_manifest import parse_target_manifest, validate_target_manifest_file

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
    provenance_verified: bool = True

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
            "provenance_verified": self.provenance_verified,
            "scope_tasks": list(self.scope_tasks),
            "claim_boundary": list(self.claim_boundary),
            "findings": [f.to_dict() for f in self.findings],
            "observations": [obs.to_dict() for obs in self.observations],
        }
        return d


class ReviewOrchestrationError(Exception):
    """Base exception for review reporting orchestration."""


SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_safe_output_name(assessment_id: str) -> None:
    """Validate that an assessment_id is safe to use as a file name component without path traversal."""
    if not assessment_id or not assessment_id.strip():
        raise ReviewOrchestrationError("Assessment ID cannot be empty.")
    if not SAFE_FILENAME_REGEX.match(assessment_id) or ".." in assessment_id:
        raise ReviewOrchestrationError(
            f"Assessment ID contains path traversal or invalid characters for output filename: {assessment_id!r}"
        )


class ReviewValidationError(ReviewOrchestrationError):
    """Raised when assessment YAML fails linter/schema validation."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


class ReviewProvenanceError(ReviewOrchestrationError):
    """Raised when target provenance or corpus snapshot validation fails."""


class IReviewReportOrchestrator(Protocol):
    def orchestrate(
        self,
        assessment_path: Path,
        manifest_path: Path | None = None,
        repo_path: Path | None = None,
        allow_unverified_provenance: bool = False,
        tasks_ref: Path | None = None,
        evidence_schema: Path | None = None,
        review_queue_schema: Path | None = None,
    ) -> ReadOnlyReviewRecord:
        """Validates input, materializes domain models, and projects to review record."""
        ...


class IReadOnlyReviewProjector(Protocol):
    def project(
        self, report: CorpusAssessmentReport, provenance_verified: bool = True
    ) -> ReadOnlyReviewRecord:
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
    1. Bit-for-bit reproducibility via deterministic ordering (task_id, finding_id, basis tie-breakers).
    2. Zero evaluative inference: never changes verdicts or infers closure.
    3. Dimension preservation: keeps verdict, strength, recommendation, basis, cannot_claim, and source_ref separate.

    Note:
        Expects a structurally and contractually validated CorpusAssessmentReport.
        Validation orchestration is the responsibility of the caller (e.g. S1-D2 CLI).
    """

    def project(
        self, report: CorpusAssessmentReport, provenance_verified: bool = True
    ) -> ReadOnlyReviewRecord:
        sorted_findings: list[ReadOnlyReviewFindingRecord] = []
        for finding in sorted(report.findings, key=lambda f: (f.task_id, f.finding_id)):
            sorted_basis = sorted(
                finding.basis,
                key=lambda b: (
                    BASIS_PRIORITY.get(b.type, 99),
                    b.rationale,
                    b.task_id or "",
                    b.source or "",
                ),
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
            provenance_verified=provenance_verified,
        )


def _escape_markdown_table_cell(val: str) -> str:
    """Escapes pipe delimiters and collapses newlines for Markdown table cells."""
    return val.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").replace("\r", "").strip()


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
            f"- **Provenance Verified**: `{'true' if record.provenance_verified else 'false'}`",
            f"- **Total Scoped Tasks**: `{len(record.scope_tasks)}`",
            f"- **Total Findings**: `{len(record.findings)}`",
            f"- **Total Observations**: `{len(record.observations)}`",
            "",
        ]

        if not record.provenance_verified:
            lines.extend([
                "> [!WARNING]",
                "> **Provenance Verification: UNVERIFIED**",
                "> This report was generated without verifying repository commit, manifest digest, corpus digest, or file existence against the actual target repository.",
                "",
            ])

        lines.extend([
            "## Claim Boundary & Non-Claims",
            "",
        ])


        for cb in record.claim_boundary:
            cb_clean = cb.strip()
            if not cb_clean:
                continue
            lines.append("> [!IMPORTANT]")
            for line in cb_clean.splitlines():
                lines.append(f"> {line}" if line else ">")
            lines.append("")

        lines.extend([
            "## Findings Summary",
            "",
            "| Task ID | Finding ID | Verdict | Evidence Strength | Queue Recommendation | Source Reference |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for f in record.findings:
            esc_task = _escape_markdown_table_cell(f.task_id)
            esc_fid = _escape_markdown_table_cell(f.finding_id)
            esc_verdict = _escape_markdown_table_cell(f.coverage_verdict)
            esc_strength = _escape_markdown_table_cell(f.evidence_strength)
            esc_rq = _escape_markdown_table_cell(f.review_queue_recommendation)
            esc_ref = _escape_markdown_table_cell(f.company_source_ref)
            lines.append(
                f"| `{esc_task}` | `{esc_fid}` | `{esc_verdict}` | `{esc_strength}` | `{esc_rq}` | `{esc_ref}` |"
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


class ReviewReportOrchestrator:
    """Orchestrates validation, domain loading, snapshot verification, and projection."""

    def __init__(
        self,
        projector: IReadOnlyReviewProjector | None = None,
        corpus_resolver: IRepoCorpusResolver | None = None,
        source_ref_validator: ICorpusSourceRefValidator | None = None,
    ) -> None:
        self.projector = projector or ReadOnlyReviewProjector()
        self.corpus_resolver = corpus_resolver or RepoCorpusResolver()
        self.source_ref_validator = source_ref_validator or StrictCorpusSourceRefValidator()

    def orchestrate(
        self,
        assessment_path: Path,
        manifest_path: Path | None = None,
        repo_path: Path | None = None,
        allow_unverified_provenance: bool = False,
        tasks_ref: Path | None = None,
        evidence_schema: Path | None = None,
        review_queue_schema: Path | None = None,
    ) -> ReadOnlyReviewRecord:
        assessment_path = Path(assessment_path)
        if not assessment_path.is_file():
            raise ReviewValidationError([f"Assessment file not found: {assessment_path}"])

        # 1. Structural and linter validation via validate_ssdf_assessment
        validation_errors = validate_ssdf_assessment(
            assessment_path,
            tasks_ref=tasks_ref or DEFAULT_TASKS_REF,
            evidence_schema=evidence_schema or DEFAULT_EVIDENCE_SCHEMA,
            review_queue_schema=review_queue_schema or DEFAULT_REVIEW_QUEUE_SCHEMA,
        )
        if validation_errors:
            raise ReviewValidationError(validation_errors)

        # 2. Parse YAML and load into CorpusAssessmentReport domain object
        try:
            with open(assessment_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            raise ReviewValidationError([f"Failed to read or parse YAML: {e}"])

        try:
            report = parse_corpus_assessment_dict(data)
        except CorpusAssessmentError as e:
            raise ReviewValidationError([f"Corpus assessment schema error: {e}"])

        # Validate navigation manifest_path does not escape with .. or absolute path
        nav_manifest_path = Path(report.target.manifest_path)
        if nav_manifest_path.is_absolute() or ".." in nav_manifest_path.parts:
            raise ReviewProvenanceError(
                f"assessment.target.manifest_path must be a clean relative path without traversal: {report.target.manifest_path!r}"
            )

        # 3. Provenance and Trust Boundary Check
        provenance_verified = False
        if report.target.target_type == "repository_corpus":
            if not allow_unverified_provenance:
                if manifest_path is None or repo_path is None:
                    raise ReviewProvenanceError(
                        "Repository corpus assessment requires both --manifest and --repo-path for full provenance verification. "
                        "To explicitly produce an unverified report, specify --allow-unverified-provenance."
                    )

            if manifest_path is not None and repo_path is not None:
                repo_path_obj = Path(repo_path).resolve()
                if not repo_path_obj.is_dir():
                    raise ReviewProvenanceError(
                        f"Target repository directory not found: {repo_path_obj}"
                    )

                manifest_file = Path(manifest_path).resolve()
                if not manifest_file.is_file():
                    raise ReviewProvenanceError(
                        f"Target manifest file not found: {manifest_file}"
                    )

                if not manifest_file.is_relative_to(repo_path_obj):
                    raise ReviewProvenanceError(
                        f"Target manifest {manifest_file} is located outside target repository {repo_path_obj}"
                    )

                manifest_errors = validate_target_manifest_file(manifest_file)
                if manifest_errors:
                    raise ReviewProvenanceError(
                        f"Target manifest validation failed: {manifest_errors}"
                    )

                try:
                    manifest_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
                    manifest = parse_target_manifest(manifest_data)
                except Exception as e:
                    raise ReviewProvenanceError(f"Failed to parse target manifest: {e}")

                if manifest.digest != report.target.manifest_digest:
                    raise ReviewProvenanceError(
                        f"Target manifest digest mismatch: manifest file computed {manifest.digest}, "
                        f"assessment declared {report.target.manifest_digest}"
                    )

                try:
                    snapshot = self.corpus_resolver.resolve(
                        manifest=manifest,
                        repo_path=repo_path_obj,
                    )
                    validate_report_against_snapshot(report, snapshot, self.source_ref_validator)
                except Exception as e:
                    raise ReviewProvenanceError(str(e))

                provenance_verified = True

        # 4. Pure deterministic projection
        return self.projector.project(report, provenance_verified=provenance_verified)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic Review Engine CLI for SSDF repository corpus assessments."
    )
    parser.add_argument("target", type=Path, help="Path to assessment YAML file")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path to authoritative target manifest YAML file (required for repository_corpus unless --allow-unverified-provenance)",
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="Path to repository root (required for repository_corpus unless --allow-unverified-provenance)",
    )
    parser.add_argument(
        "--allow-unverified-provenance",
        action="store_true",
        help="Explicitly permit generating a review report without repository provenance verification",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default=None,
        help="Output report format (markdown, json, or both)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory to write rendered review reports",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print rendered report to standard output stream",
    )
    parser.add_argument(
        "--reference",
        "--tasks-ref",
        dest="tasks_ref",
        type=Path,
        default=DEFAULT_TASKS_REF,
        help="Path to authoritative NIST SSDF tasks reference YAML",
    )
    parser.add_argument(
        "--evidence-schema",
        type=Path,
        default=DEFAULT_EVIDENCE_SCHEMA,
        help="Path to evidence record schema YAML",
    )
    parser.add_argument(
        "--review-queue-schema",
        type=Path,
        default=DEFAULT_REVIEW_QUEUE_SCHEMA,
        help="Path to review queue schema YAML",
    )

    args = parser.parse_args(argv)

    # Resolution of default output behavior:
    # If neither --out-dir nor --stdout is specified, default to --stdout
    if not args.out_dir and not args.stdout:
        args.stdout = True

    # Validate output format constraints
    if args.stdout and args.format == "both":
        sys.stderr.write("Error: --format both cannot be used with --stdout; choose markdown or json.\n")
        return 1

    selected_format = args.format
    if selected_format is None:
        selected_format = "both" if args.out_dir else "markdown"

    orchestrator = ReviewReportOrchestrator()
    try:
        record = orchestrator.orchestrate(
            assessment_path=args.target,
            manifest_path=args.manifest,
            repo_path=args.repo_path,
            allow_unverified_provenance=args.allow_unverified_provenance,
            tasks_ref=args.tasks_ref,
            evidence_schema=args.evidence_schema,
            review_queue_schema=args.review_queue_schema,
        )
    except ReviewValidationError as exc:
        sys.stderr.write("Review Validation Failed:\n")
        for err in exc.errors:
            sys.stderr.write(f"  - {err}\n")
        return 1
    except ReviewProvenanceError as exc:
        sys.stderr.write(f"Review Provenance Validation Failed: {exc}\n")
        return 1
    except ReviewOrchestrationError as exc:
        sys.stderr.write(f"Review Orchestration Failed: {exc}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"Unexpected error during review orchestration: {exc}\n")
        return 1

    renderer = DeterministicReviewReportRenderer()

    # Handle --stdout
    if args.stdout:
        if selected_format == "json":
            sys.stdout.write(renderer.render_json(record) + "\n")
        else:
            sys.stdout.write(renderer.render_markdown(record))

    # Handle --out-dir with safe filename containment validation
    if args.out_dir:
        try:
            _validate_safe_output_name(record.assessment_id)
        except ReviewOrchestrationError as exc:
            sys.stderr.write(f"Output path validation failed: {exc}\n")
            return 1

        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        assessment_id = record.assessment_id

        if selected_format in ("markdown", "both"):
            md_path = (out_dir / f"{assessment_id}.review.md").resolve()
            if not md_path.is_relative_to(out_dir):
                sys.stderr.write(f"Output path validation failed: {md_path} escapes output directory {out_dir}\n")
                return 1
            md_path.write_text(renderer.render_markdown(record), encoding="utf-8")

        if selected_format in ("json", "both"):
            json_path = (out_dir / f"{assessment_id}.review.json").resolve()
            if not json_path.is_relative_to(out_dir):
                sys.stderr.write(f"Output path validation failed: {json_path} escapes output directory {out_dir}\n")
                return 1
            json_path.write_text(renderer.render_json(record) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())


