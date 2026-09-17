from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from _schema_rules import SchemaDefinitionError, load_schema, string_list

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TASKS_REF = ROOT / "references" / "nist-ssdf" / "v1.1" / "tasks.yaml"
DEFAULT_EVIDENCE_SCHEMA = ROOT / "schemas" / "evidence-record.schema.yaml"
DEFAULT_REVIEW_QUEUE_SCHEMA = ROOT / "schemas" / "review-queue.schema.yaml"

COVERAGE_VERDICTS = {
    "COVERED",
    "PARTIAL",
    "MISSING",
    "NOT_APPLICABLE",
    "UNRESOLVED",
}

ALLOWED_BASIS_TYPES = {
    "nist_normative",
    "local_derived_guidance",
    "reviewer_inference",
}

TASK_ID_REGEX = re.compile(r"^[A-Z]{2}\.\d+\.\d+$")

# Affirmative claim patterns that cannot be made by reviewer without proof.
# These regexes intentionally avoid bare words (like 'compliance', which appears in PW.8.1).
AFFIRMATIVE_PROHIBITED_PATTERNS = [
    # Compliance / Conformance
    re.compile(r"\b(?:is|are|was|were)\s+(?:fully\s+)?(?:nist\s+)?(?:ssdf\s+)?compliant\b", re.I),
    re.compile(r"\b(?:is|are|was|were)\s+(?:in\s+)?(?:nist\s+)?(?:ssdf\s+)?conformance\b", re.I),
    re.compile(r"\bconforms?\s+to\s+nist(?:\s+ssdf)?\b", re.I),
    re.compile(r"\bcompliant\s+with\s+nist(?:\s+ssdf)?\b", re.I),
    re.compile(r"\bfully\s+compliant\b", re.I),
    # Production Safety / Implementation
    re.compile(r"\bproduction\s+safe\b", re.I),
    re.compile(r"\bproduction\s+safety\b", re.I),
    re.compile(r"\bfully\s+implemented\b", re.I),
    # Vulnerability closure / Remediation completion
    re.compile(r"\b(?:all\s+)?vulnerabilities\s+(?:are|were)\s+fixed\b", re.I),
    re.compile(r"\bvulnerability\s+(?:is|was)\s+fixed\b", re.I),
    re.compile(r"\bvulnerabilities\s+(?:are|were)\s+remediated\b", re.I),
    re.compile(r"\bremediation\s+(?:is|was)\s+complete(?:d)?\b", re.I),
    # Risk closure
    re.compile(r"\brisk(?:s)?\s+(?:is|are|was|were)\s+closed\b", re.I),
    re.compile(r"\brisk(?:s)?\s+(?:is|are|was|were)\s+eliminated\b", re.I),
    # Control effectiveness
    re.compile(r"\bcontrol(?:s)?\s+(?:is|are|was|were)\s+effective\b", re.I),
    re.compile(r"\bcontrol\s+effectiveness\b", re.I),
    # Audit readiness
    re.compile(r"\baudit\s+ready\b", re.I),
    re.compile(r"\baudit\s+readiness\b", re.I),
    # Evidence completeness
    re.compile(r"\bevidence\s+(?:is|was)\s+complete\b", re.I),
    re.compile(r"\bevidence\s+completeness\b", re.I),
]

# Prohibit quantitative coverage/compliance percentages in reviewer rationales
QUANTITATIVE_PERCENTAGE_PATTERN = re.compile(
    r"\b\d+%\s+(?:compliant|conformance|ssdf|coverage|of\s+the\s+policy|of\s+gaps|of\s+critical\s+gaps)\b",
    re.I,
)

# Negation / boundary markers that indicate a legitimate disclaimer or negative observation
NEGATION_CONTEXT_PREFIXES = (
    "not ",
    "does not ",
    "do not ",
    "cannot ",
    "without ",
    "never ",
    "failed to ",
    "fails to ",
    "insufficient to ",
)


def load_vocabularies_fail_closed(
    evidence_schema_path: Path = DEFAULT_EVIDENCE_SCHEMA,
    review_queue_schema_path: Path = DEFAULT_REVIEW_QUEUE_SCHEMA,
) -> tuple[set[str], set[str], list[str]]:
    errors: list[str] = []
    evidence_strength: set[str] = set()
    review_queue_status: set[str] = set()

    try:
        ev_schema = load_schema(evidence_schema_path, "evidence-record")
        evidence_strength = set(string_list(ev_schema, "allowed_strength"))
    except (SchemaDefinitionError, OSError) as exc:
        errors.append(f"failed to load evidence schema fail-closed: {exc}")

    try:
        rq_schema = load_schema(review_queue_schema_path, "review-queue")
        review_queue_status = set(string_list(rq_schema, "allowed_status"))
    except (SchemaDefinitionError, OSError) as exc:
        errors.append(f"failed to load review-queue schema fail-closed: {exc}")

    return evidence_strength, review_queue_status, errors


def load_and_validate_reference(ref_path: Path) -> tuple[set[str], str | None, list[str]]:
    errors: list[str] = []
    if not ref_path.exists():
        return set(), None, [f"reference file not found: {ref_path}"]

    try:
        data = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return set(), None, [f"invalid YAML in reference file {ref_path}: {exc}"]

    if not isinstance(data, dict):
        return set(), None, [f"reference root must be a mapping: {ref_path}"]

    fw = data.get("framework")
    expected_baseline: str | None = None
    if isinstance(fw, dict):
        fid = fw.get("id")
        fver = fw.get("version")
        if fid and fver:
            expected_baseline = f"{fid}_v{fver}"
    if not expected_baseline:
        errors.append(f"reference file missing framework id or version: {ref_path}")

    tasks_list = data.get("tasks")
    if not isinstance(tasks_list, list) or not tasks_list:
        return set(), expected_baseline, [f"reference tasks must be a non-empty list: {ref_path}"]

    task_ids: set[str] = set()
    for idx, t in enumerate(tasks_list, start=1):
        if not isinstance(t, dict):
            errors.append(f"reference task {idx} must be a mapping")
            continue
        tid = t.get("task_id")
        if not tid or not isinstance(tid, str) or not tid.strip():
            errors.append(f"reference task {idx} missing or empty task_id")
            continue
        if not TASK_ID_REGEX.match(tid):
            errors.append(f"reference task {idx} invalid task_id format: {tid!r}")
        if tid in task_ids:
            errors.append(f"reference duplicate task_id: {tid!r}")
        task_ids.add(tid)

    if not task_ids:
        errors.append(f"empty reference task set: {ref_path}")

    return task_ids, expected_baseline, errors


def _is_negated(text: str, match_start: int) -> bool:
    prefix = text[max(0, match_start - 35) : match_start].lower()
    return any(neg in prefix for neg in NEGATION_CONTEXT_PREFIXES)


def validate_ssdf_assessment(
    path: Path,
    tasks_ref: Path = DEFAULT_TASKS_REF,
    evidence_schema: Path = DEFAULT_EVIDENCE_SCHEMA,
    review_queue_schema: Path = DEFAULT_REVIEW_QUEUE_SCHEMA,
) -> list[str]:
    errors: list[str] = []

    # 1. Authority Inputs Validation (Fail closed)
    allowed_tasks, expected_baseline, ref_errors = load_and_validate_reference(tasks_ref)
    if ref_errors:
        errors.extend(ref_errors)

    allowed_strength, allowed_rq_status, schema_errors = load_vocabularies_fail_closed(
        evidence_schema_path=evidence_schema,
        review_queue_schema_path=review_queue_schema,
    )
    if schema_errors:
        errors.extend(schema_errors)

    if errors:
        # Halt early if authoritative references or schemas fail to load
        return errors

    # 2. Assessment YAML loading
    if not path.exists():
        return [f"assessment file not found: {path}"]

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"invalid YAML in {path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"assessment root must be a mapping: {path}"]

    # 3. Assessment Header Envelope validation
    assessment_hdr = payload.get("assessment")
    scope_tasks_set: set[str] = set()
    if not isinstance(assessment_hdr, dict):
        errors.append("missing or invalid 'assessment' header mapping")
    else:
        for req_field in ("id", "baseline", "target", "scope_tasks", "claim_boundary"):
            val = assessment_hdr.get(req_field)
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"assessment header missing required field: {req_field}")

        assessment_baseline = assessment_hdr.get("baseline")
        if assessment_baseline and expected_baseline and assessment_baseline != expected_baseline:
            errors.append(
                f"assessment baseline {assessment_baseline!r} does not match reference baseline {expected_baseline!r}"
            )

        scope_tasks = assessment_hdr.get("scope_tasks")
        if not isinstance(scope_tasks, list) or not scope_tasks:
            errors.append("assessment scope_tasks must be a non-empty list")
        else:
            if len(scope_tasks) != len(set(scope_tasks)):
                errors.append("assessment scope_tasks contains duplicate task IDs")
            for t in scope_tasks:
                if not isinstance(t, str) or not t.strip():
                    errors.append("assessment scope_tasks must contain non-empty string task IDs")
                    continue
                if t not in allowed_tasks:
                    errors.append(f"assessment scope_tasks contains task outside reference: {t!r}")
                scope_tasks_set.add(t)

        claim_boundary = assessment_hdr.get("claim_boundary")
        if not isinstance(claim_boundary, list) or not claim_boundary:
            errors.append("assessment claim_boundary must be a non-empty list")

    # 4. Finding ID tracking for uniqueness
    seen_finding_ids: set[str] = set()

    # Helper for claim scanning on reviewer-authored strings only
    def scan_reviewer_authored(text: str, context_label: str) -> None:
        for pat in AFFIRMATIVE_PROHIBITED_PATTERNS:
            for match in pat.finditer(text):
                if not _is_negated(text, match.start()):
                    errors.append(
                        f"{context_label}: prohibited claim found outside cannot_claim: {match.group(0)!r}"
                    )
        pct_match = QUANTITATIVE_PERCENTAGE_PATTERN.search(text)
        if pct_match:
            errors.append(
                f"{context_label}: prohibited percentage claim without defined denominator: {pct_match.group(0)!r}"
            )

    # 5. Results (task_finding) validation
    results = payload.get("results") or []
    if not isinstance(results, list):
        errors.append("'results' must be a list of task findings")
        results = []

    for idx, finding in enumerate(results, start=1):
        if not isinstance(finding, dict):
            errors.append(f"finding {idx}: must be a mapping")
            continue

        fid = finding.get("finding_id", f"finding_{idx}")
        if not isinstance(fid, str) or not fid.strip():
            errors.append(f"finding {idx}: missing or empty finding_id")
        else:
            if fid in seen_finding_ids:
                errors.append(f"duplicate finding_id: {fid!r}")
            seen_finding_ids.add(fid)

        ftype = finding.get("finding_type")
        if ftype != "task_finding":
            errors.append(f"{fid}: finding_type must be 'task_finding', got {ftype!r}")

        task_id = finding.get("task_id")
        if not task_id or not isinstance(task_id, str):
            errors.append(f"{fid}: missing or non-string task_id")
        else:
            if "/" in task_id or not TASK_ID_REGEX.match(task_id):
                errors.append(f"{fid}: composite or invalid task_id: {task_id!r}")
            elif task_id not in allowed_tasks:
                errors.append(f"{fid}: unknown task_id: {task_id!r}")
            elif scope_tasks_set and task_id not in scope_tasks_set:
                errors.append(f"{fid}: task_id {task_id!r} is not in assessment.scope_tasks")

        # Verdict
        verdict = finding.get("coverage_verdict")
        if verdict not in COVERAGE_VERDICTS:
            errors.append(f"{fid}: invalid coverage_verdict: {verdict!r}")

        # Evidence strength
        ev_strength = finding.get("evidence_strength")
        if ev_strength not in allowed_strength:
            errors.append(f"{fid}: invalid evidence_strength: {ev_strength!r}")

        # Review queue recommendation
        rq_rec = finding.get("review_queue_recommendation")
        if rq_rec not in allowed_rq_status:
            errors.append(f"{fid}: invalid review_queue_recommendation: {rq_rec!r}")

        # Cannot claim
        cc = finding.get("cannot_claim")
        if not isinstance(cc, list) or not cc or any(not isinstance(x, str) or not x.strip() for x in cc):
            errors.append(f"{fid}: cannot_claim must be a non-empty list of strings")

        # Source ref and statement
        if not finding.get("company_source_ref"):
            errors.append(f"{fid}: missing company_source_ref")
        if not finding.get("company_statement"):
            errors.append(f"{fid}: missing company_statement")

        # Reviewer-authored claim check on assessment_rationale (company_statement is NOT scanned)
        rationale = finding.get("assessment_rationale")
        if isinstance(rationale, list):
            for r_idx, r_item in enumerate(rationale, start=1):
                if isinstance(r_item, str):
                    scan_reviewer_authored(r_item, f"{fid} assessment_rationale[{r_idx}]")
        elif isinstance(rationale, str):
            scan_reviewer_authored(rationale, f"{fid} assessment_rationale")

        # Basis checks
        basis_list = finding.get("basis")
        if not isinstance(basis_list, list) or not basis_list:
            errors.append(f"{fid}: basis must be a non-empty list")
        else:
            has_nist_normative = False
            for b_idx, b in enumerate(basis_list, start=1):
                if not isinstance(b, dict):
                    errors.append(f"{fid} basis[{b_idx}]: must be a mapping")
                    continue
                b_type = b.get("type")
                if b_type not in ALLOWED_BASIS_TYPES:
                    errors.append(f"{fid} basis[{b_idx}]: invalid basis type {b_type!r}")

                b_rat = b.get("rationale")
                if not b_rat or not isinstance(b_rat, str) or not b_rat.strip():
                    errors.append(f"{fid} basis[{b_idx}]: missing or empty rationale")
                else:
                    scan_reviewer_authored(b_rat, f"{fid} basis[{b_idx}].rationale")

                if b_type == "nist_normative":
                    has_nist_normative = True
                    b_task = b.get("task_id")
                    if not b_task:
                        errors.append(f"{fid} basis[{b_idx}]: nist_normative basis must specify task_id")
                    elif task_id and b_task != task_id:
                        errors.append(
                            f"{fid} basis[{b_idx}]: basis task_id {b_task!r} does not match finding task_id {task_id!r}"
                        )
                    elif b_task not in allowed_tasks:
                        errors.append(f"{fid} basis[{b_idx}]: nist_normative task_id {b_task!r} not in reference")
                    if not b.get("source"):
                        errors.append(f"{fid} basis[{b_idx}]: nist_normative basis must specify source")

            if not has_nist_normative:
                errors.append(f"{fid}: task_finding must include at least one 'nist_normative' basis")

    # 6. Non-normative observations validation
    observations = payload.get("non_normative_observations") or []
    if not isinstance(observations, list):
        errors.append("'non_normative_observations' must be a list")
        observations = []

    for idx, obs in enumerate(observations, start=1):
        if not isinstance(obs, dict):
            errors.append(f"observation {idx}: must be a mapping")
            continue

        oid = obs.get("finding_id", f"observation_{idx}")
        if not isinstance(oid, str) or not oid.strip():
            errors.append(f"observation {idx}: missing or empty finding_id")
        else:
            if oid in seen_finding_ids:
                errors.append(f"duplicate finding_id: {oid!r}")
            seen_finding_ids.add(oid)

        otype = obs.get("finding_type")
        if otype != "non_normative_observation":
            errors.append(f"{oid}: finding_type must be 'non_normative_observation', got {otype!r}")

        if "task_id" in obs:
            errors.append(f"{oid}: non_normative_observation must not have a task_id")

        if "coverage_verdict" in obs:
            errors.append(f"{oid}: non_normative_observation must not have a coverage_verdict")

        if not obs.get("company_source_ref"):
            errors.append(f"{oid}: missing company_source_ref")

        obs_text = obs.get("observation")
        if not obs_text or not isinstance(obs_text, str) or not obs_text.strip():
            errors.append(f"{oid}: missing or empty observation")
        else:
            scan_reviewer_authored(obs_text, f"{oid}.observation")

        obs_basis = obs.get("basis")
        if isinstance(obs_basis, str):
            if obs_basis != "reviewer_inference":
                errors.append(f"{oid}: non_normative_observation basis must be 'reviewer_inference'")
        elif isinstance(obs_basis, list):
            if not obs_basis or any(
                (b if isinstance(b, str) else b.get("type")) != "reviewer_inference"
                for b in obs_basis
            ):
                errors.append(f"{oid}: non_normative_observation basis must be 'reviewer_inference'")
        else:
            errors.append(f"{oid}: non_normative_observation basis must be 'reviewer_inference'")

        rq_rec = obs.get("review_queue_recommendation")
        if rq_rec not in allowed_rq_status:
            errors.append(f"{oid}: invalid review_queue_recommendation: {rq_rec!r}")

        cc = obs.get("cannot_claim")
        if not isinstance(cc, list) or not cc or any(not isinstance(x, str) or not x.strip() for x in cc):
            errors.append(f"{oid}: cannot_claim must be a non-empty list of strings")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic linter for S0 SSDF Direct Assessment YAML documents."
    )
    parser.add_argument("target", type=Path, help="Path to assessment YAML file")
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
    args = parser.parse_args()

    errors = validate_ssdf_assessment(
        args.target,
        tasks_ref=args.tasks_ref,
        evidence_schema=args.evidence_schema,
        review_queue_schema=args.review_queue_schema,
    )
    if errors:
        print("ssdf_assessment: FAIL")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print("ssdf_assessment: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()
