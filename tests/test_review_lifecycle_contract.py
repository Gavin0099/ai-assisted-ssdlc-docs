"""C1-C8 lifecycle fixtures contain synthetic decisions only, never real approvals."""
import copy
import json

import yaml

from test_report_data_contract import ContractTestCase
from tools.report_data_contract import ReportContractError
from tools.review_lifecycle_contract import (
    load_review_lifecycle, parse_acceptance_decision, parse_review_lifecycle,
    parse_sync_decision, parse_sync_verification,
)


class TestReviewLifecycleContract(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.lifecycle = {"report_data_ref": self.bundle.ref("report-data.json"), "machine_baseline_ref": None,
                          "review_recommendation": {"opinion": "CHANGES_REQUESTED", "reason": "Synthetic document correction requested."},
                          "acceptance_ref": None,
                          "sync": {"state": "not_checked", "target_ref": None, "decision_ref": None, "verification_ref": None}}
        self.save_lifecycle()

    def save_lifecycle(self):
        self.lifecycle["report_data_ref"] = self.bundle.ref("report-data.json")
        self.bundle.write_json("review-lifecycle.json", self.lifecycle)

    def bindings(self, with_target=False):
        result = {"report_data_sha256": self.bundle.ref("report-data.json")["sha256"],
                  "assessment_sha256": self.bundle.ref("assessment.yaml")["sha256"],
                  "evidence_ref": self.bundle.ref("evidence.txt")}
        if with_target:
            result["target_sha256"] = self.bundle.ref("target.yaml")["sha256"]
        return result

    def accept(self):
        self.bundle.write_json("acceptance.json", {"decision": "accepted", **self.bindings()})
        self.lifecycle["acceptance_ref"] = self.bundle.ref("acceptance.json")
        self.save_lifecycle()

    def set_sync(self, state="synced", target=None):
        target = copy.deepcopy(self.bundle.assessment) if target is None else target
        target["assessment"]["id"] = "synthetic-machine"
        self.bundle.write("target.yaml", yaml.safe_dump(target, sort_keys=False).encode())
        self.bundle.write_json("sync-decision.json", {"decision": "synchronize", **self.bindings(True)})
        self.bundle.write_json("sync-verification.json", {"result": "matched" if state == "synced" else "not_synced", **self.bindings(True)})
        self.lifecycle["sync"] = {"state": state, "target_ref": self.bundle.ref("target.yaml"),
                                  "decision_ref": self.bundle.ref("sync-decision.json") if state == "synced" else None,
                                  "verification_ref": self.bundle.ref("sync-verification.json")}
        self.save_lifecycle()

    def load(self):
        return load_review_lifecycle("review-lifecycle.json", self.root)

    def rewrite_record(self, name, changes, lifecycle_ref):
        value = json.loads((self.root / name).read_text(encoding="utf-8"))
        value.update(changes)
        self.bundle.write_json(name, value)
        if lifecycle_ref == "acceptance_ref":
            self.lifecycle[lifecycle_ref] = self.bundle.ref(name)
        else:
            self.lifecycle["sync"][lifecycle_ref] = self.bundle.ref(name)
        self.save_lifecycle()

    def test_c1_covered_weak_p1_changes_requested_draft_not_synced_coexist(self):
        old = copy.deepcopy(self.bundle.assessment)
        old["assessment"]["target"]["commit"] = "2" * 40
        old["results"][0].update(coverage_verdict="PARTIAL", evidence_strength="medium")
        self.set_sync("not_synced", old)
        before = self.snapshot()
        loaded = self.load()
        self.assertFalse(loaded.accepted)
        self.assertEqual(loaded.lifecycle.review_recommendation.opinion, "CHANGES_REQUESTED")
        self.assertEqual(loaded.lifecycle.sync.state, "not_synced")
        self.assertEqual(loaded.report_data.assessment.report.findings[0].coverage_verdict, "COVERED")
        self.assertEqual(loaded.report_data.assessment.report.findings[0].evidence_strength, "weak")
        self.assertEqual(loaded.report_data.data.actions[0].priority, "P1")
        self.assertEqual(before, self.snapshot())

    def test_c2_recommendation_accepted_is_not_an_acceptance_event(self):
        self.lifecycle["review_recommendation"]["opinion"] = "ACCEPTED"
        self.save_lifecycle()
        loaded = self.load()
        self.assertFalse(loaded.accepted)
        self.assertEqual(loaded.lifecycle.sync.state, "not_checked")
        self.assertEqual(loaded.report_data.assessment.report.findings[0].review_queue_recommendation, "needs_changes")

    def test_structured_acceptance_binds_exact_bytes_without_syncing(self):
        self.accept()
        before = self.snapshot()
        loaded = self.load()
        self.assertTrue(loaded.accepted)
        self.assertEqual(loaded.lifecycle.sync.state, "not_checked")
        self.assertIsNone(loaded.target)
        self.assertEqual(before, self.snapshot())

    def test_c5_historical_baseline_preserves_distinct_corpus_and_values(self):
        old = copy.deepcopy(self.bundle.assessment)
        old["assessment"]["target"].update(commit="2" * 40, corpus_digest="3" * 64)
        old["results"][0].update(coverage_verdict="PARTIAL", evidence_strength="medium")
        self.bundle.write("baseline.yaml", yaml.safe_dump(old).encode())
        self.lifecycle["machine_baseline_ref"] = self.bundle.ref("baseline.yaml")
        self.save_lifecycle()
        loaded = self.load()
        self.assertEqual(loaded.machine_baseline.report.findings[0].coverage_verdict, "PARTIAL")
        self.assertEqual(loaded.machine_baseline.report.findings[0].evidence_strength, "medium")
        self.assertEqual(loaded.report_data.assessment.report.findings[0].coverage_verdict, "COVERED")
        self.assertNotEqual(loaded.machine_baseline.report.target.corpus_digest, loaded.report_data.corpus.corpus_digest)
        self.assertEqual(loaded.lifecycle.sync.state, "not_checked")

    def test_sync_requires_actual_target_match_and_structured_action(self):
        self.set_sync()
        before = self.snapshot()
        loaded = self.load()
        self.assertEqual(loaded.lifecycle.sync.state, "synced")
        self.assertEqual(loaded.sync_decision.decision, "synchronize")
        self.assertFalse(loaded.accepted)
        self.assertNotEqual(loaded.target.report.id, loaded.report_data.assessment.report.id)
        self.assertEqual(before, self.snapshot())

    def test_c5_same_verdict_different_scope_or_results_cannot_be_synced(self):
        def different_task_scope(a):
            a["assessment"]["scope_tasks"] = ["PW.8.1"]
            a["results"][0]["task_id"] = "PW.8.1"
            a["results"][0]["basis"][0]["task_id"] = "PW.8.1"

        mutations = [
            ("task_scope", different_task_scope),
            ("repo", lambda a: a["assessment"]["target"].update(repo="other/repo")),
            ("commit", lambda a: a["assessment"]["target"].update(commit="2" * 40)),
            ("manifest", lambda a: a["assessment"]["target"].update(manifest_digest="2" * 64)),
            ("corpus", lambda a: a["assessment"]["target"].update(corpus_digest="2" * 64)),
            ("strength", lambda a: a["results"][0].update(evidence_strength="medium")),
            ("queue", lambda a: a["results"][0].update(review_queue_recommendation="pending")),
            ("cannot_claim", lambda a: a["results"][0].update(cannot_claim=["Cannot claim company-wide coverage."])),
            ("rationale", lambda a: a["results"][0].update(assessment_rationale=["Different recorded assessment reason."])),
            ("basis_order", lambda a: a["results"][0]["basis"].reverse()),
            ("statement", lambda a: a["results"][0].update(company_statement="Different source statement.")),
            ("identified_evidence", lambda a: a["results"][0].update(identified_evidence=[{"type": "policy", "source_ref": "policy.md#release"}])),
            ("claim_boundary", lambda a: a["assessment"].update(claim_boundary=["Cannot claim company-wide coverage."])),
        ]
        for name, mutate in mutations:
            with self.subTest(dimension=name):
                target = copy.deepcopy(self.bundle.assessment)
                mutate(target)
                self.set_sync(target=target)  # All fingerprints valid: content checks must still reject.
                with self.assertRaisesRegex(ReportContractError, "sync.verification"):
                    self.load()

    def test_c6_missing_and_unknown_decisions_fail_closed(self):
        self.accept()
        for token in [None, "ACCEPTED", "pending", True]:
            with self.subTest(token=token):
                self.rewrite_record("acceptance.json", {"decision": token}, "acceptance_ref")
                with self.assertRaises(ReportContractError):
                    self.load()
        self.accept()
        record = json.loads((self.root / "acceptance.json").read_text())
        del record["decision"]
        self.bundle.write_json("acceptance.json", record)
        self.lifecycle["acceptance_ref"] = self.bundle.ref("acceptance.json")
        self.save_lifecycle()
        with self.assertRaisesRegex(ReportContractError, "missing/unknown"):
            self.load()

    def test_c6_markdown_file_exists_but_is_not_acceptance_or_sync_proof(self):
        self.bundle.write("decision.md", b"Synthetic chat: accepted and synced.\n")
        self.lifecycle["acceptance_ref"] = self.bundle.ref("decision.md")
        self.save_lifecycle()
        with self.assertRaisesRegex(ReportContractError, "JSON"):
            self.load()
        self.lifecycle["acceptance_ref"] = None
        self.set_sync()
        for key in ["decision_ref", "verification_ref"]:
            with self.subTest(key=key):
                self.set_sync()
                self.lifecycle["sync"][key] = self.bundle.ref("decision.md")
                self.save_lifecycle()
                with self.assertRaisesRegex(ReportContractError, "JSON"):
                    self.load()

    def test_acceptance_binding_checks_both_report_and_assessment_hashes(self):
        for field in ["report_data_sha256", "assessment_sha256"]:
            with self.subTest(field=field):
                self.accept()
                self.rewrite_record("acceptance.json", {field: "2" * 64}, "acceptance_ref")
                with self.assertRaisesRegex(ReportContractError, "decision.binding"):
                    self.load()

    def test_c6_old_acceptance_does_not_cover_new_report_bytes(self):
        self.accept()
        self.bundle.data["actions"][0]["details"]["要修改或補什麼"] = "Different synthetic correction wording."
        self.bundle.save()
        self.save_lifecycle()  # lifecycle points at new report; old acceptance remains pinned.
        with self.assertRaisesRegex(ReportContractError, "decision.binding"):
            self.load()

    def test_sync_binding_checks_report_assessment_and_target_hashes(self):
        for name, key in [("sync-decision.json", "decision_ref"), ("sync-verification.json", "verification_ref")]:
            for field in ["report_data_sha256", "assessment_sha256", "target_sha256"]:
                with self.subTest(record=name, field=field):
                    self.set_sync()
                    self.rewrite_record(name, {field: "2" * 64}, key)
                    with self.assertRaisesRegex(ReportContractError, "decision.binding"):
                        self.load()

    def test_sync_state_and_reference_requirements_are_consistent(self):
        self.set_sync()
        good = copy.deepcopy(self.lifecycle)
        mutations = [{"state": "not_checked"}, {"state": "synced", "decision_ref": None},
                     {"state": "not_synced", "verification_ref": None}, {"state": "not_synced", "target_ref": None}, {"state": "SYNCED"}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                data = copy.deepcopy(good)
                data["sync"].update(mutation)
                with self.assertRaisesRegex(ReportContractError, "sync.state"):
                    parse_review_lifecycle(data)

    def test_sync_result_disagrees_with_state_or_actual_content(self):
        self.set_sync()
        self.rewrite_record("sync-verification.json", {"result": "not_synced"}, "verification_ref")
        with self.assertRaisesRegex(ReportContractError, "sync.verification"):
            self.load()
        self.set_sync("not_synced")  # Equal contents cannot support a mismatch claim.
        with self.assertRaisesRegex(ReportContractError, "sync.verification"):
            self.load()
        self.set_sync()
        self.rewrite_record("sync-verification.json", {"result": "verified"}, "verification_ref")
        with self.assertRaisesRegex(ReportContractError, "sync.result"):
            self.load()

    def test_non_null_invalid_proofs_raise_instead_of_becoming_draft(self):
        self.lifecycle["acceptance_ref"] = {"path": "not-found.json", "sha256": "2" * 64}
        self.save_lifecycle()
        with self.assertRaises(ReportContractError):
            self.load()
        self.accept()
        self.bundle.write("acceptance.json", b"{}")
        with self.assertRaisesRegex(ReportContractError, "artifact.hash"):
            self.load()

    def test_every_decision_evidence_ref_is_verified(self):
        self.accept()
        self.bundle.write("evidence.txt", b"tampered synthetic supporting evidence")
        with self.assertRaisesRegex(ReportContractError, "artifact.hash"):
            self.load()
        self.lifecycle["acceptance_ref"] = None
        self.set_sync()
        self.rewrite_record("sync-decision.json", {"evidence_ref": {"path": "../outside.txt", "sha256": "2" * 64}}, "decision_ref")
        with self.assertRaisesRegex(ReportContractError, "relative path"):
            self.load()

    def test_decision_parsers_are_strict_about_shape_and_types(self):
        self.set_sync()
        for parser, value in [(parse_acceptance_decision, {"decision": "accepted", **self.bindings()}),
                              (parse_sync_decision, {"decision": "synchronize", **self.bindings(True)}),
                              (parse_sync_verification, {"result": "matched", **self.bindings(True)})]:
            with self.subTest(parser=parser.__name__):
                self.assertIsNotNone(parser(value))
                with self.assertRaises(ReportContractError):
                    parser({**value, "extra_decision": "accepted"})
                with self.assertRaises(ReportContractError):
                    parser({**value, "assessment_sha256": True})

    def test_lifecycle_preserves_incomplete_report_without_inventing_acceptance(self):
        self.bundle.data["actions"] = None
        self.bundle.save()
        self.save_lifecycle()
        loaded = self.load()
        self.assertFalse(loaded.report_data.validation.complete)
        self.assertFalse(loaded.accepted)
        self.assertEqual(loaded.lifecycle.sync.state, "not_checked")

    def test_decision_evidence_is_relative_to_the_decision_file(self):
        self.bundle.write("decisions/evidence.txt", b"Synthetic nested evidence.")
        value = {"decision": "accepted", **self.bindings()}
        value["evidence_ref"] = {**self.bundle.ref("decisions/evidence.txt"), "path": "evidence.txt"}
        self.bundle.write_json("decisions/acceptance.json", value)
        self.lifecycle["acceptance_ref"] = self.bundle.ref("decisions/acceptance.json")
        self.save_lifecycle()
        self.assertTrue(self.load().accepted)


if __name__ == "__main__":
    import unittest
    unittest.main()
