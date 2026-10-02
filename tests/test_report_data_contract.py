"""Minimal synthetic REPORT-3B fixtures; no REPORT-2/branch-16 migration.

Expected behavior comes from frozen contract sections 1-7 / C1-C8.
Fixed identity digests below are precomputed fixture constants, not calls to
the production parser/digest routine. Runtime ArtifactRefs hash fixture bytes.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from tools.report_data_contract import (
    ArtifactRef, ArtifactStore, ReportContractError, decode_json,
    load_report_data, parse_report_data,
)

POLICY_HASH = "b4b631dd5041e2e31bad3cce4b139d0fcd5ca11239efece7022a5593afc2d4c4"
CORPUS_HASH = "8170a1a0cd1da753a74eedbf44783cc752125a78e7705e1b45633e9683fb05b8"
MANIFEST_HASH = "5d94bf21da55ac458ab9e6323ec9e428b4b4db5b0fc6e93e17d410a82dedb821"
BASELINE = "NIST_SP_800_218_v1.1"


class MinimalBundle:
    def __init__(self, root):
        self.root = root
        self.write("policy.md", b"Synthetic document statements only.\n")
        self.write("evidence.txt", b"Synthetic decision evidence; not a real approval.\n")
        self.manifest = {
            "target": {"source_type": "github", "repo": "example/ssdlc", "commit": "1" * 40},
            "authority_surface": {"include": ["policy.md"], "exclude": []},
            "baseline": {"framework": "NIST_SP_800_218", "version": "1.1"},
            "mode": {"read_only": True},
        }
        self.assessment = {
            "assessment": {"id": "synthetic-human", "baseline": BASELINE,
                           "target": {"type": "repository_corpus", "repo": "example/ssdlc", "commit": "1" * 40,
                                      "manifest_path": "manifest.yaml", "manifest_digest": MANIFEST_HASH, "corpus_digest": CORPUS_HASH},
                           "scope_tasks": ["PW.4.4"], "claim_boundary": ["Document coverage only; no implementation claim."]},
            "results": [{"finding_id": "F-44", "finding_type": "task_finding", "task_id": "PW.4.4",
                         "company_source_ref": "policy.md#component", "company_statement": "Synthetic component management requirement.",
                         "coverage_verdict": "COVERED", "basis": [
                             {"type": "nist_normative", "task_id": "PW.4.4", "source": BASELINE, "rationale": "Task requirement as normative basis."},
                             {"type": "reviewer_inference", "rationale": "Synthetic independent observation."}],
                         "assessment_rationale": ["The synthetic document states the requirement."],
                         "identified_evidence": [{"type": "policy", "source_ref": "policy.md#component"}],
                         "evidence_strength": "weak", "review_queue_recommendation": "needs_changes",
                         "cannot_claim": ["Cannot claim implementation or release approval."]}],
        }
        self.metadata = {"target_commit": "1" * 40, "total_files": 1, "total_bytes": 36,
                         "manifest_digest": MANIFEST_HASH, "corpus_digest": CORPUS_HASH,
                         "files": [{"relative_path": "policy.md", "content_hash": POLICY_HASH, "byte_size": 36}]}
        self.data = {"contract_version": "0.1", "report_id": "synthetic-report",
                     "assessment_ref": {}, "corpus_metadata_ref": {},
                     "task_supplements": [{"finding_id": "F-44", "document_refs": ["policy.md#component"],
                                            "gap_items": [], "improvement_items": []}],
                     "actions": [self.action()], "auxiliary_sources": [],
                     "source_authority": [{"path": "policy.md", "state": "draft", "raw_status": "Draft",
                                           "status_source_ref": "policy.md#header", "approval_ref": None}],
                     "retained_content_refs": []}
        self.save()

    def write(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def write_json(self, name, value):
        self.write(name, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())

    def ref(self, name):
        return {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def save(self):
        self.write("manifest.yaml", yaml.safe_dump(self.manifest, sort_keys=False).encode())
        self.write("assessment.yaml", yaml.safe_dump(self.assessment, sort_keys=False).encode())
        self.write_json("corpus.json", self.metadata)
        self.data["assessment_ref"] = self.ref("assessment.yaml")
        self.data["corpus_metadata_ref"] = self.ref("corpus.json")
        self.write_json("report-data.json", self.data)

    def action(self, action_id="E-05"):
        return {"action_id": action_id, "group": "A", "kind": "文件宣稱待修", "priority": "P1",
                "priority_reason": "Synthetic premature approval statement.", "scope_labels": ["Synthetic Product"],
                "finding_refs": [], "locations": [{"source_ref": "policy.md#release", "source_scope": "corpus", "display_text": "policy.md §release"}],
                "basis": [{"type": "local_derived_guidance", "source": "policy.md#release", "rationale": "Draft statements cannot establish approval."}],
                "details": {"規則依據與效力": "合成草稿的宣稱限制，非已生效公司政策。", "目前哪裡有問題": "合成文件提前宣稱已核准。",
                            "要修改或補什麼": "移除未有證明的核准文字。", "完成確認方式": "修改處能追到實際決策紀錄。",
                            "適用條件與待確認事項": "本例只用於 contract 測試。", "對判定的影響與不能宣稱": "不自動降低 Task coverage 或證明實作。",
                            "修訂句": "請修改 policy.md §release 的提前核准文字；完成後核對真實決策來源。"}, "tracking": None}

    def gap(self, basis_refs=(0,), source_refs=("policy.md#component",)):
        return {"text": "Synthetic task-relevant gap.", "source_refs": list(source_refs), "basis_refs": list(basis_refs)}

    def load(self, **kwargs):
        return load_report_data("report-data.json", self.root, **kwargs)


class ContractTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.bundle = MinimalBundle(self.root)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}


class TestReportDataContract(ContractTestCase):
    def test_c1_covered_weak_p1_action_is_valid_and_read_only(self):
        before = self.snapshot()
        result = self.bundle.load()
        self.assertTrue(result.validation.complete)
        self.assertEqual(result.assessment.report.findings[0].coverage_verdict, "COVERED")
        self.assertEqual(result.assessment.report.findings[0].evidence_strength, "weak")
        self.assertEqual(result.assessment.report.findings[0].review_queue_recommendation, "needs_changes")
        self.assertEqual(result.data.actions[0].priority, "P1")
        self.assertEqual(result.data.actions[0].finding_refs, ())
        self.assertEqual(before, self.snapshot())

    def test_c2_improvement_does_not_downgrade_coverage(self):
        self.bundle.data["task_supplements"][0]["improvement_items"] = [self.bundle.gap(basis_refs=(1,))]
        self.bundle.save()
        self.assertEqual(self.bundle.load().assessment.report.findings[0].coverage_verdict, "COVERED")

    def test_c2_gap_verdict_contradictions_fail_without_rewriting(self):
        for verdict, gaps in [("COVERED", [self.bundle.gap()]), ("PARTIAL", [])]:
            with self.subTest(verdict=verdict):
                self.bundle.assessment["results"][0]["coverage_verdict"] = verdict
                self.bundle.data["task_supplements"][0]["gap_items"] = gaps
                self.bundle.save()
                before = self.snapshot()
                with self.assertRaisesRegex(ReportContractError, "verdict/gap"):
                    self.bundle.load()
                self.assertEqual(before, self.snapshot())

    def test_partial_with_normative_gap_is_valid(self):
        self.bundle.assessment["results"][0]["coverage_verdict"] = "PARTIAL"
        self.bundle.data["task_supplements"][0]["gap_items"] = [self.bundle.gap()]
        self.bundle.save()
        self.assertTrue(self.bundle.load().validation.complete)

    def test_inference_only_gap_cannot_establish_task_requirement(self):
        self.bundle.assessment["results"][0]["coverage_verdict"] = "PARTIAL"
        self.bundle.data["task_supplements"][0]["gap_items"] = [self.bundle.gap(basis_refs=(1,))]
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "normative"):
            self.bundle.load()

    def test_c3_null_and_empty_remain_distinct(self):
        s = self.bundle.data["task_supplements"][0]
        s["gap_items"] = None
        self.bundle.data["actions"] = None
        self.bundle.save()
        result = self.bundle.load()
        self.assertIsNone(result.data.task_supplements[0].gap_items)
        self.assertIsNone(result.data.actions)
        self.assertFalse(result.validation.complete)
        self.assertIn("actions not organized", result.validation.incomplete)
        s["gap_items"] = []
        self.bundle.data["actions"] = []
        self.bundle.save()
        result = self.bundle.load()
        self.assertEqual(result.data.task_supplements[0].gap_items, ())
        self.assertEqual(result.data.actions, ())
        self.assertTrue(result.validation.complete)

    def test_c3_missing_supplement_is_explicitly_incomplete(self):
        self.bundle.data["task_supplements"] = []
        self.bundle.save()
        self.assertIn("supplement missing: F-44", self.bundle.load().validation.incomplete)

    def test_c4_uncollected_is_not_unspecified(self):
        record = self.bundle.data["source_authority"][0]
        record.update(state=None, raw_status=None, status_source_ref=None)
        self.bundle.save()
        result = self.bundle.load()
        self.assertIsNone(result.data.source_authority[0].state)
        self.assertIn("authority uncollected: policy.md", result.validation.incomplete)
        record.update(state="unspecified", status_source_ref="policy.md#reviewed-header")
        self.bundle.save()
        result = self.bundle.load()
        self.assertEqual(result.data.source_authority[0].state, "unspecified")
        self.assertTrue(result.validation.complete)

    def test_c4_unspecified_requires_review_evidence(self):
        self.bundle.data["source_authority"][0].update(state="unspecified", raw_status=None, status_source_ref=None)
        with self.assertRaisesRegex(ReportContractError, "authority"):
            parse_report_data(self.bundle.data)

    def test_authority_missing_duplicate_extra_are_rejected(self):
        original = copy.deepcopy(self.bundle.data["source_authority"])
        extra = {**original[0], "path": "auxiliary.md"}
        for records in [[], original + original, original + [extra]]:
            with self.subTest(records=records):
                self.bundle.data["source_authority"] = records
                self.bundle.save()
                with self.assertRaisesRegex(ReportContractError, "source_authority"):
                    self.bundle.load()

    def test_supplement_duplicate_unknown_observation_ids_are_rejected(self):
        original = copy.deepcopy(self.bundle.data["task_supplements"])
        for supplements in [original + original, [{**original[0], "finding_id": "O-01"}], [{**original[0], "finding_id": "unknown"}]]:
            with self.subTest(supplements=supplements):
                self.bundle.data["task_supplements"] = supplements
                self.bundle.save()
                with self.assertRaisesRegex(ReportContractError, "supplement"):
                    self.bundle.load()

    def test_basis_index_boundaries_and_boolean_are_rejected(self):
        for index in [-1, 2, True, "0"]:
            with self.subTest(index=index):
                self.bundle.data["task_supplements"][0]["improvement_items"] = [self.bundle.gap(basis_refs=(index,))]
                self.bundle.save()
                with self.assertRaisesRegex(ReportContractError, "basis"):
                    self.bundle.load()

    def test_invalid_d1_sources_and_sentinel_expansion_are_rejected(self):
        for source in ["missing.md#s", "../policy.md#s", "<corpus>#unmentioned", "C:/policy.md#s"]:
            with self.subTest(source=source):
                self.bundle.data["task_supplements"][0]["document_refs"] = [source]
                self.bundle.save()
                with self.assertRaises(ReportContractError):
                    self.bundle.load()

    def test_original_missing_sentinel_can_be_referenced_by_gap_only(self):
        finding = self.bundle.assessment["results"][0]
        finding.update(coverage_verdict="MISSING", company_source_ref="<corpus>#unmentioned",
                       identified_evidence=[{"type": "absence", "source_ref": "<corpus>#unmentioned"}])
        self.bundle.data["task_supplements"][0].update(document_refs=[], gap_items=[self.bundle.gap(source_refs=("<corpus>#unmentioned",))])
        self.bundle.save()
        self.assertTrue(self.bundle.load().validation.complete)

    def test_action_ids_groups_priorities_and_refs_are_checked(self):
        for key, value in [("group", "D"), ("priority", "P4"), ("priority", None), ("finding_refs", ["unknown"]), ("locations", [])]:
            with self.subTest(key=key, value=value):
                action = self.bundle.action()
                action[key] = value
                self.bundle.data["actions"] = [action]
                self.bundle.save()
                with self.assertRaises(ReportContractError):
                    self.bundle.load()
        self.bundle.data["actions"] = [self.bundle.action(), self.bundle.action()]
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "action_id"):
            self.bundle.load()

    def test_action_may_reference_observation_without_task_relation(self):
        self.bundle.assessment["non_normative_observations"] = [{"finding_id": "O-01", "finding_type": "non_normative_observation",
            "company_source_ref": "policy.md#release", "observation": "Synthetic wording concern.", "basis": "reviewer_inference",
            "review_queue_recommendation": "needs_changes", "cannot_claim": ["Cannot claim normative task gap."]}]
        self.bundle.data["actions"][0]["finding_refs"] = ["O-01"]
        self.bundle.save()
        self.assertEqual(self.bundle.load().data.actions[0].finding_refs, ("O-01",))

    def test_c8_auxiliary_e13_is_authorized_pinned_and_excluded_from_corpus(self):
        source = "docs/SSDLC-deliverables-overview.md"
        self.bundle.write("auxiliary/overview.md", b"Synthetic auxiliary overview, not company data.\n")
        self.bundle.data["auxiliary_sources"] = [{"source_ref": source, "artifact_ref": self.bundle.ref("auxiliary/overview.md")}]
        action = self.bundle.action("E-13")
        action["locations"] = [{"source_ref": source + "#list", "source_scope": "auxiliary", "display_text": "Synthetic overview §list"}]
        self.bundle.data["actions"] = [action]
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "authorization"):
            self.bundle.load()
        result = self.bundle.load(authorized_auxiliary_sources=frozenset({source}))
        self.assertEqual(result.corpus.corpus_digest, CORPUS_HASH)
        self.assertEqual([f[0] for f in result.corpus.files], ["policy.md"])
        self.assertEqual(len(result.data.source_authority), 1)
        self.assertEqual(result.data.actions[0].action_id, "E-13")
        action["locations"][0]["source_scope"] = "corpus"
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "location.scope"):
            self.bundle.load(authorized_auxiliary_sources=frozenset({source}))

    def test_auxiliary_missing_duplicate_and_corpus_relabel_are_rejected(self):
        for records in [[{"source_ref": "policy.md", "artifact_ref": self.bundle.ref("policy.md")}],
                        [{"source_ref": "aux.md", "artifact_ref": self.bundle.ref("policy.md")}] * 2]:
            with self.subTest(records=records):
                self.bundle.data["auxiliary_sources"] = records
                self.bundle.save()
                with self.assertRaisesRegex(ReportContractError, "auxiliary_sources"):
                    self.bundle.load(authorized_auxiliary_sources=frozenset({"policy.md", "aux.md"}))
        self.bundle.data["auxiliary_sources"] = []
        self.bundle.data["actions"][0]["locations"][0]["source_scope"] = "auxiliary"
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "location.scope"):
            self.bundle.load()

    def test_assessment_metadata_identity_mismatches_are_rejected(self):
        original = copy.deepcopy(self.bundle.assessment)
        for field, value in [("repo", "other/repo"), ("commit", "2" * 40), ("manifest_digest", "2" * 64), ("corpus_digest", "2" * 64)]:
            with self.subTest(field=field):
                self.bundle.assessment = copy.deepcopy(original)
                self.bundle.assessment["assessment"]["target"][field] = value
                self.bundle.save()
                with self.assertRaisesRegex(ReportContractError, "assessment/corpus"):
                    self.bundle.load()

    def test_metadata_internal_digest_count_types_and_membership_are_rejected(self):
        original = copy.deepcopy(self.bundle.metadata)
        for field, value in [("total_files", 2), ("total_files", True), ("total_bytes", 35),
                             ("corpus_digest", "2" * 64), ("target_commit", "2" * 40), ("manifest_digest", "2" * 64)]:
            with self.subTest(field=field):
                self.bundle.metadata = copy.deepcopy(original)
                self.bundle.metadata[field] = value
                self.bundle.save()
                with self.assertRaises(ReportContractError):
                    self.bundle.load()
        self.bundle.metadata = copy.deepcopy(original)
        self.bundle.metadata["files"] *= 2
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "duplicate"):
            self.bundle.load()

    def test_c8_metadata_cannot_smuggle_auxiliary_into_pinned_authority_surface(self):
        source = "docs/SSDLC-deliverables-overview.md"
        self.bundle.metadata["files"].append({"relative_path": source, "content_hash": POLICY_HASH, "byte_size": 36})
        # Attack fixture forges internally consistent metadata; rejection must
        # come from the fixed manifest, not an unrelated count/hash failure.
        forged_digest = hashlib.sha256((f"{source}\t{POLICY_HASH}\npolicy.md\t{POLICY_HASH}\n").encode()).hexdigest()
        self.bundle.metadata.update(total_files=2, total_bytes=72, corpus_digest=forged_digest)
        self.bundle.assessment["assessment"]["target"]["corpus_digest"] = forged_digest
        self.bundle.data["source_authority"].append({**self.bundle.data["source_authority"][0], "path": source, "status_source_ref": source + "#header"})
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "corpus.scope"):
            self.bundle.load()

    def test_artifact_hash_mismatch_and_missing_file_are_rejected(self):
        self.bundle.data["assessment_ref"]["sha256"] = "2" * 64
        self.bundle.write_json("report-data.json", self.bundle.data)
        with self.assertRaisesRegex(ReportContractError, "artifact.hash"):
            self.bundle.load()
        self.bundle.data["assessment_ref"]["path"] = "absent.yaml"
        self.bundle.write_json("report-data.json", self.bundle.data)
        with self.assertRaisesRegex(ReportContractError, "unavailable"):
            self.bundle.load()

    def test_pinned_manifest_content_digest_is_not_just_metadata_self_report(self):
        self.bundle.manifest["authority_surface"]["exclude"] = ["auxiliary/**"]
        self.bundle.save()  # Existing report/metadata still bind the original manifest digest.
        with self.assertRaisesRegex(ReportContractError, "manifest/corpus"):
            self.bundle.load()

    def test_all_optional_evidence_refs_are_verified_without_approval_inference(self):
        original = copy.deepcopy(self.bundle.data)
        for slot in ["status_source_ref", "approval_ref", "tracking"]:
            with self.subTest(slot=slot):
                self.bundle.data = copy.deepcopy(original)
                ref = self.bundle.ref("evidence.txt")
                if slot == "tracking":
                    self.bundle.data["actions"][0]["tracking"] = {"statement": "Synthetic tracking note only.", "evidence_refs": [ref]}
                else:
                    self.bundle.data["source_authority"][0][slot] = ref
                self.bundle.save()
                self.assertEqual(self.bundle.load().data.source_authority[0].state, "draft")
                ref["sha256"] = "2" * 64
                self.bundle.save()
                with self.assertRaisesRegex(ReportContractError, "artifact.hash"):
                    self.bundle.load()

    def test_entry_and_nested_relative_paths_are_checked(self):
        for name in ["../report-data.json", "/report-data.json", "C:/report-data.json", "C:report-data.json", "\\\\host\\share\\report.json",
                     "sub/../report-data.json", "sub\\..\\report-data.json", "policy.md:stream", ".. /file", "file\x00"]:
            with self.subTest(name=name), self.assertRaisesRegex(ReportContractError, "relative path"):
                load_report_data(name, self.root)
        self.bundle.data["retained_content_refs"] = [{"path": "../private.md", "sha256": "2" * 64}]
        with self.assertRaises(ReportContractError):
            parse_report_data(self.bundle.data)

    def test_c8_retained_content_is_verified_without_reinterpreting_it(self):
        self.bundle.write("history.md", b"Synthetic historical text: this is not a decision or task result.\n")
        self.bundle.data["retained_content_refs"] = [self.bundle.ref("history.md")]
        self.bundle.save()
        before = self.snapshot()
        self.assertTrue(self.bundle.load().validation.complete)
        self.assertEqual(before, self.snapshot())
        self.bundle.write("history.md", b"changed")
        with self.assertRaisesRegex(ReportContractError, "artifact.hash"):
            self.bundle.load()

    def test_strict_json_and_unknown_fields_fail_closed(self):
        for raw in [b'{"a":1,"a":2}', b'{"a":NaN}', b'[]', b'\xff', b'{']:
            with self.subTest(raw=raw), self.assertRaises(ReportContractError):
                parse_report_data(decode_json(raw, "test"))
        for key, value in [("coverage_override", "COVERED"), ("contract_version", 0.1), ("actions", "[]")]:
            with self.subTest(key=key):
                data = copy.deepcopy(self.bundle.data)
                data[key] = value
                with self.assertRaises(ReportContractError):
                    parse_report_data(data)

    def test_assessment_duplicate_yaml_and_scalar_coercion_fail_closed(self):
        self.bundle.write("assessment.yaml", (yaml.safe_dump(self.bundle.assessment) + "assessment: {}\n").encode())
        self.bundle.data["assessment_ref"] = self.bundle.ref("assessment.yaml")
        self.bundle.write_json("report-data.json", self.bundle.data)
        with self.assertRaisesRegex(ReportContractError, "duplicate"):
            self.bundle.load()
        self.bundle.assessment["results"][0]["task_id"] = ["PW.4.4"]
        self.bundle.save()
        with self.assertRaisesRegex(ReportContractError, "non-empty string"):
            self.bundle.load()

    def test_c7_task_scope_and_cannot_claim_are_preserved(self):
        finding = self.bundle.assessment["results"][0]
        finding.update(task_id="PW.8.1", cannot_claim=["Only synthetic products A/B; cannot claim company-wide coverage."])
        finding["basis"][0]["task_id"] = "PW.8.1"
        self.bundle.assessment["assessment"]["scope_tasks"] = ["PW.8.1"]
        self.bundle.save()
        result = self.bundle.load()
        self.assertEqual(result.assessment.report.findings[0].cannot_claim, ["Only synthetic products A/B; cannot claim company-wide coverage."])
        self.assertEqual(result.data.actions[0].scope_labels, ("Synthetic Product",))


class TestArtifactRootBoundary(ContractTestCase):
    def test_resolved_directory_replaced_before_open_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as outside:
            outside_bytes = b"Synthetic private bytes outside the caller-authorized root."
            (Path(outside) / "private.txt").write_bytes(outside_bytes)
            raced = self.root / "race"
            retired = self.root / "retired"
            raced.mkdir()
            (raced / "private.txt").write_bytes(b"Authorized synthetic bytes.")
            store = ArtifactStore(self.root)
            resolve = store.resolve
            read_calls = []
            opened_descriptors = []
            fdopen = os.fdopen

            class ObservedFile:
                def __init__(self, handle):
                    self.handle = handle
                    opened_descriptors.append(handle.fileno())

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.handle.close()

                def fileno(self):
                    return self.handle.fileno()

                def read(self):
                    read_calls.append(self.fileno())
                    return self.handle.read()

            def resolve_then_swap(*args, **kwargs):
                resolved = resolve(*args, **kwargs)
                raced.rename(retired)
                if os.name == "nt":
                    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(raced), outside], capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                else:
                    raced.symlink_to(outside, target_is_directory=True)
                return resolved

            try:
                with patch.object(store, "resolve", side_effect=resolve_then_swap), patch(
                    "tools.report_data_contract.os.fdopen", side_effect=lambda *a, **k: ObservedFile(fdopen(*a, **k))
                ):
                    # A matching hash must never authorize reading an outside file.
                    ref = ArtifactRef("race/private.txt", hashlib.sha256(outside_bytes).hexdigest())
                    with self.assertRaisesRegex(ReportContractError, "opened target escapes report root"):
                        store.read_ref(ref, self.root / "report-data.json")
                self.assertEqual(read_calls, [])
                self.assertEqual(len(opened_descriptors), 1)
                with self.assertRaises(OSError):
                    os.fstat(opened_descriptors[0])  # Failed admission closes the handle.
            finally:
                if os.name == "nt" and retired.exists() and raced.exists():
                    os.rmdir(raced)
                elif raced.is_symlink():
                    raced.unlink()

    def test_unavailable_opened_handle_metadata_fails_before_read(self):
        store = ArtifactStore(self.root)
        with patch.object(store, "_opened_path", side_effect=OSError("handle metadata unavailable")):
            with self.assertRaisesRegex(ReportContractError, "handle metadata unavailable"):
                store.read_ref(ArtifactRef("policy.md", POLICY_HASH), self.root / "report-data.json")

    def test_symlink_escape_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as outside:
            private = Path(outside) / "private.txt"
            private.write_bytes(b"Synthetic outside-root bytes.")
            link = self.root / "escape.txt"
            try:
                link.symlink_to(private)
            except OSError as exc:
                self.skipTest(f"OS cannot create symlink: {exc}")
            ref = ArtifactRef("escape.txt", "2" * 64)
            with patch("tools.report_data_contract.os.open", side_effect=AssertionError("outside file must not be opened")) as read:
                with self.assertRaisesRegex(ReportContractError, "escapes report root"):
                    ArtifactStore(self.root).read_ref(ref, self.root / "report-data.json")
                read.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows junction boundary")
    def test_windows_junction_escape_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as outside:
            (Path(outside) / "private.txt").write_bytes(b"Synthetic outside-root bytes.")
            junction = self.root / "junction"
            result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), outside], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            try:
                with patch("tools.report_data_contract.os.open", side_effect=AssertionError("outside file must not be opened")) as read:
                    with self.assertRaisesRegex(ReportContractError, "escapes report root"):
                        ArtifactStore(self.root).read_ref(ArtifactRef("junction/private.txt", "2" * 64), self.root / "report-data.json")
                    read.assert_not_called()
            finally:
                os.rmdir(junction)  # Remove only the test-created link, never its target.

    def test_symlink_inside_root_can_be_read_and_hash_checked(self):
        link = self.root / "inside.txt"
        try:
            link.symlink_to(self.root / "policy.md")
        except OSError as exc:
            self.skipTest(f"OS cannot create symlink: {exc}")
        _, raw = ArtifactStore(self.root).read_ref(ArtifactRef("inside.txt", POLICY_HASH), self.root / "report-data.json")
        self.assertEqual(raw, b"Synthetic document statements only.\n")


if __name__ == "__main__":
    unittest.main()
