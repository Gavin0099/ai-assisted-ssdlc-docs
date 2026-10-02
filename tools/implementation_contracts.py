#!/usr/bin/env python3
"""Strict S2 ACL rule and expectation-set admission with canonical digests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlsplit

from tools.implementation_matchers import (
    EvidenceAssertion,
    ExpectedScalar,
    ExpectedScalarKind,
    InvalidRuleError,
    MatcherKind,
    validate_assertion,
)

SUPPORTED_SET_VERSION = "1.0"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SELECTOR_UNSUPPORTED_CHARS = set("[]{}!~^")
_RULESET_ADMISSION_TOKEN = object()
_RULE_ADMISSION_TOKEN = object()
_POLICY_ADMISSION_TOKEN = object()
_EXPECTATION_SET_ADMISSION_TOKEN = object()
_EXPECTATION_ADMISSION_TOKEN = object()
PILOT_TASKS = frozenset({"PO.3.1", "PW.4.4", "PS.2.1"})


class ContractInputError(ValueError):
    """Raised when an S2 ruleset or expectation set is invalid."""


class CandidateQuantifier(str, Enum):
    ANY = "ANY"
    ALL = "ALL"


class RuleApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RepositoryIdentityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class RuleApplicability:
    status: RuleApplicabilityStatus
    reason: str | None = None

    def __post_init__(self) -> None:
        if type(self.status) is not RuleApplicabilityStatus:
            _fail("Applicability requires a supported status enum.")
        if self.status is RuleApplicabilityStatus.APPLICABLE:
            if self.reason is not None:
                _fail("APPLICABLE reason must be null.")
        elif type(self.reason) is not str or not self.reason.strip():
            _fail("NOT_APPLICABLE requires a non-empty reason.")


@dataclass(frozen=True)
class ImplementationEvidenceRule:
    rule_id: str
    rule_digest: str
    task_id: str
    evidence_kind: str
    candidate_selectors: tuple[str, ...]
    candidate_quantifier: CandidateQuantifier
    assertion: EvidenceAssertion
    applicability: RuleApplicability
    _admission_token: object = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        _validate_rule_shape(self)


@dataclass(frozen=True)
class PolicyImplementationExpectation:
    expectation_id: str
    expectation_digest: str
    task_id: str
    policy_assessment_id: str
    policy_finding_id: str
    policy_source_ref: str
    expected_evidence_kinds: tuple[str, ...]
    verification_rule_ids: tuple[str, ...]
    _admission_token: object = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        _validate_expectation_shape(self)


@dataclass(frozen=True)
class ImplementationEvidenceRuleset:
    ruleset_version: str
    rules: tuple[ImplementationEvidenceRule, ...]
    ruleset_digest: str
    _admission_token: object = field(init=False, repr=False, compare=False, default=None)
    _admitted_digest: str | None = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        _validate_ruleset_shape(self)


@dataclass(frozen=True)
class PolicyAssessmentIdentity:
    assessment_id: str
    target_source_type: str
    target_repo: str
    target_commit: str
    target_manifest_digest: str
    target_corpus_digest: str

    def __post_init__(self) -> None:
        for label in ("assessment_id", "target_repo"):
            _require_string(getattr(self, label), label)
        if type(self.target_source_type) is not str or self.target_source_type not in {"github", "local_git"}:
            _fail("Unsupported policy source type.")
        if type(self.target_commit) is not str or not re.fullmatch(r"[0-9a-f]{40}", self.target_commit):
            _fail("Policy commit must be a full lowercase SHA-1.")
        _require_digest(self.target_manifest_digest, "target_manifest_digest")
        _require_digest(self.target_corpus_digest, "target_corpus_digest")


@dataclass(frozen=True)
class PolicyFindingAuthority:
    finding_id: str
    task_id: str
    company_source_ref: str


class PolicyAssessmentAdmission:
    """Immutable validated authority; the marker is not human-approval proof."""

    __slots__ = ("_identity", "_findings", "_admission_token", "_snapshot",
                 "_assessment_sha256", "_manifest_sha256", "_identity_status", "_reason_codes")

    def __init__(
        self,
        identity: PolicyAssessmentIdentity,
        findings: tuple[PolicyFindingAuthority, ...],
        *,
        _token: object,
        snapshot: Any,
        assessment_sha256: str,
        manifest_sha256: str,
        identity_status: RepositoryIdentityStatus = RepositoryIdentityStatus.VERIFIED,
        reason_codes: tuple[str, ...] = (),
    ) -> None:
        if _token is not _POLICY_ADMISSION_TOKEN:
            raise ContractInputError(
                "Policy admissions must be created by admit_policy_assessment()."
            )
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_findings", findings)
        object.__setattr__(self, "_admission_token", _token)
        object.__setattr__(self, "_snapshot", snapshot)
        object.__setattr__(self, "_assessment_sha256", assessment_sha256)
        object.__setattr__(self, "_manifest_sha256", manifest_sha256)
        object.__setattr__(self, "_identity_status", identity_status)
        object.__setattr__(self, "_reason_codes", reason_codes)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("PolicyAssessmentAdmission is immutable.")

    @property
    def identity(self) -> PolicyAssessmentIdentity:
        return self._identity

    @property
    def findings(self) -> tuple[PolicyFindingAuthority, ...]:
        return self._findings

    @property
    def snapshot(self) -> Any:
        return self._snapshot

    @property
    def assessment_sha256(self) -> str:
        return self._assessment_sha256

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    @property
    def policy_snapshot_integrity_verified(self) -> bool:
        return True

    @property
    def policy_repository_identity_status(self) -> RepositoryIdentityStatus:
        return self._identity_status

    @property
    def policy_unverified_reason_codes(self) -> tuple[str, ...]:
        return self._reason_codes


@dataclass(frozen=True)
class PolicyImplementationExpectationSet:
    expectation_set_version: str
    policy_assessment_identity: PolicyAssessmentIdentity
    expectations: tuple[PolicyImplementationExpectation, ...]
    expectation_set_digest: str
    _admission_token: object = field(init=False, repr=False, compare=False, default=None)
    _admitted_digest: str | None = field(init=False, repr=False, compare=False, default=None)
    _policy_admission: PolicyAssessmentAdmission | None = field(init=False, repr=False, compare=False, default=None)
    _ruleset: ImplementationEvidenceRuleset | None = field(init=False, repr=False, compare=False, default=None)

    def __post_init__(self) -> None:
        _validate_expectation_set_shape(self)


def _fail(message: str) -> None:
    raise ContractInputError(message)


def _require_object(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail(f"{label} must be a mapping with string keys.")
    unknown = set(value) - keys
    missing = keys - set(value)
    if unknown:
        _fail(f"{label} contains unknown fields.")
    if missing:
        _fail(f"{label} is missing required fields: {', '.join(sorted(missing))}.")
    return value


def _require_string(value: Any, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a non-empty string.")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        _fail(f"{label} must contain valid Unicode scalars.")
    return value


def _require_nonempty_string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        _fail(f"{label} must be a non-empty list of strings.")
    if any(not isinstance(item, str) or not item for item in value):
        _fail(f"{label} must contain only non-empty strings.")
    if len(set(value)) != len(value):
        _fail(f"{label} must not contain duplicates.")
    return tuple(value)


def _require_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not DIGEST_PATTERN.fullmatch(value):
        _fail(f"{label} must be 64 lowercase hexadecimal characters.")
    return value


def _canonical_digest(payload: dict[str, Any]) -> str:
    try:
        encoded = _canonical_json(payload).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise ContractInputError("Canonical S2 digest payload is invalid.") from None
    return hashlib.sha256(encoded).hexdigest()


def _integer_json(value: int) -> str:
    """Decimal JSON without modifying Python's process-wide conversion limit."""
    if value < 0:
        return "-" + _integer_json(-value)
    width = max(1, (value.bit_length() * 30103 // 100000) + 1)
    powers: dict[int, int] = {}

    def digits(number: int, count: int, padded: bool = False) -> str:
        if count <= 18:
            result = str(number)
            return result.zfill(count) if padded else result
        right_width = count // 2
        if right_width not in powers:
            powers[right_width] = 10 ** right_width
        high, low = divmod(number, powers[right_width])
        return digits(high, count - right_width, padded) + digits(low, right_width, True)

    return digits(value, width).lstrip("0") or "0"


def _canonical_json(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return _integer_json(value)
    if type(value) is str:
        return json.dumps(value, ensure_ascii=False)
    if type(value) is list:
        return "[" + ",".join(_canonical_json(item) for item in value) + "]"
    if type(value) is dict and all(type(key) is str for key in value):
        return "{" + ",".join(_canonical_json(key) + ":" + _canonical_json(value[key])
                              for key in sorted(value)) + "}"
    _fail("Canonical JSON only accepts typed domain payloads.")


def _expected_scalar_payload(value: ExpectedScalar | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {"kind": value.kind.value, "value": value.value}


def _assertion_payload(assertion: EvidenceAssertion) -> dict[str, Any]:
    return {
        "matcher": assertion.matcher.value,
        "target_path_expression": assertion.target_path_expression,
        "expected_value": _expected_scalar_payload(assertion.expected_value),
    }


def _validate_selector(selector: str, label: str) -> None:
    _require_string(selector, label)
    if selector != selector.strip():
        _fail(f"{label} must not contain surrounding whitespace.")
    if "\\" in selector:
        _fail(f"{label} must use POSIX '/' separators.")
    if selector.startswith("/") or re.match(r"^[a-zA-Z]:", selector):
        _fail(f"{label} must be a repository-relative path.")
    if ".." in selector.split("/"):
        _fail(f"{label} must not contain a '..' path segment.")
    if any(character in selector for character in SELECTOR_UNSUPPORTED_CHARS):
        _fail(f"{label} uses glob syntax outside Supported Glob Subset v1.")


def _strings_tuple(value: Any, label: str) -> None:
    if type(value) is not tuple or not value:
        _fail(f"{label} must be a non-empty immutable tuple.")
    for item in value:
        _require_string(item, label)
    if len(set(value)) != len(value):
        _fail(f"{label} contains duplicates.")


def _validate_task(task: Any) -> None:
    if type(task) is not str or task not in PILOT_TASKS:
        _fail("Task is outside the frozen S2 Pilot scope.")


def _validate_source_path(source_ref: str) -> None:
    _require_string(source_ref, "policy_source_ref")
    path = source_ref.split("#", 1)[0]
    if not path or path == "<corpus>" or path.startswith("/") or "\\" in path or re.match(r"^[A-Za-z]:", path):
        _fail("Policy source must identify a relative corpus file.")
    if any(part in {"", ".", ".."} for part in path.split("/")):
        _fail("Policy source contains an invalid path segment.")


def _validate_rule_shape(rule: ImplementationEvidenceRule) -> None:
    _require_string(rule.rule_id, "rule_id")
    _require_digest(rule.rule_digest, "rule_digest")
    _validate_task(rule.task_id)
    _require_string(rule.evidence_kind, "evidence_kind")
    _strings_tuple(rule.candidate_selectors, "candidate_selectors")
    for selector in rule.candidate_selectors:
        _validate_selector(selector, "candidate_selectors")
    if type(rule.candidate_quantifier) is not CandidateQuantifier:
        _fail("candidate_quantifier requires a supported enum.")
    if type(rule.assertion) is not EvidenceAssertion or type(rule.applicability) is not RuleApplicability:
        _fail("Rule assertion and applicability must be strict domain objects.")
    try:
        rule.assertion.__post_init__()
        if rule.assertion.expected_value is not None:
            rule.assertion.expected_value.__post_init__()
        validate_assertion(rule.assertion)
        rule.applicability.__post_init__()
    except InvalidRuleError:
        raise ContractInputError("Rule assertion is invalid.") from None


def _validate_expectation_shape(expectation: PolicyImplementationExpectation) -> None:
    for label in ("expectation_id", "policy_assessment_id", "policy_finding_id"):
        _require_string(getattr(expectation, label), label)
    _require_digest(expectation.expectation_digest, "expectation_digest")
    _validate_task(expectation.task_id)
    _validate_source_path(expectation.policy_source_ref)
    _strings_tuple(expectation.expected_evidence_kinds, "expected_evidence_kinds")
    _strings_tuple(expectation.verification_rule_ids, "verification_rule_ids")


def _domain_tuple(value: Any, domain_type: type, label: str) -> None:
    if type(value) is not tuple or not value or any(type(item) is not domain_type for item in value):
        _fail(f"{label} must be a non-empty tuple of domain objects.")


def _validate_ruleset_shape(ruleset: ImplementationEvidenceRuleset) -> None:
    if type(ruleset.ruleset_version) is not str or ruleset.ruleset_version != SUPPORTED_SET_VERSION:
        _fail("Unsupported ruleset version.")
    _require_digest(ruleset.ruleset_digest, "ruleset_digest")
    _domain_tuple(ruleset.rules, ImplementationEvidenceRule, "rules")
    for rule in ruleset.rules:
        _validate_rule_shape(rule)
    if len({rule.rule_id for rule in ruleset.rules}) != len(ruleset.rules):
        _fail("Ruleset contains duplicate rule IDs.")


def _validate_expectation_set_shape(expectation_set: PolicyImplementationExpectationSet) -> None:
    if type(expectation_set.expectation_set_version) is not str or expectation_set.expectation_set_version != SUPPORTED_SET_VERSION:
        _fail("Unsupported expectation-set version.")
    if type(expectation_set.policy_assessment_identity) is not PolicyAssessmentIdentity:
        _fail("A strict policy identity is required.")
    expectation_set.policy_assessment_identity.__post_init__()
    _require_digest(expectation_set.expectation_set_digest, "expectation_set_digest")
    _domain_tuple(expectation_set.expectations, PolicyImplementationExpectation, "expectations")
    for expectation in expectation_set.expectations:
        _validate_expectation_shape(expectation)
    if len({item.expectation_id for item in expectation_set.expectations}) != len(expectation_set.expectations):
        _fail("Expectation set contains duplicate IDs.")


def _parse_expected_scalar(value: Any) -> ExpectedScalar:
    data = _require_object(value, "expected_value", {"kind", "value"})
    try:
        kind = ExpectedScalarKind(data["kind"])
        return ExpectedScalar(kind=kind, value=data["value"])
    except (ValueError, InvalidRuleError):
        raise ContractInputError("expected_value has an unsupported kind or value type.") from None


def _parse_assertion(value: Any) -> EvidenceAssertion:
    data = _require_object(
        value,
        "assertion",
        {"matcher", "target_path_expression", "expected_value"},
    )
    try:
        matcher = MatcherKind(data["matcher"])
    except (ValueError, TypeError):
        raise ContractInputError("assertion.matcher is not supported.") from None
    target_path = data["target_path_expression"]
    if target_path is not None and not isinstance(target_path, str):
        _fail("assertion.target_path_expression must be a string or null.")
    expected_data = data["expected_value"]
    expected = None if expected_data is None else _parse_expected_scalar(expected_data)
    try:
        assertion = EvidenceAssertion(
            matcher=matcher,
            target_path_expression=target_path,
            expected_value=expected,
        )
        validate_assertion(assertion)
        return assertion
    except InvalidRuleError:
        raise ContractInputError(
            "assertion fields or structured path do not match the selected matcher contract."
        ) from None


def _parse_applicability(value: Any) -> RuleApplicability:
    data = _require_object(value, "applicability", {"status", "reason"})
    try:
        status = RuleApplicabilityStatus(data["status"])
    except (ValueError, TypeError):
        raise ContractInputError("applicability.status is not supported.") from None
    reason = data["reason"]
    if status is RuleApplicabilityStatus.APPLICABLE:
        if reason is not None:
            _fail("APPLICABLE rules must have applicability.reason set to null.")
    elif not isinstance(reason, str) or not reason.strip():
        _fail("NOT_APPLICABLE rules require a non-empty applicability.reason.")
    return RuleApplicability(status=status, reason=reason)


def _rule_semantic_payload(rule: ImplementationEvidenceRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "task_id": rule.task_id,
        "evidence_kind": rule.evidence_kind,
        "candidate_selectors": list(rule.candidate_selectors),
        "candidate_quantifier": rule.candidate_quantifier.value,
        "assertion": _assertion_payload(rule.assertion),
        "applicability": {
            "status": rule.applicability.status.value,
            "reason": rule.applicability.reason,
        },
    }


def _expectation_semantic_payload(
    expectation: PolicyImplementationExpectation,
) -> dict[str, Any]:
    return {
        "expectation_id": expectation.expectation_id,
        "task_id": expectation.task_id,
        "policy_assessment_id": expectation.policy_assessment_id,
        "policy_finding_id": expectation.policy_finding_id,
        "policy_source_ref": expectation.policy_source_ref,
        "expected_evidence_kinds": list(expectation.expected_evidence_kinds),
        "verification_rule_ids": sorted(expectation.verification_rule_ids),
    }


def compute_rule_digest(rule: ImplementationEvidenceRule) -> str:
    """Compute a rule's semantic digest; the supplied rule_digest is excluded."""
    _validate_rule_shape(rule)
    return _canonical_digest(_rule_semantic_payload(rule))


def compute_expectation_digest(
    expectation: PolicyImplementationExpectation,
) -> str:
    """Compute an expectation's semantic digest; its digest field is excluded."""
    _validate_expectation_shape(expectation)
    return _canonical_digest(_expectation_semantic_payload(expectation))


def _compute_ruleset_digest(
    version: str, rules: tuple[ImplementationEvidenceRule, ...]
) -> str:
    semantic_rules = [
        _rule_semantic_payload(rule) for rule in sorted(rules, key=lambda item: item.rule_id)
    ]
    return _canonical_digest({"ruleset_version": version, "rules": semantic_rules})


def compute_ruleset_digest(ruleset: ImplementationEvidenceRuleset) -> str:
    """Compute the semantic set digest, excluding child and set digest fields."""
    _validate_ruleset_shape(ruleset)
    return _compute_ruleset_digest(ruleset.ruleset_version, ruleset.rules)


def compute_ruleset_semantic_digest(
    rules: tuple[ImplementationEvidenceRule, ...],
    version: str = SUPPORTED_SET_VERSION,
) -> str:
    """Compute canonical ruleset digest for an explicit tuple of semantic rules."""
    _domain_tuple(rules, ImplementationEvidenceRule, "rules")
    for rule in rules:
        _validate_rule_shape(rule)
    if len({rule.rule_id for rule in rules}) != len(rules):
        _fail("Rules contain duplicate IDs.")
    if type(version) is not str or version != SUPPORTED_SET_VERSION:
        raise ContractInputError("Unsupported ruleset version.")
    return _compute_ruleset_digest(version, rules)


def verify_admitted_ruleset(ruleset: Any) -> ImplementationEvidenceRuleset:
    """Revalidate a ruleset aggregate before a downstream consumer uses it."""
    if (
        not isinstance(ruleset, ImplementationEvidenceRuleset)
        or getattr(ruleset, "_admission_token", None) is not _RULESET_ADMISSION_TOKEN
    ):
        _fail("An admitted ImplementationEvidenceRuleset is required.")
    _validate_ruleset_shape(ruleset)
    if ruleset._admitted_digest != ruleset.ruleset_digest:
        _fail("Ruleset differs from its admitted fingerprint.")
    for rule in ruleset.rules:
        if getattr(rule, "_admission_token", None) is not _RULE_ADMISSION_TOKEN:
            _fail("Admitted ruleset contains a rule without loader admission.")
        if compute_rule_digest(rule) != rule.rule_digest:
            _fail("Admitted rule changed after digest verification.")
    if compute_ruleset_digest(ruleset) != ruleset.ruleset_digest:
        _fail("Admitted ruleset changed after digest verification.")
    return ruleset


def _compute_expectation_set_digest(
    version: str,
    identity: PolicyAssessmentIdentity,
    expectations: tuple[PolicyImplementationExpectation, ...],
) -> str:
    semantic_expectations = [
        _expectation_semantic_payload(expectation)
        for expectation in sorted(expectations, key=lambda item: item.expectation_id)
    ]
    return _canonical_digest(
        {
            "expectation_set_version": version,
            "policy_assessment_identity": _identity_payload(identity),
            "expectations": semantic_expectations,
        }
    )


def compute_expectation_set_digest(
    expectation_set: PolicyImplementationExpectationSet,
) -> str:
    """Compute the semantic expectation-set digest, excluding digest fields."""
    _validate_expectation_set_shape(expectation_set)
    return _compute_expectation_set_digest(
        expectation_set.expectation_set_version,
        expectation_set.policy_assessment_identity,
        expectation_set.expectations,
    )


def compute_expectation_set_semantic_digest(
    identity: PolicyAssessmentIdentity,
    expectations: tuple[PolicyImplementationExpectation, ...],
    version: str = SUPPORTED_SET_VERSION,
) -> str:
    """Compute canonical expectation-set digest from semantic input values."""
    if type(identity) is not PolicyAssessmentIdentity:
        raise ContractInputError("identity must be a PolicyAssessmentIdentity.")
    identity.__post_init__()
    _domain_tuple(expectations, PolicyImplementationExpectation, "expectations")
    for expectation in expectations:
        _validate_expectation_shape(expectation)
    if len({item.expectation_id for item in expectations}) != len(expectations):
        _fail("Expectations contain duplicate IDs.")
    if type(version) is not str or version != SUPPORTED_SET_VERSION:
        raise ContractInputError("Unsupported expectation-set version.")
    return _compute_expectation_set_digest(version, identity, expectations)


def verify_admitted_expectation_set(
    expectation_set: Any,
    *, ruleset: ImplementationEvidenceRuleset | None = None,
) -> PolicyImplementationExpectationSet:
    """Revalidate an expectation-set aggregate before a downstream consumer uses it."""
    if (
        not isinstance(expectation_set, PolicyImplementationExpectationSet)
        or getattr(expectation_set, "_admission_token", None)
        is not _EXPECTATION_SET_ADMISSION_TOKEN
    ):
        _fail("An admitted PolicyImplementationExpectationSet is required.")
    _validate_expectation_set_shape(expectation_set)
    if expectation_set._admitted_digest != expectation_set.expectation_set_digest:
        _fail("Expectation set differs from its admitted fingerprint.")
    bound_rules = verify_admitted_ruleset(expectation_set._ruleset)
    if ruleset is not None and verify_admitted_ruleset(ruleset).ruleset_digest != bound_rules.ruleset_digest:
        _fail("Consumer ruleset differs from expectation admission.")
    _validate_expectation_links(expectation_set, expectation_set._policy_admission, bound_rules)
    for expectation in expectation_set.expectations:
        if getattr(expectation, "_admission_token", None) is not _EXPECTATION_ADMISSION_TOKEN:
            _fail("Admitted expectation set contains an expectation without loader admission.")
        if compute_expectation_digest(expectation) != expectation.expectation_digest:
            _fail("Admitted expectation changed after digest verification.")
    if compute_expectation_set_digest(expectation_set) != expectation_set.expectation_set_digest:
        _fail("Admitted expectation set changed after digest verification.")
    return expectation_set


def _parse_rule(value: Any) -> ImplementationEvidenceRule:
    data = _require_object(
        value,
        "rule",
        {
            "rule_id",
            "rule_digest",
            "task_id",
            "evidence_kind",
            "candidate_selectors",
            "candidate_quantifier",
            "assertion",
            "applicability",
        },
    )
    rule_id = _require_string(data["rule_id"], "rule.rule_id")
    task_id = _require_string(data["task_id"], "rule.task_id")
    evidence_kind = _require_string(data["evidence_kind"], "rule.evidence_kind")
    selectors = _require_nonempty_string_list(
        data["candidate_selectors"], "rule.candidate_selectors"
    )
    for index, selector in enumerate(selectors):
        _validate_selector(selector, f"rule.candidate_selectors[{index}]")
    try:
        quantifier = CandidateQuantifier(data["candidate_quantifier"])
    except (ValueError, TypeError):
        raise ContractInputError("rule.candidate_quantifier is not supported.") from None
    assertion = _parse_assertion(data["assertion"])
    applicability = _parse_applicability(data["applicability"])
    supplied_digest = _require_digest(data["rule_digest"], "rule.rule_digest")
    rule = ImplementationEvidenceRule(
        rule_id=rule_id,
        rule_digest=supplied_digest,
        task_id=task_id,
        evidence_kind=evidence_kind,
        candidate_selectors=selectors,
        candidate_quantifier=quantifier,
        assertion=assertion,
        applicability=applicability,
    )
    expected_digest = compute_rule_digest(rule)
    if supplied_digest != expected_digest:
        _fail(f"Rule '{rule_id}' digest does not match its semantic fields.")
    object.__setattr__(rule, "_admission_token", _RULE_ADMISSION_TOKEN)
    return rule


def _parse_expectation(value: Any) -> PolicyImplementationExpectation:
    data = _require_object(
        value,
        "expectation",
        {
            "expectation_id",
            "expectation_digest",
            "task_id",
            "policy_assessment_id",
            "policy_finding_id",
            "policy_source_ref",
            "expected_evidence_kinds",
            "verification_rule_ids",
        },
    )
    expectation_id = _require_string(data["expectation_id"], "expectation.expectation_id")
    task_id = _require_string(data["task_id"], "expectation.task_id")
    assessment_id = _require_string(
        data["policy_assessment_id"], "expectation.policy_assessment_id"
    )
    finding_id = _require_string(data["policy_finding_id"], "expectation.policy_finding_id")
    source_ref = _require_string(data["policy_source_ref"], "expectation.policy_source_ref")
    evidence_kinds = _require_nonempty_string_list(
        data["expected_evidence_kinds"], "expectation.expected_evidence_kinds"
    )
    rule_ids = _require_nonempty_string_list(
        data["verification_rule_ids"], "expectation.verification_rule_ids"
    )
    supplied_digest = _require_digest(
        data["expectation_digest"], "expectation.expectation_digest"
    )
    expectation = PolicyImplementationExpectation(
        expectation_id=expectation_id,
        expectation_digest=supplied_digest,
        task_id=task_id,
        policy_assessment_id=assessment_id,
        policy_finding_id=finding_id,
        policy_source_ref=source_ref,
        expected_evidence_kinds=evidence_kinds,
        verification_rule_ids=rule_ids,
    )
    expected_digest = compute_expectation_digest(expectation)
    if supplied_digest != expected_digest:
        _fail(f"Expectation '{expectation_id}' digest does not match its semantic fields.")
    object.__setattr__(expectation, "_admission_token", _EXPECTATION_ADMISSION_TOKEN)
    return expectation


def load_ruleset(data: Any) -> ImplementationEvidenceRuleset:
    """Admit a strict v1 ruleset and verify child and aggregate digests."""
    root = _require_object(
        data, "ruleset", {"ruleset_version", "rules", "ruleset_digest"}
    )
    if root["ruleset_version"] != SUPPORTED_SET_VERSION or not isinstance(
        root["ruleset_version"], str
    ):
        _fail("ruleset_version must be the supported string '1.0'.")
    if not isinstance(root["rules"], list) or not root["rules"]:
        _fail("ruleset.rules must be a non-empty list.")
    rules = tuple(_parse_rule(item) for item in root["rules"])
    rule_ids = [rule.rule_id for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        _fail("ruleset contains duplicate rule_id values.")
    expected_digest = _compute_ruleset_digest(SUPPORTED_SET_VERSION, rules)
    supplied_digest = _require_digest(root["ruleset_digest"], "ruleset_digest")
    if supplied_digest != expected_digest:
        _fail("ruleset_digest does not match its semantic rules.")
    admitted = ImplementationEvidenceRuleset(
        ruleset_version=SUPPORTED_SET_VERSION,
        rules=rules,
        ruleset_digest=supplied_digest,
    )
    object.__setattr__(admitted, "_admission_token", _RULESET_ADMISSION_TOKEN)
    object.__setattr__(admitted, "_admitted_digest", supplied_digest)
    return admitted


def _parse_policy_identity(value: Any) -> PolicyAssessmentIdentity:
    data = _require_object(
        value,
        "policy_assessment_identity",
        {
            "assessment_id",
            "target_source_type",
            "target_repo",
            "target_commit",
            "target_manifest_digest",
            "target_corpus_digest",
        },
    )
    source_type = _require_string(
        data["target_source_type"], "policy_assessment_identity.target_source_type"
    )
    if source_type not in {"local_git", "github"}:
        _fail("policy_assessment_identity.target_source_type is not supported.")
    commit = _require_string(
        data["target_commit"], "policy_assessment_identity.target_commit"
    )
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        _fail("policy_assessment_identity.target_commit must be lowercase full SHA-1.")
    return PolicyAssessmentIdentity(
        assessment_id=_require_string(data["assessment_id"], "policy_assessment_identity.assessment_id"),
        target_source_type=source_type,
        target_repo=_require_string(data["target_repo"], "policy_assessment_identity.target_repo"),
        target_commit=commit,
        target_manifest_digest=_require_digest(
            data["target_manifest_digest"],
            "policy_assessment_identity.target_manifest_digest",
        ),
        target_corpus_digest=_require_digest(
            data["target_corpus_digest"],
            "policy_assessment_identity.target_corpus_digest",
        ),
    )


def _identity_payload(identity: PolicyAssessmentIdentity) -> dict[str, str]:
    return {
        "assessment_id": identity.assessment_id,
        "target_source_type": identity.target_source_type,
        "target_repo": identity.target_repo,
        "target_commit": identity.target_commit,
        "target_manifest_digest": identity.target_manifest_digest,
        "target_corpus_digest": identity.target_corpus_digest,
    }


def load_expectation_set(
    data: Any,
    *,
    policy_admission: PolicyAssessmentAdmission,
    ruleset: ImplementationEvidenceRuleset,
) -> PolicyImplementationExpectationSet:
    """Admit an expectation set against verified S1 findings and rule set.

    This verifies S1 structure, target provenance, unique findings, and source
    path membership through ReviewReportOrchestrator. It does not prove policy
    semantic correctness or human approval identity.
    """
    if (
        not isinstance(policy_admission, PolicyAssessmentAdmission)
        or getattr(policy_admission, "_admission_token", None)
        is not _POLICY_ADMISSION_TOKEN
    ):
        _fail("A verified PolicyAssessmentAdmission is required.")
    verify_admitted_ruleset(ruleset)
    root = _require_object(
        data,
        "expectation_set",
        {
            "expectation_set_version",
            "policy_assessment_identity",
            "expectations",
            "expectation_set_digest",
        },
    )
    if root["expectation_set_version"] != SUPPORTED_SET_VERSION or not isinstance(
        root["expectation_set_version"], str
    ):
        _fail("expectation_set_version must be the supported string '1.0'.")
    identity = _parse_policy_identity(root["policy_assessment_identity"])
    if identity != policy_admission.identity:
        _fail("Expectation-set policy identity does not match the admitted assessment identity.")
    expectations_raw = root["expectations"]
    if not isinstance(expectations_raw, list) or not expectations_raw:
        _fail("expectation_set.expectations must be a non-empty list.")
    expectations = tuple(_parse_expectation(item) for item in expectations_raw)
    expectation_ids = [expectation.expectation_id for expectation in expectations]
    if len(expectation_ids) != len(set(expectation_ids)):
        _fail("expectation set contains duplicate expectation_id values.")

    admitted = PolicyImplementationExpectationSet(
        expectation_set_version=SUPPORTED_SET_VERSION,
        policy_assessment_identity=identity,
        expectations=expectations,
        expectation_set_digest=_require_digest(root["expectation_set_digest"], "expectation_set_digest"),
    )
    _validate_expectation_links(admitted, policy_admission, ruleset)
    if compute_expectation_set_digest(admitted) != admitted.expectation_set_digest:
        _fail("expectation_set_digest does not match its semantic contents.")
    object.__setattr__(admitted, "_admission_token", _EXPECTATION_SET_ADMISSION_TOKEN)
    object.__setattr__(admitted, "_admitted_digest", admitted.expectation_set_digest)
    object.__setattr__(admitted, "_policy_admission", policy_admission)
    object.__setattr__(admitted, "_ruleset", ruleset)
    return admitted


def _validate_expectation_links(
    expectation_set: PolicyImplementationExpectationSet,
    policy_admission: PolicyAssessmentAdmission,
    ruleset: ImplementationEvidenceRuleset,
) -> None:
    if not isinstance(policy_admission, PolicyAssessmentAdmission) or getattr(policy_admission, "_admission_token", None) is not _POLICY_ADMISSION_TOKEN:
        _fail("Actual policy admission is required.")
    identity = expectation_set.policy_assessment_identity
    if identity != policy_admission.identity:
        _fail("Expectation identity differs from admitted policy authority.")
    rules_by_id = {rule.rule_id: rule for rule in ruleset.rules}
    finding_links = {
        finding.finding_id: finding for finding in policy_admission.findings
    }
    for expectation in expectation_set.expectations:
        if expectation.policy_assessment_id != identity.assessment_id:
            _fail(
                f"Expectation '{expectation.expectation_id}' assessment_id does not match the set identity."
            )
        finding = finding_links.get(expectation.policy_finding_id)
        if finding is None:
            _fail(
                f"Expectation '{expectation.expectation_id}' references no admitted task finding."
            )
        if (
            finding.task_id != expectation.task_id
            or finding.company_source_ref != expectation.policy_source_ref
        ):
            _fail(
                f"Expectation '{expectation.expectation_id}' task/source reference does not match its admitted finding."
            )
        if expectation.policy_source_ref == "<corpus>#unmentioned":
            _fail(
                f"Expectation '{expectation.expectation_id}' source reference has no policy corpus path."
            )
        _validate_source_path(expectation.policy_source_ref)
        if policy_admission.snapshot.get_file(expectation.policy_source_ref.split("#", 1)[0]) is None:
            _fail("Expectation source is not a policy corpus member.")
        for rule_id in expectation.verification_rule_ids:
            rule = rules_by_id.get(rule_id)
            if rule is None:
                _fail(
                    f"Expectation '{expectation.expectation_id}' references an unknown rule_id."
                )
            if rule.task_id != expectation.task_id:
                _fail(
                    f"Expectation '{expectation.expectation_id}' references a rule for a different task."
                )
        kinds = {rules_by_id[rule_id].evidence_kind for rule_id in expectation.verification_rule_ids}
        if kinds != set(expectation.expected_evidence_kinds):
            _fail("Expected evidence kinds must exactly match the referenced rule kinds.")


def admit_policy_assessment(
    assessment_path: Path | str,
    manifest_path: Path | str,
    repo_path: Path | str,
) -> PolicyAssessmentAdmission:
    """Admit actual S1 validation and materialization, never a provenance flag."""
    from tools.corpus_assessment_engine import parse_corpus_assessment_dict
    from tools.repo_corpus_resolver import GitCapabilityError, GitCliClient, RepoCorpusResolver
    from tools.review_engine import ReviewReportOrchestrator
    from tools.validate_target_manifest import parse_target_manifest

    class CapturingResolver:
        snapshot = None

        def resolve(self, manifest: Any, repo_path: Path) -> Any:
            _verify_repository_identity(manifest.target.source_type, manifest.target.repo, repo_path)
            self.snapshot = RepoCorpusResolver(git_client=git_client).resolve(manifest, repo_path)
            return self.snapshot

    try:
        assessment_file = Path(assessment_path)
        manifest_file = Path(manifest_path)
        repository = Path(repo_path).resolve()
        assessment_bytes = assessment_file.read_bytes()
        manifest_bytes = manifest_file.read_bytes()
        parsed_report = parse_corpus_assessment_dict(_load_policy_yaml(assessment_bytes))
        manifest = parse_target_manifest(_load_policy_yaml(manifest_bytes))
        git_client = GitCliClient()  # Preserve prerequisite errors outside S1's broad wrapper.
        resolver = CapturingResolver()
        # The S1 linter and parser read the same captured assessment bytes.
        # Repeated reads of a concurrently edited source cannot validate a
        # different version and lend its approval to this fingerprint.
        with TemporaryDirectory(prefix="s2-policy-admission-") as temp_root:
            captured_assessment = Path(temp_root) / "assessment.yaml"
            captured_assessment.write_bytes(assessment_bytes)
            report, provenance_verified = ReviewReportOrchestrator(corpus_resolver=resolver).load_and_verify(
                assessment_path=captured_assessment,
                manifest_path=manifest_file,
                repo_path=repository,
                allow_unverified_provenance=False,
            )
        snapshot = resolver.snapshot
        if not provenance_verified or snapshot is None:
            _fail("S1 policy assessment lacks an actual verified snapshot.")
        if (
            report != parsed_report
            or snapshot.manifest != manifest
            or assessment_file.read_bytes() != assessment_bytes
            or manifest_file.read_bytes() != manifest_bytes
            or snapshot.corpus_digest != report.target.corpus_digest
            or snapshot.target_commit != report.target.commit
        ):
            _fail("Policy inputs changed during validation or materialization.")
        _verify_repository_identity(manifest.target.source_type, manifest.target.repo, repository)
        if (
            manifest.target.repo != report.target.repo
            or manifest.target.commit.lower() != report.target.commit
            or manifest.digest != report.target.manifest_digest
        ):
            _fail("S1 target manifest identity changed after provenance admission.")
        identity = PolicyAssessmentIdentity(
            assessment_id=report.id,
            target_source_type=manifest.target.source_type,
            target_repo=report.target.repo,
            target_commit=report.target.commit,
            target_manifest_digest=report.target.manifest_digest,
            target_corpus_digest=report.target.corpus_digest,
        )
        findings = tuple(
            PolicyFindingAuthority(
                finding_id=finding.finding_id,
                task_id=finding.task_id,
                company_source_ref=finding.company_source_ref,
            )
            for finding in report.findings
        )
        if not findings or len({finding.finding_id for finding in findings}) != len(findings):
            _fail("S1 policy assessment has no unique task findings.")
        return PolicyAssessmentAdmission(
            identity,
            findings,
            _token=_POLICY_ADMISSION_TOKEN,
            snapshot=snapshot,
            assessment_sha256=hashlib.sha256(assessment_bytes).hexdigest(),
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        )
    except GitCapabilityError:
        raise ContractInputError(str(GitCapabilityError())) from None
    except ContractInputError:
        raise
    except Exception:
        raise ContractInputError(
            "S1 policy assessment admission failed closed."
        ) from None


def _verify_repository_identity(source_type: str, declared_repo: str, repository: Path) -> None:
    """Known host/path mismatches cannot become identity uncertainty."""
    from tools.repo_corpus_resolver import GitCliClient
    client = GitCliClient()
    top_level = client._run(["rev-parse", "--show-toplevel"], repository)
    if top_level.returncode == 0:
        actual_root = Path(top_level.stdout.strip()).resolve()
    else:
        bare = client._run(["rev-parse", "--is-bare-repository"], repository)
        git_dir = client._run(["rev-parse", "--absolute-git-dir"], repository)
        if bare.returncode != 0 or bare.stdout.strip() != "true" or git_dir.returncode != 0:
            _fail("S2 source root is not an identified Git repository.")
        actual_root = Path(git_dir.stdout.strip()).resolve()
    if actual_root != repository.resolve():
        _fail("S2 source root differs from the actual Git repository root.")
    if source_type == "local_git":
        if Path(declared_repo).resolve() != repository.resolve():
            _fail("Declared local policy repository does not match the materialized root.")
        return
    origin = client.get_remote_url(repository)
    if not origin:
        _fail("Policy repository identity is unverified.")
    if origin.startswith("git@github.com:"):
        host, path = "github.com", origin[len("git@github.com:"):]
    else:
        parsed = urlsplit(origin)
        if parsed.scheme not in {"https", "http", "ssh", "git"} or parsed.query or parsed.fragment:
            _fail("Policy repository origin is not an identified GitHub repository.")
        host, path = parsed.hostname, parsed.path.lstrip("/")
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if host != "github.com" or path.casefold() != declared_repo.casefold():
        _fail("Policy repository has a known identity mismatch.")


def _load_policy_yaml(content: bytes) -> Any:
    """S1 SafeLoader semantics with unambiguous string-keyed policy mappings."""
    import yaml

    class UniquePolicyLoader(yaml.SafeLoader):
        def construct_mapping(self, node: Any, deep: bool = False) -> dict:
            self.flatten_mapping(node)
            keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
            if any(type(key) is not str for key in keys) or len(set(keys)) != len(keys):
                _fail("Policy YAML mapping keys must be unique strings.")
            return super().construct_mapping(node, deep=deep)

    value = yaml.load(content.decode("utf-8", errors="strict"), Loader=UniquePolicyLoader)
    active: set[int] = set()
    completed: set[int] = set()

    def visit(item: Any) -> None:
        if not isinstance(item, (dict, list)):
            return
        identity = id(item)
        if identity in active:
            _fail("Policy YAML must not contain cyclic aliases.")
        if identity in completed:
            return
        active.add(identity)
        for child in item.values() if isinstance(item, dict) else item:
            visit(child)
        active.remove(identity)
        completed.add(identity)

    visit(value)
    return value


__all__ = [
    "CandidateQuantifier",
    "ContractInputError",
    "ImplementationEvidenceRule",
    "ImplementationEvidenceRuleset",
    "PolicyAssessmentIdentity",
    "PolicyAssessmentAdmission",
    "PolicyFindingAuthority",
    "PolicyImplementationExpectation",
    "PolicyImplementationExpectationSet",
    "RuleApplicability",
    "RuleApplicabilityStatus",
    "RepositoryIdentityStatus",
    "load_expectation_set",
    "load_ruleset",
    "admit_policy_assessment",
    "compute_expectation_digest",
    "compute_expectation_set_semantic_digest",
    "compute_expectation_set_digest",
    "compute_rule_digest",
    "compute_ruleset_semantic_digest",
    "compute_ruleset_digest",
    "verify_admitted_expectation_set",
    "verify_admitted_ruleset",
]
