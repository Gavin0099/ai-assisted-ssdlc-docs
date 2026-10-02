"""S2-C1: actual dual admission and non-aggregated verification records; no output I/O."""
from __future__ import annotations

import hashlib
import json
from dataclasses import InitVar, dataclass, field
from pathlib import Path

from tools.implementation_contracts import (
    ContractInputError, PolicyAssessmentAdmission, PolicyAssessmentIdentity,
    PolicyImplementationExpectationSet, ImplementationEvidenceRuleset,
    RepositoryIdentityStatus, admit_policy_assessment, load_expectation_set, load_ruleset,
    validate_identity_state, verify_admitted_policy_assessment,
    verify_admitted_expectation_set, verify_admitted_ruleset,
)
from tools.implementation_evaluator import (
    ImplementationVerificationItem, ImplementationEvidenceVerdict, evaluate_expectation_set,
)
from tools.product_corpus_resolver import (
    ProductCorpusResolver, ProductCorpusSnapshot, verify_admitted_product_snapshot,
)
from tools.validate_product_target_manifest import parse_product_target_manifest_file
from tools.repo_corpus_resolver import GitCapabilityError, GitCliClient, glob_to_regex

# Frozen S2-A §7 text, with Markdown emphasis removed for data storage.
CANONICAL_CLAIM_BOUNDARY = (
    "不保證工具執行成效 (No Tool Effectiveness Claim)：配置了 CodeQL 或 Trivy 僅證明具備該憑證，不保證工具在 CI 成功執行，亦不保證代碼零漏洞。",
    "不保證執行環境安全 (No Execution Environment Security Claim)：靜態腳本正確，不保證 GitHub Actions Runner 或 CI Host 未遭竄改。",
    "不保證相依套件安全 (No Component Safety Claim)：存在 `package-lock.json` 不代表所有第三方套件已經過安全審查或無已暴露 CVE。",
    "不保證發佈產物完整性 (No Release Integrity Guarantee)：存在簽章或 checksum 腳本，不保證發佈產物未在傳輸或部署中遭到中間人攻擊。",
    "不保證法規或組織合規 (No Compliance or Conformance Claim)：本驗證僅為靜態憑證之客觀投影，絕不構成 NIST SP 800-218 合規證明。",
)
_RECORD_TOKEN = object()


class VerificationInputError(ValueError):
    """Invalid admission/context/record; never a legitimate negative evidence verdict."""


def _context_values(policy, product, expectations, rules, allow_unverified):
    if type(allow_unverified) is not bool:
        raise VerificationInputError("Provenance opt-in must be boolean.")
    verify_admitted_policy_assessment(policy)
    verify_admitted_product_snapshot(product)
    verify_admitted_ruleset(rules)
    verify_admitted_expectation_set(expectations, ruleset=rules)
    if expectations.policy_assessment_identity != policy.identity or expectations._policy_admission is not policy:
        raise VerificationInputError("Record policy context differs from expectation admission.")
    for status, reasons in ((policy.policy_repository_identity_status, policy.policy_unverified_reason_codes),
                            (product.product_repository_identity_status, product.product_unverified_reason_codes)):
        validate_identity_state(status, reasons)
        if status is RepositoryIdentityStatus.UNVERIFIED and not allow_unverified:
            raise VerificationInputError("Unverified repository identity requires explicit opt-in.")
    return dict(
        policy_assessment_identity=policy.identity,
        policy_snapshot_integrity_verified=policy.policy_snapshot_integrity_verified,
        policy_repository_identity_status=policy.policy_repository_identity_status,
        policy_unverified_reason_codes=policy.policy_unverified_reason_codes,
        product_target_source_type=product.manifest.target.source_type,
        product_target_repo=product.manifest.target.repo,
        product_target_commit=product.target_commit,
        product_manifest_digest=product.manifest_digest,
        product_corpus_digest=product.corpus_digest,
        product_snapshot_integrity_verified=product.product_snapshot_integrity_verified,
        product_repository_identity_status=product.product_repository_identity_status,
        product_unverified_reason_codes=product.product_unverified_reason_codes,
        expectation_set_digest=expectations.expectation_set_digest,
        ruleset_digest=rules.ruleset_digest,
    )


@dataclass(frozen=True)
class ImplementationVerificationRecord:
    verification_id: str
    policy: InitVar[PolicyAssessmentAdmission]
    product: InitVar[ProductCorpusSnapshot]
    expectations: InitVar[PolicyImplementationExpectationSet]
    rules: InitVar[ImplementationEvidenceRuleset]
    verified_items: tuple[ImplementationVerificationItem, ...]
    claim_boundary: tuple[str, ...]
    allow_unverified_provenance: InitVar[bool] = False
    policy_assessment_identity: PolicyAssessmentIdentity = field(init=False)
    policy_snapshot_integrity_verified: bool = field(init=False)
    policy_repository_identity_status: RepositoryIdentityStatus = field(init=False)
    policy_unverified_reason_codes: tuple[str, ...] = field(init=False)
    product_target_source_type: str = field(init=False)
    product_target_repo: str = field(init=False)
    product_target_commit: str = field(init=False)
    product_manifest_digest: str = field(init=False)
    product_corpus_digest: str = field(init=False)
    product_snapshot_integrity_verified: bool = field(init=False)
    product_repository_identity_status: RepositoryIdentityStatus = field(init=False)
    product_unverified_reason_codes: tuple[str, ...] = field(init=False)
    expectation_set_digest: str = field(init=False)
    ruleset_digest: str = field(init=False)
    _context: tuple = field(init=False, repr=False, compare=False)
    _token: object = field(init=False, repr=False, compare=False)
    _seal: str = field(init=False, repr=False, compare=False)

    def __post_init__(self, policy, product, expectations, rules, allow_unverified_provenance):
        try:
            context = (policy, product, expectations, rules, allow_unverified_provenance)
            values = _context_values(*context)
            for key, value in values.items():
                object.__setattr__(self, key, value)
            object.__setattr__(self, "_context", context)
            _validate_record(self)
            # Public construction accepts items only after mechanical verification.
            # Shape/ref metadata alone cannot establish verdicts or concrete nodes.
            if self.verified_items != evaluate_expectation_set(expectations, rules, product):
                raise VerificationInputError("Record items differ from actual mechanical evaluation.")
            object.__setattr__(self, "_seal", _record_seal(self))
            object.__setattr__(self, "_token", _RECORD_TOKEN)
        except Exception:
            raise VerificationInputError("Verification record failed domain validation.") from None

    @property
    def policy_provenance_verified(self):
        return self.policy_snapshot_integrity_verified and self.policy_repository_identity_status is RepositoryIdentityStatus.VERIFIED

    @property
    def product_provenance_verified(self):
        return self.product_snapshot_integrity_verified and self.product_repository_identity_status is RepositoryIdentityStatus.VERIFIED

    @property
    def provenance_verified(self):
        return self.policy_provenance_verified and self.product_provenance_verified


def _validate_record(record):
    if type(record.verification_id) is not str or not record.verification_id:
        raise VerificationInputError("Verification ID must be a non-empty Unicode string.")
    record.verification_id.encode("utf-8", errors="strict")
    if (type(record.claim_boundary) is not tuple or len(record.claim_boundary) != 5
            or any(type(c) is not str for c in record.claim_boundary)
            or set(record.claim_boundary) != set(CANONICAL_CLAIM_BOUNDARY)):
        raise VerificationInputError("All five exact frozen claim boundaries are required.")
    if (type(record.verified_items) is not tuple
            or any(type(item) is not ImplementationVerificationItem for item in record.verified_items)):
        raise VerificationInputError("Record items must be an immutable domain tuple.")
    policy, product, expectations, rules, _ = record._context
    values = _context_values(*record._context)
    for key, value in values.items():
        actual = getattr(record, key)
        if type(actual) is not type(value) or actual != value:
            raise VerificationInputError("Record provenance differs from actual admissions.")
    rules_by_id = {r.rule_id: r for r in rules.rules}
    expected_edges = {(e.expectation_id, rid): (e, rules_by_id[rid])
                      for e in expectations.expectations for rid in e.verification_rule_ids
                      }
    keys = tuple((item.task_id, item.expectation_id, item.rule_id) for item in record.verified_items)
    edges = tuple((item.expectation_id, item.rule_id) for item in record.verified_items)
    if (keys != tuple(sorted(keys)) or len(edges) != len(expected_edges)
            or len(set(edges)) != len(edges) or set(edges) != set(expected_edges)):
        raise VerificationInputError("Record must contain every admitted edge exactly once in canonical order.")
    files = {f.relative_path: f for f in product.files}
    for item in record.verified_items:
        item.__post_init__()
        expectation, rule = expected_edges[(item.expectation_id, item.rule_id)]
        if (item.task_id != expectation.task_id or item.task_id != rule.task_id
                or item.expectation_digest != expectation.expectation_digest or item.rule_digest != rule.rule_digest):
            raise VerificationInputError("Record edge task/digests differ from admitted payloads.")
        is_na = rule.applicability.status.value == "NOT_APPLICABLE"
        if is_na != (item.verdict is ImplementationEvidenceVerdict.RULE_NOT_APPLICABLE):
            raise VerificationInputError("Record applicability differs from its rule.")
        if is_na and item.applicability_reason != rule.applicability.reason:
            raise VerificationInputError("Record applicability reason differs from its rule.")
        matcher = rule.assertion.matcher.value
        expected_kind = "file_existence" if matcher == "FILE_EXISTS" else "yaml_path" if matcher.startswith("YAML") else "json_pointer"
        selectors = tuple(glob_to_regex(s) for s in rule.candidate_selectors)
        for ref in item.evidence_refs:
            f = files.get(ref.repo_path)
            value = ref.repo_path if expected_kind == "file_existence" else rule.assertion.target_path_expression
            if (f is None or f.content_hash != ref.content_digest
                    or not any(s.fullmatch(ref.repo_path) for s in selectors)
                    or ref.locator.kind != expected_kind or ref.locator.value != value):
                raise VerificationInputError("Record ref differs from admitted file/rule locator.")


def _record_seal(record):
    # Source content and expected/observed values deliberately never enter a record.
    payload = {name: getattr(record, name) for name in (
        "verification_id", "product_target_source_type", "product_target_repo", "product_target_commit",
        "product_manifest_digest", "product_corpus_digest", "expectation_set_digest", "ruleset_digest")}
    payload["policy_identity"] = vars(record.policy_assessment_identity)
    payload["claims"] = record.claim_boundary
    payload["states"] = [record.policy_snapshot_integrity_verified, record.product_snapshot_integrity_verified,
        record.policy_repository_identity_status.value, record.product_repository_identity_status.value,
        record.policy_unverified_reason_codes, record.product_unverified_reason_codes]
    payload["items"] = [dict(
        expectation_id=i.expectation_id, expectation_digest=i.expectation_digest, task_id=i.task_id,
        rule_id=i.rule_id, rule_digest=i.rule_digest, verdict=i.verdict.value,
        discrepancy_details=i.discrepancy_details, applicability_reason=i.applicability_reason, explanation=i.explanation,
        evidence_refs=[dict(repo_path=r.repo_path, content_digest=r.content_digest,
            kind=r.locator.kind, value=r.locator.value, nodes=r.resolved_node_paths, snippet=r.matched_snippet)
            for r in i.evidence_refs]) for i in record.verified_items]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def verify_verification_record(record):
    if type(record) is not ImplementationVerificationRecord or getattr(record, "_token", None) is not _RECORD_TOKEN:
        raise VerificationInputError("An admitted verification record is required.")
    try:
        _validate_record(record)
        if _record_seal(record) != record._seal:
            raise VerificationInputError("Record differs from its admitted fingerprint.")
    except Exception:
        raise VerificationInputError("Verification record failed integrity revalidation.") from None
    return record


class ImplementationVerificationOrchestrator:
    def verify(self, *, verification_id: str, assessment_path: Path | str,
               policy_manifest_path: Path | str, policy_repo_path: Path | str,
               product_manifest_path: Path | str, product_repo_path: Path | str,
               ruleset_data: dict, expectation_set_data: dict,
               allow_unverified_provenance: bool = False) -> ImplementationVerificationRecord:
        """Admit both real snapshots, load explicit ACL data, and evaluate every edge."""
        try:
            GitCliClient()  # Keep the actionable prerequisite outside policy's redacted S1 wrapper.
            policy = admit_policy_assessment(assessment_path, policy_manifest_path, policy_repo_path,
                                            allow_unverified_provenance=allow_unverified_provenance)
            manifest = parse_product_target_manifest_file(product_manifest_path)
            product = ProductCorpusResolver().resolve(manifest, product_repo_path,
                                                     allow_unverified_provenance=allow_unverified_provenance)
            rules = load_ruleset(ruleset_data)
            expectations = load_expectation_set(expectation_set_data, policy_admission=policy, ruleset=rules)
            items = evaluate_expectation_set(expectations, rules, product)
            return ImplementationVerificationRecord(verification_id, policy, product, expectations, rules,
                items, CANONICAL_CLAIM_BOUNDARY, allow_unverified_provenance)
        except GitCapabilityError:
            raise VerificationInputError(str(GitCapabilityError())) from None
        except Exception:
            raise VerificationInputError("Static implementation verification failed closed.") from None
