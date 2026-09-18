from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.corpus_assessment_engine import (
    CorpusAssessmentBasis,
    CorpusAssessmentError,
    CorpusAssessmentReport,
    CorpusAssessmentTarget,
    CorpusDigestMismatchError,
    CorpusObservation,
    CorpusTaskFinding,
    IdentifiedEvidence,
    InvalidCorpusSentinelError,
    ManifestDigestMismatchError,
    SourceRefNotFoundError,
    StrictCorpusSourceRefValidator,
    parse_corpus_assessment_dict,
    validate_corpus_assessment_provenance,
    validate_report_against_snapshot,
)
from tools.repo_corpus_resolver import CorpusFile, CorpusSnapshot
from tools.validate_ssdf_assessment import validate_ssdf_assessment
from tools.validate_target_manifest import (
    AuthoritySurfaceSpec,
    BaselineSpec,
    ModeSpec,
    TargetManifest,
    TargetSpec,
)


class TestCorpusAssessment(unittest.TestCase):
    def setUp(self) -> None:
        self.commit = "39b270f8f3c74aee2afcebe6935272a352691dff"
        self.file1 = CorpusFile(
            relative_path="policy/security.md",
            content_hash="aa" * 32,
            byte_size=100,
            content="Security policy content.",
        )
        self.file2 = CorpusFile(
            relative_path="process/review.md",
            content_hash="bb" * 32,
            byte_size=120,
            content="Review process content.",
        )
        files = (self.file1, self.file2)
        total_files = len(files)
        total_bytes = sum(f.byte_size for f in files)

        hasher = hashlib.sha256()
        for f in sorted(files, key=lambda x: x.relative_path):
            hasher.update(f"{f.relative_path}\t{f.content_hash}\n".encode("utf-8"))
        corpus_digest = hasher.hexdigest()

        self.manifest = TargetManifest(
            target=TargetSpec(
                source_type="github",
                repo="Gavin0099/ai-assisted-ssdlc-docs",
                commit=self.commit,
            ),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**", "process/**"),
                exclude=(),
            ),
            baseline=BaselineSpec(
                framework="NIST_SP_800_218",
                version="1.1",
            ),
            mode=ModeSpec(read_only=True),
        )

        self.snapshot = CorpusSnapshot(
            manifest=self.manifest,
            target_commit=self.commit,
            files=files,
            total_files=total_files,
            total_bytes=total_bytes,
            corpus_digest=corpus_digest,
        )
        self.valid_target = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit=self.commit,
            manifest_path="examples/sample-target-manifest.yaml",
            manifest_digest=self.snapshot.manifest_digest,
            corpus_digest=self.snapshot.corpus_digest,
        )

        scope_tasks = ["PO.1.2", "PO.3.1", "PS.2.1", "PW.1.1", "PW.4.4", "PW.8.1", "RV.1.3"]
        findings = []
        for idx, task_id in enumerate(scope_tasks, start=1):
            findings.append(
                CorpusTaskFinding(
                    finding_id=f"F-S1-TEST-{idx:02d}",
                    task_id=task_id,
                    company_source_ref="policy/security.md#2-security-requirements",
                    company_statement="All software requirements shall be identified and reviewed.",
                    coverage_verdict="PARTIAL",
                    basis=[
                        CorpusAssessmentBasis(
                            type="nist_normative",
                            task_id=task_id,
                            source="NIST_SP_800_218_v1.1",
                            rationale="Selected task requirement.",
                        ),
                        CorpusAssessmentBasis(
                            type="local_derived_guidance",
                            rationale="Local derived guidance observation.",
                        ),
                    ],
                    assessment_rationale=[
                        "The policy document defines the requirement in part but lacks detailed review criteria."
                    ],
                    identified_evidence=[
                        IdentifiedEvidence(
                            type="policy_statement",
                            source_ref="policy/security.md#2-security-requirements",
                        )
                    ],
                    evidence_strength="weak",
                    review_queue_recommendation="needs_changes",
                    cannot_claim=[
                        "This policy statement does not prove implementation or compliance."
                    ],
                )
            )

        self.valid_report = CorpusAssessmentReport(
            id="S1-TEST-001",
            baseline="NIST_SP_800_218_v1.1",
            target=self.valid_target,
            scope_tasks=scope_tasks,
            claim_boundary=[
                "This assessment evaluates document coverage across the materialized repository corpus only.",
                "It does not establish NIST SSDF conformance or organizational compliance.",
            ],
            findings=findings,
        )

    def test_target_provenance_validation_matches_snapshot(self) -> None:
        validate_corpus_assessment_provenance(self.snapshot, self.valid_target)

    def test_target_provenance_commit_mismatch_fails_closed(self) -> None:
        tampered_target = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit="00" * 20,
            manifest_path="examples/sample-target-manifest.yaml",
            manifest_digest=self.snapshot.manifest_digest,
            corpus_digest=self.snapshot.corpus_digest,
        )
        with self.assertRaises(CorpusAssessmentError) as ctx:
            validate_corpus_assessment_provenance(self.snapshot, tampered_target)
        self.assertIn("does not match target commit", str(ctx.exception))

    def test_target_provenance_manifest_digest_mismatch_fails_closed(self) -> None:
        tampered_target = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit=self.commit,
            manifest_path="examples/sample-target-manifest.yaml",
            manifest_digest="99" * 32,
            corpus_digest=self.snapshot.corpus_digest,
        )
        with self.assertRaises(ManifestDigestMismatchError) as ctx:
            validate_corpus_assessment_provenance(self.snapshot, tampered_target)
        self.assertIn("does not match target manifest_digest", str(ctx.exception))

    def test_target_provenance_corpus_digest_mismatch_fails_closed(self) -> None:
        tampered_target = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit=self.commit,
            manifest_path="examples/sample-target-manifest.yaml",
            manifest_digest=self.snapshot.manifest_digest,
            corpus_digest="11" * 32,
        )
        with self.assertRaises(CorpusDigestMismatchError) as ctx:
            validate_corpus_assessment_provenance(self.snapshot, tampered_target)
        self.assertIn("does not match target corpus_digest", str(ctx.exception))

    def test_target_manifest_digest_validation_invalid_hex(self) -> None:
        with self.assertRaises(CorpusAssessmentError) as ctx:
            CorpusAssessmentTarget(
                repo="Gavin0099/ai-assisted-ssdlc-docs",
                commit=self.commit,
                manifest_path="examples/sample-target-manifest.yaml",
                manifest_digest="invalid-digest",
                corpus_digest=self.snapshot.corpus_digest,
            )
        self.assertIn("64-character hex SHA-256", str(ctx.exception))

    def test_source_ref_validation_success_for_existing_file(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        validator.validate_source_ref(self.snapshot, "policy/security.md#section-1")
        validator.validate_source_ref(self.snapshot, "process/review.md")

    def test_source_ref_validation_fails_for_nonexistent_file(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        with self.assertRaises(SourceRefNotFoundError) as ctx:
            validator.validate_source_ref(self.snapshot, "policy/missing-file.md#sec-1")
        self.assertIn("missing-file.md", str(ctx.exception))

    def test_source_ref_validation_fails_for_empty_ref(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        with self.assertRaises(SourceRefNotFoundError):
            validator.validate_source_ref(self.snapshot, "")

    def test_source_ref_validation_allows_exact_corpus_sentinel_for_missing_or_unresolved(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        validator.validate_source_ref(self.snapshot, "<corpus>#unmentioned", coverage_verdict="MISSING")
        validator.validate_source_ref(self.snapshot, "<corpus>#unmentioned", coverage_verdict="UNRESOLVED")

    def test_source_ref_validation_rejects_sentinel_for_covered_or_partial(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        with self.assertRaises(InvalidCorpusSentinelError) as ctx:
            validator.validate_source_ref(self.snapshot, "<corpus>#unmentioned", coverage_verdict="COVERED")
        self.assertIn("permitted only for MISSING or UNRESOLVED", str(ctx.exception))

        with self.assertRaises(InvalidCorpusSentinelError) as ctx:
            validator.validate_source_ref(self.snapshot, "<corpus>#unmentioned", coverage_verdict="PARTIAL")
        self.assertIn("permitted only for MISSING or UNRESOLVED", str(ctx.exception))

    def test_source_ref_validation_rejects_sentinel_for_not_applicable(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        with self.assertRaises(InvalidCorpusSentinelError) as ctx:
            validator.validate_source_ref(self.snapshot, "<corpus>#unmentioned", coverage_verdict="NOT_APPLICABLE")
        self.assertIn("permitted only for MISSING or UNRESOLVED", str(ctx.exception))

    def test_source_ref_validation_rejects_malformed_or_invented_sentinels(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        with self.assertRaises(InvalidCorpusSentinelError) as ctx:
            validator.validate_source_ref(self.snapshot, "<corpus>#invented", coverage_verdict="MISSING")
        self.assertIn("only '<corpus>#unmentioned' is supported", str(ctx.exception))

        with self.assertRaises(InvalidCorpusSentinelError) as ctx:
            validator.validate_source_ref(self.snapshot, "<corpus-not-real>", coverage_verdict="MISSING")
        self.assertIn("only '<corpus>#unmentioned' is supported", str(ctx.exception))

    def test_source_ref_normalization_with_backslashes(self) -> None:
        validator = StrictCorpusSourceRefValidator()
        validator.validate_source_ref(self.snapshot, r"policy\security.md#section-1")

    def test_validate_report_against_snapshot_success(self) -> None:
        validate_report_against_snapshot(self.valid_report, self.snapshot)

    def test_validate_report_against_snapshot_with_valid_observation(self) -> None:
        obs = CorpusObservation(
            finding_id="OBS-S1-01",
            company_source_ref="process/review.md#notes",
            observation="Observed engineering review procedure.",
        )
        report_with_obs = CorpusAssessmentReport(
            id="S1-TEST-OBS",
            baseline="NIST_SP_800_218_v1.1",
            target=self.valid_target,
            scope_tasks=self.valid_report.scope_tasks,
            claim_boundary=self.valid_report.claim_boundary,
            findings=self.valid_report.findings,
            observations=[obs],
        )
        validate_report_against_snapshot(report_with_obs, self.snapshot)

    def test_validate_report_against_snapshot_fails_when_observation_references_phantom_file(self) -> None:
        obs = CorpusObservation(
            finding_id="OBS-S1-PHANTOM",
            company_source_ref="phantom/doc.md#notes",
            observation="Observed phantom file.",
        )
        report_with_obs = CorpusAssessmentReport(
            id="S1-TEST-OBS-PHANTOM",
            baseline="NIST_SP_800_218_v1.1",
            target=self.valid_target,
            scope_tasks=self.valid_report.scope_tasks,
            claim_boundary=self.valid_report.claim_boundary,
            findings=self.valid_report.findings,
            observations=[obs],
        )
        with self.assertRaises(SourceRefNotFoundError):
            validate_report_against_snapshot(report_with_obs, self.snapshot)

    def test_validate_report_against_snapshot_fails_on_phantom_source_ref(self) -> None:
        phantom_finding = CorpusTaskFinding(
            finding_id="F-S1-PHANTOM",
            task_id="PO.1.2",
            company_source_ref="phantom/doc.md#sec",
            company_statement="Statement",
            coverage_verdict="PARTIAL",
            basis=[CorpusAssessmentBasis(type="nist_normative", rationale="r")],
            assessment_rationale=["r"],
            identified_evidence=[],
            evidence_strength="weak",
            review_queue_recommendation="needs_changes",
            cannot_claim=["none"],
        )
        tampered_report = CorpusAssessmentReport(
            id="S1-TEST-002",
            baseline="NIST_SP_800_218_v1.1",
            target=self.valid_target,
            scope_tasks=["PO.1.2"],
            claim_boundary=["boundary"],
            findings=[phantom_finding],
        )
        with self.assertRaises(SourceRefNotFoundError):
            validate_report_against_snapshot(tampered_report, self.snapshot)

    def test_validate_report_against_snapshot_fails_on_empty_findings(self) -> None:
        empty_report = CorpusAssessmentReport(
            id="S1-TEST-EMPTY",
            baseline="NIST_SP_800_218_v1.1",
            target=self.valid_target,
            scope_tasks=["PO.1.2"],
            claim_boundary=["boundary"],
            findings=[],
        )
        with self.assertRaises(CorpusAssessmentError) as ctx:
            validate_report_against_snapshot(empty_report, self.snapshot)
        self.assertIn("at least one finding", str(ctx.exception))

    def test_parse_corpus_assessment_dict_roundtrip(self) -> None:
        obs = CorpusObservation(
            finding_id="OBS-S1-01",
            company_source_ref="process/review.md#notes",
            observation="Observed engineering review procedure.",
        )
        report_with_obs = CorpusAssessmentReport(
            id="S1-TEST-001",
            baseline="NIST_SP_800_218_v1.1",
            target=self.valid_target,
            scope_tasks=self.valid_report.scope_tasks,
            claim_boundary=self.valid_report.claim_boundary,
            findings=self.valid_report.findings,
            observations=[obs],
        )

        report_dict = report_with_obs.to_dict()
        parsed = parse_corpus_assessment_dict(report_dict)
        self.assertEqual(parsed.id, report_with_obs.id)
        self.assertEqual(parsed.target.manifest_digest, report_with_obs.target.manifest_digest)
        self.assertEqual(parsed.target.corpus_digest, report_with_obs.target.corpus_digest)
        self.assertEqual(len(parsed.findings), len(report_with_obs.findings))
        self.assertEqual(len(parsed.observations), 1)
        self.assertEqual(parsed.observations[0].finding_id, "OBS-S1-01")

    def test_report_serialization_and_linter_validation(self) -> None:
        yaml_str = self.valid_report.to_yaml()
        self.assertIn("repository_corpus", yaml_str)
        self.assertIn(self.snapshot.manifest_digest, yaml_str)
        self.assertIn(self.snapshot.corpus_digest, yaml_str)

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "s1-test-assessment.yaml"
            tmp_path.write_text(yaml_str, encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertEqual(errors, [], f"Validator returned errors: {errors}")

    def test_linter_rejects_missing_target_fields(self) -> None:
        report_dict = self.valid_report.to_dict()
        del report_dict["assessment"]["target"]["manifest_digest"]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("manifest_digest" in e for e in errors), f"Expected manifest_digest error: {errors}")

    def test_linter_rejects_invalid_manifest_digest_hex(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["assessment"]["target"]["manifest_digest"] = "short-digest"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("manifest_digest must be a 64-character hex" in e for e in errors), f"Expected manifest_digest format error: {errors}")

    def test_linter_rejects_invalid_commit_hex(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["assessment"]["target"]["commit"] = "not-a-valid-sha"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("40-character hex SHA" in e for e in errors), f"Expected commit format error: {errors}")

    def test_linter_rejects_invalid_digest_hex(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["assessment"]["target"]["corpus_digest"] = "short-digest"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("corpus_digest must be a 64-character hex" in e for e in errors), f"Expected digest format error: {errors}")

    def test_linter_rejects_invalid_target_type(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["assessment"]["target"]["type"] = "unknown_type"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("repository_corpus" in e for e in errors), f"Expected type error: {errors}")

    def test_linter_rejects_sentinel_for_partial_verdict(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["results"][0]["coverage_verdict"] = "PARTIAL"
        report_dict["results"][0]["company_source_ref"] = "<corpus>#unmentioned"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("sentinel '<corpus>#unmentioned' is permitted only for MISSING or UNRESOLVED" in e for e in errors), f"Expected sentinel error: {errors}")

    def test_linter_rejects_sentinel_for_not_applicable_verdict(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["results"][0]["coverage_verdict"] = "NOT_APPLICABLE"
        report_dict["results"][0]["company_source_ref"] = "<corpus>#unmentioned"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("sentinel '<corpus>#unmentioned' is permitted only for MISSING or UNRESOLVED" in e for e in errors), f"Expected sentinel error: {errors}")

    def test_linter_rejects_malformed_corpus_sentinel(self) -> None:
        report_dict = self.valid_report.to_dict()
        report_dict["results"][0]["coverage_verdict"] = "MISSING"
        report_dict["results"][0]["company_source_ref"] = "<corpus>#invented"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "invalid.yaml"
            tmp_path.write_text(yaml.dump(report_dict), encoding="utf-8")
            errors = validate_ssdf_assessment(tmp_path)
            self.assertTrue(any("invalid sentinel format" in e for e in errors), f"Expected sentinel error: {errors}")


if __name__ == "__main__":
    unittest.main()
