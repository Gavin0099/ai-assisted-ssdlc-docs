from __future__ import annotations

import copy
import os
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.implementation_contracts import (
    CandidateQuantifier,
    ContractInputError,
    ImplementationEvidenceRule,
    ImplementationEvidenceRuleset,
    PolicyAssessmentAdmission,
    PolicyImplementationExpectation,
    RuleApplicability,
    RuleApplicabilityStatus,
    _RULE_ADMISSION_TOKEN,
    _RULESET_ADMISSION_TOKEN,
    admit_policy_assessment,
    compute_expectation_digest,
    compute_expectation_set_digest,
    compute_expectation_set_semantic_digest,
    compute_rule_digest,
    compute_ruleset_digest,
    compute_ruleset_semantic_digest,
    load_expectation_set,
    load_ruleset,
    verify_admitted_expectation_set,
    verify_admitted_ruleset,
    verify_expectation_ruleset_integrity,
    EvidenceAssertion,
    MatcherKind,
)
from tools.repo_corpus_resolver import RepoCorpusResolver
from tools.validate_target_manifest import parse_target_manifest

RULE_DIGEST = "0388f5ccd4962cd665c31a554a87ee80d558aa19394444e7c8ac337e8c4fbb67"
RULESET_DIGEST = "0094bc63c2d41244874dc61a0a215e19be756c238b23749f2220ce793aa581d6"
EXPECTATION_DIGEST = "b738287ed401b27c03d81f3943522ae710e62a31965307b1683cd2971f8f8a21"
EXPECTATION_SET_DIGEST = "24a4c6bb1cf2956fa086b83e1520859285339e25482c1fb03c726a2be0d1af49"
EXPECTATION_SET_2_DIGEST = "7971c9d7e2b32355121cc9d01e075f411c6504e59f3c414c406a6eb5fcd7722a"
RULE_2_DIGEST = "ab51720bbd397fc91f7323e5ec82bbc9e5f83d6d9ef7ab4d98f64772503f9a5f"
RULESET_2_DIGEST = "967d6bccbd3dc2590d6e7e89ff30179a53d2fcefdbb727f60c51a3d634a119dd"
EXP_2_DIGEST = "b48ccb009fba1ab1287f1244b6a3b48b361ffef98f039151186c8c719ca2b5ac"
EXP_UNKNOWN_RULE_DIGEST = "d90eb87e803a97e95ce1a32e481cb1f23e414e547ebde55ae5c4b1c973d32896"
EXP_UNKNOWN_RULE_SET_DIGEST = "41b5d0e2229213e27ba170eb4865532064829bfdf21c16aa56ca62ad39ba9457"
EXP_CROSS_TASK_DIGEST = "663723062c9913ebbdf64ec1a25fa19592d069ab26e15519b20aeb013d2171d8"
EXP_CROSS_TASK_SET_DIGEST = "55a29338e8c29cbe074e8c994014a50a6413e22d75e37644a9d59e9e52c95e08"
ALTERED_IDENTITY_SET_DIGEST = "dd994986c0a4a1bedf3de8051dc1515d270c295968a89579864fbe68ba12f092"
EXP_UNKNOWN_FINDING_DIGEST = "3a3e201ff900d2271fee25f55dc0bc2daae1518e532605c46e3e7cea0b621edf"
EXP_UNKNOWN_FINDING_SET_DIGEST = "b3f2ce9a13b709c02e7656d27f7f904067c07512860e4ba4cf7dba1ad74a73c7"
EXP_SOURCE_MISMATCH_DIGEST = "29295cf477bf850eac34c92e71c2c174bb8bb31820d31b8a59ef08fdc335b450"
EXP_SOURCE_MISMATCH_SET_DIGEST = "2f979b63159a044232025d84d18c49e2b69224d1e1de081a414f975352928dc0"
EXP_TASK_MISMATCH_DIGEST = EXP_CROSS_TASK_DIGEST
EXP_TASK_MISMATCH_SET_DIGEST = EXP_CROSS_TASK_SET_DIGEST


def rule(rule_id: str = "RULE-1", task_id: str = "PW.4.4") -> dict:
    semantic = {
        "rule_id": rule_id,
        "task_id": task_id,
        "evidence_kind": "dependency_lockfile",
        "candidate_selectors": ["src/**"],
        "candidate_quantifier": "ANY",
        "assertion": {
            "expected_value": None,
            "matcher": "FILE_EXISTS",
            "target_path_expression": None,
        },
        "applicability": {"reason": None, "status": "APPLICABLE"},
    }
    known_digests = {
        ("RULE-1", "PW.4.4"): RULE_DIGEST,
        ("RULE-2", "PW.4.4"): RULE_2_DIGEST,
    }
    return {**semantic, "rule_digest": known_digests[(rule_id, task_id)]}


def expectation(expectation_id: str = "EXP-1", rule_ids: list[str] | None = None) -> dict:
    semantic = {
        "expectation_id": expectation_id,
        "task_id": "PW.4.4",
        "policy_assessment_id": "ASSESS-1",
        "policy_finding_id": "FIND-1",
        "policy_source_ref": "policy/dependencies.md#locking",
        "expected_evidence_kinds": ["dependency_lockfile"],
        "verification_rule_ids": rule_ids or ["RULE-1"],
    }
    known_digests = {
        ("EXP-1", ("RULE-1",)): EXPECTATION_DIGEST,
        ("EXP-2", ("RULE-1",)): EXP_2_DIGEST,
    }
    return {
        **semantic,
        "expectation_digest": known_digests[(expectation_id, tuple(semantic["verification_rule_ids"]))],
    }


def ruleset_data() -> dict:
    return {
        "ruleset_version": "1.0",
        "rules": [rule()],
        "ruleset_digest": RULESET_DIGEST,
    }


def expectation_set_data() -> dict:
    return {
        "expectation_set_version": "1.0",
        "expectations": [expectation()],
        "policy_assessment_identity": {
            "assessment_id": "ASSESS-1",
            "target_source_type": "github",
            "target_repo": "example/policy",
            "target_commit": "e40ae7fee3fb70b1adb5a17ba814839b550ee0e0",
            "target_manifest_digest": "350a8774b27aae2ab5c281850fdf2198a1e6568603d447523a80784dd8688455",
            "target_corpus_digest": "af25cfc47a923597affbacad4019bb552cf8e12e0d270113bba5f0632ff83a12",
        },
        "expectation_set_digest": EXPECTATION_SET_DIGEST,
    }


def run_git(repo_path: Path, *args: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
    }
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


def make_policy_admission(root_path: Path) -> tuple[PolicyAssessmentAdmission, Path]:
    repo_path = root_path / "policy-repo"
    repo_path.mkdir()
    run_git(repo_path, "init", "-b", "main")
    run_git(repo_path, "config", "user.name", "S2 Test Assessor")
    run_git(repo_path, "config", "user.email", "s2-test@example.invalid")
    run_git(
        repo_path,
        "remote",
        "add",
        "origin",
        "https://github.com/example/policy.git",
    )
    policy_file = repo_path / "policy" / "dependencies.md"
    policy_file.parent.mkdir()
    policy_file.write_text("# Dependency policy\nLock dependencies.\n", encoding="utf-8")
    run_git(repo_path, "add", "policy/dependencies.md")
    run_git(repo_path, "commit", "-m", "add policy source")
    commit = run_git(repo_path, "rev-parse", "HEAD")
    manifest_path = repo_path / "target-manifest.yaml"
    manifest_path.write_text(
        f'''manifest_version: "1.0"
target:
  source_type: github
  repo: example/policy
  commit: "{commit}"
authority_surface:
  include:
    - "policy/**"
baseline:
  framework: NIST_SP_800_218
  version: "1.1"
mode:
  read_only: true
''',
        encoding="utf-8",
    )
    run_git(repo_path, "add", "target-manifest.yaml")
    run_git(repo_path, "commit", "-m", "add target manifest")
    manifest = parse_target_manifest(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )
    snapshot = RepoCorpusResolver().resolve(manifest, repo_path)
    assessment_path = root_path / "assessment.yaml"
    assessment_data = {
        "assessment": {
            "id": "ASSESS-1",
            "baseline": "NIST_SP_800_218_v1.1",
            "target": {
                "type": "repository_corpus",
                "repo": "example/policy",
                "commit": manifest.target.commit,
                "manifest_path": "target-manifest.yaml",
                "manifest_digest": manifest.digest,
                "corpus_digest": snapshot.corpus_digest,
            },
            "scope_tasks": ["PW.4.4"],
            "claim_boundary": ["Assessment is limited to the policy corpus."],
        },
        "results": [
            {
                "finding_id": "FIND-1",
                "finding_type": "task_finding",
                "task_id": "PW.4.4",
                "company_source_ref": "policy/dependencies.md#locking",
                "company_statement": "Dependencies must be locked.",
                "coverage_verdict": "PARTIAL",
                "basis": [
                    {
                        "type": "nist_normative",
                        "task_id": "PW.4.4",
                        "source": "NIST_SP_800_218_v1.1",
                        "rationale": "The task concerns verification of third-party components.",
                    }
                ],
                "assessment_rationale": ["The policy describes dependency locking."],
                "identified_evidence": [
                    {
                        "type": "policy",
                        "source_ref": "policy/dependencies.md#locking",
                    }
                ],
                "evidence_strength": "medium",
                "review_queue_recommendation": "needs_changes",
                "cannot_claim": ["This does not prove implementation or compliance."],
            }
        ],
    }
    assessment_path.write_text(
        yaml.safe_dump(assessment_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    admission = admit_policy_assessment(
        assessment_path,
        manifest_path,
        repo_path,
    )
    return admission, assessment_path


class ImplementationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.policy_admission, self.assessment_path = make_policy_admission(
            Path(self.temp_dir.name)
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_ruleset_matches_independent_rule_and_set_goldens(self) -> None:
        admitted = load_ruleset(ruleset_data())

        self.assertEqual(admitted.ruleset_digest, RULESET_DIGEST)
        self.assertEqual(admitted.rules[0].rule_digest, RULE_DIGEST)

    def test_expectation_set_matches_independent_expectation_and_set_goldens(self) -> None:
        rules = load_ruleset(ruleset_data())
        admitted = load_expectation_set(
            expectation_set_data(),
            policy_admission=self.policy_admission,
            ruleset=rules,
        )

        self.assertEqual(admitted.expectation_set_digest, EXPECTATION_SET_DIGEST)
        self.assertEqual(admitted.expectations[0].expectation_digest, EXPECTATION_DIGEST)

    def test_set_digest_sorts_rules_and_expectations_by_primary_id(self) -> None:
        data = ruleset_data()
        data["rules"].append(rule("RULE-2"))
        data["ruleset_digest"] = RULESET_2_DIGEST
        admitted = load_ruleset(data)
        reversed_data = copy.deepcopy(data)
        reversed_data["rules"].reverse()
        reversed_admitted = load_ruleset(reversed_data)
        self.assertEqual(admitted.ruleset_digest, reversed_admitted.ruleset_digest)

        exp_data = expectation_set_data()
        second_exp = expectation("EXP-2")
        exp_data["expectations"].append(second_exp)
        exp_data["expectation_set_digest"] = EXPECTATION_SET_2_DIGEST
        admitted_expectations = load_expectation_set(
            exp_data,
            policy_admission=self.policy_admission,
            ruleset=load_ruleset(ruleset_data()),
        )
        reversed_expectations = copy.deepcopy(exp_data)
        reversed_expectations["expectations"].reverse()
        reversed_admitted = load_expectation_set(
            reversed_expectations,
            policy_admission=self.policy_admission,
            ruleset=load_ruleset(ruleset_data()),
        )
        self.assertEqual(
            admitted_expectations.expectation_set_digest,
            reversed_admitted.expectation_set_digest,
        )

    def test_unknown_fields_and_wrong_digest_fail_closed(self) -> None:
        unknown = ruleset_data()
        unknown["approved"] = True
        with self.assertRaises(ContractInputError):
            load_ruleset(unknown)

        wrong_digest = ruleset_data()
        wrong_digest["ruleset_digest"] = "A" * 64
        with self.assertRaises(ContractInputError):
            load_ruleset(wrong_digest)

        wrong_child_digest = ruleset_data()
        wrong_child_digest["rules"][0]["rule_digest"] = "0" * 64
        with self.assertRaises(ContractInputError):
            load_ruleset(wrong_child_digest)

    def test_duplicate_rule_ids_and_duplicate_selectors_are_rejected(self) -> None:
        duplicate_id = ruleset_data()
        duplicate_id["rules"].append(copy.deepcopy(duplicate_id["rules"][0]))
        with self.assertRaises(ContractInputError):
            load_ruleset(duplicate_id)

        duplicate_selector = ruleset_data()
        duplicate_selector["rules"][0]["candidate_selectors"] = ["src/**", "src/**"]
        with self.assertRaises(ContractInputError):
            load_ruleset(duplicate_selector)

    def test_applicability_invariants_and_reason_validation(self) -> None:
        # 1. APPLICABLE + reason=None -> PASS
        valid_applicable = ruleset_data()
        admitted = load_ruleset(valid_applicable)
        self.assertEqual(admitted.rules[0].applicability.status, RuleApplicabilityStatus.APPLICABLE)
        self.assertIsNone(admitted.rules[0].applicability.reason)

        # 2. APPLICABLE + reason="something" -> FAIL
        invalid_applicable = copy.deepcopy(ruleset_data())
        invalid_applicable["rules"][0]["applicability"] = {
            "status": "APPLICABLE",
            "reason": "Not allowed for applicable",
        }
        rule_obj = ImplementationEvidenceRule(
            rule_id=invalid_applicable["rules"][0]["rule_id"],
            rule_digest="dummy",
            task_id=invalid_applicable["rules"][0]["task_id"],
            evidence_kind=invalid_applicable["rules"][0]["evidence_kind"],
            candidate_selectors=tuple(invalid_applicable["rules"][0]["candidate_selectors"]),
            candidate_quantifier=CandidateQuantifier.ANY,
            assertion=EvidenceAssertion(matcher=MatcherKind.FILE_EXISTS),
            applicability=RuleApplicability(
                status=RuleApplicabilityStatus.APPLICABLE,
                reason="Not allowed for applicable",
            ),
        )
        invalid_applicable["rules"][0]["rule_digest"] = compute_rule_digest(rule_obj)
        invalid_applicable["ruleset_digest"] = compute_ruleset_semantic_digest((rule_obj,))
        with self.assertRaises(ContractInputError):
            load_ruleset(invalid_applicable)

        # 3. NOT_APPLICABLE + non-empty reason -> PASS
        valid_not_applicable = copy.deepcopy(ruleset_data())
        valid_not_applicable["rules"][0]["applicability"] = {
            "status": "NOT_APPLICABLE",
            "reason": "No lockfile requirement in this context",
        }
        na_rule_obj = ImplementationEvidenceRule(
            rule_id=valid_not_applicable["rules"][0]["rule_id"],
            rule_digest="dummy",
            task_id=valid_not_applicable["rules"][0]["task_id"],
            evidence_kind=valid_not_applicable["rules"][0]["evidence_kind"],
            candidate_selectors=tuple(valid_not_applicable["rules"][0]["candidate_selectors"]),
            candidate_quantifier=CandidateQuantifier.ANY,
            assertion=EvidenceAssertion(matcher=MatcherKind.FILE_EXISTS),
            applicability=RuleApplicability(
                status=RuleApplicabilityStatus.NOT_APPLICABLE,
                reason="No lockfile requirement in this context",
            ),
        )
        valid_not_applicable["rules"][0]["rule_digest"] = compute_rule_digest(na_rule_obj)
        valid_not_applicable["ruleset_digest"] = compute_ruleset_semantic_digest((na_rule_obj,))
        na_admitted = load_ruleset(valid_not_applicable)
        self.assertEqual(na_admitted.rules[0].applicability.status, RuleApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(
            na_admitted.rules[0].applicability.reason,
            "No lockfile requirement in this context",
        )

        # 4. NOT_APPLICABLE + None / "" -> FAIL
        for empty_reason in (None, "", "   "):
            with self.subTest(empty_reason=empty_reason):
                na_empty = copy.deepcopy(ruleset_data())
                na_empty["rules"][0]["applicability"] = {
                    "status": "NOT_APPLICABLE",
                    "reason": empty_reason,
                }
                with self.assertRaises(ContractInputError):
                    load_ruleset(na_empty)

        # 5. Unknown status -> FAIL
        unknown_status = copy.deepcopy(ruleset_data())
        unknown_status["rules"][0]["applicability"] = {
            "status": "MAYBE_APPLICABLE",
            "reason": "Unknown status value",
        }
        with self.assertRaises(ContractInputError):
            load_ruleset(unknown_status)

    def test_load_expectation_set_revalidates_ruleset_integrity_rejecting_tampering(self) -> None:
        rules = load_ruleset(ruleset_data())

        # Tamper semantic fields (candidate_selectors) via replace() while keeping tokens and digests intact
        tampered_rule = replace(
            rules.rules[0],
            candidate_selectors=("tampered/**",),
        )
        tampered_rules = replace(
            rules,
            rules=(tampered_rule,),
        )
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=tampered_rules,
            )

        # Tamper child rule_digest only
        tampered_rule_digest = replace(
            rules,
            rules=(replace(rules.rules[0], rule_digest="0" * 64),),
        )
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=tampered_rule_digest,
            )

        # Tamper aggregate ruleset_digest only
        tampered_ruleset_digest = replace(
            rules,
            ruleset_digest="0" * 64,
        )
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=tampered_ruleset_digest,
            )

        # 1. Replace applicability into illegal combination + recomputed child/set digests -> verify_admitted_ruleset FAIL
        illegal_app_rule = replace(
            rules.rules[0],
            applicability=RuleApplicability(
                status=RuleApplicabilityStatus.APPLICABLE,
                reason="illegal reason for applicable",
            ),
        )
        illegal_app_rule = replace(
            illegal_app_rule,
            rule_digest=compute_rule_digest(illegal_app_rule),
        )
        illegal_app_ruleset = replace(
            rules,
            rules=(illegal_app_rule,),
        )
        illegal_app_ruleset = replace(
            illegal_app_ruleset,
            ruleset_digest=compute_ruleset_digest(illegal_app_ruleset),
        )
        with self.assertRaises(ContractInputError):
            verify_admitted_ruleset(illegal_app_ruleset)
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=illegal_app_ruleset,
            )

        # 2. Replace selector with traversal ../escape/** + recomputed digests -> FAIL
        traversal_rule = replace(
            rules.rules[0],
            candidate_selectors=("../escape/**",),
        )
        traversal_rule = replace(
            traversal_rule,
            rule_digest=compute_rule_digest(traversal_rule),
        )
        traversal_ruleset = replace(
            rules,
            rules=(traversal_rule,),
        )
        traversal_ruleset = replace(
            traversal_ruleset,
            ruleset_digest=compute_ruleset_digest(traversal_ruleset),
        )
        with self.assertRaises(ContractInputError):
            verify_admitted_ruleset(traversal_ruleset)
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=traversal_ruleset,
            )

        # 3. Replace YAML path with illegal grammar + recomputed digests -> FAIL
        bad_grammar_rule = replace(
            rules.rules[0],
            assertion=EvidenceAssertion(
                matcher=MatcherKind.YAML_PATH_EXISTS,
                target_path_expression="jobs..steps",  # invalid double dot / empty token
            ),
        )
        bad_grammar_rule = replace(
            bad_grammar_rule,
            rule_digest=compute_rule_digest(bad_grammar_rule),
        )
        bad_grammar_ruleset = replace(
            rules,
            rules=(bad_grammar_rule,),
        )
        bad_grammar_ruleset = replace(
            bad_grammar_ruleset,
            ruleset_digest=compute_ruleset_digest(bad_grammar_ruleset),
        )
        with self.assertRaises(ContractInputError):
            verify_admitted_ruleset(bad_grammar_ruleset)
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=bad_grammar_ruleset,
            )

    def test_verify_admitted_expectation_set_revalidates_domain_integrity_with_recomputed_digests(self) -> None:
        rules = load_ruleset(ruleset_data())
        admitted_set = load_expectation_set(
            expectation_set_data(),
            policy_admission=self.policy_admission,
            ruleset=rules,
        )

        # 4. Replace expectation expected_evidence_kinds=() + recomputed child/set digests -> FAIL
        empty_kinds_exp = replace(
            admitted_set.expectations[0],
            expected_evidence_kinds=(),
        )
        empty_kinds_exp = replace(
            empty_kinds_exp,
            expectation_digest=compute_expectation_digest(empty_kinds_exp),
        )
        empty_kinds_set = replace(
            admitted_set,
            expectations=(empty_kinds_exp,),
        )
        empty_kinds_set = replace(
            empty_kinds_set,
            expectation_set_digest=compute_expectation_set_digest(empty_kinds_set),
        )
        with self.assertRaises(ContractInputError):
            verify_admitted_expectation_set(empty_kinds_set)

    def test_revalidation_rejects_unsupported_set_versions_with_recomputed_digests(self) -> None:
        rules = load_ruleset(ruleset_data())
        admitted_set = load_expectation_set(
            expectation_set_data(),
            policy_admission=self.policy_admission,
            ruleset=rules,
        )

        # 1. ruleset_version -> "2.0" + recomputed ruleset_digest -> verify_admitted_ruleset FAIL
        v2_ruleset = replace(rules, ruleset_version="2.0")
        v2_ruleset = replace(
            v2_ruleset,
            ruleset_digest=compute_ruleset_digest(v2_ruleset),
        )
        with self.assertRaises(ContractInputError):
            verify_admitted_ruleset(v2_ruleset)

        # 2. expectation_set_version -> "2.0" + recomputed expectation_set_digest -> verify_admitted_expectation_set FAIL
        v2_exp_set = replace(admitted_set, expectation_set_version="2.0")
        v2_exp_set = replace(
            v2_exp_set,
            expectation_set_digest=compute_expectation_set_digest(v2_exp_set),
        )
        with self.assertRaises(ContractInputError):
            verify_admitted_expectation_set(v2_exp_set)

    def test_joint_cross_set_integrity_revalidation(self) -> None:
        rules = load_ruleset(ruleset_data())
        admitted_set = load_expectation_set(
            expectation_set_data(),
            policy_admission=self.policy_admission,
            ruleset=rules,
        )

        # Intrinsic validation passes
        verify_admitted_expectation_set(admitted_set)
        verify_admitted_ruleset(rules)
        valid_set, valid_rules = verify_expectation_ruleset_integrity(admitted_set, rules)
        self.assertEqual(len(valid_set.expectations), 1)
        self.assertEqual(len(valid_rules.rules), 1)

        # 3. Admitted ExpectationSet has verification_rule_ids / expected_evidence_kinds replaced + recomputed digests
        # Standalone expectation verifier passes intrinsically, but joint verifier fails due to ruleset mismatch
        mismatched_exp = replace(
            admitted_set.expectations[0],
            verification_rule_ids=("RULE-UNKNOWN-FOR-CURRENT-RULESET",),
            expected_evidence_kinds=("dependency_lockfile",),
        )
        mismatched_exp = replace(
            mismatched_exp,
            expectation_digest=compute_expectation_digest(mismatched_exp),
        )
        mismatched_set = replace(
            admitted_set,
            expectations=(mismatched_exp,),
        )
        mismatched_set = replace(
            mismatched_set,
            expectation_set_digest=compute_expectation_set_digest(mismatched_set),
        )

        # Standalone verifier passes because expectation itself is well-formed and digests match
        verify_admitted_expectation_set(mismatched_set)

        # Joint verifier MUST fail because referenced rule is missing in current ruleset
        with self.assertRaises(ContractInputError):
            verify_expectation_ruleset_integrity(mismatched_set, rules)

        # Also test undeclared evidence kind mismatch in joint verification
        kind_mismatch_exp = replace(
            admitted_set.expectations[0],
            verification_rule_ids=("RULE-1",),
            expected_evidence_kinds=("sast_workflow",),  # RULE-1 is dependency_lockfile
        )
        kind_mismatch_exp = replace(
            kind_mismatch_exp,
            expectation_digest=compute_expectation_digest(kind_mismatch_exp),
        )
        kind_mismatch_set = replace(
            admitted_set,
            expectations=(kind_mismatch_exp,),
        )
        kind_mismatch_set = replace(
            kind_mismatch_set,
            expectation_set_digest=compute_expectation_set_digest(kind_mismatch_set),
        )

        verify_admitted_expectation_set(kind_mismatch_set)
        with self.assertRaises(ContractInputError):
            verify_expectation_ruleset_integrity(kind_mismatch_set, rules)

    def test_expectation_set_requires_exact_caller_admitted_identity(self) -> None:
        altered = expectation_set_data()
        altered["policy_assessment_identity"]["target_commit"] = "e" * 40
        altered["expectation_set_digest"] = ALTERED_IDENTITY_SET_DIGEST

        with self.assertRaises(ContractInputError):
            load_expectation_set(
                altered,
                policy_admission=self.policy_admission,
                ruleset=load_ruleset(ruleset_data()),
            )

    def test_expectation_rejects_unknown_rule_and_cross_task_reference(self) -> None:
        rules = load_ruleset(ruleset_data())
        unknown_rule = expectation_set_data()
        unknown_rule["expectations"][0]["verification_rule_ids"] = ["RULE-UNKNOWN"]
        unknown_rule["expectations"][0]["expectation_digest"] = EXP_UNKNOWN_RULE_DIGEST
        unknown_rule["expectation_set_digest"] = EXP_UNKNOWN_RULE_SET_DIGEST
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                unknown_rule,
                policy_admission=self.policy_admission,
                ruleset=rules,
            )

        cross_task = copy.deepcopy(expectation_set_data())
        cross_task["expectations"][0]["task_id"] = "PS.2.1"
        cross_task["expectations"][0]["expectation_digest"] = EXP_CROSS_TASK_DIGEST
        cross_task["expectation_set_digest"] = EXP_CROSS_TASK_SET_DIGEST
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                cross_task,
                policy_admission=self.policy_admission,
                ruleset=rules,
            )

    def test_expectation_evidence_kind_integrity(self) -> None:
        # 1. Negative: duplicate expected_evidence_kinds
        dup_kinds = expectation_set_data()
        dup_kinds["expectations"][0]["expected_evidence_kinds"] = [
            "dependency_lockfile",
            "dependency_lockfile",
        ]
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                dup_kinds,
                policy_admission=self.policy_admission,
                ruleset=load_ruleset(ruleset_data()),
            )

        # 2. Negative: expected_evidence_kinds empty list
        empty_kinds = expectation_set_data()
        empty_kinds["expectations"][0]["expected_evidence_kinds"] = []
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                empty_kinds,
                policy_admission=self.policy_admission,
                ruleset=load_ruleset(ruleset_data()),
            )

        # 3. Negative: expected kind not covered by referenced rules (e.g., expects A and B, but referenced rules only cover A)
        missing_rule_coverage = copy.deepcopy(expectation_set_data())
        missing_rule_coverage["expectations"][0]["expected_evidence_kinds"] = [
            "dependency_lockfile",
            "sast_workflow",
        ]
        exp_obj = PolicyImplementationExpectation(
            expectation_id=missing_rule_coverage["expectations"][0]["expectation_id"],
            expectation_digest="dummy",
            task_id=missing_rule_coverage["expectations"][0]["task_id"],
            policy_assessment_id=missing_rule_coverage["expectations"][0]["policy_assessment_id"],
            policy_finding_id=missing_rule_coverage["expectations"][0]["policy_finding_id"],
            policy_source_ref=missing_rule_coverage["expectations"][0]["policy_source_ref"],
            expected_evidence_kinds=tuple(missing_rule_coverage["expectations"][0]["expected_evidence_kinds"]),
            verification_rule_ids=tuple(missing_rule_coverage["expectations"][0]["verification_rule_ids"]),
        )
        missing_rule_coverage["expectations"][0]["expectation_digest"] = compute_expectation_digest(exp_obj)
        missing_rule_coverage["expectation_set_digest"] = compute_expectation_set_semantic_digest(
            self.policy_admission.identity,
            (exp_obj,),
            version=missing_rule_coverage["expectation_set_version"],
        )
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                missing_rule_coverage,
                policy_admission=self.policy_admission,
                ruleset=load_ruleset(ruleset_data()),
            )

        # 4. Negative: rule brings in an undeclared evidence kind (rule has sast_workflow, expectation only declared dependency_lockfile)
        r_sast = {
            "rule_id": "RULE-SAST",
            "task_id": "PW.4.4",
            "evidence_kind": "sast_workflow",
            "candidate_selectors": ["src/**"],
            "candidate_quantifier": "ANY",
            "assertion": {
                "expected_value": None,
                "matcher": "FILE_EXISTS",
                "target_path_expression": None,
            },
            "applicability": {"reason": None, "status": "APPLICABLE"},
        }
        r_sast["rule_digest"] = compute_rule_digest(
            ImplementationEvidenceRule(
                rule_id=r_sast["rule_id"],
                rule_digest="dummy",
                task_id=r_sast["task_id"],
                evidence_kind=r_sast["evidence_kind"],
                candidate_selectors=tuple(r_sast["candidate_selectors"]),
                candidate_quantifier=CandidateQuantifier.ANY,
                assertion=EvidenceAssertion(
                    matcher=MatcherKind.FILE_EXISTS,
                    target_path_expression=None,
                    expected_value=None,
                ),
                applicability=RuleApplicability(status=RuleApplicabilityStatus.APPLICABLE),
            )
        )
        two_rules_data = {
            "ruleset_version": "1.0",
            "rules": [rule(), r_sast],
            "ruleset_digest": "dummy",
        }
        two_rules_data["ruleset_digest"] = compute_ruleset_digest(
            ImplementationEvidenceRuleset(
                ruleset_version="1.0",
                rules=tuple(
                    load_ruleset({
                        "ruleset_version": "1.0",
                        "rules": [rule()],
                        "ruleset_digest": RULESET_DIGEST,
                    }).rules
                ),
                ruleset_digest=RULESET_DIGEST,
                _admission_token=_RULESET_ADMISSION_TOKEN,
            )
        )
        # Parse ruleset with both rules
        loaded_two_rules = load_ruleset({
            "ruleset_version": "1.0",
            "rules": [rule(), r_sast],
            "ruleset_digest": compute_ruleset_semantic_digest(
                tuple(
                    ImplementationEvidenceRule(
                        rule_id=r["rule_id"],
                        rule_digest=r["rule_digest"],
                        task_id=r["task_id"],
                        evidence_kind=r["evidence_kind"],
                        candidate_selectors=tuple(r["candidate_selectors"]),
                        candidate_quantifier=CandidateQuantifier(r["candidate_quantifier"]),
                        assertion=EvidenceAssertion(
                            matcher=MatcherKind(r["assertion"]["matcher"]),
                            target_path_expression=r["assertion"]["target_path_expression"],
                            expected_value=r["assertion"]["expected_value"],
                        ),
                        applicability=RuleApplicability(
                            status=RuleApplicabilityStatus(r["applicability"]["status"]),
                            reason=r["applicability"]["reason"],
                        ),
                        _admission_token=_RULE_ADMISSION_TOKEN,
                    )
                    for r in [rule(), r_sast]
                )
            ),
        })

        undeclared_kind_exp = copy.deepcopy(expectation_set_data())
        undeclared_kind_exp["expectations"][0]["verification_rule_ids"] = ["RULE-1", "RULE-SAST"]
        exp_undeclared_obj = PolicyImplementationExpectation(
            expectation_id=undeclared_kind_exp["expectations"][0]["expectation_id"],
            expectation_digest="dummy",
            task_id=undeclared_kind_exp["expectations"][0]["task_id"],
            policy_assessment_id=undeclared_kind_exp["expectations"][0]["policy_assessment_id"],
            policy_finding_id=undeclared_kind_exp["expectations"][0]["policy_finding_id"],
            policy_source_ref=undeclared_kind_exp["expectations"][0]["policy_source_ref"],
            expected_evidence_kinds=tuple(undeclared_kind_exp["expectations"][0]["expected_evidence_kinds"]),
            verification_rule_ids=("RULE-1", "RULE-SAST"),
        )
        undeclared_kind_exp["expectations"][0]["expectation_digest"] = compute_expectation_digest(exp_undeclared_obj)
        undeclared_kind_exp["expectation_set_digest"] = compute_expectation_set_semantic_digest(
            self.policy_admission.identity,
            (exp_undeclared_obj,),
            version=undeclared_kind_exp["expectation_set_version"],
        )
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                undeclared_kind_exp,
                policy_admission=self.policy_admission,
                ruleset=loaded_two_rules,
            )

        # 5. Positive: multiple declared kinds with exactly matching referenced rules
        valid_multi_exp = copy.deepcopy(undeclared_kind_exp)
        valid_multi_exp["expectations"][0]["expected_evidence_kinds"] = [
            "dependency_lockfile",
            "sast_workflow",
        ]
        exp_valid_multi_obj = PolicyImplementationExpectation(
            expectation_id=valid_multi_exp["expectations"][0]["expectation_id"],
            expectation_digest="dummy",
            task_id=valid_multi_exp["expectations"][0]["task_id"],
            policy_assessment_id=valid_multi_exp["expectations"][0]["policy_assessment_id"],
            policy_finding_id=valid_multi_exp["expectations"][0]["policy_finding_id"],
            policy_source_ref=valid_multi_exp["expectations"][0]["policy_source_ref"],
            expected_evidence_kinds=("dependency_lockfile", "sast_workflow"),
            verification_rule_ids=("RULE-1", "RULE-SAST"),
        )
        valid_multi_exp["expectations"][0]["expectation_digest"] = compute_expectation_digest(exp_valid_multi_obj)
        valid_multi_exp["expectation_set_digest"] = compute_expectation_set_semantic_digest(
            self.policy_admission.identity,
            (exp_valid_multi_obj,),
            version=valid_multi_exp["expectation_set_version"],
        )
        admitted = load_expectation_set(
            valid_multi_exp,
            policy_admission=self.policy_admission,
            ruleset=loaded_two_rules,
        )
        self.assertEqual(
            admitted.expectations[0].expected_evidence_kinds,
            ("dependency_lockfile", "sast_workflow"),
        )

    def test_expectation_rejects_duplicate_ids_and_unknown_fields(self) -> None:
        duplicate_id = expectation_set_data()
        duplicate_id["expectations"].append(copy.deepcopy(duplicate_id["expectations"][0]))
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                duplicate_id,
                policy_admission=self.policy_admission,
                ruleset=load_ruleset(ruleset_data()),
            )

        unknown = expectation_set_data()
        unknown["expectations"][0]["approved"] = True
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                unknown,
                policy_admission=self.policy_admission,
                ruleset=load_ruleset(ruleset_data()),
            )

    def test_policy_finding_must_be_unique_and_source_ref_must_match(self) -> None:
        for field, value, child_digest, set_digest in (
            (
                "policy_finding_id",
                "UNKNOWN-FINDING",
                EXP_UNKNOWN_FINDING_DIGEST,
                EXP_UNKNOWN_FINDING_SET_DIGEST,
            ),
            (
                "policy_source_ref",
                "policy/other.md#locking",
                EXP_SOURCE_MISMATCH_DIGEST,
                EXP_SOURCE_MISMATCH_SET_DIGEST,
            ),
            (
                "task_id",
                "PS.2.1",
                EXP_TASK_MISMATCH_DIGEST,
                EXP_TASK_MISMATCH_SET_DIGEST,
            ),
        ):
            with self.subTest(field=field):
                data = expectation_set_data()
                data["expectations"][0][field] = value
                data["expectations"][0]["expectation_digest"] = child_digest
                data["expectation_set_digest"] = set_digest
                with self.assertRaises(ContractInputError):
                    load_expectation_set(
                        data,
                        policy_admission=self.policy_admission,
                        ruleset=load_ruleset(ruleset_data()),
                    )

    def test_unadmitted_policy_and_ruleset_objects_cannot_cross_boundary(self) -> None:
        forged = object.__new__(PolicyAssessmentAdmission)
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=forged,
                ruleset=load_ruleset(ruleset_data()),
            )

        forged_ruleset = object.__new__(type(load_ruleset(ruleset_data())))
        with self.assertRaises(ContractInputError):
            load_expectation_set(
                expectation_set_data(),
                policy_admission=self.policy_admission,
                ruleset=forged_ruleset,
            )

    def test_digest_fields_require_lowercase_sha256(self) -> None:
        for digest in ("A" * 64, "x" * 64, "0" * 63):
            data = ruleset_data()
            data["ruleset_digest"] = digest
            with self.subTest(digest=digest):
                with self.assertRaises(ContractInputError):
                    load_ruleset(data)

    def test_rule_expectation_and_set_digests_exclude_their_own_digest_fields(self) -> None:
        ruleset = load_ruleset(ruleset_data())
        admitted_set = load_expectation_set(
            expectation_set_data(),
            policy_admission=self.policy_admission,
            ruleset=ruleset,
        )
        self.assertEqual(compute_rule_digest(ruleset.rules[0]), RULE_DIGEST)
        self.assertEqual(
            compute_rule_digest(replace(ruleset.rules[0], rule_digest="f" * 64)),
            RULE_DIGEST,
        )
        self.assertEqual(compute_expectation_digest(admitted_set.expectations[0]), EXPECTATION_DIGEST)
        self.assertEqual(
            compute_expectation_digest(
                replace(admitted_set.expectations[0], expectation_digest="f" * 64)
            ),
            EXPECTATION_DIGEST,
        )
        self.assertEqual(compute_ruleset_digest(ruleset), RULESET_DIGEST)
        changed_ruleset = replace(
            ruleset,
            rules=(replace(ruleset.rules[0], rule_digest="f" * 64),),
            ruleset_digest="e" * 64,
        )
        self.assertEqual(compute_ruleset_digest(changed_ruleset), RULESET_DIGEST)
        self.assertEqual(compute_expectation_set_digest(admitted_set), EXPECTATION_SET_DIGEST)
        changed_expectation_set = replace(
            admitted_set,
            expectations=(
                replace(admitted_set.expectations[0], expectation_digest="f" * 64),
            ),
            expectation_set_digest="e" * 64,
        )
        self.assertEqual(
            compute_expectation_set_digest(changed_expectation_set),
            EXPECTATION_SET_DIGEST,
        )

    def test_policy_admission_fails_on_unmaterialized_source_and_bad_target_digest(self) -> None:
        repo_path = self.assessment_path.parent / "policy-repo"
        manifest_path = repo_path / "target-manifest.yaml"
        base = yaml.safe_load(self.assessment_path.read_text(encoding="utf-8"))

        missing_source = copy.deepcopy(base)
        missing_source["results"][0]["company_source_ref"] = "policy/not-present.md#section"
        self.assessment_path.write_text(
            yaml.safe_dump(missing_source, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment_path, manifest_path, repo_path)

        bad_digest = copy.deepcopy(base)
        bad_digest["assessment"]["target"]["manifest_digest"] = "f" * 64
        self.assessment_path.write_text(
            yaml.safe_dump(bad_digest, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment_path, manifest_path, repo_path)

    def test_policy_admission_fails_on_duplicate_finding_identity(self) -> None:
        repo_path = self.assessment_path.parent / "policy-repo"
        manifest_path = repo_path / "target-manifest.yaml"
        duplicated = yaml.safe_load(self.assessment_path.read_text(encoding="utf-8"))
        duplicated["results"].append(copy.deepcopy(duplicated["results"][0]))
        duplicated["assessment"]["scope_tasks"] = ["PW.4.4", "PW.8.1"]
        duplicated["results"][1]["task_id"] = "PW.8.1"
        duplicated["results"][1]["basis"][0]["task_id"] = "PW.8.1"
        self.assessment_path.write_text(
            yaml.safe_dump(duplicated, sort_keys=False), encoding="utf-8"
        )

        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment_path, manifest_path, repo_path)


if __name__ == "__main__":
    unittest.main()