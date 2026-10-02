"""REPORT-4C expectations: frozen REPORT-3B and presentation contract v1.4.

Synthetic records deliberately combine COVERED, weak, P1, draft and an
independent queue opinion. Tests assert visible output and unchanged inputs;
they do not establish semantic assessment correctness or human acceptance.
"""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote

import yaml

from test_report_data_contract import ContractTestCase
from tools.assessment_markdown import MarkdownProjectionError, render_markdown
from tools.generate_assessment_markdown import TEMPLATE_FILES, TEMPLATE_ROOT, generate
from tools import generate_assessment_markdown as application
from tools.report_data_contract import ReportContractError
from tools.review_lifecycle_contract import load_review_lifecycle


REPO = Path(__file__).resolve().parents[1]
SUMMARY_SECTIONS = ["1. 結論", "2. 工程師要處理什麼", "3. 建議處理順序", "4. 詳細 NIST 判定"]
TECHNICAL_SECTIONS = ["1. Review 結論與宣稱邊界", "2. 固定範圍與閱讀方法", "3. 上次結果與問題追蹤",
                      "4. 工程師修正與補證的完整依據", "5. 各 Task 的評估紀錄", "6. 逐份文件與跨文件觀察", "7. 來源指紋", "8. 驗證與停止點"]
FIELD_NAMES = ["finding_id / finding_type", "Task / task_id", "NIST Task Expectation", "Company Document Statements",
               "Identified Document Evidence", "Company Source / company_source_ref", "Task Coverage Gap", "Improvement Opportunity",
               "Coverage Verdict / coverage_verdict", "Evidence Strength / evidence_strength", "Corpus Authority Context",
               "Assessment Rationale / assessment_rationale", "Basis", "Review Queue Recommendation", "Cannot Claim / cannot_claim"]


def assert_links(test, directory):
    for path in directory.glob("*.md"):
        for href in re.findall(r"(?<!\\)\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            location, _, anchor = unquote(href).partition("#")
            target = (directory / location) if location else path
            test.assertTrue(target.is_file(), (path.name, href))
            if anchor:
                test.assertIn(f'<a id="{anchor}"></a>', target.read_text(encoding="utf-8"))


class TestAssessmentMarkdown(ContractTestCase):
    def setUp(self):
        super().setUp()
        self.outputs = tempfile.TemporaryDirectory()
        self.addCleanup(self.outputs.cleanup)
        self.out = Path(self.outputs.name) / "reports"
        self.lifecycle = {"report_data_ref": {}, "machine_baseline_ref": None,
                          "review_recommendation": {"opinion": "CHANGES_REQUESTED", "reason": "Synthetic independent review reason."},
                          "acceptance_ref": None, "sync": {"state": "not_checked", "target_ref": None, "decision_ref": None, "verification_ref": None}}
        self.save_lifecycle()

    def save_lifecycle(self):
        self.lifecycle["report_data_ref"] = self.bundle.ref("report-data.json")
        self.bundle.write_json("review-lifecycle.json", self.lifecycle)

    def load(self):
        return load_review_lifecycle("review-lifecycle.json", self.root)

    def render(self, **changes):
        args = {"date": "2026-10-02", "title": "合成文件審閱", "templates": {k: (TEMPLATE_ROOT / v).read_text(encoding="utf-8") for k, v in TEMPLATE_FILES.items()}, "source_links": {}}
        args.update(changes)
        return render_markdown(self.load(), **args)

    def generate(self, **changes):
        args = {"date": "2026-10-02", "title": "合成文件審閱"}
        args.update(changes)
        return generate(self.root, "review-lifecycle.json", self.out, **args)

    def accept(self):
        self.bundle.write_json("acceptance.json", {"decision": "accepted", "report_data_sha256": self.bundle.ref("report-data.json")["sha256"],
                               "assessment_sha256": self.bundle.ref("assessment.yaml")["sha256"], "evidence_ref": self.bundle.ref("evidence.txt")})
        self.lifecycle["acceptance_ref"] = self.bundle.ref("acceptance.json")
        self.save_lifecycle()

    def sync(self, state="synced", old=False):
        target = copy.deepcopy(self.bundle.assessment)
        target["assessment"]["id"] = "synthetic-machine"
        if old:
            target["assessment"]["target"].update(commit="2" * 40, corpus_digest="3" * 64)
            target["results"][0].update(coverage_verdict="PARTIAL", evidence_strength="medium")
        self.bundle.write("target.yaml", yaml.safe_dump(target, sort_keys=False).encode())
        binding = {"report_data_sha256": self.bundle.ref("report-data.json")["sha256"], "assessment_sha256": self.bundle.ref("assessment.yaml")["sha256"],
                   "target_sha256": self.bundle.ref("target.yaml")["sha256"], "evidence_ref": self.bundle.ref("evidence.txt")}
        self.bundle.write_json("verification.json", {"result": "matched" if state == "synced" else "not_synced", **binding})
        self.bundle.write_json("decision.json", {"decision": "synchronize", **binding})
        self.lifecycle["sync"] = {"state": state, "target_ref": self.bundle.ref("target.yaml"), "decision_ref": self.bundle.ref("decision.json") if state == "synced" else None, "verification_ref": self.bundle.ref("verification.json")}
        self.save_lifecycle()

    def test_fixed_sections_six_columns_and_fifteen_task_fields(self):
        docs = self.render()
        self.assertEqual(re.findall(r"^## (.+)$", docs["synthetic-report-summary.md"], re.M), SUMMARY_SECTIONS)
        actions = docs["synthetic-report-actions.md"]
        self.assertEqual(re.findall(r"^## (.+)$", actions, re.M), ["A. 文件要修改", "B. 證據要補", "C. 改善建議"])
        self.assertIn("| ID | 類型 | 哪裡有問題 | 現在的問題 | 要怎麼改 | 怎樣算改完 |", actions)
        tech = docs["synthetic-report-technical-review.md"]
        self.assertEqual(re.findall(r"^## (.+)$", tech, re.M), TECHNICAL_SECTIONS)
        task = tech.split("### PW.4.4\n", 1)[1].split("## 6.", 1)[0]
        found = re.findall(r"\*\*[^\n]*（([^\n]*)）\*\*", task)
        self.assertEqual(found, FIELD_NAMES)

    def test_c1_dimensions_and_original_action_details_coexist(self):
        self.sync("not_synced", old=True)
        docs = self.render()
        tech = docs["synthetic-report-technical-review.md"]
        for expected in ("COVERED", "weak", "P1", "HUMAN REVIEW DRAFT", "needs_changes", "CHANGES_REQUESTED", "與指定 target 未同步"):
            self.assertIn(expected.replace("_", "\\_"), tech)
        for value in self.bundle.data["actions"][0]["details"].values():
            self.assertIn(value, tech)
        self.assertIn("未記錄關係，不推論 NIST 對應", tech)
        self.assertIn('synthetic-report-technical-review.md#e-05', docs["synthetic-report-actions.md"])

    def test_verdict_and_strength_are_not_hardcoded_or_changed(self):
        self.bundle.assessment["results"][0].update(coverage_verdict="PARTIAL", evidence_strength="medium")
        self.bundle.data["task_supplements"][0]["gap_items"] = [self.bundle.gap()]
        self.bundle.save()
        self.save_lifecycle()
        docs = self.render()
        summary = docs["synthetic-report-summary.md"]
        self.assertIn("PARTIAL 1", summary)
        self.assertIn("medium 1", summary)
        self.assertNotIn("COVERED 1", summary)
        self.assertIn("Synthetic task-relevant gap.", docs["synthetic-report-technical-review.md"])

    def test_improvement_and_scope_limit_are_preserved(self):
        self.bundle.assessment["results"][0]["cannot_claim"] = ["Only Product One; do not extrapolate company-wide."]
        self.bundle.assessment["assessment"]["claim_boundary"].append("Only Product One; no company-wide scope.")
        self.bundle.data["task_supplements"][0]["improvement_items"] = [self.bundle.gap(basis_refs=(1,))]
        self.bundle.save()
        self.save_lifecycle()
        docs = self.render()
        self.assertIn("COVERED 1", docs["synthetic-report-summary.md"])
        self.assertIn("Only Product One; no company-wide scope.", docs["synthetic-report-summary.md"])
        self.assertIn("Only Product One; do not extrapolate company-wide.", docs["synthetic-report-technical-review.md"])

    def test_null_and_uncollected_fail_before_output(self):
        pristine = copy.deepcopy(self.bundle.data)
        for change in ("gap", "improvement", "actions", "missing_supplement", "authority"):
            with self.subTest(change=change):
                self.bundle.data = copy.deepcopy(pristine)
                if change in ("gap", "improvement"):
                    self.bundle.data["task_supplements"][0][change + "_items"] = None
                elif change == "actions":
                    self.bundle.data["actions"] = None
                elif change == "missing_supplement":
                    self.bundle.data["task_supplements"] = []
                else:
                    self.bundle.data["source_authority"][0].update(state=None, raw_status=None, status_source_ref=None)
                self.bundle.save()
                self.save_lifecycle()
                before = self.snapshot()
                with self.assertRaisesRegex(MarkdownProjectionError, "incomplete"):
                    self.generate()
                self.assertFalse(self.out.exists())
                self.assertEqual(before, self.snapshot())

    def test_empty_actions_are_explicit_not_unorganized(self):
        self.bundle.data["actions"] = []
        self.bundle.save()
        self.save_lifecycle()
        doc = self.render()["synthetic-report-actions.md"]
        self.assertEqual(doc.count("本次未列。"), 3)

    def test_approved_header_does_not_establish_acceptance(self):
        self.bundle.data["source_authority"][0].update(state="approved", raw_status="Approved")
        self.bundle.save()
        self.save_lifecycle()
        docs = self.render()
        self.assertIn("文件標示 Approved 1", docs["synthetic-report-summary.md"])
        self.assertIn("HUMAN REVIEW DRAFT", docs["synthetic-report-summary.md"])
        self.assertIn("未查驗核准者身分", docs["synthetic-report-summary.md"])

    def test_review_recommendation_is_not_acceptance(self):
        self.lifecycle["review_recommendation"]["opinion"] = "ACCEPTED"
        self.save_lifecycle()
        doc = self.render()["synthetic-report-summary.md"]
        self.assertIn("HUMAN REVIEW DRAFT", doc)
        self.assertIn("未提供綁定本版的接受紀錄", doc)

    def test_accepted_without_sync_stays_draft_but_acceptance_is_visible(self):
        self.accept()
        doc = self.render()["synthetic-report-summary.md"]
        self.assertIn("HUMAN REVIEW DRAFT", doc)
        self.assertIn("人工報告已接受（結構化紀錄綁定本版", doc)
        self.assertIn("尚未核查同步", doc)

    def test_synced_without_acceptance_stays_draft(self):
        self.sync()
        doc = self.render()["synthetic-report-summary.md"]
        self.assertIn("HUMAN REVIEW DRAFT", doc)
        self.assertIn("與指定 target 同步紀錄已驗證", doc)

    def test_accepted_and_synced_shows_both_without_release_claim(self):
        self.accept()
        self.sync()
        doc = self.render()["synthetic-report-summary.md"]
        self.assertIn("**已接受且與指定 target 同步｜", doc)
        self.assertIn("Document coverage only; no implementation claim.", doc)

    def test_machine_history_does_not_supply_previous_human_verdict(self):
        self.sync("not_synced", old=True)
        self.lifecycle["machine_baseline_ref"] = self.bundle.ref("target.yaml")
        self.save_lifecycle()
        doc = self.render()["synthetic-report-technical-review.md"]
        self.assertIn("歷史 machine baseline（獨立來源）", doc)
        self.assertIn("2" * 40, doc)
        self.assertIn("3" * 64, doc)
        self.assertIn("PARTIAL 1", doc)
        self.assertIn("未提供結構化的上一版人工 Task verdict", doc)

    def test_full_rationale_and_non_normative_observation_are_retained(self):
        self.bundle.assessment["results"][0]["assessment_rationale"].append("Improvement: this is opaque rationale, never a structured gap.")
        self.bundle.assessment["non_normative_observations"] = [{"finding_id": "O-01", "finding_type": "non_normative_observation", "company_source_ref": "policy.md#header", "observation": "Needs clarification only.", "basis": "reviewer_inference", "review_queue_recommendation": "pending", "cannot_claim": ["Cannot create a new action from this observation."]}]
        self.bundle.save()
        self.save_lifecycle()
        doc = self.render()["synthetic-report-technical-review.md"]
        self.assertIn("Improvement: this is opaque rationale, never a structured gap.", doc)
        self.assertIn("### O-01", doc)
        self.assertIn("Needs clarification only.", doc)
        self.assertIn("Cannot create a new action from this observation.", doc)
        self.assertEqual(doc.count('<a id="e-'), 1)

    def test_deterministic_noop_and_inputs_unchanged(self):
        before = self.snapshot()
        first = self.generate()
        file_bytes = {p.name: p.read_bytes() for p in self.out.iterdir()}
        second = self.generate()
        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertEqual(file_bytes, {p.name: p.read_bytes() for p in self.out.iterdir()})
        self.assertEqual(before, self.snapshot())
        assert_links(self, self.out)

    def test_changed_output_and_input_overlap_are_refused(self):
        self.generate()
        before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        with self.assertRaisesRegex(MarkdownProjectionError, "differs"):
            self.generate(title="另一份標題")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.out.iterdir()})
        with self.assertRaisesRegex(MarkdownProjectionError, "disjoint"):
            generate(self.root, "review-lifecycle.json", self.root / "output", date="2026-10-02")

    def test_invalid_reference_preserves_previous_output_and_input(self):
        self.generate()
        output_before = {p.name: p.read_bytes() for p in self.out.iterdir()}
        self.lifecycle["report_data_ref"]["sha256"] = "0" * 64
        self.bundle.write_json("review-lifecycle.json", self.lifecycle)
        before = self.snapshot()
        with self.assertRaises(ReportContractError):
            self.generate()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(output_before, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_malformed_acceptance_is_not_downgraded_to_draft(self):
        self.bundle.write_json("acceptance.json", {"decision": "accepted"})
        self.lifecycle["acceptance_ref"] = self.bundle.ref("acceptance.json")
        self.save_lifecycle()
        with self.assertRaises(ReportContractError):
            self.generate()
        self.assertFalse(self.out.exists())

    def test_missing_template_field_or_heading_fails(self):
        originals = {k: (TEMPLATE_ROOT / v).read_text(encoding="utf-8") for k, v in TEMPLATE_FILES.items()}
        for replacement in (originals["summary"].replace("$stop", ""), originals["summary"].replace("## 1. 結論", "## 1. Other")):
            with self.subTest(replacement=replacement):
                templates = {**originals, "summary": replacement}
                with self.assertRaises(MarkdownProjectionError):
                    self.render(templates=templates)

    def test_unsafe_report_id_date_and_multiline_title_fail(self):
        self.bundle.data["report_id"] = "../bad"
        self.bundle.save()
        self.save_lifecycle()
        with self.assertRaisesRegex(MarkdownProjectionError, "filename"):
            self.render()
        self.bundle.data["report_id"] = "synthetic-report"
        self.bundle.save()
        self.save_lifecycle()
        for date in ("2026-2-2", "2026-02-30"):
            with self.assertRaises(MarkdownProjectionError):
                self.render(date=date)
        with self.assertRaises(MarkdownProjectionError):
            self.render(title="Hi\n## fake")

    def test_markdown_and_html_input_cannot_change_layout(self):
        hostile = '<script>alert(1)</script> | [fake](https://example.com)\n## forged'
        self.bundle.data["actions"][0]["details"]["目前哪裡有問題"] = hostile
        self.bundle.assessment["results"][0]["company_statement"] = hostile
        self.bundle.save()
        self.save_lifecycle()
        docs = self.render()
        for body in docs.values():
            self.assertNotIn("<script>", body)
            self.assertNotIn("\n## forged", body)
            self.assertNotIn("[fake](", body)
        self.assertIn(r"\|", docs["synthetic-report-actions.md"])

    def test_crlf_cr_and_lf_preserve_single_six_column_action_row(self):
        for value in ("left\rright", "left\r\nright", "left\nright"):
            with self.subTest(value=repr(value)):
                self.bundle.data["actions"][0]["details"]["目前哪裡有問題"] = value
                self.bundle.save()
                self.save_lifecycle()
                doc = self.render()["synthetic-report-actions.md"]
                self.assertNotIn("\r", doc)
                row = next(line for line in doc.splitlines() if line.startswith("| [E-05]"))
                self.assertIn("left<br>right", row)
                self.assertEqual(len(row.split("|")), 8)  # Six cells plus both margins.
                self.assertIn("修改處能追到實際決策紀錄。", row)

    def test_real_output_parent_swap_is_blocked_before_report_bytes(self):
        arena = Path(self.outputs.name)
        self.out = arena / "parent" / "reports"
        external = arena / "external"
        external.mkdir()
        original_parent = arena / "original-parent"
        real_temp = tempfile.TemporaryDirectory
        swapped = []
        def swap_before_staging(*args, **kwargs):
            # Every moved/replaced path remains in this owned test arena.
            self.assertTrue(self.out.parent.resolve().is_relative_to(arena.resolve()))
            self.out.parent.rename(original_parent)
            swapped.append(True)
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.out.parent), str(external)], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                self.out.parent.symlink_to(external, target_is_directory=True)
            return real_temp(*args, **kwargs)
        before = self.snapshot()
        try:
            with patch.object(application.tempfile, "TemporaryDirectory", swap_before_staging):
                with self.assertRaises((OSError, MarkdownProjectionError)):
                    self.generate()
            self.assertEqual(list(external.iterdir()), [])
            self.assertEqual(before, self.snapshot())
        finally:
            if swapped:
                if os.name == "nt":
                    os.rmdir(self.out.parent)  # Junction itself; never recurse into target.
                else:
                    self.out.parent.unlink()
                original_parent.rename(self.out.parent)

    def test_staging_failure_leaves_no_partial_report(self):
        original = application._write_file
        written = []
        def fail_second(stage, directory_fd, name, raw):
            written.append(name)
            if len(written) == 2:
                raise OSError("synthetic second-file write failure")
            return original(stage, directory_fd, name, raw)
        before = self.snapshot()
        with patch.object(application, "_write_file", fail_second):
            with self.assertRaises(OSError):
                self.generate()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.out.parent.iterdir()), [])
        self.assertEqual(before, self.snapshot())

    def test_real_stage_swap_cannot_publish_forged_bundle(self):
        arena = Path(self.outputs.name)
        external = arena / "external"
        external.mkdir()
        for name in ("summary", "actions", "technical-review"):
            (external / f"synthetic-report-{name}.md").write_text("FORGED OUTPUT", encoding="utf-8")
        original_publish = application._publish_stage
        swapped = []
        def swap(stage, stage_fd, temp_fd, parent_fd, out):
            self.assertTrue(stage.resolve().is_relative_to(arena.resolve()))
            stage.rename(stage.parent / "held-bundle")
            swapped.append(stage)
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(stage), str(external)], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                stage.symlink_to(external, target_is_directory=True)
            try:
                return original_publish(stage, stage_fd, temp_fd, parent_fd, out)
            finally:
                if os.name == "nt":
                    os.rmdir(stage)
                else:
                    stage.unlink()
        before = self.snapshot()
        with patch.object(application, "_publish_stage", swap):
            with self.assertRaises((OSError, MarkdownProjectionError)):
                self.generate()
        self.assertFalse(self.out.exists())
        self.assertEqual(before, self.snapshot())
        self.assertEqual({p.read_text(encoding="utf-8") for p in external.iterdir()}, {"FORGED OUTPUT"})

    def test_cli_failure_is_nonzero_and_creates_no_report(self):
        process = subprocess.run([sys.executable, "-X", "utf8", "-m", "tools.generate_assessment_markdown", "--report-root", str(self.root), "--out-dir", str(self.out), "--date", "bad"], cwd=REPO, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(process.returncode, 1)
        self.assertEqual(json.loads(process.stdout)["status"], "failed")
        self.assertFalse(self.out.exists())


class TestSyntheticReportingMarkdown(unittest.TestCase):
    def test_recorded_actions_task_scope_and_auxiliary_links(self):
        from reporting_fixtures import AUXILIARY, reporting_bundle
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "inputs"
            bundle = reporting_bundle(root)
            bundle.lifecycle["machine_baseline_ref"] = bundle.ref("target.yaml")
            bundle.write_json("review-lifecycle.json", bundle.lifecycle)
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            out = Path(temp) / "reports"
            with self.assertRaisesRegex(ReportContractError, "authorization"):
                generate(root, "review-lifecycle.json", out, date="2026-10-02")
            self.assertFalse(out.exists())
            receipt = generate(root, "review-lifecycle.json", out, date="2026-10-02", title="合成 SSDLC", authorized_auxiliary_sources=frozenset({AUXILIARY}))
            self.assertFalse(receipt["accepted_record"])
            self.assertEqual(receipt["sync_state"], "not_synced")
            self.assertEqual(len(list(out.iterdir())), 3)
            summary = (out / "synthetic-report-summary.md").read_text(encoding="utf-8")
            self.assertIn("1 份固定文件及 1 個 Task", summary)
            self.assertIn("COVERED 1", summary)
            self.assertIn("weak 1", summary)
            self.assertIn("草稿 1／審核中 0／讀過但未標示狀態 0／文件標示 Approved 0", summary)
            self.assertIn("E-05（P1）", summary)
            technical = (out / "synthetic-report-technical-review.md").read_text(encoding="utf-8")
            self.assertEqual(technical.count('<a id="e-'), 3)
            self.assertEqual(len(re.findall(r"^### (?:PO|PS|PW|RV)\.\d\.\d$", technical, re.M)), 1)
            self.assertIn("PARTIAL 1", technical)
            self.assertIn("auxiliary", technical)
            self.assertIn("不加入 coverage、corpus digest 或 authority 統計", technical)
            assert_links(self, out)
            self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()})
