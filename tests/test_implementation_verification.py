from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import traceback
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tests.test_implementation_contracts import (
    make_policy_admission, run_git, ruleset_data, expectation_set_data,
    rehash_rules, rehash_expectations,
)
from tools.implementation_contracts import (
    ContractInputError, RepositoryIdentityStatus, admit_policy_assessment,
    load_ruleset, load_expectation_set, verify_admitted_expectation_set,
)
from tools.product_corpus_resolver import ProductCorpusResolver, verify_admitted_product_snapshot, CorpusResolverError
from tools.validate_product_target_manifest import parse_product_target_manifest
from tools.implementation_evaluator import evaluate_expectation_set
from tools.implementation_verification import (
    CANONICAL_CLAIM_BOUNDARY, ImplementationVerificationRecord, ImplementationVerificationOrchestrator,
    VerificationInputError, verify_verification_record,
)
from tools.implementation_contracts import classify_repository_identity, verify_admitted_policy_assessment


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.policy, self.assessment = make_policy_admission(self.root)
        self.policy_repo = self.root / "policy-repo"
        self.policy_manifest = self.policy_repo / "target-manifest.yaml"
        self.product_repo = self.root / "product-repo"
        self.product_repo.mkdir()
        run_git(self.product_repo, "init", "-b", "main")
        run_git(self.product_repo, "config", "user.name", "Synthetic S2")
        run_git(self.product_repo, "config", "user.email", "synthetic@example.invalid")
        run_git(self.product_repo, "remote", "add", "origin", "https://github.com/example/product.git")
        path = self.product_repo / "src" / "file.lock"
        path.parent.mkdir()
        path.write_bytes(b"locked\n")
        run_git(self.product_repo, "add", "src/file.lock")
        run_git(self.product_repo, "commit", "-m", "synthetic evidence")
        self.manifest = parse_product_target_manifest({
            "manifest_version": "1.0", "target": {"source_type": "github", "repo": "example/product",
                "commit": run_git(self.product_repo, "rev-parse", "HEAD")},
            "authority_surface": {"include": ["src/**"]}, "mode": {"read_only": True}})
        self.product = ProductCorpusResolver().resolve(self.manifest, self.product_repo)
        self.rules = load_ruleset(ruleset_data())
        self.exps = load_expectation_set(expectation_set_data(), policy_admission=self.policy, ruleset=self.rules)
        self.product_manifest = self.product_repo / "product-manifest.json"
        self.product_manifest.write_text(json.dumps(self.manifest._payload()), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_policy_consumer_rechecks_actual_frozen_content(self):
        file = self.policy.snapshot.files[0]
        corrupt = replace(self.policy.snapshot, files=(replace(file, content="synthetic altered bytes\n"),))
        object.__setattr__(self.policy, "_snapshot", corrupt)
        with self.assertRaises(ContractInputError):
            verify_admitted_expectation_set(self.exps, ruleset=self.rules)

    def test_policy_consumer_rechecks_actual_manifest_and_authority(self):
        snapshot = self.policy.snapshot
        manifest = snapshot.manifest
        for changed in (
            replace(manifest, authority_surface=replace(manifest.authority_surface, include=("outside/**",))),
            replace(manifest, authority_surface=replace(manifest.authority_surface, exclude=("policy/**",))),
            replace(manifest, mode=replace(manifest.mode, read_only=False)),
            replace(manifest, baseline=replace(manifest.baseline, version="9.9")),
        ):
            object.__setattr__(self.policy, "_snapshot", replace(snapshot, manifest=changed))
            with self.subTest(changed=changed), self.assertRaises(ContractInputError):
                verify_admitted_expectation_set(self.exps, ruleset=self.rules)
        object.__setattr__(self.policy, "_snapshot", snapshot)

    def test_policy_unreferenced_missing_sentinel_remains_valid_s1_input(self):
        import yaml
        data = yaml.safe_load(self.assessment.read_text(encoding="utf-8"))
        missing = copy.deepcopy(data["results"][0])
        missing.update(finding_id="MISSING-1", task_id="PO.3.1",
                       company_source_ref="<corpus>#unmentioned", coverage_verdict="MISSING")
        missing["basis"][0]["task_id"] = "PO.3.1"
        data["assessment"]["scope_tasks"].append("PO.3.1")
        data["results"].append(missing)
        self.assessment.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        from tools.validate_ssdf_assessment import validate_ssdf_assessment
        self.assertEqual(validate_ssdf_assessment(self.assessment), [])
        record = self.orchestrate()
        self.assertEqual(len(record.verified_items), 1)
        self.assertEqual(record.verified_items[0].task_id, "PW.4.4")
        # The sentinel is assessment metadata, never an implementation-policy source.
        bad = expectation_set_data()
        bad["expectations"][0].update(policy_finding_id="MISSING-1", task_id="PO.3.1",
                                     policy_source_ref="<corpus>#unmentioned")
        rehash_expectations(bad)
        with self.assertRaises(VerificationInputError):
            self.orchestrate(expectation_set_data=bad)

    def record(self, *, policy=None, product=None, exps=None, rules=None, items=None,
               claims=CANONICAL_CLAIM_BOUNDARY, allow=False):
        p = policy or self.policy
        product = product or self.product
        exps = exps or self.exps
        rules = rules or self.rules
        if items is None:
            items = evaluate_expectation_set(exps, rules, product)
        return ImplementationVerificationRecord("SYNTHETIC-1", p, product, exps, rules, items, claims, allow)

    def orchestrate(self, **overrides):
        args = dict(verification_id="SYNTHETIC-1", assessment_path=self.assessment,
                    policy_manifest_path=self.policy_manifest, policy_repo_path=self.policy_repo,
                    product_manifest_path=self.product_manifest, product_repo_path=self.product_repo,
                    ruleset_data=ruleset_data(), expectation_set_data=expectation_set_data())
        return ImplementationVerificationOrchestrator().verify(**{**args, **overrides})

    def test_canonical_claims_are_exact_frozen_section_seven_text(self):
        spec = (Path(__file__).resolve().parents[1] / "docs/specs/s2-a-implementation-evidence-spec.md").read_text(encoding="utf-8")
        section = spec.split("## 7. ", 1)[1].split("## 8. ", 1)[0]
        expected = tuple(re.sub(r"^[1-5]\. ", "", line).replace("**", "")
                         for line in section.splitlines() if re.match(r"^[1-5]\. ", line))
        self.assertEqual(CANONICAL_CLAIM_BOUNDARY, expected)

    def test_dual_provenance_four_status_combinations_and_explicit_opt_in(self):
        for policy_verified, product_verified in ((True, True), (False, True), (True, False), (False, False)):
            with self.subTest(policy=policy_verified, product=product_verified):
                for repo, verified, url in ((self.policy_repo, policy_verified, "https://github.com/example/policy.git"),
                                           (self.product_repo, product_verified, "https://github.com/example/product.git")):
                    remotes = run_git(repo, "remote").splitlines()
                    if "origin" in remotes:
                        run_git(repo, "remote", "remove", "origin")
                    if verified:
                        run_git(repo, "remote", "add", "origin", url)
                if not (policy_verified and product_verified):
                    with self.assertRaises(VerificationInputError):
                        self.orchestrate()
                record = self.orchestrate(allow_unverified_provenance=True)
                self.assertEqual(record.policy_provenance_verified, policy_verified)
                self.assertEqual(record.product_provenance_verified, product_verified)
                self.assertEqual(record.provenance_verified, policy_verified and product_verified)
                self.assertIs(record.policy_snapshot_integrity_verified, True)
                self.assertIs(record.product_snapshot_integrity_verified, True)
                self.assertEqual(record.policy_unverified_reason_codes,
                                 () if policy_verified else ("REPOSITORY_IDENTITY_UNVERIFIED",))
                self.assertEqual(record.product_unverified_reason_codes,
                                 () if product_verified else ("REPOSITORY_IDENTITY_UNVERIFIED",))
                self.assertEqual(record.product_corpus_digest, self.product.corpus_digest)
                verify_verification_record(record)

    def test_default_admissions_do_not_opt_in_missing_origin(self):
        run_git(self.policy_repo, "remote", "remove", "origin")
        run_git(self.product_repo, "remote", "remove", "origin")
        with self.assertRaises(ContractInputError):
            admit_policy_assessment(self.assessment, self.policy_manifest, self.policy_repo)
        with self.assertRaises(CorpusResolverError):
            ProductCorpusResolver().resolve(self.manifest, self.product_repo)

    def test_known_identity_mismatch_cannot_be_opted_in(self):
        for repo, proper in ((self.policy_repo, "policy"), (self.product_repo, "product")):
            for bad in ("https://github.com/example/other.git", f"https://gitlab.com/example/{proper}.git"):
                with self.subTest(repo=repo.name, origin=bad):
                    run_git(repo, "remote", "set-url", "origin", bad)
                    with self.assertRaises(VerificationInputError):
                        self.orchestrate(allow_unverified_provenance=True)
            run_git(repo, "remote", "set-url", "origin", f"https://github.com/example/{proper}.git")

    def test_empty_or_multiple_origin_values_are_fatal_not_uncertain(self):
        run_git(self.product_repo, "config", "remote.origin.url", "")
        with self.assertRaises(VerificationInputError):
            self.orchestrate(allow_unverified_provenance=True)
        run_git(self.product_repo, "config", "remote.origin.url", "https://github.com/example/product.git")
        run_git(self.product_repo, "config", "--add", "remote.origin.url", "https://github.com/example/other.git")
        with self.assertRaises(VerificationInputError):
            self.orchestrate(allow_unverified_provenance=True)

    def test_git_config_errors_are_not_identity_uncertainty(self):
        from tools.repo_corpus_resolver import GitCliClient
        original = GitCliClient._run
        def command(client, args, cwd):
            if args[:2] == ["config", "--get-all"]:
                return subprocess.CompletedProcess(args, 128, "", "SYNTHETIC_PRIVATE_STDERR")
            return original(client, args, cwd)
        with patch.object(GitCliClient, "_run", command):
            with self.assertRaises(VerificationInputError):
                self.orchestrate(allow_unverified_provenance=True)

    def test_identity_transition_during_materialization_is_rejected(self):
        from tools.repo_corpus_resolver import RepoCorpusResolver
        original = RepoCorpusResolver.materialize
        def mutate(resolver, manifest, repo_path):
            result = original(resolver, manifest, repo_path)
            run_git(repo_path, "remote", "remove", "origin")
            return result
        with patch.object(RepoCorpusResolver, "materialize", mutate):
            with self.assertRaises(VerificationInputError):
                self.orchestrate(allow_unverified_provenance=True)

    def test_missing_manifests_and_invalid_digests_never_opt_in(self):
        bad_rules = ruleset_data()
        bad_rules["ruleset_digest"] = "a" * 64
        bad_exps = expectation_set_data()
        bad_exps["expectation_set_digest"] = "a" * 64
        for overrides in ({"policy_manifest_path": self.root / "missing"},
                          {"product_manifest_path": self.root / "missing"},
                          {"ruleset_data": bad_rules}, {"expectation_set_data": bad_exps}):
            with self.subTest(overrides=tuple(overrides)), self.assertRaises(VerificationInputError):
                self.orchestrate(allow_unverified_provenance=True, **overrides)

    def test_bad_pinned_commit_and_child_root_are_fatal(self):
        child = self.product_repo / "src"
        with self.assertRaises(VerificationInputError):
            self.orchestrate(product_repo_path=child, allow_unverified_provenance=True)
        data = self.manifest._payload()
        data["target"]["commit"] = "0" * 40
        self.product_manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(VerificationInputError):
            self.orchestrate(allow_unverified_provenance=True)

    def test_record_exact_edge_and_payload_invariants(self):
        item = evaluate_expectation_set(self.exps, self.rules, self.product)[0]
        cases = ((), (item, item), (replace(item, rule_id="foreign"),),
                 (replace(item, expectation_id="foreign"),), (replace(item, task_id="PS.2.1"),),
                 (replace(item, rule_digest="a" * 64),), (replace(item, expectation_digest="a" * 64),),
                 [item])
        for items in cases:
            with self.subTest(items=repr(items)), self.assertRaises(VerificationInputError):
                self.record(items=items)

    def test_record_rejects_mechanically_false_but_well_formed_items(self):
        from tools.implementation_evaluator import ImplementationEvidenceVerdict
        item = evaluate_expectation_set(self.exps, self.rules, self.product)[0]
        false_missing = replace(item, verdict=ImplementationEvidenceVerdict.EVIDENCE_MISSING,
                                evidence_refs=())
        with self.subTest(case="false_missing"), self.assertRaises(VerificationInputError):
            self.record(items=(false_missing,))
        # Concrete addresses must be evaluator results, not just valid RFC6901 syntax.
        path = self.product_repo / "src/file.lock"
        path.write_bytes(b'{"flag":true}\n')
        run_git(self.product_repo, "add", "src/file.lock")
        run_git(self.product_repo, "commit", "-m", "synthetic structured evidence")
        payload = self.manifest._payload()
        payload["target"]["commit"] = run_git(self.product_repo, "rev-parse", "HEAD")
        product = ProductCorpusResolver().resolve(parse_product_target_manifest(payload), self.product_repo)
        data = ruleset_data()
        data["rules"][0]["assertion"] = {"matcher": "JSON_POINTER_EXISTS",
            "target_path_expression": "/flag", "expected_value": None}
        rehash_rules(data)
        rules = load_ruleset(data)
        exps = load_expectation_set(expectation_set_data(), policy_admission=self.policy, ruleset=rules)
        item = evaluate_expectation_set(exps, rules, product)[0]
        false_found = replace(item, evidence_refs=(replace(item.evidence_refs[0],
                                                          resolved_node_paths=("/invented",)),))
        with self.subTest(case="invented_node"), self.assertRaises(VerificationInputError):
            self.record(product=product, rules=rules, exps=exps, items=(false_found,))

    def test_record_claim_boundary_is_not_renderer_repairable(self):
        for claims in ((), CANONICAL_CLAIM_BOUNDARY[:-1], CANONICAL_CLAIM_BOUNDARY + ("extra",),
                       (CANONICAL_CLAIM_BOUNDARY[0],) * 5, tuple("changed" for _ in range(5)),
                       list(CANONICAL_CLAIM_BOUNDARY)):
            with self.subTest(claims=repr(claims)), self.assertRaises(VerificationInputError):
                self.record(claims=claims)

    def test_record_cannot_accept_serialized_provenance_flags(self):
        with self.assertRaises(TypeError):
            ImplementationVerificationRecord(policy_snapshot_integrity_verified=True)
        with self.assertRaises(VerificationInputError):
            self.record(allow=1)

    def test_record_verifier_rejects_metadata_mutation_without_repair(self):
        for name, value in (("product_snapshot_integrity_verified", False),
                            ("product_repository_identity_status", "VERIFIED"),
                            ("product_target_commit", "a" * 40),
                            ("verified_items", ()), ("claim_boundary", ())):
            record = self.record()
            object.__setattr__(record, name, value)
            with self.subTest(name=name), self.assertRaises(VerificationInputError):
                verify_verification_record(record)
            self.assertEqual(getattr(record, name), value)

    def test_policy_original_seal_rejects_recomputed_identity_content_and_status(self):
        for name, value in (("_assessment_sha256", "a" * 64), ("_manifest_sha256", "a" * 64),
                            ("_identity_status", RepositoryIdentityStatus.UNVERIFIED),
                            ("_reason_codes", ("REPOSITORY_IDENTITY_UNVERIFIED",))):
            policy = admit_policy_assessment(self.assessment, self.policy_manifest, self.policy_repo)
            object.__setattr__(policy, name, value)
            with self.subTest(name=name), self.assertRaises(ContractInputError):
                verify_admitted_policy_assessment(policy)

    def test_unverified_product_cannot_be_promoted_by_metadata_flip(self):
        run_git(self.product_repo, "remote", "remove", "origin")
        product = ProductCorpusResolver().resolve(self.manifest, self.product_repo, allow_unverified_provenance=True)
        object.__setattr__(product, "_identity_status", RepositoryIdentityStatus.VERIFIED)
        object.__setattr__(product, "_reason_codes", ())
        with self.assertRaises(CorpusResolverError):
            verify_admitted_product_snapshot(product)

    def test_record_refs_bind_actual_snapshot_and_rule_locator(self):
        item = evaluate_expectation_set(self.exps, self.rules, self.product)[0]
        ref = item.evidence_refs[0]
        for bad_ref in (replace(ref, content_digest="a" * 64),
                        replace(ref, repo_path="src/other.lock", locator=replace(ref.locator, value="src/other.lock"))):
            with self.subTest(ref=bad_ref.repo_path), self.assertRaises(VerificationInputError):
                self.record(items=(replace(item, evidence_refs=(bad_ref,)),))

    def test_identity_pair_reasons_cannot_be_mutated_to_unknown_codes(self):
        object.__setattr__(self.product, "_reason_codes", ("UNKNOWN",))
        with self.assertRaises(CorpusResolverError):
            verify_admitted_product_snapshot(self.product)

    def test_orchestrator_preserves_only_fixed_git_prerequisite(self):
        from tools.repo_corpus_resolver import GitCapabilityError
        marker = "SYNTHETIC_PRIVATE_STDERR"
        failure = GitCapabilityError()
        failure.args = (marker,)
        with patch("tools.implementation_verification.GitCliClient", side_effect=failure):
            try:
                self.orchestrate()
            except VerificationInputError as exc:
                self.assertIn("Git 2.48+", str(exc))
                self.assertNotIn(marker, traceback.format_exc())
            else:
                self.fail("Unsupported Git must fail before admissions")

    def test_policy_membership_error_is_never_an_identity_opt_in_case(self):
        data = expectation_set_data()
        data["expectations"][0]["policy_source_ref"] = "policy/other.md#locking"
        rehash_expectations(data)
        with self.assertRaises(VerificationInputError):
            self.orchestrate(expectation_set_data=data, allow_unverified_provenance=True)

    def test_unverified_record_still_requires_explicit_record_opt_in(self):
        run_git(self.product_repo, "remote", "remove", "origin")
        product = ProductCorpusResolver().resolve(self.manifest, self.product_repo, allow_unverified_provenance=True)
        with self.assertRaises(VerificationInputError):
            self.record(product=product)
        self.assertFalse(self.record(product=product, allow=True).provenance_verified)
