from __future__ import annotations

import copy
import json
import traceback
import unittest
from unittest.mock import patch
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from tools.implementation_contracts import (
    CandidateQuantifier,
    ContractInputError,
    ImplementationEvidenceRule,
    PolicyAssessmentIdentity,
    PolicyImplementationExpectation,
    RuleApplicability,
    RuleApplicabilityStatus,
    compute_expectation_digest,
    compute_expectation_set_semantic_digest,
    compute_rule_digest,
    compute_ruleset_semantic_digest,
    load_expectation_set,
    load_ruleset,
)
from tools.implementation_evaluator import (
    EvidenceLocator,
    EvidenceRef,
    EvaluatorInputError,
    ImplementationEvidenceVerdict,
    ImplementationVerificationItem,
    evaluate_expectation_set,
)
from tools.implementation_matchers import (
    DiscrepancyCode,
    EvidenceAssertion,
    ExpectedScalar,
    ExpectedScalarKind,
    InvalidEvidenceInputError,
    InvalidRuleError,
    MatcherKind,
)
from tools.product_corpus_resolver import CorpusResolverError, ProductCorpusResolver
from tools.validate_product_target_manifest import parse_product_target_manifest
from tests.test_implementation_contracts import make_policy_admission, run_git


def make_rule(
    *,
    rule_id: str = "RULE-1",
    task_id: str = "PW.4.4",
    evidence_kind: str = "dependency_lockfile",
    selectors: list[str] | None = None,
    quantifier: str = "ANY",
    matcher: str = "FILE_EXISTS",
    target_path: str | None = None,
    expected_value: dict | None = None,
    applicability: dict | None = None,
) -> ImplementationEvidenceRule:
    assertion_expected = None
    if expected_value is not None:
        assertion_expected = ExpectedScalar(
            ExpectedScalarKind(expected_value["kind"]), expected_value["value"]
        )
    assertion = EvidenceAssertion(
        matcher=MatcherKind(matcher),
        target_path_expression=target_path,
        expected_value=assertion_expected,
    )
    applicability_data = applicability or {"status": "APPLICABLE", "reason": None}
    return ImplementationEvidenceRule(
        rule_id=rule_id,
        rule_digest="0" * 64,
        task_id=task_id,
        evidence_kind=evidence_kind,
        candidate_selectors=tuple(["src/**"] if selectors is None else selectors),
        candidate_quantifier=CandidateQuantifier(quantifier),
        assertion=assertion,
        applicability=RuleApplicability(
            RuleApplicabilityStatus(applicability_data["status"]),
            applicability_data["reason"],
        ),
    )


def make_admitted_ruleset(rule_value: ImplementationEvidenceRule):
    rule_digest = compute_rule_digest(rule_value)
    canonical_rule = replace(rule_value, rule_digest=rule_digest)
    ruleset_digest = compute_ruleset_semantic_digest((canonical_rule,))
    return load_ruleset(
        {
            "ruleset_version": "1.0",
            "rules": [_rule_to_input(canonical_rule)],
            "ruleset_digest": ruleset_digest,
        }
    )


def _rule_to_input(rule_value: ImplementationEvidenceRule) -> dict:
    expected = rule_value.assertion.expected_value
    return {
        "rule_id": rule_value.rule_id,
        "rule_digest": rule_value.rule_digest,
        "task_id": rule_value.task_id,
        "evidence_kind": rule_value.evidence_kind,
        "candidate_selectors": list(rule_value.candidate_selectors),
        "candidate_quantifier": rule_value.candidate_quantifier.value,
        "assertion": {
            "matcher": rule_value.assertion.matcher.value,
            "target_path_expression": rule_value.assertion.target_path_expression,
            "expected_value": None
            if expected is None
            else {"kind": expected.kind.value, "value": expected.value},
        },
        "applicability": {
            "status": rule_value.applicability.status.value,
            "reason": rule_value.applicability.reason,
        },
    }


def make_admitted_expectations(
    policy_admission,
    rules: tuple[ImplementationEvidenceRule, ...],
    *,
    expectation_specs: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
):
    expectation_specs = expectation_specs or (("EXP-1", (rules[0].rule_id,)),)
    expectation_values = tuple(
        PolicyImplementationExpectation(
            expectation_id=expectation_id,
            expectation_digest="0" * 64,
            task_id="PW.4.4",
            policy_assessment_id=policy_admission.identity.assessment_id,
            policy_finding_id="FIND-1",
            policy_source_ref="policy/dependencies.md#locking",
            expected_evidence_kinds=("dependency_lockfile",),
            verification_rule_ids=rule_ids,
        )
        for expectation_id, rule_ids in expectation_specs
    )
    expectation_values = tuple(
        replace(value, expectation_digest=compute_expectation_digest(value))
        for value in expectation_values
    )
    set_digest = compute_expectation_set_semantic_digest(
        policy_admission.identity, expectation_values
    )
    return load_expectation_set(
        {
            "expectation_set_version": "1.0",
            "policy_assessment_identity": {
                "assessment_id": policy_admission.identity.assessment_id,
                "target_source_type": policy_admission.identity.target_source_type,
                "target_repo": policy_admission.identity.target_repo,
                "target_commit": policy_admission.identity.target_commit,
                "target_manifest_digest": policy_admission.identity.target_manifest_digest,
                "target_corpus_digest": policy_admission.identity.target_corpus_digest,
            },
            "expectations": [
                {
                    "expectation_id": value.expectation_id,
                    "expectation_digest": value.expectation_digest,
                    "task_id": value.task_id,
                    "policy_assessment_id": value.policy_assessment_id,
                    "policy_finding_id": value.policy_finding_id,
                    "policy_source_ref": value.policy_source_ref,
                    "expected_evidence_kinds": list(value.expected_evidence_kinds),
                    "verification_rule_ids": list(value.verification_rule_ids),
                }
                for value in expectation_values
            ],
            "expectation_set_digest": set_digest,
        },
        policy_admission=policy_admission,
        ruleset=load_ruleset(
            {
                "ruleset_version": "1.0",
                "rules": [_rule_to_input(rule) for rule in rules],
                "ruleset_digest": compute_ruleset_semantic_digest(rules),
            }
        ),
    )


class EvaluatorTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        self.policy_admission, _assessment_path = make_policy_admission(self.root_dir)
        self.repo_dir = self.root_dir / "product-repo"
        self.repo_dir.mkdir()
        run_git(self.repo_dir, "init", "-b", "main")
        run_git(self.repo_dir, "config", "user.name", "S2 Evaluator")
        run_git(self.repo_dir, "config", "user.email", "s2-evaluator@example.invalid")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _snapshot(self, files: dict[str, str]):
        for relative_path, content in files.items():
            path = self.repo_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
        run_git(self.repo_dir, "add", ".")
        run_git(self.repo_dir, "commit", "-m", "add product evidence")
        commit = run_git(self.repo_dir, "rev-parse", "HEAD")
        manifest = parse_product_target_manifest(
            {
                "manifest_version": "1.0",
                "target": {
                    "source_type": "local_git",
                    "repo": str(self.repo_dir),
                    "commit": commit,
                },
                "authority_surface": {"include": ["src/**"]},
                "mode": {"read_only": True},
            }
        )
        return ProductCorpusResolver().resolve(manifest, self.repo_dir)

    def _admitted(
        self,
        rule_value: ImplementationEvidenceRule,
        expectation_specs: tuple[tuple[str, tuple[str, ...]], ...] | None = None,
    ):
        ruleset = make_admitted_ruleset(rule_value)
        expectation_set = make_admitted_expectations(
            self.policy_admission,
            ruleset.rules,
            expectation_specs=expectation_specs,
        )
        return expectation_set, ruleset


class ImplementationEvaluatorTests(EvaluatorTestBase):
    def test_file_exists_returns_one_ref_with_specified_locator(self) -> None:
        snapshot = self._snapshot({"src/package.lock": "locked\n"})
        rule_value = make_rule(selectors=["src/*.lock"])
        expectation_set, ruleset = self._admitted(rule_value)

        items = evaluate_expectation_set(expectation_set, ruleset, snapshot)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].verdict, ImplementationEvidenceVerdict.EVIDENCE_FOUND)
        self.assertEqual(
            items[0].evidence_refs[0],
            type(items[0].evidence_refs[0])(
                repo_path="src/package.lock",
                content_digest=snapshot.get_file("src/package.lock").content_hash,
                locator=EvidenceLocator("file_existence", "src/package.lock"),
            ),
        )

    def test_empty_candidate_set_is_missing_but_not_applicable_takes_precedence(self) -> None:
        snapshot = self._snapshot({"src/readme.txt": "out of scope\n"})
        applicable, applicable_rules = self._admitted(
            make_rule(selectors=["src/*.lock"])
        )
        missing = evaluate_expectation_set(applicable, applicable_rules, snapshot)
        self.assertEqual(missing[0].verdict, ImplementationEvidenceVerdict.EVIDENCE_MISSING)
        self.assertEqual(missing[0].evidence_refs, ())
        self.assertIsNone(missing[0].discrepancy_details)

        not_applicable_rule = make_rule(
            selectors=["src/*.lock"],
            applicability={"status": "NOT_APPLICABLE", "reason": "No dependency lockfile applies."},
        )
        not_applicable, not_applicable_rules = self._admitted(not_applicable_rule)
        result = evaluate_expectation_set(not_applicable, not_applicable_rules, snapshot)
        self.assertEqual(result[0].verdict, ImplementationEvidenceVerdict.RULE_NOT_APPLICABLE)
        self.assertEqual(result[0].evidence_refs, ())
        self.assertEqual(result[0].applicability_reason, "No dependency lockfile applies.")

    def test_any_and_all_quantify_files_not_yaml_nodes(self) -> None:
        snapshot = self._snapshot(
            {
                "src/a.yml": "steps:\n  - uses: expected/action@v1\n  - uses: other/action@v1\n",
                "src/b.yml": "steps:\n  - uses: other/action@v1\n",
            }
        )
        assertion_kwargs = {
            "matcher": "YAML_PATH_EQUALS",
            "target_path": "steps[*].uses",
            "expected_value": {"kind": "STRING", "value": "expected/action@v1"},
        }
        any_set, any_rules = self._admitted(
            make_rule(selectors=["src/*.yml"], quantifier="ANY", **assertion_kwargs)
        )
        any_item = evaluate_expectation_set(any_set, any_rules, snapshot)[0]
        self.assertEqual(any_item.verdict, ImplementationEvidenceVerdict.EVIDENCE_FOUND)
        self.assertEqual([ref.repo_path for ref in any_item.evidence_refs], ["src/a.yml"])
        self.assertEqual(
            any_item.evidence_refs[0].resolved_node_paths,
            ("/steps/0/uses",),
        )

        all_set, all_rules = self._admitted(
            make_rule(selectors=["src/*.yml"], quantifier="ALL", **assertion_kwargs)
        )
        all_item = evaluate_expectation_set(all_set, all_rules, snapshot)[0]
        self.assertEqual(all_item.verdict, ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY)
        self.assertEqual([ref.repo_path for ref in all_item.evidence_refs], ["src/b.yml"])
        self.assertEqual(
            all_item.discrepancy_details,
            '[{"code":"VALUE_MISMATCH","repo_path":"src/b.yml"}]',
        )

    def test_any_failure_reports_all_candidates_with_sanitized_json(self) -> None:
        secret_a = "private-observed-value-A"
        secret_b = "private-observed-value-B"
        snapshot = self._snapshot(
            {
                "src/b.yml": f"token: {secret_b}\n",
                "src/a.yml": f"token: {secret_a}\n",
            }
        )
        rule_value = make_rule(
            selectors=["src/*.yml"],
            matcher="YAML_PATH_EQUALS",
            target_path="token",
            expected_value={"kind": "STRING", "value": "required-token"},
        )
        expectation_set, ruleset = self._admitted(rule_value)

        item = evaluate_expectation_set(expectation_set, ruleset, snapshot)[0]

        self.assertEqual(item.verdict, ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY)
        self.assertEqual(
            [ref.repo_path for ref in item.evidence_refs], ["src/a.yml", "src/b.yml"]
        )
        self.assertEqual(
            item.discrepancy_details,
            '[{"code":"VALUE_MISMATCH","repo_path":"src/a.yml"},'
            '{"code":"VALUE_MISMATCH","repo_path":"src/b.yml"}]',
        )
        self.assertNotIn(secret_a, repr(item))
        self.assertNotIn(secret_b, repr(item))
        self.assertNotIn("required-token", repr(item))

    def test_selector_union_deduplicates_and_sorts_paths(self) -> None:
        snapshot = self._snapshot(
            {"src/b.lock": "b\n", "src/a.lock": "a\n", "src/c.txt": "c\n"}
        )
        rule_value = make_rule(selectors=["src/*.lock", "src/a.*"])
        expectation_set, ruleset = self._admitted(rule_value)

        item = evaluate_expectation_set(expectation_set, ruleset, snapshot)[0]

        self.assertEqual(item.verdict, ImplementationEvidenceVerdict.EVIDENCE_FOUND)
        self.assertEqual(
            [ref.repo_path for ref in item.evidence_refs], ["src/a.lock", "src/b.lock"]
        )

    def test_each_expectation_rule_link_produces_distinct_item_without_rollup(self) -> None:
        snapshot = self._snapshot({"src/package.lock": "locked\n"})
        rule_value = make_rule(selectors=["src/*.lock"])
        expectation_set, ruleset = self._admitted(
            rule_value,
            expectation_specs=(("EXP-1", ("RULE-1",)), ("EXP-2", ("RULE-1",))),
        )

        items = evaluate_expectation_set(expectation_set, ruleset, snapshot)

        self.assertEqual(
            [(item.expectation_id, item.rule_id, item.verdict) for item in items],
            [
                ("EXP-1", "RULE-1", ImplementationEvidenceVerdict.EVIDENCE_FOUND),
                ("EXP-2", "RULE-1", ImplementationEvidenceVerdict.EVIDENCE_FOUND),
            ],
        )

    def test_selector_pattern_failure_is_not_treated_as_empty_candidate_set(self) -> None:
        snapshot = self._snapshot({"src/readme.txt": "none\n"})
        with self.assertRaises(ContractInputError):
            make_rule(selectors=["src/[a].txt"])
        with self.assertRaises(ContractInputError):
            make_rule(matcher="YAML_PATH_EXISTS", target_path="enabled..path")
        with self.assertRaises(ContractInputError):
            make_rule(selectors=[])

    def test_candidate_invalid_yaml_fails_closed_not_as_discrepancy(self) -> None:
        snapshot = self._snapshot({"src/bad.yml": "token: [unterminated\n"})
        rule_value = make_rule(
            selectors=["src/*.yml"],
            matcher="YAML_PATH_EXISTS",
            target_path="token",
        )
        expectation_set, ruleset = self._admitted(rule_value)

        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(expectation_set, ruleset, snapshot)

    def test_evaluator_rejects_unadmitted_product_snapshot(self) -> None:
        snapshot = self._snapshot({"src/file.lock": "locked\n"})
        expectation_set, ruleset = self._admitted(make_rule())
        forged_snapshot = object.__new__(type(snapshot))

        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(expectation_set, ruleset, forged_snapshot)

    def test_admitted_rule_or_expectation_mutation_is_rejected_before_evaluation(self) -> None:
        snapshot = self._snapshot({"src/file.lock": "locked\n"})
        rule_value = make_rule(selectors=["src/*.lock"])
        expectation_set, ruleset = self._admitted(rule_value)
        changed_rule = replace(
            ruleset.rules[0], candidate_selectors=("src/*.txt",)
        )
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(expectation_set, replace(ruleset, rules=(changed_rule,)), snapshot)

        changed_expectation = replace(
            expectation_set.expectations[0], task_id="PS.2.1"
        )
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(replace(expectation_set, expectations=(changed_expectation,)), ruleset, snapshot)

    def test_domain_values_reject_invalid_verdict_discrepancy_order_and_refs(self) -> None:
        with self.assertRaises(ValueError):
            ImplementationVerificationItem(
                expectation_id="EXP-1",
                expectation_digest="a" * 64,
                task_id="PW.4.4",
                rule_id="RULE-1",
                rule_digest="b" * 64,
                verdict="UNKNOWN",  # type: ignore[arg-type]
                evidence_refs=(),
            )

        with self.assertRaises(ValueError):
            ImplementationVerificationItem(
                expectation_id="EXP-1",
                expectation_digest="a" * 64,
                task_id="PW.4.4",
                rule_id="RULE-1",
                rule_digest="b" * 64,
                verdict=ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY,
                evidence_refs=(
                    EvidenceRef("src/a.yml", "c" * 64, EvidenceLocator("yaml_path", "key"), ("/key",)),
                    EvidenceRef("src/b.yml", "d" * 64, EvidenceLocator("yaml_path", "key"), ("/key",)),
                ),
                discrepancy_details=(
                    '[{"code":"VALUE_MISMATCH","repo_path":"src/b.yml"},'
                    '{"code":"VALUE_MISMATCH","repo_path":"src/a.yml"}]'
                ),
            )

        with self.assertRaises(ValueError):
            EvidenceRef("src/../outside.yml", "c" * 64, EvidenceLocator("yaml_path", "key"))
        with self.assertRaises(ValueError):
            EvidenceRef("src/./file.yml", "c" * 64, EvidenceLocator("yaml_path", "key"))
        with self.assertRaises(ValueError):
            EvidenceRef(
                "src/file.yml",
                "c" * 64,
                EvidenceLocator("yaml_path", "key"),
                resolved_node_paths=("jobs.steps",),
            )

        with self.assertRaises(ValueError):
            EvidenceRef(
                "src/file.yml",
                "c" * 64,
                EvidenceLocator("file_existence", "src/other.yml"),
            )
        with self.assertRaises(ValueError):
            EvidenceRef(
                "src/file.json",
                "c" * 64,
                EvidenceLocator("json_pointer", "value"),
            )

    def test_replaced_snapshot_and_admitted_aggregates_fail_integrity_checks(self) -> None:
        snapshot = self._snapshot({"src/file.lock": "locked\n"})
        expectation_set, ruleset = self._admitted(make_rule())
        file = snapshot.get_file("src/file.lock")
        altered_file = replace(file, content="secret altered content\n")
        with self.assertRaises(CorpusResolverError):
            replace(snapshot, files=(altered_file,))
        with self.assertRaises(CorpusResolverError):
            replace(snapshot, files=[file])

        mutable_snapshot = object.__new__(type(snapshot))
        for field_name in snapshot.__dataclass_fields__:
            object.__setattr__(mutable_snapshot, field_name, getattr(snapshot, field_name))
        object.__setattr__(mutable_snapshot, "files", [file])
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(expectation_set, ruleset, mutable_snapshot)

        changed_rule = replace(ruleset.rules[0], candidate_selectors=("src/*.txt",))
        changed_ruleset = replace(ruleset, rules=(changed_rule,))
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(expectation_set, changed_ruleset, snapshot)

        changed_expectation = replace(
            expectation_set.expectations[0], policy_source_ref="policy/other.md#sec"
        )
        changed_set = replace(expectation_set, expectations=(changed_expectation,))
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(changed_set, ruleset, snapshot)

    def test_same_id_foreign_ruleset_cannot_replace_bound_semantics(self) -> None:
        snapshot = self._snapshot({"src/file.lock": "locked\n"})
        expectation_set, _ = self._admitted(make_rule(selectors=["src/missing.lock"]))
        foreign_rules = make_admitted_ruleset(make_rule(selectors=["src/file.lock"]))
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(expectation_set, foreign_rules, snapshot)

    def test_file_quantifier_complete_matrix(self) -> None:
        snapshot = self._snapshot({
            "src/aa.yml": "value: true\n", "src/ab.yml": "value: true\n",
            "src/ma.yml": "value: true\n", "src/mb.yml": "value: false\n",
            "src/fa.yml": "value: false\n", "src/fb.yml": "value: false\n",
        })
        # Frozen S2-A's file-level matrix, independent of matcher implementation.
        cases = (
            ("ANY", "a", "EVIDENCE_FOUND", ("aa", "ab")),
            ("ALL", "a", "EVIDENCE_FOUND", ("aa", "ab")),
            ("ANY", "m", "EVIDENCE_FOUND", ("ma",)),
            ("ALL", "m", "EVIDENCE_DISCREPANCY", ("mb",)),
            ("ANY", "f", "EVIDENCE_DISCREPANCY", ("fa", "fb")),
            ("ALL", "f", "EVIDENCE_DISCREPANCY", ("fa", "fb")),
            ("ANY", "none", "EVIDENCE_MISSING", ()),
            ("ALL", "none", "EVIDENCE_MISSING", ()),
        )
        for quantifier, prefix, verdict, paths in cases:
            with self.subTest(quantifier=quantifier, prefix=prefix):
                exps, rules = self._admitted(make_rule(
                    selectors=[f"src/{prefix}*.yml"], quantifier=quantifier,
                    matcher="YAML_PATH_EQUALS", target_path="value",
                    expected_value={"kind": "BOOLEAN", "value": True}))
                item = evaluate_expectation_set(exps, rules, snapshot)[0]
                self.assertEqual(item.verdict.value, verdict)
                self.assertEqual(tuple(r.repo_path for r in item.evidence_refs),
                                 tuple(f"src/{p}.yml" for p in paths))
                if verdict == "EVIDENCE_DISCREPANCY":
                    self.assertEqual(json.loads(item.discrepancy_details),
                                     [{"code": "VALUE_MISMATCH", "repo_path": f"src/{p}.yml"}
                                      for p in paths])

    def test_any_success_cannot_hide_later_invalid_evidence(self) -> None:
        marker = "SYNTHETIC_PRIVATE_SOURCE"
        snapshot = self._snapshot({"src/a.yml": "key: true\n",
                                   "src/z.yml": f"key: [{marker}\n"})
        exps, rules = self._admitted(make_rule(selectors=["src/*.yml"],
            matcher="YAML_PATH_EXISTS", target_path="key"))
        try:
            evaluate_expectation_set(exps, rules, snapshot)
        except EvaluatorInputError:
            self.assertNotIn(marker, traceback.format_exc())
        else:
            self.fail("ANY must validate every candidate before returning a verdict")

    def test_not_applicable_does_not_parse_but_still_requires_admission(self) -> None:
        snapshot = self._snapshot({"src/bad.yml": "[bad\n"})
        exps, rules = self._admitted(make_rule(matcher="YAML_PATH_EXISTS", target_path="key",
            applicability={"status": "NOT_APPLICABLE", "reason": "Explicit synthetic exemption"}))
        self.assertEqual(evaluate_expectation_set(exps, rules, snapshot)[0].verdict.value,
                         "RULE_NOT_APPLICABLE")
        with self.assertRaises(EvaluatorInputError):
            evaluate_expectation_set(replace(exps), rules, snapshot)

    def test_node_locations_preserve_traversal_not_lexical_index_order(self) -> None:
        content = "steps:\n" + "  - uses: match\n" * 12
        snapshot = self._snapshot({"src/file.yml": content})
        exps, rules = self._admitted(make_rule(matcher="YAML_PATH_EQUALS",
            target_path="steps[*].uses", expected_value={"kind": "STRING", "value": "match"}))
        ref = evaluate_expectation_set(exps, rules, snapshot)[0].evidence_refs[0]
        self.assertEqual(ref.resolved_node_paths, tuple(f"/steps/{i}/uses" for i in range(12)))
        self.assertEqual(ref.locator, EvidenceLocator("yaml_path", "steps[*].uses"))

    def test_root_and_escaped_key_locators(self) -> None:
        snapshot = self._snapshot({"src/root.json": '{"a/b~c":{"":null}}'})
        for expression, nodes in (("", ("",)), ("/a~1b~0c/", ("/a~1b~0c/",))):
            exps, rules = self._admitted(make_rule(matcher="JSON_POINTER_EXISTS",
                                                  target_path=expression))
            ref = evaluate_expectation_set(exps, rules, snapshot)[0].evidence_refs[0]
            self.assertEqual(ref.locator.value, expression)
            self.assertEqual(ref.resolved_node_paths, nodes)

    def test_discrepancy_codes_and_node_consistency(self) -> None:
        snapshot = self._snapshot({"src/a.yml": "other: true\n", "src/b.yml": "key: {}\n",
                                   "src/c.yml": "key: false\n"})
        exps, rules = self._admitted(make_rule(quantifier="ALL", matcher="YAML_PATH_EQUALS",
            target_path="key", expected_value={"kind": "BOOLEAN", "value": True}))
        item = evaluate_expectation_set(exps, rules, snapshot)[0]
        self.assertEqual(item.discrepancy_details,
            '[{"code":"NO_NODE_MATCH","repo_path":"src/a.yml"},'
            '{"code":"UNCOMPARABLE_NODE","repo_path":"src/b.yml"},'
            '{"code":"VALUE_MISMATCH","repo_path":"src/c.yml"}]')
        self.assertEqual(tuple(r.resolved_node_paths for r in item.evidence_refs),
                         ((), ("/key",), ("/key",)))

    def test_item_models_reject_mutable_and_malformed_fields(self) -> None:
        ref = EvidenceRef("src/a.yml", "c" * 64, EvidenceLocator("yaml_path", "key"), ("/key",))
        valid = dict(expectation_id="E", expectation_digest="a" * 64, task_id="PW.4.4",
                     rule_id="R", rule_digest="b" * 64,
                     verdict=ImplementationEvidenceVerdict.EVIDENCE_FOUND, evidence_refs=(ref,))
        for patch in ({"evidence_refs": [ref]}, {"evidence_refs": (ref, ref)},
                      {"expectation_id": 1}, {"rule_id": ""}, {"task_id": "PW.8.1"},
                      {"explanation": 1}, {"explanation": "\ud800"}):
            with self.subTest(patch=repr(patch)), self.assertRaises(ValueError):
                ImplementationVerificationItem(**{**valid, **patch})

    def test_discrepancy_ref_paths_and_codes_cannot_disagree(self) -> None:
        for nodes, code in (((), "VALUE_MISMATCH"), ((), "UNCOMPARABLE_NODE"),
                            (("/key",), "NO_NODE_MATCH")):
            ref = EvidenceRef("src/a.yml", "c" * 64, EvidenceLocator("yaml_path", "key"), nodes)
            with self.subTest(nodes=nodes, code=code), self.assertRaises(ValueError):
                ImplementationVerificationItem("E", "a" * 64, "PW.4.4", "R", "b" * 64,
                    ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY, (ref,),
                    f'[{"{"}"code":"{code}","repo_path":"src/a.yml"{"}"}]')
        ref = EvidenceRef("src/a.yml", "c" * 64, EvidenceLocator("yaml_path", "key"), ("/key",))
        for payload in ('[{"code":"VALUE_MISMATCH","repo_path":"src/other.yml"}]',
                        '[{"code":"VALUE_MISMATCH","repo_path":"src/a.yml","secret":"hidden"}]'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                ImplementationVerificationItem("E", "a" * 64, "PW.4.4", "R", "b" * 64,
                    ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY, (ref,), payload)

    def test_ref_and_locator_strict_shapes(self) -> None:
        for kind, value in (("unknown", "x"), ("json_pointer", "missing-slash"),
                            ("yaml_path", "key..bad"), ("file_existence", "../bad"),
                            ("json_pointer", "\ud800"), (True, "key")):
            with self.subTest(kind=kind, value=repr(value)), self.assertRaises(ValueError):
                EvidenceLocator(kind, value)
        for path, nodes in (("src/a.yml", ["/key"]), ("src/a.yml", ("/key", "/key")),
                            ("src/a\tb.yml", ()), ("src/a\nb.yml", ()), (None, ())):
            with self.subTest(path=repr(path), nodes=nodes), self.assertRaises(ValueError):
                EvidenceRef(path, "c" * 64, EvidenceLocator("yaml_path", "key"), nodes)

    def test_multi_rule_edges_remain_independent_and_ordered(self) -> None:
        snapshot = self._snapshot({"src/file.lock": "locked\n"})
        missing = make_admitted_ruleset(make_rule(rule_id="Z", selectors=["src/missing.lock"])).rules[0]
        found = make_admitted_ruleset(make_rule(rule_id="A", selectors=["src/file.lock"])).rules[0]
        rules = load_ruleset({"ruleset_version": "1.0", "rules": [_rule_to_input(missing), _rule_to_input(found)],
                             "ruleset_digest": compute_ruleset_semantic_digest((missing, found))})
        exps = make_admitted_expectations(self.policy_admission, rules.rules,
            expectation_specs=(("Z", ("Z", "A")), ("A", ("A", "Z"))))
        items = evaluate_expectation_set(exps, rules, snapshot)
        self.assertEqual(tuple((i.expectation_id, i.rule_id, i.verdict.value) for i in items), (
            ("A", "A", "EVIDENCE_FOUND"), ("A", "Z", "EVIDENCE_MISSING"),
            ("Z", "A", "EVIDENCE_FOUND"), ("Z", "Z", "EVIDENCE_MISSING")))
        self.assertEqual(items, evaluate_expectation_set(exps, rules, snapshot))
        for item in items:
            self.assertFalse(hasattr(item, "priority"))
            self.assertFalse(hasattr(item, "coverage_verdict"))

    def test_verdict_field_matrix_rejects_illegal_combinations(self) -> None:
        ref = EvidenceRef("src/a.lock", "c" * 64, EvidenceLocator("file_existence", "src/a.lock"))
        cases = (("EVIDENCE_FOUND", (), None, None),
                 ("EVIDENCE_MISSING", (ref,), None, None),
                 ("EVIDENCE_MISSING", (), "[]", None),
                 ("EVIDENCE_DISCREPANCY", (ref,), None, None),
                 ("RULE_NOT_APPLICABLE", (), None, "  "),
                 ("RULE_NOT_APPLICABLE", (), None, 1),
                 ("RULE_NOT_APPLICABLE", (ref,), None, "reason"))
        for verdict, refs, discrepancy, reason in cases:
            with self.subTest(verdict=verdict, reason=reason), self.assertRaises(ValueError):
                ImplementationVerificationItem("E", "a" * 64, "PW.4.4", "R", "b" * 64,
                    ImplementationEvidenceVerdict(verdict), refs, discrepancy, reason)

    def test_file_lookup_uses_one_admitted_index_not_repeated_linear_scans(self) -> None:
        files = {f"src/{i:02d}.lock": f"locked {i}\n" for i in range(48)}
        snapshot = self._snapshot(files)
        exps, rules = self._admitted(make_rule())
        with patch.object(type(snapshot), "get_file", side_effect=snapshot.get_file) as lookup:
            item = evaluate_expectation_set(exps, rules, snapshot)[0]
        self.assertEqual(item.verdict.value, "EVIDENCE_FOUND")
        self.assertEqual(tuple(ref.repo_path for ref in item.evidence_refs),
                         tuple(f"src/{i:02d}.lock" for i in range(48)))
        self.assertEqual(tuple(ref.content_digest for ref in item.evidence_refs),
                         tuple(file.content_hash for file in snapshot.files))
        self.assertEqual(lookup.call_count, 0, "Repeated linear scans reintroduce quadratic candidate lookup")


if __name__ == "__main__":
    unittest.main()
