from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.implementation_contracts import (
    ContractInputError,
    PolicyAssessmentAdmission,
    admit_policy_assessment,
    compute_expectation_digest,
    compute_expectation_set_digest,
    compute_rule_digest,
    compute_ruleset_digest,
    compute_ruleset_semantic_digest,
    compute_expectation_set_semantic_digest,
    load_expectation_set,
    load_ruleset,
    verify_admitted_ruleset,
    verify_admitted_expectation_set,
)
from tools.repo_corpus_resolver import RepoCorpusResolver
from tools.validate_target_manifest import parse_target_manifest
from tools.implementation_matchers import EvidenceAssertion, ExpectedScalar, ExpectedScalarKind, MatcherKind

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


def fixture_hash(payload: dict) -> str:
    """Independent frozen-spec JSON oracle, deliberately not a production helper."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def rehash_rules(data: dict) -> dict:
    fields = ("rule_id", "task_id", "evidence_kind", "candidate_selectors",
              "candidate_quantifier", "assertion", "applicability")
    payloads = []
    for item in data["rules"]:
        payload = {field: item[field] for field in fields}
        item["rule_digest"] = fixture_hash(payload)
        payloads.append(payload)
    data["ruleset_digest"] = fixture_hash({"ruleset_version": data["ruleset_version"],
                                         "rules": sorted(payloads, key=lambda item: item["rule_id"])})
    return data


def rehash_expectations(data: dict) -> dict:
    fields = ("expectation_id", "task_id", "policy_assessment_id", "policy_finding_id",
              "policy_source_ref", "expected_evidence_kinds", "verification_rule_ids")
    payloads = []
    for item in data["expectations"]:
        payload = {field: item[field] for field in fields}
        payload["verification_rule_ids"] = sorted(item["verification_rule_ids"])
        item["expectation_digest"] = fixture_hash(payload)
        payloads.append(payload)
    data["expectation_set_digest"] = fixture_hash({
        "expectation_set_version": data["expectation_set_version"],
        "policy_assessment_identity": data["policy_assessment_identity"],
        "expectations": sorted(payloads, key=lambda item: item["expectation_id"]),
    })
    return data


def run_git(repo_path: Path, *args: str) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
        "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
    }
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
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
    policy_file.write_text("# Dependency policy\nLock dependencies.\n", encoding="utf-8", newline="\n")
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

    def test_applicability_reason_is_required_only_for_not_applicable(self) -> None:
        not_applicable = ruleset_data()
        not_applicable["rules"][0]["applicability"] = {
            "reason": "No lockfile requirement",
            "status": "NOT_APPLICABLE",
        }
        admitted = load_ruleset(rehash_rules(not_applicable))
        self.assertEqual(admitted.rules[0].applicability.reason, "No lockfile requirement")
        for status, reason in (("APPLICABLE", "why"), ("NOT_APPLICABLE", None),
                               ("NOT_APPLICABLE", "  "), ("NOT_APPLICABLE", 1)):
            with self.subTest(status=status, reason=reason):
                invalid = ruleset_data()
                invalid["rules"][0]["applicability"] = {"status": status, "reason": reason}
                with self.assertRaises(ContractInputError):
                    load_ruleset(rehash_rules(invalid))

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

    def test_fixture_oracle_matches_the_independent_fixed_goldens(self) -> None:
        self.assertEqual(rehash_rules(ruleset_data()), ruleset_data())
        self.assertEqual(rehash_expectations(expectation_set_data()), expectation_set_data())

    def test_evidence_kinds_match_referenced_rules_in_both_directions(self) -> None:
        for kinds in (["dependency_lockfile", "release_signature"], ["release_signature"]):
            with self.subTest(kinds=kinds):
                data = expectation_set_data()
                data["expectations"][0]["expected_evidence_kinds"] = kinds
                with self.assertRaises(ContractInputError):
                    load_expectation_set(rehash_expectations(data),
                                         policy_admission=self.policy_admission,
                                         ruleset=load_ruleset(ruleset_data()))

    def test_dataclass_replace_does_not_retain_aggregate_admission(self) -> None:
        rules = load_ruleset(ruleset_data())
        exps = load_expectation_set(expectation_set_data(), policy_admission=self.policy_admission,
                                   ruleset=rules)
        for value, verifier in ((rules, verify_admitted_ruleset), (exps, verify_admitted_expectation_set)):
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(ContractInputError):
                    verifier(replace(value))

    def test_recomputed_empty_selector_cannot_reenter_admitted_boundary(self) -> None:
        rules = load_ruleset(ruleset_data())
        with self.assertRaises(ContractInputError):
            changed = replace(rules.rules[0], candidate_selectors=())
            changed = replace(changed, rule_digest=compute_rule_digest(changed))
            changed_set = replace(rules, rules=(changed,),
                                  ruleset_digest=compute_ruleset_semantic_digest((changed,)))
            verify_admitted_ruleset(changed_set)

    def test_recomputed_source_cannot_reenter_admitted_boundary(self) -> None:
        rules = load_ruleset(ruleset_data())
        exps = load_expectation_set(expectation_set_data(), policy_admission=self.policy_admission,
                                   ruleset=rules)
        changed = replace(exps.expectations[0], policy_source_ref="outside.md#fake")
        changed = replace(changed, expectation_digest=compute_expectation_digest(changed))
        changed_set = replace(exps, expectations=(changed,), expectation_set_digest=
                              compute_expectation_set_semantic_digest(exps.policy_assessment_identity, (changed,)))
        with self.assertRaises(ContractInputError):
            verify_admitted_expectation_set(changed_set)

    def test_policy_admission_retains_the_actual_snapshot_and_fingerprints(self) -> None:
        admission = self.policy_admission
        self.assertTrue(admission.policy_snapshot_integrity_verified)
        self.assertEqual(admission.policy_repository_identity_status.value, "VERIFIED")
        self.assertEqual(admission.policy_unverified_reason_codes, ())
        self.assertEqual(admission.snapshot.corpus_digest, admission.identity.target_corpus_digest)
        self.assertEqual(admission.snapshot.get_file("policy/dependencies.md").content,
                         "# Dependency policy\nLock dependencies.\n")
        self.assertEqual(admission.assessment_sha256,
                         hashlib.sha256(self.assessment_path.read_bytes()).hexdigest())
        self.assertEqual(admission.manifest_sha256, hashlib.sha256(
            (self.assessment_path.parent / "policy-repo" / "target-manifest.yaml").read_bytes()).hexdigest())
        with self.assertRaises(AttributeError):
            admission._findings = ()

    def test_github_same_path_on_wrong_host_is_a_known_identity_mismatch(self) -> None:
        repo = self.assessment_path.parent / "policy-repo"
        run_git(repo, "remote", "set-url", "origin", "https://elsewhere.example/example/policy.git")
        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment_path, repo / "target-manifest.yaml", repo)

    def test_local_git_declared_path_must_match_materialized_repository(self) -> None:
        repo = self.assessment_path.parent / "policy-repo"
        manifest_file = repo / "target-manifest.yaml"
        data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
        data["target"]["source_type"] = "local_git"
        data["target"]["repo"] = str(repo.parent / "different-repo")
        manifest_file.write_text(yaml.safe_dump(data), encoding="utf-8")
        manifest = parse_target_manifest(data)
        assessment = yaml.safe_load(self.assessment_path.read_text(encoding="utf-8"))
        assessment["assessment"]["target"]["repo"] = data["target"]["repo"]
        assessment["assessment"]["target"]["manifest_digest"] = manifest.digest
        self.assessment_path.write_text(yaml.safe_dump(assessment), encoding="utf-8")
        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment_path, manifest_file, repo)

    def test_provenance_flag_does_not_replace_original_manifest_and_snapshot(self) -> None:
        data = yaml.safe_load(self.assessment_path.read_text(encoding="utf-8"))
        data["provenance_verified"] = True
        self.assessment_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        for manifest in (None, self.assessment_path.parent / "missing.yaml"):
            with self.subTest(manifest=str(manifest)):
                with self.assertRaises(ContractInputError):
                    admit_policy_assessment(self.assessment_path, manifest,
                                            self.assessment_path.parent / "policy-repo")

    def test_policy_parse_error_has_no_source_bearing_traceback_chain(self) -> None:
        import traceback
        secret = "TEST_SOURCE_MUST_NOT_ESCAPE"
        self.assessment_path.write_text("assessment: [\n" + secret, encoding="utf-8")
        try:
            admit_policy_assessment(self.assessment_path,
                                    self.assessment_path.parent / "policy-repo" / "target-manifest.yaml",
                                    self.assessment_path.parent / "policy-repo")
        except ContractInputError as error:
            self.assertNotIn(secret, "".join(traceback.format_exception(error)))
        else:
            self.fail("Invalid assessment was admitted")

    def test_duplicate_policy_yaml_keys_fail_closed(self) -> None:
        with self.assessment_path.open("a", encoding="utf-8") as stream:
            stream.write("\nresults: []\n")
        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment_path,
                                    self.assessment_path.parent / "policy-repo" / "target-manifest.yaml",
                                    self.assessment_path.parent / "policy-repo")

    def test_large_integer_digest_is_native_json_without_process_digit_limit_changes(self) -> None:
        import sys
        rules = load_ruleset(ruleset_data())
        value = 10 ** 5000 - 1
        assertion = EvidenceAssertion(MatcherKind.JSON_POINTER_EQUALS, "/version",
                                      ExpectedScalar(ExpectedScalarKind.INTEGER, value))
        model = replace(rules.rules[0], assertion=assertion)
        payload = {key: val for key, val in ruleset_data()["rules"][0].items() if key != "rule_digest"}
        marker = "INTEGER_MARKER"
        payload["assertion"] = {"matcher": "JSON_POINTER_EQUALS", "target_path_expression": "/version",
                                "expected_value": {"kind": "INTEGER", "value": marker}}
        json_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).replace(
            '"INTEGER_MARKER"', "9" * 5000).encode("utf-8")
        before = sys.get_int_max_str_digits()
        self.assertEqual(compute_rule_digest(model), hashlib.sha256(json_bytes).hexdigest())
        self.assertEqual(sys.get_int_max_str_digits(), before)

    def test_every_policy_identity_field_is_bound_even_after_rehash(self) -> None:
        changes = {"assessment_id": "ASSESS-2", "target_source_type": "local_git",
                   "target_repo": "other/policy", "target_commit": "a" * 40,
                   "target_manifest_digest": "a" * 64, "target_corpus_digest": "a" * 64}
        for field, value in changes.items():
            with self.subTest(field=field):
                data = expectation_set_data()
                data["policy_assessment_identity"][field] = value
                with self.assertRaises(ContractInputError):
                    load_expectation_set(rehash_expectations(data), policy_admission=self.policy_admission,
                                         ruleset=load_ruleset(ruleset_data()))

    def test_source_anchor_is_exact_and_identified_evidence_is_not_authority(self) -> None:
        data = expectation_set_data()
        data["expectations"][0]["policy_source_ref"] = "policy/dependencies.md#different-anchor"
        with self.assertRaises(ContractInputError):
            load_expectation_set(rehash_expectations(data), policy_admission=self.policy_admission,
                                 ruleset=load_ruleset(ruleset_data()))
        # Anchor existence is not claimed; the original fixture intentionally has no #locking anchor.
        assessment = yaml.safe_load(self.assessment_path.read_text(encoding="utf-8"))
        assessment["results"][0]["company_source_ref"] = "policy/dependencies.md#changed"
        self.assessment_path.write_text(yaml.safe_dump(assessment), encoding="utf-8")
        admission = admit_policy_assessment(self.assessment_path,
                                            self.assessment_path.parent / "policy-repo" / "target-manifest.yaml",
                                            self.assessment_path.parent / "policy-repo")
        with self.assertRaises(ContractInputError):
            load_expectation_set(expectation_set_data(), policy_admission=admission,
                                 ruleset=load_ruleset(ruleset_data()))
        old_set = load_expectation_set(expectation_set_data(), policy_admission=self.policy_admission,
                                       ruleset=load_ruleset(ruleset_data()))
        self.assertEqual(old_set.expectations[0].policy_source_ref, "policy/dependencies.md#locking")
        self.assertNotEqual(admission.assessment_sha256, self.policy_admission.assessment_sha256)

    def test_author_order_and_unordered_rule_refs_follow_frozen_digest_contract(self) -> None:
        data = ruleset_data()
        data["rules"][0]["candidate_selectors"] = ["src/**", "config/**"]
        first = load_ruleset(rehash_rules(data))
        data["rules"][0]["candidate_selectors"].reverse()
        second = load_ruleset(rehash_rules(data))
        self.assertNotEqual(first.ruleset_digest, second.ruleset_digest)
        rules_data = ruleset_data()
        rules_data["rules"].append(rule("RULE-2"))
        rules = load_ruleset(rehash_rules(rules_data))
        exp_data = expectation_set_data()
        exp_data["expectations"][0]["verification_rule_ids"] = ["RULE-2", "RULE-1"]
        first_exp = load_expectation_set(rehash_expectations(exp_data),
                                         policy_admission=self.policy_admission, ruleset=rules)
        exp_data["expectations"][0]["verification_rule_ids"].reverse()
        second_exp = load_expectation_set(rehash_expectations(exp_data),
                                          policy_admission=self.policy_admission, ruleset=rules)
        self.assertEqual(first_exp.expectation_set_digest, second_exp.expectation_set_digest)

    def test_strict_direct_model_types_and_collection_shapes(self) -> None:
        model = load_ruleset(ruleset_data()).rules[0]
        for change in ({"candidate_selectors": ["src/**"]}, {"candidate_quantifier": "ANY"},
                       {"task_id": "PW.8.1"}, {"evidence_kind": []}, {"rule_digest": "A" * 64}):
            with self.subTest(change=change):
                with self.assertRaises(ContractInputError):
                    replace(model, **change)

    def test_snapshot_comes_from_pinned_git_bytes_despite_dirty_working_file(self) -> None:
        repo = self.assessment_path.parent / "policy-repo"
        (repo / "policy" / "dependencies.md").write_text("Uncommitted content\n", encoding="utf-8")
        fresh = admit_policy_assessment(self.assessment_path, repo / "target-manifest.yaml", repo)
        self.assertEqual(fresh.snapshot.corpus_digest, self.policy_admission.snapshot.corpus_digest)
        self.assertEqual(fresh.snapshot.files, self.policy_admission.snapshot.files)

    def test_observation_and_identified_evidence_cannot_supply_a_task_finding(self) -> None:
        data = yaml.safe_load(self.assessment_path.read_text(encoding="utf-8"))
        data["non_normative_observations"] = [{
            "finding_id": "OBS-1", "finding_type": "non_normative_observation",
            "company_source_ref": "policy/dependencies.md#locking",
            "observation": "An inventory could be clearer.", "basis": "reviewer_inference",
            "review_queue_recommendation": "pending", "cannot_claim": ["Not a task requirement."],
        }]
        self.assessment_path.write_text(yaml.safe_dump(data), encoding="utf-8")
        admission = admit_policy_assessment(self.assessment_path,
                                            self.assessment_path.parent / "policy-repo" / "target-manifest.yaml",
                                            self.assessment_path.parent / "policy-repo")
        self.assertEqual(tuple(finding.finding_id for finding in admission.findings), ("FIND-1",))
        exps = expectation_set_data()
        exps["expectations"][0]["policy_finding_id"] = "OBS-1"
        with self.assertRaises(ContractInputError):
            load_expectation_set(rehash_expectations(exps), policy_admission=admission,
                                 ruleset=load_ruleset(ruleset_data()))

    def test_assessment_edit_during_s1_validation_cannot_lend_approval_to_other_bytes(self) -> None:
        from unittest.mock import patch
        from tools.review_engine import validate_ssdf_assessment
        original = self.assessment_path.read_bytes()

        def concurrent_edit(path: Path, **kwargs: object) -> list:
            self.assertEqual(path.read_bytes(), original)
            errors = validate_ssdf_assessment(path, **kwargs)
            data = yaml.safe_load(original)
            data["results"][0]["company_source_ref"] = "policy/dependencies.md#different"
            self.assessment_path.write_text(yaml.safe_dump(data), encoding="utf-8")
            return errors

        with patch("tools.review_engine.validate_ssdf_assessment", side_effect=concurrent_edit):
            with self.assertRaises(ContractInputError):
                admit_policy_assessment(self.assessment_path,
                                        self.assessment_path.parent / "policy-repo" / "target-manifest.yaml",
                                        self.assessment_path.parent / "policy-repo")


if __name__ == "__main__":
    unittest.main()
