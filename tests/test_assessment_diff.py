from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.assessment_diff import (
    AssessmentDiffEngine,
    DeterministicDiffRenderer,
    DiffKind,
)
from tools.corpus_assessment_engine import (
    CorpusAssessmentBasis,
    CorpusAssessmentReport,
    CorpusAssessmentTarget,
    CorpusTaskFinding,
    IdentifiedEvidence,
)


class TestAssessmentDiff(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AssessmentDiffEngine()
        self.renderer = DeterministicDiffRenderer()

        self.target_base = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit="1111111111111111111111111111111111111111",
            manifest_path="target-manifest.yaml",
            manifest_digest="a" * 64,
            corpus_digest="b" * 64,
            target_type="repository_corpus",
        )

        self.scope_tasks = ["PO.1.2", "PO.3.1", "PS.2.1", "PW.1.1", "PW.4.4", "PW.8.1", "RV.1.3"]
        self.claim_boundary_base = [
            "This assessment does not prove compliance.",
            "This does not guarantee vulnerability absence.",
        ]

    def _create_report(
        self,
        report_id: str,
        target: CorpusAssessmentTarget | None = None,
        findings: list[CorpusTaskFinding] | None = None,
        claim_boundary: list[str] | None = None,
    ) -> CorpusAssessmentReport:
        if findings is None:
            findings = []
            for idx, task_id in enumerate(self.scope_tasks, start=1):
                findings.append(
                    CorpusTaskFinding(
                        finding_id=f"F-BASE-{idx:02d}",
                        task_id=task_id,
                        company_source_ref=f"policy/p{idx}.md#sec-1",
                        company_statement=f"Company statement for {task_id}.",
                        coverage_verdict="PARTIAL",
                        basis=[
                            CorpusAssessmentBasis(
                                type="nist_normative",
                                task_id=task_id,
                                source="NIST_SP_800_218_v1.1",
                                rationale="Normative requirement text.",
                            )
                        ],
                        assessment_rationale=[f"Rationale for {task_id}."],
                        identified_evidence=[
                            IdentifiedEvidence(
                                type="policy",
                                source_ref=f"policy/p{idx}.md#sec-1",
                            )
                        ],
                        evidence_strength="medium",
                        review_queue_recommendation="accepted",
                        cannot_claim=["No compliance guarantee"],
                    )
                )

        return CorpusAssessmentReport(
            id=report_id,
            baseline="NIST_SP_800_218_v1.1",
            target=target or self.target_base,
            scope_tasks=list(self.scope_tasks),
            claim_boundary=claim_boundary or list(self.claim_boundary_base),
            findings=findings,
        )

    def test_identical_reports_all_unchanged(self) -> None:
        """Scenario 9: Identical assessment comparison produces all UNCHANGED status."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        record = self.engine.compare(report_a, report_b)

        self.assertEqual(record.baseline_id, "REPORT-A")
        self.assertEqual(record.target_id, "REPORT-B")
        self.assertEqual(record.added_count, 0)
        self.assertEqual(record.removed_count, 0)
        self.assertEqual(record.modified_count, 0)
        self.assertEqual(record.unchanged_count, 7)
        self.assertEqual(len(record.target_metadata_diff), 0)

        for td in record.task_diffs:
            self.assertEqual(td.diff_kind, DiffKind.UNCHANGED)
            self.assertEqual(td.verdict_transition, ("PARTIAL", "PARTIAL"))
            self.assertEqual(td.changed_fields, ())

    def test_verdict_and_field_transition_objective(self) -> None:
        """Scenario 10: Modifying verdict and source ref records transitions without sentiment."""
        report_a = self._create_report("REPORT-A")

        # In report B, change PO.1.2 verdict to COVERED and source_ref
        findings_b = []
        for f in report_a.findings:
            if f.task_id == "PO.1.2":
                findings_b.append(
                    CorpusTaskFinding(
                        finding_id=f.finding_id,
                        task_id=f.task_id,
                        company_source_ref="policy/updated_policy.md#sec-2",
                        company_statement=f.company_statement,
                        coverage_verdict="COVERED",
                        basis=f.basis,
                        assessment_rationale=["Updated rationale."],
                        identified_evidence=f.identified_evidence,
                        evidence_strength=f.evidence_strength,
                        review_queue_recommendation=f.review_queue_recommendation,
                        cannot_claim=f.cannot_claim,
                    )
                )
            else:
                findings_b.append(f)

        report_b = self._create_report("REPORT-B", findings=findings_b)

        record = self.engine.compare(report_a, report_b)

        self.assertEqual(record.modified_count, 1)
        self.assertEqual(record.unchanged_count, 6)
        self.assertEqual(record.added_count, 0)
        self.assertEqual(record.removed_count, 0)

        po12_diff = next(td for td in record.task_diffs if td.task_id == "PO.1.2")
        self.assertEqual(po12_diff.diff_kind, DiffKind.MODIFIED)
        self.assertEqual(po12_diff.verdict_transition, ("PARTIAL", "COVERED"))

        changed_names = {cf.field_name for cf in po12_diff.changed_fields}
        self.assertIn("coverage_verdict", changed_names)
        self.assertIn("company_source_ref", changed_names)

    def test_added_and_removed_findings(self) -> None:
        """Scenario 11: Task findings added and removed between assessments."""
        # Report A has PO.1.2 and PO.3.1
        findings_a = [
            CorpusTaskFinding(
                finding_id="F-01",
                task_id="PO.1.2",
                company_source_ref="policy/a.md",
                company_statement="Statement A",
                coverage_verdict="COVERED",
                basis=[],
                assessment_rationale=["Rationale"],
                identified_evidence=[IdentifiedEvidence(type="policy_document", source_ref="policy/a.md")],
                evidence_strength="HIGH",
                review_queue_recommendation="ACCEPT",
                cannot_claim=[],
            ),
            CorpusTaskFinding(
                finding_id="F-02",
                task_id="PO.3.1",
                company_source_ref="policy/b.md",
                company_statement="Statement B",
                coverage_verdict="MISSING",
                basis=[],
                assessment_rationale=["Rationale"],
                identified_evidence=[IdentifiedEvidence(type="policy_document", source_ref="policy/b.md")],
                evidence_strength="LOW",
                review_queue_recommendation="REVISE",
                cannot_claim=[],
            ),
        ]
        # Report B has PO.3.1 and PS.2.1
        findings_b = [
            CorpusTaskFinding(
                finding_id="F-02",
                task_id="PO.3.1",
                company_source_ref="policy/b.md",
                company_statement="Statement B",
                coverage_verdict="MISSING",
                basis=[],
                assessment_rationale=["Rationale"],
                identified_evidence=[IdentifiedEvidence(type="policy_document", source_ref="policy/b.md")],
                evidence_strength="LOW",
                review_queue_recommendation="REVISE",
                cannot_claim=[],
            ),
            CorpusTaskFinding(
                finding_id="F-03",
                task_id="PS.2.1",
                company_source_ref="policy/c.md",
                company_statement="Statement C",
                coverage_verdict="PARTIAL",
                basis=[],
                assessment_rationale=["Rationale"],
                identified_evidence=[IdentifiedEvidence(type="policy_document", source_ref="policy/c.md")],
                evidence_strength="MEDIUM",
                review_queue_recommendation="ACCEPT",
                cannot_claim=[],
            ),
        ]

        report_a = self._create_report("REPORT-A", findings=findings_a)
        report_b = self._create_report("REPORT-B", findings=findings_b)

        record = self.engine.compare(report_a, report_b)

        self.assertEqual(record.added_count, 1)  # PS.2.1
        self.assertEqual(record.removed_count, 1)  # PO.1.2
        self.assertEqual(record.unchanged_count, 1)  # PO.3.1
        self.assertEqual(record.modified_count, 0)

        diff_map = {td.task_id: td for td in record.task_diffs}
        self.assertEqual(diff_map["PO.1.2"].diff_kind, DiffKind.REMOVED)
        self.assertEqual(diff_map["PO.1.2"].verdict_transition, ("COVERED", None))
        self.assertEqual(diff_map["PS.2.1"].diff_kind, DiffKind.ADDED)
        self.assertEqual(diff_map["PS.2.1"].verdict_transition, (None, "PARTIAL"))
        self.assertEqual(diff_map["PO.3.1"].diff_kind, DiffKind.UNCHANGED)

    def test_metadata_commit_and_digest_diff(self) -> None:
        """Target metadata differences are captured."""
        target_b = CorpusAssessmentTarget(
            repo="Gavin0099/ai-assisted-ssdlc-docs",
            commit="2222222222222222222222222222222222222222",
            manifest_path="target-manifest.yaml",
            manifest_digest="c" * 64,
            corpus_digest="d" * 64,
            target_type="repository_corpus",
        )
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B", target=target_b)

        record = self.engine.compare(report_a, report_b)

        meta_diffs = {fd.field_name: (fd.baseline_value, fd.target_value) for fd in record.target_metadata_diff}
        self.assertIn("commit", meta_diffs)
        self.assertEqual(meta_diffs["commit"], ("1" * 40, "2" * 40))
        self.assertIn("manifest_digest", meta_diffs)
        self.assertIn("corpus_digest", meta_diffs)

    def test_claim_boundary_merging_and_deduplication(self) -> None:
        """Claim boundaries from baseline and target are merged, deduplicated, and sorted."""
        cb_a = ["Boundary B", "Boundary A"]
        cb_b = ["Boundary C", "Boundary A"]
        report_a = self._create_report("REPORT-A", claim_boundary=cb_a)
        report_b = self._create_report("REPORT-B", claim_boundary=cb_b)

        record = self.engine.compare(report_a, report_b)

        self.assertEqual(record.claim_boundary, ("Boundary A", "Boundary B", "Boundary C"))

    def test_no_evaluative_sentiment_in_rendered_markdown(self) -> None:
        """Rendered Markdown strictly avoids evaluative words like improved, regressed, compliant."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        record = self.engine.compare(report_a, report_b)
        md = self.renderer.render_markdown(record)

        # Prohibited evaluative/sentiment terms
        forbidden = [
            "improved",
            "improvement",
            "regressed",
            "regression",
            "remediated",
            "remediation complete",
            "fully compliant",
            "conforming",
            "safe",
            "better",
            "worse",
        ]
        md_lower = md.lower()
        for word in forbidden:
            self.assertNotIn(word, md_lower, f"Prohibited evaluative word found: {word}")

    def test_deterministic_json_output(self) -> None:
        """JSON output is deterministic and matches schema dictionary."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        record = self.engine.compare(report_a, report_b)
        json_str = self.renderer.render_json(record)
        data = json.loads(json_str)

        self.assertEqual(data["baseline_id"], "REPORT-A")
        self.assertEqual(data["target_id"], "REPORT-B")
        self.assertEqual(data["summary"]["unchanged"], 7)
        self.assertEqual(data["summary"]["total_tasks"], 7)

    def test_basis_reordering_produces_unchanged_status(self) -> None:
        """Codex finding test: Canonical basis ordering prevents false-positive MODIFIED on permutation."""
        basis_1 = CorpusAssessmentBasis(
            type="nist_normative",
            task_id="PO.1.2",
            source="NIST_SP_800_218_v1.1",
            rationale="Normative rationale.",
        )
        basis_2 = CorpusAssessmentBasis(
            type="reviewer_inference",
            rationale="Inference rationale.",
        )

        findings_a = [
            CorpusTaskFinding(
                finding_id="F-PO12-01",
                task_id="PO.1.2",
                company_source_ref="policy/sec.md",
                company_statement="Statement",
                coverage_verdict="COVERED",
                basis=[basis_1, basis_2],
                assessment_rationale=["Rationale."],
                identified_evidence=[],
                evidence_strength="strong",
                review_queue_recommendation="accepted",
                cannot_claim=[],
            )
        ]
        # In findings_b, reverse the basis order: [basis_2, basis_1]
        findings_b = [
            CorpusTaskFinding(
                finding_id="F-PO12-01",
                task_id="PO.1.2",
                company_source_ref="policy/sec.md",
                company_statement="Statement",
                coverage_verdict="COVERED",
                basis=[basis_2, basis_1],
                assessment_rationale=["Rationale."],
                identified_evidence=[],
                evidence_strength="strong",
                review_queue_recommendation="accepted",
                cannot_claim=[],
            )
        ]

        report_a = self._create_report("REPORT-A", findings=findings_a)
        report_b = self._create_report("REPORT-B", findings=findings_b)

        record = self.engine.compare(report_a, report_b)
        self.assertEqual(record.unchanged_count, 1)
        self.assertEqual(record.modified_count, 0)
        self.assertEqual(record.task_diffs[0].diff_kind, DiffKind.UNCHANGED)


    def test_rationale_change_marked_modified(self) -> None:
        """Changing only assessment_rationale marks the finding MODIFIED."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        # Mutate rationale on PO.1.2
        target_findings = list(report_b.findings)
        first_finding = target_findings[0]
        target_findings[0] = CorpusTaskFinding(
            finding_id=first_finding.finding_id,
            task_id=first_finding.task_id,
            company_source_ref=first_finding.company_source_ref,
            company_statement=first_finding.company_statement,
            coverage_verdict=first_finding.coverage_verdict,
            basis=first_finding.basis,
            assessment_rationale=["Updated rationale text with new analysis."],
            identified_evidence=first_finding.identified_evidence,
            evidence_strength=first_finding.evidence_strength,
            review_queue_recommendation=first_finding.review_queue_recommendation,
            cannot_claim=first_finding.cannot_claim,
        )
        report_b = CorpusAssessmentReport(
            id=report_b.id,
            baseline=report_b.baseline,
            target=report_b.target,
            scope_tasks=report_b.scope_tasks,
            claim_boundary=report_b.claim_boundary,
            findings=target_findings,
        )

        record = self.engine.compare(report_a, report_b)
        self.assertEqual(record.modified_count, 1)
        self.assertEqual(record.unchanged_count, 6)
        diff_p12 = next(d for d in record.task_diffs if d.task_id == "PO.1.2")
        self.assertEqual(diff_p12.diff_kind, DiffKind.MODIFIED)
        changed_fields = {f.field_name for f in diff_p12.changed_fields}
        self.assertIn("assessment_rationale", changed_fields)

    def test_evidence_change_marked_modified(self) -> None:
        """Changing only identified_evidence marks the finding MODIFIED."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        target_findings = list(report_b.findings)
        first_finding = target_findings[0]
        target_findings[0] = CorpusTaskFinding(
            finding_id=first_finding.finding_id,
            task_id=first_finding.task_id,
            company_source_ref=first_finding.company_source_ref,
            company_statement=first_finding.company_statement,
            coverage_verdict=first_finding.coverage_verdict,
            basis=first_finding.basis,
            assessment_rationale=first_finding.assessment_rationale,
            identified_evidence=[
                IdentifiedEvidence(
                    type="procedure",
                    source_ref="policy/updated_proc.md#sec-2",
                )
            ],
            evidence_strength=first_finding.evidence_strength,
            review_queue_recommendation=first_finding.review_queue_recommendation,
            cannot_claim=first_finding.cannot_claim,
        )
        report_b = CorpusAssessmentReport(
            id=report_b.id,
            baseline=report_b.baseline,
            target=report_b.target,
            scope_tasks=report_b.scope_tasks,
            claim_boundary=report_b.claim_boundary,
            findings=target_findings,
        )

        record = self.engine.compare(report_a, report_b)
        self.assertEqual(record.modified_count, 1)
        self.assertEqual(record.unchanged_count, 6)
        diff_p12 = next(d for d in record.task_diffs if d.task_id == "PO.1.2")
        self.assertEqual(diff_p12.diff_kind, DiffKind.MODIFIED)
        changed_fields = {f.field_name for f in diff_p12.changed_fields}
        self.assertIn("identified_evidence", changed_fields)

    def test_evidence_reordering_is_unchanged(self) -> None:
        """Reordering identified_evidence does not produce a MODIFIED finding."""
        ev1 = IdentifiedEvidence(type="policy", source_ref="policy/doc1.md#s1")
        ev2 = IdentifiedEvidence(type="procedure", source_ref="policy/doc2.md#s2")

        report_a = self._create_report(
            "REPORT-A",
            findings=[
                CorpusTaskFinding(
                    finding_id="F-01",
                    task_id="PO.1.2",
                    company_source_ref="policy/doc1.md",
                    company_statement="Statement",
                    coverage_verdict="COVERED",
                    basis=[
                        CorpusAssessmentBasis(
                            type="nist_normative",
                            task_id="PO.1.2",
                            source="NIST",
                            rationale="Rationale",
                        )
                    ],
                    assessment_rationale=["Rationale"],
                    identified_evidence=[ev1, ev2],
                    evidence_strength="high",
                    review_queue_recommendation="accepted",
                    cannot_claim=["No guarantee"],
                )
            ],
        )

        report_b = self._create_report(
            "REPORT-B",
            findings=[
                CorpusTaskFinding(
                    finding_id="F-01",
                    task_id="PO.1.2",
                    company_source_ref="policy/doc1.md",
                    company_statement="Statement",
                    coverage_verdict="COVERED",
                    basis=[
                        CorpusAssessmentBasis(
                            type="nist_normative",
                            task_id="PO.1.2",
                            source="NIST",
                            rationale="Rationale",
                        )
                    ],
                    assessment_rationale=["Rationale"],
                    identified_evidence=[ev2, ev1],  # reversed
                    evidence_strength="high",
                    review_queue_recommendation="accepted",
                    cannot_claim=["No guarantee"],
                )
            ],
        )

        record = self.engine.compare(report_a, report_b)
        self.assertEqual(record.modified_count, 0)
        self.assertEqual(record.unchanged_count, 1)
        self.assertEqual(record.task_diffs[0].diff_kind, DiffKind.UNCHANGED)

    def test_cli_diff_requires_provenance_or_allow_unverified(self) -> None:
        """CLI diff on repository_corpus fails closed without provenance or explicit allow flag."""
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from tempfile import TemporaryDirectory
        from tools.review_engine import main

        report = self._create_report("DIFF-TEST-PROV")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_path = tmp_path / "assessment.yaml"
            assessment_path.write_text(report.to_yaml(), encoding="utf-8")

            # 1. Fail closed without --allow-unverified-provenance
            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                exit_code = main([
                    str(assessment_path),
                    "--diff-baseline", str(assessment_path),
                    "--stdout",
                ])
            self.assertEqual(exit_code, 1)
            self.assertIn("Review Provenance Validation Failed", stderr_buf.getvalue())
            self.assertIn("--allow-unverified-provenance", stderr_buf.getvalue())

            # 2. Succeed with --allow-unverified-provenance and render UNVERIFIED warning
            stdout_buf = io.StringIO()
            with redirect_stdout(stdout_buf):
                exit_code = main([
                    str(assessment_path),
                    "--diff-baseline", str(assessment_path),
                    "--stdout",
                    "--allow-unverified-provenance",
                ])
            self.assertEqual(exit_code, 0)
            output = stdout_buf.getvalue()
            self.assertIn("# Assessment Comparison Diff", output)
            self.assertIn("Provenance Verification: UNVERIFIED", output)
            self.assertIn("--allow-unverified-provenance", output)

    def test_cli_diff_baseline_stdout_markdown(self) -> None:
        """CLI --diff-baseline prints diff report to stdout when unverified provenance is allowed."""
        import io
        from contextlib import redirect_stdout
        from tempfile import TemporaryDirectory
        from tools.review_engine import main

        report = self._create_report("DIFF-TEST-001")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_path = tmp_path / "assessment.yaml"
            assessment_path.write_text(report.to_yaml(), encoding="utf-8")

            stdout_buf = io.StringIO()
            with redirect_stdout(stdout_buf):
                exit_code = main([
                    str(assessment_path),
                    "--diff-baseline", str(assessment_path),
                    "--stdout",
                    "--allow-unverified-provenance",
                ])

            self.assertEqual(exit_code, 0)
            output = stdout_buf.getvalue()
            self.assertIn("# Assessment Comparison Diff", output)
            self.assertIn("## Comparison Summary", output)
            self.assertIn("UNCHANGED", output)

    def test_cli_diff_baseline_out_dir(self) -> None:
        """CLI --diff-baseline writes .diff.md and .diff.json to out-dir."""
        from tempfile import TemporaryDirectory
        from tools.review_engine import main

        report = self._create_report("DIFF-TEST-002")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_path = tmp_path / "assessment.yaml"
            assessment_path.write_text(report.to_yaml(), encoding="utf-8")
            out_dir = tmp_path / "out"

            exit_code = main([
                str(assessment_path),
                "--diff-baseline", str(assessment_path),
                "--out-dir", str(out_dir),
                "--format", "both",
                "--allow-unverified-provenance",
            ])

            self.assertEqual(exit_code, 0)
            diff_files = list(out_dir.glob("*.diff.*"))
            self.assertEqual(len(diff_files), 2)
            md_files = list(out_dir.glob("*.diff.md"))
            json_files = list(out_dir.glob("*.diff.json"))
            self.assertEqual(len(md_files), 1)
            self.assertEqual(len(json_files), 1)

            md_content = md_files[0].read_text(encoding="utf-8")
            self.assertIn("# Assessment Comparison Diff", md_content)
            json_data = json.loads(json_files[0].read_text(encoding="utf-8"))
            self.assertEqual(json_data["summary"]["unchanged"], 7)
            self.assertFalse(json_data["provenance_verified"])

    def test_cli_diff_missing_baseline_fails_closed(self) -> None:
        """CLI --diff-baseline fails closed when baseline file does not exist."""
        import io
        from contextlib import redirect_stderr
        from tempfile import TemporaryDirectory
        from tools.review_engine import main

        report = self._create_report("DIFF-TEST-003")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_path = tmp_path / "assessment.yaml"
            assessment_path.write_text(report.to_yaml(), encoding="utf-8")

            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                exit_code = main([
                    str(assessment_path),
                    "--diff-baseline", "non_existent_baseline.yaml",
                    "--allow-unverified-provenance",
                ])

            self.assertEqual(exit_code, 1)
            self.assertIn("Assessment file not found: non_existent_baseline.yaml", stderr_buf.getvalue())

    def test_cannot_claim_reordering_is_modified(self) -> None:
        """Scenario 13: Reordering cannot_claim entries changes author order, marking the task MODIFIED."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        target_findings = list(report_b.findings)
        first_finding = target_findings[0]
        base_cc = ["This does not prove compliance.", "This does not guarantee vulnerability absence."]
        rev_cc = ["This does not guarantee vulnerability absence.", "This does not prove compliance."]

        findings_a = list(report_a.findings)
        findings_a[0] = CorpusTaskFinding(
            finding_id=first_finding.finding_id,
            task_id=first_finding.task_id,
            company_source_ref=first_finding.company_source_ref,
            company_statement=first_finding.company_statement,
            coverage_verdict=first_finding.coverage_verdict,
            basis=first_finding.basis,
            assessment_rationale=first_finding.assessment_rationale,
            identified_evidence=first_finding.identified_evidence,
            evidence_strength=first_finding.evidence_strength,
            review_queue_recommendation=first_finding.review_queue_recommendation,
            cannot_claim=base_cc,
        )
        report_a = CorpusAssessmentReport(
            id=report_a.id,
            baseline=report_a.baseline,
            target=report_a.target,
            scope_tasks=report_a.scope_tasks,
            claim_boundary=report_a.claim_boundary,
            findings=findings_a,
        )

        target_findings[0] = CorpusTaskFinding(
            finding_id=first_finding.finding_id,
            task_id=first_finding.task_id,
            company_source_ref=first_finding.company_source_ref,
            company_statement=first_finding.company_statement,
            coverage_verdict=first_finding.coverage_verdict,
            basis=first_finding.basis,
            assessment_rationale=first_finding.assessment_rationale,
            identified_evidence=first_finding.identified_evidence,
            evidence_strength=first_finding.evidence_strength,
            review_queue_recommendation=first_finding.review_queue_recommendation,
            cannot_claim=rev_cc,
        )
        report_b = CorpusAssessmentReport(
            id=report_b.id,
            baseline=report_b.baseline,
            target=report_b.target,
            scope_tasks=report_b.scope_tasks,
            claim_boundary=report_b.claim_boundary,
            findings=target_findings,
        )

        record = self.engine.compare(report_a, report_b)
        self.assertEqual(record.modified_count, 1)
        self.assertEqual(record.unchanged_count, 6)
        diff_task = next(d for d in record.task_diffs if d.task_id == first_finding.task_id)
        self.assertEqual(diff_task.diff_kind, DiffKind.MODIFIED)
        changed_fields = {f.field_name for f in diff_task.changed_fields}
        self.assertIn("cannot_claim", changed_fields)

    def test_observation_comparison_scope_notice(self) -> None:
        """Diff record and rendered outputs explicitly declare observation comparison is not included."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        record = self.engine.compare(report_a, report_b)
        self.assertFalse(record.observations_compared)

        md = self.renderer.render_markdown(record)
        self.assertIn("Observation Comparison", md)
        self.assertIn("Not included in this comparison", md)

        json_data = json.loads(self.renderer.render_json(record))
        self.assertFalse(json_data["observations_compared"])

    def test_cli_diff_cross_commit_provenance_verified_pass(self) -> None:
        """Scenario 12: Cross-commit diff with independent baseline/target manifests verifies provenance."""
        import io
        import subprocess
        from contextlib import redirect_stdout
        from tempfile import TemporaryDirectory
        import yaml
        from tools.repo_corpus_resolver import RepoCorpusResolver
        from tools.review_engine import main
        from tools.validate_target_manifest import parse_target_manifest

        with TemporaryDirectory() as tmp_dir:
            repo_dir = Path(tmp_dir) / "repo"
            repo_dir.mkdir()

            def run_git(args: list[str]) -> str:
                return subprocess.check_output(
                    ["git"] + args,
                    cwd=repo_dir,
                    text=True,
                    stderr=subprocess.PIPE,
                ).strip()

            run_git(["init", "-b", "main"])
            run_git(["config", "user.name", "Diff Test"])
            run_git(["config", "user.email", "diff@example.com"])

            policy_dir = repo_dir / "policy"
            policy_dir.mkdir(parents=True)
            sec_file = policy_dir / "security.md"

            # Commit A
            sec_file.write_text("# Security Policy\nVersion 1 statement.\n", encoding="utf-8")
            run_git(["add", "policy/"])
            run_git(["commit", "-m", "commit A"])
            commit_a = run_git(["rev-parse", "HEAD"])

            manifest_a_content = f"""manifest_version: "1.0"
target:
  source_type: local_git
  repo: "{repo_dir.as_posix()}"
  commit: "{commit_a}"
authority_surface:
  include:
    - "policy/**"
  exclude: []
baseline:
  framework: NIST_SP_800_218
  version: "1.1"
mode:
  read_only: true
  enforce_clean: false
"""
            manifest_a_path = repo_dir / "target-manifest-a.yaml"
            manifest_a_path.write_text(manifest_a_content, encoding="utf-8")

            # Commit B
            sec_file.write_text("# Security Policy\nVersion 2 updated statement.\n", encoding="utf-8")
            run_git(["add", "policy/"])
            run_git(["commit", "-m", "commit B"])
            commit_b = run_git(["rev-parse", "HEAD"])

            manifest_b_content = f"""manifest_version: "1.0"
target:
  source_type: local_git
  repo: "{repo_dir.as_posix()}"
  commit: "{commit_b}"
authority_surface:
  include:
    - "policy/**"
  exclude: []
baseline:
  framework: NIST_SP_800_218
  version: "1.1"
mode:
  read_only: true
  enforce_clean: false
"""
            manifest_b_path = repo_dir / "target-manifest-b.yaml"
            manifest_b_path.write_text(manifest_b_content, encoding="utf-8")

            # Resolve snapshot A
            resolver = RepoCorpusResolver()
            m_a = parse_target_manifest(yaml.safe_load(manifest_a_content))
            snap_a = resolver.resolve(manifest=m_a, repo_path=repo_dir)

            target_a = CorpusAssessmentTarget(
                repo=repo_dir.as_posix(),
                commit=commit_a,
                manifest_path="target-manifest-a.yaml",
                manifest_digest=m_a.digest,
                corpus_digest=snap_a.corpus_digest,
                target_type="repository_corpus",
            )
            evidence_item = IdentifiedEvidence(
                type="policy_statement",
                source_ref="policy/security.md#security-policy",
            )
            findings_a = [
                CorpusTaskFinding(
                    finding_id=f"F-A-{idx:02d}",
                    task_id=t,
                    company_source_ref="policy/security.md#security-policy",
                    company_statement="Statement v1",
                    coverage_verdict="PARTIAL",
                    basis=[CorpusAssessmentBasis(type="nist_normative", task_id=t, source="NIST_SP_800_218_v1.1", rationale="Normative")],
                    assessment_rationale=["Rationale v1"],
                    identified_evidence=[evidence_item],
                    evidence_strength="medium",
                    review_queue_recommendation="accepted",
                    cannot_claim=["No compliance"],
                )
                for idx, t in enumerate(self.scope_tasks, start=1)
            ]
            report_a = CorpusAssessmentReport(
                id="ASSESS-A",
                baseline="NIST_SP_800_218_v1.1",
                target=target_a,
                scope_tasks=list(self.scope_tasks),
                claim_boundary=list(self.claim_boundary_base),
                findings=findings_a,
            )
            assess_a_file = Path(tmp_dir) / "assess_a.yaml"
            assess_a_file.write_text(report_a.to_yaml(), encoding="utf-8")

            # Resolve snapshot B
            m_b = parse_target_manifest(yaml.safe_load(manifest_b_content))
            snap_b = resolver.resolve(manifest=m_b, repo_path=repo_dir)

            target_b = CorpusAssessmentTarget(
                repo=repo_dir.as_posix(),
                commit=commit_b,
                manifest_path="target-manifest-b.yaml",
                manifest_digest=m_b.digest,
                corpus_digest=snap_b.corpus_digest,
                target_type="repository_corpus",
            )
            findings_b = [
                CorpusTaskFinding(
                    finding_id=f"F-B-{idx:02d}",
                    task_id=t,
                    company_source_ref="policy/security.md#security-policy",
                    company_statement="Statement v2",
                    coverage_verdict="COVERED" if t == "PO.1.2" else "PARTIAL",
                    basis=[CorpusAssessmentBasis(type="nist_normative", task_id=t, source="NIST_SP_800_218_v1.1", rationale="Normative")],
                    assessment_rationale=["Rationale v2"],
                    identified_evidence=[evidence_item],
                    evidence_strength="medium",
                    review_queue_recommendation="accepted",
                    cannot_claim=["No compliance"],
                )
                for idx, t in enumerate(self.scope_tasks, start=1)
            ]
            report_b = CorpusAssessmentReport(
                id="ASSESS-B",
                baseline="NIST_SP_800_218_v1.1",
                target=target_b,
                scope_tasks=list(self.scope_tasks),
                claim_boundary=list(self.claim_boundary_base),
                findings=findings_b,
            )
            assess_b_file = Path(tmp_dir) / "assess_b.yaml"
            assess_b_file.write_text(report_b.to_yaml(), encoding="utf-8")

            # 1. Positive CLI diff execution with --stdout
            stdout_buf = io.StringIO()
            with redirect_stdout(stdout_buf):
                exit_code = main([
                    str(assess_b_file),
                    "--diff-baseline", str(assess_a_file),
                    "--manifest", str(manifest_b_path),
                    "--baseline-manifest", str(manifest_a_path),
                    "--repo-path", str(repo_dir),
                    "--stdout",
                ])

            self.assertEqual(exit_code, 0)
            output = stdout_buf.getvalue()
            self.assertIn("# Assessment Comparison Diff", output)
            self.assertNotIn("Provenance Verification: UNVERIFIED", output)
            self.assertIn(commit_a, output)
            self.assertIn(commit_b, output)
            self.assertIn("Observation Comparison", output)

            # 2. Positive CLI diff execution with --out-dir and --format both
            out_dir = Path(tmp_dir) / "diff_out"
            exit_code_dir = main([
                str(assess_b_file),
                "--diff-baseline", str(assess_a_file),
                "--manifest", str(manifest_b_path),
                "--baseline-manifest", str(manifest_a_path),
                "--repo-path", str(repo_dir),
                "--out-dir", str(out_dir),
                "--format", "both",
            ])
            self.assertEqual(exit_code_dir, 0)

            # Check written files
            json_files = list(out_dir.glob("*.diff.json"))
            md_files = list(out_dir.glob("*.diff.md"))
            self.assertEqual(len(json_files), 1)
            self.assertEqual(len(md_files), 1)
            json_data = json.loads(json_files[0].read_text(encoding="utf-8"))
            self.assertTrue(json_data["provenance_verified"])
            self.assertFalse(json_data["observations_compared"])
            self.assertEqual(json_data["summary"]["total_tasks"], 7)

    def test_cli_diff_cross_commit_fails_closed_without_baseline_manifest(self) -> None:
        """Cross-commit diff fails closed if baseline manifest is omitted without allow-unverified flag."""
        import io
        from contextlib import redirect_stderr
        from tempfile import TemporaryDirectory
        from tools.review_engine import main

        report_a = self._create_report("ASSESS-A")
        report_b = self._create_report("ASSESS-B")

        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assess_a = tmp_path / "assess_a.yaml"
            assess_b = tmp_path / "assess_b.yaml"
            assess_a.write_text(report_a.to_yaml(), encoding="utf-8")
            assess_b.write_text(report_b.to_yaml(), encoding="utf-8")

            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                exit_code = main([
                    str(assess_b),
                    "--diff-baseline", str(assess_a),
                    "--manifest", "dummy_manifest.yaml",
                    "--repo-path", str(tmp_path),
                ])

            self.assertEqual(exit_code, 1)
            self.assertIn("Review Provenance Validation Failed", stderr_buf.getvalue())

    def test_default_library_compare_is_unverified_with_warning(self) -> None:
        """P1 Contract: Calling compare() directly defaults to provenance_verified=False and renders UNVERIFIED warning."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        record = self.engine.compare(report_a, report_b)
        self.assertFalse(record.provenance_verified)

        md = self.renderer.render_markdown(record)
        self.assertIn("Provenance Verification: UNVERIFIED", md)
        self.assertIn("--allow-unverified-provenance", md)

        json_data = json.loads(self.renderer.render_json(record))
        self.assertFalse(json_data["provenance_verified"])

    def test_explicit_verified_library_compare_has_no_warning(self) -> None:
        """P1 Contract: Explicitly supplying provenance_verified=True sets flag to True and renders no UNVERIFIED warning."""
        report_a = self._create_report("REPORT-A")
        report_b = self._create_report("REPORT-B")

        record = self.engine.compare(report_a, report_b, provenance_verified=True)
        self.assertTrue(record.provenance_verified)

        md = self.renderer.render_markdown(record)
        self.assertNotIn("Provenance Verification: UNVERIFIED", md)

        json_data = json.loads(self.renderer.render_json(record))
        self.assertTrue(json_data["provenance_verified"])


if __name__ == "__main__":
    unittest.main()
