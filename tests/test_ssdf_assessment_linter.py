from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LINTER_SCRIPT = ROOT / "tools" / "validate_ssdf_assessment.py"
GOLDEN_FIXTURE = ROOT / "experiments" / "s0-ssdf-direct-assessment" / "golden" / "expected-assessment.yaml"
REFERENCE_FIXTURE = ROOT / "references" / "nist-ssdf" / "v1.1" / "tasks.yaml"
DEFAULT_EVIDENCE_SCHEMA = ROOT / "schemas" / "evidence-record.schema.yaml"
DEFAULT_REVIEW_QUEUE_SCHEMA = ROOT / "schemas" / "review-queue.schema.yaml"


def run_linter(
    path: Path,
    reference: Path | None = None,
    evidence_schema: Path | None = None,
    review_queue_schema: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(LINTER_SCRIPT), str(path)]
    if reference is not None:
        cmd.extend(["--reference", str(reference)])
    if evidence_schema is not None:
        cmd.extend(["--evidence-schema", str(evidence_schema)])
    if review_queue_schema is not None:
        cmd.extend(["--review-queue-schema", str(review_queue_schema)])
    return subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class SSDFAssessmentLinterTests(unittest.TestCase):
    def test_golden_fixture_passes(self) -> None:
        result = run_linter(GOLDEN_FIXTURE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ssdf_assessment: PASS", result.stdout)

    def _run_with_mutated_golden(
        self,
        mutator,
        reference: Path | None = None,
        evidence_schema: Path | None = None,
        review_queue_schema: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        data = yaml.safe_load(GOLDEN_FIXTURE.read_text(encoding="utf-8"))
        mutator(data)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            yaml.dump(data, f)
            temp_path = Path(f.name)
        try:
            return run_linter(
                temp_path,
                reference=reference,
                evidence_schema=evidence_schema,
                review_queue_schema=review_queue_schema,
            )
        finally:
            if temp_path.exists():
                temp_path.unlink()

    # --- Negation Awareness & Reviewer Rationale Checks ---

    def test_legitimate_negation_in_rationale_passes(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].extend([
                "The available evidence does not establish NIST SSDF compliance.",
                "The review does not prove the control is effective.",
                "This policy cannot prove that all vulnerabilities are fixed.",
            ])

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_company_statement_containing_prohibited_phrase_passes(self) -> None:
        def mutate(data):
            data["results"][0]["company_statement"] = (
                "Company claims: All software is fully NIST SSDF compliant and production safe with 100% coverage."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cannot_claim_containing_prohibited_phrase_passes(self) -> None:
        def mutate(data):
            data["results"][0]["cannot_claim"].append(
                "This policy does not establish that the product is production safe or 100% compliant."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_claim_boundary_header_containing_prohibited_phrase_passes(self) -> None:
        def mutate(data):
            data["assessment"]["claim_boundary"].append(
                "Does not prove compliance with NIST SSDF or control effectiveness."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- Expanded Affirmative Prohibited Claims ---

    def test_affirmative_compliance_claim_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "Based on this section, the software is fully NIST compliant."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited claim found outside cannot_claim", result.stdout)

    def test_affirmative_vulnerabilities_fixed_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "Therefore, all vulnerabilities are fixed before shipping."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited claim found outside cannot_claim", result.stdout)

    def test_affirmative_control_effective_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "The documented control is effective against supply-chain attacks."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited claim found outside cannot_claim", result.stdout)

    def test_affirmative_audit_ready_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "The product artifact is audit ready."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited claim found outside cannot_claim", result.stdout)

    def test_affirmative_remediation_complete_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "This ensures remediation is complete."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited claim found outside cannot_claim", result.stdout)

    def test_affirmative_risk_closed_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "The security risk is closed permanently."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited claim found outside cannot_claim", result.stdout)

    def test_percentage_claim_in_reviewer_rationale_fails(self) -> None:
        def mutate(data):
            data["results"][0]["assessment_rationale"].append(
                "The organization achieved 80% coverage of required security tasks."
            )

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("prohibited percentage claim without defined denominator", result.stdout)

    # --- Provenance Binding: Baseline vs Reference ---

    def test_baseline_mismatch_with_reference_fails(self) -> None:
        def mutate(data):
            data["assessment"]["baseline"] = "NIST_SP_800_218_v1.2"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not match reference baseline 'NIST_SP_800_218_v1.1'", result.stdout)

    # --- Schema Fail-Closed Tests ---

    def test_malformed_evidence_schema_fails_closed(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write("schema_name: wrong-name\n")
            schema_path = Path(f.name)
        try:
            result = run_linter(GOLDEN_FIXTURE, evidence_schema=schema_path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("failed to load evidence schema fail-closed", result.stdout)
        finally:
            if schema_path.exists():
                schema_path.unlink()

    def test_malformed_review_queue_schema_fails_closed(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write("schema_name: review-queue\nallowed_status: []\n")
            schema_path = Path(f.name)
        try:
            result = run_linter(GOLDEN_FIXTURE, review_queue_schema=schema_path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("failed to load review-queue schema fail-closed", result.stdout)
        finally:
            if schema_path.exists():
                schema_path.unlink()

    # --- Task and Scope validation ---

    def test_unknown_task_id_fails(self) -> None:
        def mutate(data):
            data["results"][0]["task_id"] = "PW.99.9"
            data["results"][0]["basis"][0]["task_id"] = "PW.99.9"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown task_id: 'PW.99.9'", result.stdout)

    def test_composite_task_id_fails(self) -> None:
        def mutate(data):
            data["results"][0]["task_id"] = "PO.1 / RV.1"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("composite or invalid task_id: 'PO.1 / RV.1'", result.stdout)

    def test_result_task_outside_scope_tasks_fails(self) -> None:
        def mutate(data):
            data["assessment"]["scope_tasks"] = [t for t in data["assessment"]["scope_tasks"] if t != "PO.1.2"]

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not in assessment.scope_tasks", result.stdout)

    def test_duplicate_finding_id_fails(self) -> None:
        def mutate(data):
            data["results"][1]["finding_id"] = data["results"][0]["finding_id"]

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate finding_id", result.stdout)

    # --- Vocabulary validation ---

    def test_invalid_review_queue_vocabulary_fails(self) -> None:
        def mutate(data):
            data["results"][0]["review_queue_recommendation"] = "needs_review"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid review_queue_recommendation: 'needs_review'", result.stdout)

    def test_invalid_coverage_verdict_fails(self) -> None:
        def mutate(data):
            data["results"][0]["coverage_verdict"] = "PASS"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid coverage_verdict: 'PASS'", result.stdout)

    def test_invalid_evidence_strength_fails(self) -> None:
        def mutate(data):
            data["results"][0]["evidence_strength"] = "absolute"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid evidence_strength: 'absolute'", result.stdout)

    def test_missing_cannot_claim_fails(self) -> None:
        def mutate(data):
            data["results"][0]["cannot_claim"] = []

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot_claim must be a non-empty list", result.stdout)

    # --- Basis and Observation structure validation ---

    def test_task_finding_missing_nist_normative_fails(self) -> None:
        def mutate(data):
            data["results"][0]["basis"] = [
                {"type": "local_derived_guidance", "rationale": "only guidance"}
            ]

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("task_finding must include at least one 'nist_normative' basis", result.stdout)

    def test_task_finding_basis_mismatched_task_id_fails(self) -> None:
        def mutate(data):
            data["results"][0]["basis"][0]["task_id"] = "PS.2.1"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("basis task_id 'PS.2.1' does not match finding task_id 'PO.1.2'", result.stdout)

    def test_observation_with_task_id_fails(self) -> None:
        def mutate(data):
            data["non_normative_observations"][0]["task_id"] = "PO.1.2"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("non_normative_observation must not have a task_id", result.stdout)

    def test_observation_with_coverage_verdict_fails(self) -> None:
        def mutate(data):
            data["non_normative_observations"][0]["coverage_verdict"] = "PARTIAL"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("non_normative_observation must not have a coverage_verdict", result.stdout)

    def test_observation_with_non_inference_basis_fails(self) -> None:
        def mutate(data):
            data["non_normative_observations"][0]["basis"] = "nist_normative"

        result = self._run_with_mutated_golden(mutate)
        self.assertEqual(result.returncode, 1)
        self.assertIn("non_normative_observation basis must be 'reviewer_inference'", result.stdout)

    # --- Reference fail-closed tests ---

    def test_malformed_reference_fails(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write("framework:\n  id: NIST_SP_800_218\n  version: '1.1'\ntasks: 'not a list'\n")
            ref_path = Path(f.name)
        try:
            result = run_linter(GOLDEN_FIXTURE, reference=ref_path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("reference tasks must be a non-empty list", result.stdout)
        finally:
            if ref_path.exists():
                ref_path.unlink()

    def test_duplicate_reference_task_id_fails(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
            f.write(
                "framework:\n  id: NIST_SP_800_218\n  version: '1.1'\ntasks:\n  - task_id: PO.1.2\n  - task_id: PO.1.2\n"
            )
            ref_path = Path(f.name)
        try:
            result = run_linter(GOLDEN_FIXTURE, reference=ref_path)
            self.assertEqual(result.returncode, 1)
            self.assertIn("reference duplicate task_id: 'PO.1.2'", result.stdout)
        finally:
            if ref_path.exists():
                ref_path.unlink()

    # --- Required fields and non-empty results tests ---

    def test_empty_results_fails(self) -> None:
        res = self._run_with_mutated_golden(lambda d: d.update({"results": []}))
        self.assertEqual(res.returncode, 1)
        self.assertIn("assessment 'results' must be a non-empty list of findings", res.stdout)

    def test_missing_assessment_rationale_fails(self) -> None:
        def mutate(d: dict) -> None:
            del d["results"][0]["assessment_rationale"]
        res = self._run_with_mutated_golden(mutate)
        self.assertEqual(res.returncode, 1)
        self.assertIn("missing or empty assessment_rationale", res.stdout)

    def test_missing_identified_evidence_fails(self) -> None:
        def mutate(d: dict) -> None:
            del d["results"][0]["identified_evidence"]
        res = self._run_with_mutated_golden(mutate)
        self.assertEqual(res.returncode, 1)
        self.assertIn("missing or empty identified_evidence list", res.stdout)

    def test_invalid_identified_evidence_item_fails(self) -> None:
        def mutate(d: dict) -> None:
            d["results"][0]["identified_evidence"] = [{"type": ""}]
        res = self._run_with_mutated_golden(mutate)
        self.assertEqual(res.returncode, 1)
        self.assertIn("missing or empty type", res.stdout)


if __name__ == "__main__":
    unittest.main()
