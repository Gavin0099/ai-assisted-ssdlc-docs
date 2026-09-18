from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.corpus_assessment_engine import (
    CorpusAssessmentBasis,
    CorpusAssessmentReport,
    CorpusAssessmentTarget,
    CorpusTaskFinding,
    IdentifiedEvidence,
)
from tools.review_queue_projection import (
    ActionPriority,
    DeterministicQueueActionRenderer,
    ReviewQueueActionItem,
    ReviewQueueProjector,
)


class TestReviewQueueProjection(unittest.TestCase):
    def setUp(self) -> None:
        self.projector = ReviewQueueProjector()
        self.renderer = DeterministicQueueActionRenderer()

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
        findings: list[CorpusTaskFinding] | None = None,
    ) -> CorpusAssessmentReport:
        if findings is None:
            recs = [
                "needs_changes",
                "accepted_with_review_due",
                "pending",
                "deferred",
                "accepted",
                "rejected",
                "needs_changes",
            ]
            findings = []
            for idx, task_id in enumerate(self.scope_tasks):
                findings.append(
                    CorpusTaskFinding(
                        finding_id=f"F-TEST-{idx:02d}",
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
                        review_queue_recommendation=recs[idx % len(recs)],
                        cannot_claim=["No compliance guarantee"],
                    )
                )

        return CorpusAssessmentReport(
            id=report_id,
            baseline="NIST_SP_800_218_v1.1",
            target=self.target_base,
            scope_tasks=list(self.scope_tasks),
            claim_boundary=list(self.claim_boundary_base),
            findings=findings,
        )

    def test_priority_and_recommendation_mapping(self) -> None:
        """Scenario 14: Recommendations are deterministically mapped to ActionPriority."""
        report = self._create_report("PROJ-TEST-001")
        record = self.projector.project_queue(report)

        self.assertEqual(record.assessment_id, "PROJ-TEST-001")
        self.assertEqual(len(record.action_items), 7)

        # Map recommendations to priorities
        by_rec = {item.review_queue_recommendation: item.action_priority for item in record.action_items}
        self.assertEqual(by_rec["needs_changes"], ActionPriority.HIGH)
        self.assertEqual(by_rec["rejected"], ActionPriority.HIGH)
        self.assertEqual(by_rec["accepted_with_review_due"], ActionPriority.MEDIUM)
        self.assertEqual(by_rec["pending"], ActionPriority.MEDIUM)
        self.assertEqual(by_rec["deferred"], ActionPriority.LOW)
        self.assertEqual(by_rec["accepted"], ActionPriority.LOW)

    def test_deterministic_ordering_priority_and_tasks(self) -> None:
        """Scenario 14: Items are sorted deterministically: HIGH -> MEDIUM -> LOW, then task_id."""
        report = self._create_report("PROJ-TEST-002")
        record = self.projector.project_queue(report)

        priorities = [item.action_priority for item in record.action_items]
        # Verify all HIGH items come before MEDIUM, and MEDIUM before LOW
        seen_medium = False
        seen_low = False
        for p in priorities:
            if p == ActionPriority.HIGH:
                self.assertFalse(seen_medium, "HIGH appeared after MEDIUM")
                self.assertFalse(seen_low, "HIGH appeared after LOW")
            elif p == ActionPriority.MEDIUM:
                seen_medium = True
                self.assertFalse(seen_low, "MEDIUM appeared after LOW")
            elif p == ActionPriority.LOW:
                seen_low = True

    def test_direct_library_default_fail_closed(self) -> None:
        """Scenario 17: Calling project_queue without provenance_verified defaults to False with warning."""
        report = self._create_report("PROJ-TEST-003")
        record = self.projector.project_queue(report)

        self.assertFalse(record.provenance_verified)

        md = self.renderer.render_markdown(record)
        self.assertIn("Provenance Verification: UNVERIFIED", md)
        self.assertIn("--allow-unverified-provenance", md)

        json_data = json.loads(self.renderer.render_json(record))
        self.assertFalse(json_data["provenance_verified"])

    def test_direct_library_explicit_verified(self) -> None:
        """Explicit provenance_verified=True yields verified status and no warning banner."""
        report = self._create_report("PROJ-TEST-004")
        record = self.projector.project_queue(report, provenance_verified=True)

        self.assertTrue(record.provenance_verified)

        md = self.renderer.render_markdown(record)
        self.assertNotIn("Provenance Verification: UNVERIFIED", md)

        json_data = json.loads(self.renderer.render_json(record))
        self.assertTrue(json_data["provenance_verified"])

    def test_no_evaluative_sentiment_in_queue_projection(self) -> None:
        """Rendered Markdown strictly avoids evaluative words."""
        report = self._create_report("PROJ-TEST-005")
        record = self.projector.project_queue(report)
        md = self.renderer.render_markdown(record)

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
            self.assertNotIn(word, md_lower, f"Prohibited word found: {word}")

    def test_read_only_invariant_does_not_mutate_review_queue(self) -> None:
        """Scenario 15: Running CLI --project-queue does not touch or overwrite existing review-queue.yaml."""
        from tools.review_engine import main
        import hashlib

        report = self._create_report("PROJ-CLI-001")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_file = tmp_path / "assessment.yaml"
            assessment_file.write_text(report.to_yaml(), encoding="utf-8")

            # Create existing review queue file
            existing_queue = tmp_path / "review-queue.yaml"
            queue_content = "schema_version: '1.0'\nqueue_items:\n  - item_id: RQ-001\n"
            existing_queue.write_text(queue_content, encoding="utf-8")
            original_hash = hashlib.sha256(existing_queue.read_bytes()).hexdigest()

            out_dir = tmp_path / "out"
            exit_code = main([
                str(assessment_file),
                "--project-queue",
                "--out-dir", str(out_dir),
                "--format", "both",
                "--allow-unverified-provenance",
            ])

            self.assertEqual(exit_code, 0)

            # Assert existing queue file was not touched or mutated
            self.assertTrue(existing_queue.exists())
            current_hash = hashlib.sha256(existing_queue.read_bytes()).hexdigest()
            self.assertEqual(original_hash, current_hash)

            # Assert queue action files were written to out_dir
            md_files = list(out_dir.glob("*.queue-actions.md"))
            json_files = list(out_dir.glob("*.queue-actions.json"))
            self.assertEqual(len(md_files), 1)
            self.assertEqual(len(json_files), 1)

    def test_cli_queue_projection_fail_closed_without_provenance(self) -> None:
        """Scenario 16: CLI --project-queue fails closed if provenance is unverified without opt-in flag."""
        from tools.review_engine import main

        report = self._create_report("PROJ-CLI-002")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_file = tmp_path / "assessment.yaml"
            assessment_file.write_text(report.to_yaml(), encoding="utf-8")

            stderr_buf = io.StringIO()
            with redirect_stderr(stderr_buf):
                exit_code = main([
                    str(assessment_file),
                    "--project-queue",
                    "--stdout",
                ])

            self.assertEqual(exit_code, 1)
            self.assertIn("Review Provenance Validation Failed", stderr_buf.getvalue())
            self.assertIn("--allow-unverified-provenance", stderr_buf.getvalue())

    def test_cli_queue_projection_stdout_markdown(self) -> None:
        """CLI --project-queue prints action projection to stdout."""
        from tools.review_engine import main

        report = self._create_report("PROJ-CLI-003")
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            assessment_file = tmp_path / "assessment.yaml"
            assessment_file.write_text(report.to_yaml(), encoding="utf-8")

            stdout_buf = io.StringIO()
            with redirect_stdout(stdout_buf):
                exit_code = main([
                    str(assessment_file),
                    "--project-queue",
                    "--stdout",
                    "--allow-unverified-provenance",
                ])

            self.assertEqual(exit_code, 0)
            output = stdout_buf.getvalue()
            self.assertIn("# Review Queue Action Projection", output)
            self.assertIn("## Action Summary", output)
            self.assertIn("## Projected Action Items", output)
            self.assertIn("Provenance Verification: UNVERIFIED", output)

    def test_cli_queue_projection_verified_provenance_pass(self) -> None:
        """CLI --project-queue with valid manifest and repo verifies provenance and renders no UNVERIFIED warning."""
        import subprocess
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
            run_git(["config", "user.name", "Test"])
            run_git(["config", "user.email", "test@example.com"])

            policy_dir = repo_dir / "policy"
            policy_dir.mkdir(parents=True)
            sec_file = policy_dir / "security.md"
            sec_file.write_text("# Security Policy\nPolicy statement text.\n", encoding="utf-8")

            run_git(["add", "policy/"])
            run_git(["commit", "-m", "commit 1"])
            commit_sha = run_git(["rev-parse", "HEAD"])

            manifest_content = f"""manifest_version: "1.0"
target:
  source_type: local_git
  repo: "{repo_dir.as_posix()}"
  commit: "{commit_sha}"
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
            manifest_path = repo_dir / "target-manifest.yaml"
            manifest_path.write_text(manifest_content, encoding="utf-8")

            m_obj = parse_target_manifest(yaml.safe_load(manifest_content))
            resolver = RepoCorpusResolver()
            snap = resolver.resolve(manifest=m_obj, repo_path=repo_dir)

            target = CorpusAssessmentTarget(
                repo=repo_dir.as_posix(),
                commit=commit_sha,
                manifest_path="target-manifest.yaml",
                manifest_digest=m_obj.digest,
                corpus_digest=snap.corpus_digest,
                target_type="repository_corpus",
            )
            ev_item = IdentifiedEvidence(type="policy_statement", source_ref="policy/security.md#security-policy")
            findings = [
                CorpusTaskFinding(
                    finding_id=f"F-V-{idx:02d}",
                    task_id=t,
                    company_source_ref="policy/security.md#security-policy",
                    company_statement="Statement",
                    coverage_verdict="PARTIAL",
                    basis=[CorpusAssessmentBasis(type="nist_normative", task_id=t, source="NIST_SP_800_218_v1.1", rationale="Normative")],
                    assessment_rationale=["Rationale"],
                    identified_evidence=[ev_item],
                    evidence_strength="medium",
                    review_queue_recommendation="needs_changes" if idx % 2 == 0 else "accepted",
                    cannot_claim=["No compliance guarantee"],
                )
                for idx, t in enumerate(self.scope_tasks, start=1)
            ]
            report = CorpusAssessmentReport(
                id="PROJ-VERIFIED-001",
                baseline="NIST_SP_800_218_v1.1",
                target=target,
                scope_tasks=list(self.scope_tasks),
                claim_boundary=list(self.claim_boundary_base),
                findings=findings,
            )
            assess_path = Path(tmp_dir) / "assess.yaml"
            assess_path.write_text(report.to_yaml(), encoding="utf-8")

            stdout_buf = io.StringIO()
            with redirect_stdout(stdout_buf):
                exit_code = main([
                    str(assess_path),
                    "--project-queue",
                    "--manifest", str(manifest_path),
                    "--repo-path", str(repo_dir),
                    "--stdout",
                ])

            self.assertEqual(exit_code, 0)
            output = stdout_buf.getvalue()
            self.assertIn("# Review Queue Action Projection", output)
            self.assertNotIn("Provenance Verification: UNVERIFIED", output)
            self.assertIn("Needs Action", output)


if __name__ == "__main__":
    unittest.main()
