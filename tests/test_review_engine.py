import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tools.corpus_assessment_engine import (
    CorpusAssessmentBasis,
    CorpusAssessmentReport,
    CorpusAssessmentTarget,
    CorpusObservation,
    CorpusTaskFinding,
    IdentifiedEvidence,
)
from tools.review_engine import (
    DeterministicReviewReportRenderer,
    IReviewReportOrchestrator,
    ReadOnlyReviewFindingRecord,
    ReadOnlyReviewObservationRecord,
    ReadOnlyReviewProjector,
    ReadOnlyReviewRecord,
    ReviewOrchestrationError,
    ReviewProvenanceError,
    ReviewReportOrchestrator,
    ReviewValidationError,
    main,
)


class TestReviewEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.target = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit="ee3ca4a442fd5717ee186f66648dbf07e9f68247",
            manifest_path="examples/sample-target-manifest.yaml",
            manifest_digest="a" * 64,
            corpus_digest="b" * 64,
        )

        self.finding_pw81 = CorpusTaskFinding(
            finding_id="F-PW81-01",
            task_id="PW.8.1",
            company_source_ref="policy/security.md#sec-3",
            company_statement="All software components shall be inventoried.",
            coverage_verdict="PARTIAL",
            basis=[
                CorpusAssessmentBasis(
                    type="reviewer_inference",
                    rationale="Inference on package inventory.",
                ),
                CorpusAssessmentBasis(
                    type="nist_normative",
                    task_id="PW.8.1",
                    source="NIST_SP_800_218_v1.1",
                    rationale="Normative requirement on component reuse and inventory.",
                ),
                CorpusAssessmentBasis(
                    type="local_derived_guidance",
                    rationale="Local derived check on SBOM formats.",
                ),
            ],
            assessment_rationale=["Component inventory policy exists but lacks SBOM format standard."],
            identified_evidence=[
                IdentifiedEvidence(type="policy", source_ref="policy/security.md#sec-3")
            ],
            evidence_strength="medium",
            review_queue_recommendation="needs_changes",
            cannot_claim=["Does not establish SBOM implementation or vulnerability tracking."],
        )

        self.finding_po12 = CorpusTaskFinding(
            finding_id="F-PO12-01",
            task_id="PO.1.2",
            company_source_ref="policy/roles.md#sec-1",
            company_statement="Security roles and responsibilities are defined for all engineers.",
            coverage_verdict="COVERED",
            basis=[
                CorpusAssessmentBasis(
                    type="nist_normative",
                    task_id="PO.1.2",
                    source="NIST_SP_800_218_v1.1",
                    rationale="Roles defined for secure software development.",
                )
            ],
            assessment_rationale=["Comprehensive documentation of engineering security roles."],
            identified_evidence=[
                IdentifiedEvidence(type="policy", source_ref="policy/roles.md#sec-1")
            ],
            evidence_strength="strong",
            review_queue_recommendation="accepted",
            cannot_claim=["Does not prove compliance or organizational adherence."],
        )

        self.finding_pw11 = CorpusTaskFinding(
            finding_id="F-PW11-01",
            task_id="PW.1.1",
            company_source_ref="<corpus>#unmentioned",
            company_statement="Not mentioned in any policy document.",
            coverage_verdict="MISSING",
            basis=[
                CorpusAssessmentBasis(
                    type="nist_normative",
                    task_id="PW.1.1",
                    source="NIST_SP_800_218_v1.1",
                    rationale="Design software to meet security requirements.",
                )
            ],
            assessment_rationale=["No threat modeling or security design documentation found in corpus."],
            identified_evidence=[],
            evidence_strength="weak",
            review_queue_recommendation="needs_changes",
            cannot_claim=["Missing design policy does not prove absence of threat modeling in code."],
        )

        self.obs = CorpusObservation(
            finding_id="OBS-01",
            company_source_ref="process/guidelines.md#sec-2",
            observation="Coding guidelines suggest using linting tools.",
            basis="reviewer_inference",
            review_queue_recommendation="needs_changes",
            cannot_claim=["Observation does not imply compliance or deficiency."],
        )

        self.report = CorpusAssessmentReport(
            id="S1-REPORT-001",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=["PW.8.1", "PO.1.2", "PW.1.1"],
            claim_boundary=[
                "This review evaluates document coverage across the materialized repository corpus only.",
                "It does not establish NIST SSDF conformance or product security.",
            ],
            # Intentionally shuffled findings order: PW.8.1, PO.1.2, PW.1.1
            findings=[self.finding_pw81, self.finding_po12, self.finding_pw11],
            observations=[self.obs],
        )

        self.projector = ReadOnlyReviewProjector()
        self.renderer = DeterministicReviewReportRenderer()

    def test_review_projector_preserves_all_dimensions(self) -> None:
        record = self.projector.project(self.report)
        self.assertIsInstance(record, ReadOnlyReviewRecord)

        # Ensure all 6 dimensions are distinct and un-collapsed for each finding
        for f in record.findings:
            self.assertIn(f.coverage_verdict, ("COVERED", "PARTIAL", "MISSING", "NOT_APPLICABLE", "UNRESOLVED"))
            self.assertIn(f.evidence_strength, ("strong", "medium", "weak"))
            self.assertIn(f.review_queue_recommendation, ("pending", "needs_changes", "accepted", "accepted_with_review_due", "deferred", "rejected"))
            self.assertTrue(len(f.basis) > 0)
            self.assertTrue(len(f.cannot_claim) > 0)
            self.assertTrue(len(f.company_source_ref) > 0)

            # Ensure no artificial "Risk: High" / "Status: Bad" roll-up
            f_dict = f.to_dict()
            self.assertNotIn("risk_level", f_dict)
            self.assertNotIn("overall_status", f_dict)

    def test_deterministic_ordering_with_shuffled_input(self) -> None:
        record1 = self.projector.project(self.report)

        # Create another report with different initial findings order: PO.1.2, PW.1.1, PW.8.1
        shuffled_report = CorpusAssessmentReport(
            id=self.report.id,
            baseline=self.report.baseline,
            target=self.report.target,
            scope_tasks=list(self.report.scope_tasks),
            claim_boundary=list(self.report.claim_boundary),
            findings=[self.finding_po12, self.finding_pw11, self.finding_pw81],
            observations=list(self.report.observations),
        )
        record2 = self.projector.project(shuffled_report)

        # The findings in both projected records must be sorted by (task_id, finding_id):
        # Expected order: PO.1.2 -> PW.1.1 -> PW.8.1
        task_order1 = [f.task_id for f in record1.findings]
        task_order2 = [f.task_id for f in record2.findings]
        self.assertEqual(task_order1, ["PO.1.2", "PW.1.1", "PW.8.1"])
        self.assertEqual(task_order2, ["PO.1.2", "PW.1.1", "PW.8.1"])

        # Entire records must serialize identically (bit-for-bit reproducible)
        self.assertEqual(record1.to_dict(), record2.to_dict())
        self.assertEqual(
            self.renderer.render_json(record1),
            self.renderer.render_json(record2),
        )

    def test_projector_no_evaluative_inference(self) -> None:
        record = self.projector.project(self.report)
        pw81_record = next(f for f in record.findings if f.task_id == "PW.8.1")

        # Projector must faithfully preserve PARTIAL verdict, not alter it
        self.assertEqual(pw81_record.coverage_verdict, "PARTIAL")
        self.assertEqual(pw81_record.evidence_strength, "medium")
        self.assertEqual(pw81_record.review_queue_recommendation, "needs_changes")

    def test_basis_ordering_normative_first(self) -> None:
        record = self.projector.project(self.report)
        pw81_record = next(f for f in record.findings if f.task_id == "PW.8.1")

        # Original order in finding_pw81 was: reviewer_inference, nist_normative, local_derived_guidance
        # Projected order must be: nist_normative (1), local_derived_guidance (2), reviewer_inference (3)
        basis_types = [b.type for b in pw81_record.basis]
        self.assertEqual(basis_types, ["nist_normative", "local_derived_guidance", "reviewer_inference"])

    def test_claim_boundary_prominently_rendered(self) -> None:
        record = self.projector.project(self.report)
        md_out = self.renderer.render_markdown(record)

        self.assertIn("## Claim Boundary", md_out)
        for cb in self.report.claim_boundary:
            self.assertIn(cb, md_out)

        # Individual cannot_claim must also be rendered
        for f in self.report.findings:
            for cc in f.cannot_claim:
                self.assertIn(cc, md_out)

    def test_render_markdown_and_json_reproducibility(self) -> None:
        record = self.projector.project(self.report)
        md1 = self.renderer.render_markdown(record)
        md2 = self.renderer.render_markdown(record)
        self.assertEqual(md1, md2)

        json1 = self.renderer.render_json(record)
        json2 = self.renderer.render_json(record)
        self.assertEqual(json1, json2)

        # Ensure JSON is valid and roundtrippable
        parsed = json.loads(json1)
        self.assertEqual(parsed["assessment_id"], self.report.id)
        self.assertEqual(len(parsed["findings"]), 3)
        self.assertEqual(len(parsed["observations"]), 1)

    def test_observations_projected_and_sorted(self) -> None:
        obs2 = CorpusObservation(
            finding_id="OBS-00-EARLY",
            company_source_ref="process/guidelines.md#sec-1",
            observation="Another observation.",
        )
        report_with_multiple_obs = CorpusAssessmentReport(
            id=self.report.id,
            baseline=self.report.baseline,
            target=self.report.target,
            scope_tasks=list(self.report.scope_tasks),
            claim_boundary=list(self.report.claim_boundary),
            findings=list(self.report.findings),
            observations=[self.obs, obs2],  # OBS-01 before OBS-00-EARLY
        )
        record = self.projector.project(report_with_multiple_obs)
        obs_ids = [o.finding_id for o in record.observations]
        self.assertEqual(obs_ids, ["OBS-00-EARLY", "OBS-01"])

    def test_integration_with_parse_corpus_assessment_dict(self) -> None:
        from tools.corpus_assessment_engine import parse_corpus_assessment_dict

        yaml_dict = self.report.to_dict()
        parsed_report = parse_corpus_assessment_dict(yaml_dict)
        record = self.projector.project(parsed_report)

        self.assertEqual(record.assessment_id, "S1-REPORT-001")
        self.assertEqual(len(record.findings), 3)
        self.assertEqual(len(record.observations), 1)

        md = self.renderer.render_markdown(record)
        self.assertIn("# SSDF Direct Assessment Review Report: S1-REPORT-001", md)
        self.assertIn("Gavin0099/ai-assisted-ssdlc-docs", md)
        self.assertIn("F-PO12-01", md)
        self.assertIn("F-PW11-01", md)
        self.assertIn("F-PW81-01", md)
        self.assertIn("OBS-01", md)

        data = self.renderer.render_dict(record)
        self.assertEqual(data["assessment_id"], "S1-REPORT-001")
        self.assertIn("findings", data)
        self.assertIn("observations", data)

    def test_fixed_output_shape_with_empty_observations(self) -> None:
        report_no_obs = CorpusAssessmentReport(
            id="S1-REPORT-NO-OBS",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=["PO.1.2"],
            claim_boundary=["Claim boundary statement."],
            findings=[self.finding_po12],
            observations=[],
        )
        record = self.projector.project(report_no_obs)
        d = record.to_dict()
        # Must always output observations key with empty list, never omit it
        self.assertIn("observations", d)
        self.assertEqual(d["observations"], [])

        json_str = self.renderer.render_json(record)
        self.assertIn('"observations": []', json_str)

    def test_basis_tie_breaker_deterministic_ordering(self) -> None:
        basis_b = CorpusAssessmentBasis(
            type="local_derived_guidance",
            rationale="Check ownership",
            task_id="PO.1.2",
            source="source_beta",
        )
        basis_a = CorpusAssessmentBasis(
            type="local_derived_guidance",
            rationale="Check ownership",
            task_id="PO.1.2",
            source="source_alpha",
        )

        finding_order1 = CorpusTaskFinding(
            finding_id="F-TIE-01",
            task_id="PO.1.2",
            company_source_ref="policy/roles.md",
            company_statement="Statement.",
            coverage_verdict="COVERED",
            basis=[basis_b, basis_a],  # beta first
            assessment_rationale=["Rationale."],
            identified_evidence=[],
            evidence_strength="strong",
            review_queue_recommendation="accepted",
            cannot_claim=["No compliance."],
        )

        finding_order2 = CorpusTaskFinding(
            finding_id="F-TIE-01",
            task_id="PO.1.2",
            company_source_ref="policy/roles.md",
            company_statement="Statement.",
            coverage_verdict="COVERED",
            basis=[basis_a, basis_b],  # alpha first
            assessment_rationale=["Rationale."],
            identified_evidence=[],
            evidence_strength="strong",
            review_queue_recommendation="accepted",
            cannot_claim=["No compliance."],
        )

        rep1 = CorpusAssessmentReport(
            id="TIE-1",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=["PO.1.2"],
            claim_boundary=["Claim boundary."],
            findings=[finding_order1],
        )
        rep2 = CorpusAssessmentReport(
            id="TIE-1",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=["PO.1.2"],
            claim_boundary=["Claim boundary."],
            findings=[finding_order2],
        )

        rec1 = self.projector.project(rep1)
        rec2 = self.projector.project(rep2)

        # Both records must have identical basis order: alpha before beta
        sources1 = [b.source for b in rec1.findings[0].basis]
        sources2 = [b.source for b in rec2.findings[0].basis]
        self.assertEqual(sources1, ["source_alpha", "source_beta"])
        self.assertEqual(sources2, ["source_alpha", "source_beta"])
        self.assertEqual(rec1.to_dict(), rec2.to_dict())

    def test_markdown_table_cell_escaping(self) -> None:
        finding_with_pipe = CorpusTaskFinding(
            finding_id="F-PIPE-01",
            task_id="PO.1.2",
            company_source_ref="policy.md#phase|review",
            company_statement="Statement with pipe.",
            coverage_verdict="COVERED",
            basis=[
                CorpusAssessmentBasis(
                    type="nist_normative",
                    task_id="PO.1.2",
                    source="NIST_SP_800_218_v1.1",
                    rationale="Normative requirement.",
                )
            ],
            assessment_rationale=["Rationale."],
            identified_evidence=[],
            evidence_strength="strong",
            review_queue_recommendation="accepted",
            cannot_claim=["No compliance."],
        )
        report = CorpusAssessmentReport(
            id="PIPE-TEST",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=["PO.1.2"],
            claim_boundary=["Claim boundary."],
            findings=[finding_with_pipe],
        )
        record = self.projector.project(report)
        md = self.renderer.render_markdown(record)

        # Pipe delimiter in company_source_ref must be escaped as \|
        self.assertIn("policy.md#phase\\|review", md)

        # Find the summary table row for F-PIPE-01
        table_rows = [line for line in md.splitlines() if line.startswith("| `PO.1.2`")]
        self.assertEqual(len(table_rows), 1)
        # Check that splitting by unescaped pipes preserves exactly 6 data cells
        # (re.split by (?<!\\)\| yields 8 parts: leading empty, 6 cells, trailing empty)
        import re
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", table_rows[0]) if c.strip()]
        self.assertEqual(len(cells), 6)
        self.assertEqual(cells[-1], "`policy.md#phase\\|review`")

    def test_multiline_claim_boundary_rendering(self) -> None:
        multiline_cb = "This does not prove compliance.\n\nThis also does not prove implementation."
        report = CorpusAssessmentReport(
            id="MULTILINE-CB-TEST",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=["PO.1.2"],
            claim_boundary=[multiline_cb],
            findings=[self.finding_po12],
        )
        record = self.projector.project(report)
        md = self.renderer.render_markdown(record)

        expected_block = (
            "> [!IMPORTANT]\n"
            "> This does not prove compliance.\n"
            ">\n"
            "> This also does not prove implementation."
        )
        self.assertIn(expected_block, md)

    def _build_valid_7task_report(self) -> CorpusAssessmentReport:
        scope_tasks = ["PO.1.2", "PO.3.1", "PS.2.1", "PW.1.1", "PW.4.4", "PW.8.1", "RV.1.3"]
        findings = []
        for idx, task_id in enumerate(scope_tasks, start=1):
            findings.append(
                CorpusTaskFinding(
                    finding_id=f"F-TEST-{idx:02d}",
                    task_id=task_id,
                    company_source_ref="policy/security.md#sec-1",
                    company_statement="All requirements must be documented.",
                    coverage_verdict="PARTIAL",
                    basis=[
                        CorpusAssessmentBasis(
                            type="nist_normative",
                            task_id=task_id,
                            source="NIST_SP_800_218_v1.1",
                            rationale="Normative task requirement.",
                        ),
                    ],
                    assessment_rationale=["The policy requires documentation."],
                    identified_evidence=[
                        IdentifiedEvidence(
                            type="policy_statement",
                            source_ref="policy/security.md#sec-1",
                        )
                    ],
                    evidence_strength="medium",
                    review_queue_recommendation="needs_changes",
                    cannot_claim=["This does not prove compliance."],
                )
            )
        return CorpusAssessmentReport(
            id="S1-ORCH-001",
            baseline="NIST_SP_800_218_v1.1",
            target=self.target,
            scope_tasks=scope_tasks,
            claim_boundary=["This is an assessment boundary."],
            findings=findings,
            observations=[],
        )

    def test_orchestrator_validates_and_projects_success(self) -> None:
        report = self._build_valid_7task_report()
        orchestrator = ReviewReportOrchestrator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            record = orchestrator.orchestrate(yaml_path)
            self.assertIsInstance(record, ReadOnlyReviewRecord)
            self.assertEqual(record.assessment_id, "S1-ORCH-001")
            self.assertEqual(len(record.findings), 7)

    def test_orchestrator_fails_closed_on_invalid_linter_yaml(self) -> None:
        report = self._build_valid_7task_report()
        yaml_dict = report.to_dict()
        # Corrupt: inject forbidden affirmative claim in rationale
        yaml_dict["results"][0]["assessment_rationale"] = ["The system is fully compliant with NIST SSDF."]

        import yaml
        orchestrator = ReviewReportOrchestrator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "invalid-assessment.yaml"
            yaml_path.write_text(yaml.dump(yaml_dict), encoding="utf-8")

            with self.assertRaises(ReviewValidationError) as ctx:
                orchestrator.orchestrate(yaml_path)
            self.assertTrue(len(ctx.exception.errors) > 0)
            self.assertTrue(any("prohibited claim" in err for err in ctx.exception.errors))

    def test_orchestrator_fails_closed_on_missing_repo_path_manifest(self) -> None:
        report = self._build_valid_7task_report()
        orchestrator = ReviewReportOrchestrator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            empty_repo = Path(tmp_dir) / "empty_repo"
            empty_repo.mkdir()

            with self.assertRaises(ReviewProvenanceError) as ctx:
                orchestrator.orchestrate(yaml_path, repo_path=empty_repo)
            self.assertIn("Target manifest not found", str(ctx.exception))

    def test_cli_stdout_markdown_output(self) -> None:
        report = self._build_valid_7task_report()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main([str(yaml_path), "--stdout", "--format", "markdown"])

            self.assertEqual(exit_code, 0)
            out = buf.getvalue()
            self.assertIn("# SSDF Direct Assessment Review Report: S1-ORCH-001", out)
            self.assertIn("## Claim Boundary", out)

    def test_cli_stdout_json_output(self) -> None:
        report = self._build_valid_7task_report()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main([str(yaml_path), "--stdout", "--format", "json"])

            self.assertEqual(exit_code, 0)
            parsed = json.loads(buf.getvalue())
            self.assertEqual(parsed["assessment_id"], "S1-ORCH-001")
            self.assertEqual(len(parsed["findings"]), 7)

    def test_cli_out_dir_generates_both_artifacts(self) -> None:
        report = self._build_valid_7task_report()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            out_dir = Path(tmp_dir) / "reports"
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = main([str(yaml_path), "--out-dir", str(out_dir), "--format", "both"])

            self.assertEqual(exit_code, 0)
            md_file = out_dir / "S1-ORCH-001.review.md"
            json_file = out_dir / "S1-ORCH-001.review.json"
            self.assertTrue(md_file.is_file())
            self.assertTrue(json_file.is_file())

            content_md = md_file.read_text(encoding="utf-8")
            self.assertIn("# SSDF Direct Assessment Review Report: S1-ORCH-001", content_md)

    def test_cli_fails_closed_on_invalid_assessment(self) -> None:
        report = self._build_valid_7task_report()
        yaml_dict = report.to_dict()
        yaml_dict["results"][0]["cannot_claim"] = []  # Corrupt: empty cannot_claim

        import yaml
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "invalid-assessment.yaml"
            yaml_path.write_text(yaml.dump(yaml_dict), encoding="utf-8")

            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                exit_code = main([str(yaml_path), "--stdout"])

            self.assertEqual(exit_code, 1)
            err_msg = err_buf.getvalue()
            self.assertIn("cannot_claim must be a non-empty list", err_msg)

    def test_cli_fails_closed_on_stdout_format_both(self) -> None:
        report = self._build_valid_7task_report()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            err_buf = io.StringIO()
            with redirect_stderr(err_buf):
                exit_code = main([str(yaml_path), "--stdout", "--format", "both"])

            self.assertEqual(exit_code, 1)
            self.assertIn("cannot be used with --stdout", err_buf.getvalue())

    def test_cli_subprocess_invocation(self) -> None:
        import subprocess
        import sys
        report = self._build_valid_7task_report()
        with tempfile.TemporaryDirectory() as tmp_dir:
            yaml_path = Path(tmp_dir) / "valid-assessment.yaml"
            yaml_path.write_text(report.to_yaml(), encoding="utf-8")

            res = subprocess.run(
                [sys.executable, "tools/review_engine.py", str(yaml_path), "--stdout"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("# SSDF Direct Assessment Review Report: S1-ORCH-001", res.stdout)


if __name__ == "__main__":
    unittest.main()



