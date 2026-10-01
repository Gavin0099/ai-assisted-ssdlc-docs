#!/usr/bin/env python3
"""Strict S2 ACL rule and expectation-set admission with canonical digests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

SUPPORTED_SET_VERSION = "1.0"
DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SELECTOR_UNSUPPORTED_CHARS = set("[]{}!~^")
_RULESET_ADMISSION_TOKEN = object()
_RULE_ADMISSION_TOKEN = object()
_POLICY_ADMISSION_TOKEN = object()
_EXPECTATION_SET_ADMISSION_TOKEN = object()
_EXPECTATION_ADMISSION_TOKEN = object()


class InvalidRuleError(ValueError):
    """Raised when a matcher assertion or structured path is invalid."""


class MatcherKind(str, Enum):
    FILE_EXISTS = "FILE_EXISTS"
    YAML_PATH_EXISTS = "YAML_PATH_EXISTS"
    YAML_PATH_EQUALS = "YAML_PATH_EQUALS"
    JSON_POINTER_EXISTS = "JSON_POINTER_EXISTS"
    JSON_POINTER_EQUALS = "JSON_POINTER_EQUALS"


class ExpectedScalarKind(str, Enum):
    STRING = "STRING"
    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    NULL = "NULL"


@dataclass(frozen=True)
class ExpectedScalar:
    kind: ExpectedScalarKind
    value: str | bool | int | None

    def __post_init__(self) -> None:
        expected_types: dict[ExpectedScalarKind, type | None] = {
            ExpectedScalarKind.STRING: str,
            ExpectedScalarKind.BOOLEAN: bool,
            ExpectedScalarKind.INTEGER: int,
            ExpectedScalarKind.NULL: None,
        }
        if not isinstance(self.kind, ExpectedScalarKind):
            raise InvalidRuleError("Expected scalar kind is not supported.")
        expected_type = expected_types[self.kind]
        if expected_type is None:
            if self.value is not None:
                raise InvalidRuleError("NULL expected scalar must have value None.")
        elif type(self.value) is not expected_type:
            raise InvalidRuleError(
                f"{self.kind.value} expected scalar has an incompatible value type."
            )


@dataclass(frozen=True)
class EvidenceAssertion:
    matcher: MatcherKind
    target_path_expression: str | None = None
    expected_value: ExpectedScalar | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.matcher, MatcherKind):
            raise InvalidRuleError("Matcher kind is not supported.")
        if self.matcher is MatcherKind.FILE_EXISTS:
            if self.target_path_expression is not None or self.expected_value is not None:
                raise InvalidRuleError(
                    "FILE_EXISTS does not accept a path expression or expected value."
                )
            return
        if not isinstance(self.target_path_expression, str):
            raise InvalidRuleError("Structured matcher requires a path expression string.")
        if self.matcher in (
            MatcherKind.YAML_PATH_EXISTS,
            MatcherKind.JSON_POINTER_EXISTS,
        ):
            if self.expected_value is not None:
                raise InvalidRuleError(
                    "Path-exists matchers do not accept an expected value."
                )
        elif not isinstance(self.expected_value, ExpectedScalar):
            raise InvalidRuleError(
                "Path-equals matchers require a typed expected scalar."
            )


@dataclass(frozen=True)
class _PathStep:
    kind: str
    value: str


def _parse_yaml_path(expression: str) -> tuple[_PathStep, ...]:
    if expression == "":
        return ()
    steps: list[_PathStep] = []
    index = 0
    expect_key = True
    while index < len(expression):
        if expect_key:
            start = index
            while index < len(expression) and expression[index] not in ".[\\]":
                index += 1
            if index == start:
                raise InvalidRuleError("YAML path contains an empty key token.")
            steps.append(_PathStep("key", expression[start:index]))
            expect_key = False
            continue

        if expression[index] == ".":
            index += 1
            expect_key = True
            continue
        if expression[index] == "[":
            close = expression.find("]", index + 1)
            if close < 0:
                raise InvalidRuleError("YAML path contains an unclosed index token.")
            token = expression[index + 1 : close]
            if token == "*":
                steps.append(_PathStep("wildcard", token))
            elif re.fullmatch(r"0|[1-9][0-9]*", token):
                steps.append(_PathStep("index", token))
            else:
                raise InvalidRuleError("YAML path contains an unsupported index token.")
            index = close + 1
            continue
        raise InvalidRuleError("YAML path does not match S2 YAML Path Subset v1.")

    if expect_key:
        raise InvalidRuleError("YAML path must end with a non-empty key or index.")
    return tuple(steps)


def _parse_json_pointer(expression: str) -> tuple[str, ...]:
    if expression == "":
        return ()
    if not expression.startswith("/"):
        raise InvalidRuleError("JSON Pointer must be empty or start with '/'.")
    tokens = expression[1:].split("/")
    decoded: list[str] = []
    for token in tokens:
        if re.search(r"~(?![01])", token):
            raise InvalidRuleError("JSON Pointer contains an invalid '~' escape.")
        decoded.append(token.replace("~1", "/").replace("~0", "~"))
    return tuple(decoded)


def validate_assertion(assertion: EvidenceAssertion) -> None:
    """Validate assertion shape and path grammar without reading evidence bytes."""
    if not isinstance(assertion, EvidenceAssertion):
        raise InvalidRuleError("Assertion must be an EvidenceAssertion domain value.")
    if assertion.matcher in (
        MatcherKind.YAML_PATH_EXISTS,
        MatcherKind.YAML_PATH_EQUALS,
    ):
        assert assertion.target_path_expression is not None
        _parse_yaml_path(assertion.target_path_expression)
    elif assertion.matcher in (
        MatcherKind.JSON_POINTER_EXISTS,
        MatcherKind.JSON_POINTER_EQUALS,
    ):
        assert assertion.target_path_expression is not None
        _parse_json_pointer(assertion.target_path_expression)



class ContractInputError(ValueError):
    """Raised when an S2 ruleset or expectation set is invalid."""


class CandidateQuantifier(str, Enum):
    ANY = "ANY"
    ALL = "ALL"


class RuleApplicabilityStatus(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class RuleApplicability:
    status: RuleApplicabilityStatus
    reason: str | None = None


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
    _admission_token: object = field(repr=False, compare=False, default=None)


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
    _admission_token: object = field(repr=False, compare=False, default=None)


@dataclass(frozen=True)
class ImplementationEvidenceRuleset:
    ruleset_version: str
    rules: tuple[ImplementationEvidenceRule, ...]
    ruleset_digest: str
    _admission_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._admission_token is not _RULESET_ADMISSION_TOKEN:
            raise ContractInputError("Rulesets must be created by load_ruleset().")


@dataclass(frozen=True)
class PolicyAssessmentIdentity:
    assessment_id: str
    target_source_type: str
    target_repo: str
    target_commit: str
    target_manifest_digest: str
    target_corpus_digest: str


@dataclass(frozen=True)
class PolicyFindingAuthority:
    finding_id: str
    task_id: str
    company_source_ref: str


class PolicyAssessmentAdmission:
    """Unforgeable-in-normal-use result of verified S1 assessment admission."""

    __slots__ = ("_identity", "_findings", "_admission_token")

    def __init__(
        self,
        identity: PolicyAssessmentIdentity,
        findings: tuple[PolicyFindingAuthority, ...],
        *,
        _token: object,
    ) -> None:
        if _token is not _POLICY_ADMISSION_TOKEN:
            raise ContractInputError(
                "Policy admissions must be created by admit_policy_assessment()."
            )
        object.__setattr__(self, "_identity", identity)
        object.__setattr__(self, "_findings", findings)
        object.__setattr__(self, "_admission_token", _token)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("PolicyAssessmentAdmission is immutable.")

    @property
    def identity(self) -> PolicyAssessmentIdentity:
        return self._identity

    @property
    def findings(self) -> tuple[PolicyFindingAuthority, ...]:
        return self._findings


@dataclass(frozen=True)
class PolicyImplementationExpectationSet:
    expectation_set_version: str
    policy_assessment_identity: PolicyAssessmentIdentity
    expectations: tuple[PolicyImplementationExpectation, ...]
    expectation_set_digest: str
    _admission_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._admission_token is not _EXPECTATION_SET_ADMISSION_TOKEN:
            raise ContractInputError(
                "Expectation sets must be created by load_expectation_set()."
            )


def _fail(message: str) -> None:
    raise ContractInputError(message)


def _require_object(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        _fail(f"{label} must be a mapping with string keys.")
    unknown = set(value) - keys
    missing = keys - set(value)
    if unknown:
        _fail(f"{label} contains unknown fields: {', '.join(sorted(unknown))}.")
    if missing:
        _fail(f"{label} is missing required fields: {', '.join(sorted(missing))}.")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty string.")
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
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ContractInputError("Canonical S2 digest payload is invalid.") from exc
    return hashlib.sha256(encoded).hexdigest()


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


def _parse_expected_scalar(value: Any) -> ExpectedScalar:
    data = _require_object(value, "expected_value", {"kind", "value"})
    try:
        kind = ExpectedScalarKind(data["kind"])
        return ExpectedScalar(kind=kind, value=data["value"])
    except (ValueError, InvalidRuleError) as exc:
        raise ContractInputError("expected_value has an unsupported kind or value type.") from exc


def _parse_assertion(value: Any) -> EvidenceAssertion:
    data = _require_object(
        value,
        "assertion",
        {"matcher", "target_path_expression", "expected_value"},
    )
    try:
        matcher = MatcherKind(data["matcher"])
    except (ValueError, TypeError) as exc:
        raise ContractInputError("assertion.matcher is not supported.") from exc
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
    except InvalidRuleError as exc:
        raise ContractInputError(
            "assertion fields or structured path do not match the selected matcher contract."
        ) from exc


def _parse_applicability(value: Any) -> RuleApplicability:
    data = _require_object(value, "applicability", {"status", "reason"})
    try:
        status = RuleApplicabilityStatus(data["status"])
    except (ValueError, TypeError) as exc:
        raise ContractInputError("applicability.status is not supported.") from exc
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
    return _canonical_digest(_rule_semantic_payload(rule))


def compute_expectation_digest(
    expectation: PolicyImplementationExpectation,
) -> str:
    """Compute an expectation's semantic digest; its digest field is excluded."""
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
    return _compute_ruleset_digest(ruleset.ruleset_version, ruleset.rules)


def compute_ruleset_semantic_digest(
    rules: tuple[ImplementationEvidenceRule, ...],
    version: str = SUPPORTED_SET_VERSION,
) -> str:
    """Compute canonical ruleset digest for an explicit tuple of semantic rules."""
    if not isinstance(rules, tuple) or not all(
        isinstance(rule, ImplementationEvidenceRule) for rule in rules
    ):
        raise ContractInputError("rules must be a tuple of ImplementationEvidenceRule values.")
    if version != SUPPORTED_SET_VERSION:
        raise ContractInputError("Unsupported ruleset version.")
    return _compute_ruleset_digest(version, rules)


def _validate_rule_domain(rule: ImplementationEvidenceRule) -> None:
    """Validate all frozen domain invariants of an ImplementationEvidenceRule."""
    if not isinstance(rule, ImplementationEvidenceRule):
        _fail("rule must be an ImplementationEvidenceRule instance.")
    _require_string(rule.rule_id, "rule.rule_id")
    _require_string(rule.task_id, "rule.task_id")
    _require_string(rule.evidence_kind, "rule.evidence_kind")
    if not isinstance(rule.candidate_selectors, tuple) or not rule.candidate_selectors:
        _fail("rule.candidate_selectors must be a non-empty tuple of strings.")
    if len(rule.candidate_selectors) != len(set(rule.candidate_selectors)):
        _fail("rule.candidate_selectors must not contain duplicates.")
    for index, selector in enumerate(rule.candidate_selectors):
        _require_string(selector, f"rule.candidate_selectors[{index}]")
        _validate_selector(selector, f"rule.candidate_selectors[{index}]")
    if not isinstance(rule.candidate_quantifier, CandidateQuantifier):
        _fail("rule.candidate_quantifier is not supported.")
    try:
        validate_assertion(rule.assertion)
    except (InvalidRuleError, ValueError, TypeError) as exc:
        raise ContractInputError(
            "assertion fields or structured path do not match the selected matcher contract."
        ) from exc
    if not isinstance(rule.applicability, RuleApplicability):
        _fail("rule.applicability must be a RuleApplicability instance.")
    if not isinstance(rule.applicability.status, RuleApplicabilityStatus):
        _fail("applicability.status is not supported.")
    if rule.applicability.status is RuleApplicabilityStatus.APPLICABLE:
        if rule.applicability.reason is not None:
            _fail("APPLICABLE rules must have applicability.reason set to null.")
    elif (
        not isinstance(rule.applicability.reason, str)
        or not rule.applicability.reason.strip()
    ):
        _fail("NOT_APPLICABLE rules require a non-empty applicability.reason.")


def _validate_expectation_domain(expectation: PolicyImplementationExpectation) -> None:
    """Validate all frozen domain invariants of a PolicyImplementationExpectation."""
    if not isinstance(expectation, PolicyImplementationExpectation):
        _fail("expectation must be a PolicyImplementationExpectation instance.")
    _require_string(expectation.expectation_id, "expectation.expectation_id")
    _require_string(expectation.task_id, "expectation.task_id")
    _require_string(expectation.policy_assessment_id, "expectation.policy_assessment_id")
    _require_string(expectation.policy_finding_id, "expectation.policy_finding_id")
    _require_string(expectation.policy_source_ref, "expectation.policy_source_ref")
    if (
        not isinstance(expectation.expected_evidence_kinds, tuple)
        or not expectation.expected_evidence_kinds
    ):
        _fail("expectation.expected_evidence_kinds must be a non-empty tuple of strings.")
    for kind in expectation.expected_evidence_kinds:
        _require_string(kind, "expectation.expected_evidence_kinds item")
    if len(expectation.expected_evidence_kinds) != len(set(expectation.expected_evidence_kinds)):
        _fail(f"Expectation '{expectation.expectation_id}' expected_evidence_kinds must be unique.")
    if (
        not isinstance(expectation.verification_rule_ids, tuple)
        or not expectation.verification_rule_ids
    ):
        _fail("expectation.verification_rule_ids must be a non-empty tuple of strings.")
    for r_id in expectation.verification_rule_ids:
        _require_string(r_id, "expectation.verification_rule_ids item")
    if len(expectation.verification_rule_ids) != len(set(expectation.verification_rule_ids)):
        _fail(f"Expectation '{expectation.expectation_id}' verification_rule_ids must be unique.")


def verify_admitted_ruleset(ruleset: Any) -> ImplementationEvidenceRuleset:
    """Revalidate a ruleset aggregate before a downstream consumer uses it."""
    if (
        not isinstance(ruleset, ImplementationEvidenceRuleset)
        or getattr(ruleset, "_admission_token", None) is not _RULESET_ADMISSION_TOKEN
    ):
        _fail("An admitted ImplementationEvidenceRuleset is required.")
    if ruleset.ruleset_version != SUPPORTED_SET_VERSION:
        _fail("Unsupported ruleset version.")
    if not isinstance(ruleset.rules, tuple) or not ruleset.rules:
        _fail("Admitted ruleset contains no rules.")
    if len({rule.rule_id for rule in ruleset.rules}) != len(ruleset.rules):
        _fail("Admitted ruleset contains duplicate rule_id values.")
    for rule in ruleset.rules:
        if getattr(rule, "_admission_token", None) is not _RULE_ADMISSION_TOKEN:
            _fail("Admitted ruleset contains a rule without loader admission.")
        _validate_rule_domain(rule)
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
    if not isinstance(identity, PolicyAssessmentIdentity):
        raise ContractInputError("identity must be a PolicyAssessmentIdentity.")
    if not isinstance(expectations, tuple) or not all(
        isinstance(expectation, PolicyImplementationExpectation)
        for expectation in expectations
    ):
        raise ContractInputError(
            "expectations must be a tuple of PolicyImplementationExpectation values."
        )
    if version != SUPPORTED_SET_VERSION:
        raise ContractInputError("Unsupported expectation-set version.")
    return _compute_expectation_set_digest(version, identity, expectations)


def verify_admitted_expectation_set(
    expectation_set: Any,
) -> PolicyImplementationExpectationSet:
    """Revalidate an expectation-set aggregate before a downstream consumer uses it."""
    if (
        not isinstance(expectation_set, PolicyImplementationExpectationSet)
        or getattr(expectation_set, "_admission_token", None)
        is not _EXPECTATION_SET_ADMISSION_TOKEN
    ):
        _fail("An admitted PolicyImplementationExpectationSet is required.")
    if expectation_set.expectation_set_version != SUPPORTED_SET_VERSION:
        _fail("Unsupported expectation-set version.")
    if not isinstance(expectation_set.expectations, tuple) or not expectation_set.expectations:
        _fail("Admitted expectation set contains no expectations.")
    if len({item.expectation_id for item in expectation_set.expectations}) != len(
        expectation_set.expectations
    ):
        _fail("Admitted expectation set contains duplicate expectation_id values.")
    for expectation in expectation_set.expectations:
        if getattr(expectation, "_admission_token", None) is not _EXPECTATION_ADMISSION_TOKEN:
            _fail("Admitted expectation set contains an expectation without loader admission.")
        _validate_expectation_domain(expectation)
        if compute_expectation_digest(expectation) != expectation.expectation_digest:
            _fail("Admitted expectation changed after digest verification.")
    if compute_expectation_set_digest(expectation_set) != expectation_set.expectation_set_digest:
        _fail("Admitted expectation set changed after digest verification.")
    return expectation_set


def verify_expectation_ruleset_integrity(
    expectation_set: Any,
    ruleset: Any,
) -> tuple[PolicyImplementationExpectationSet, ImplementationEvidenceRuleset]:
    """Revalidate referential and evidence-kind integrity between expectation set and ruleset."""
    valid_exp_set = verify_admitted_expectation_set(expectation_set)
    valid_ruleset = verify_admitted_ruleset(ruleset)

    rules_by_id = {rule.rule_id: rule for rule in valid_ruleset.rules}
    for expectation in valid_exp_set.expectations:
        rule_evidence_kinds = set()
        for rule_id in expectation.verification_rule_ids:
            rule = rules_by_id.get(rule_id)
            if rule is None:
                _fail(
                    f"Expectation '{expectation.expectation_id}' references an unknown rule_id '{rule_id}'."
                )
            if rule.task_id != expectation.task_id:
                _fail(
                    f"Expectation '{expectation.expectation_id}' references rule '{rule_id}' for a different task."
                )
            rule_evidence_kinds.add(rule.evidence_kind)

        expected_kinds_set = set(expectation.expected_evidence_kinds)
        for expected_kind in expectation.expected_evidence_kinds:
            if expected_kind not in rule_evidence_kinds:
                _fail(
                    f"Expectation '{expectation.expectation_id}' expected evidence kind '{expected_kind}' is not covered by any referenced rule."
                )
        for rule_kind in rule_evidence_kinds:
            if rule_kind not in expected_kinds_set:
                _fail(
                    f"Expectation '{expectation.expectation_id}' references rule with undeclared evidence kind '{rule_kind}'."
                )

    return valid_exp_set, valid_ruleset


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
    try:
        quantifier = CandidateQuantifier(data["candidate_quantifier"])
    except (ValueError, TypeError) as exc:
        raise ContractInputError("rule.candidate_quantifier is not supported.") from exc
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
        _admission_token=_RULE_ADMISSION_TOKEN,
    )
    _validate_rule_domain(rule)
    expected_digest = compute_rule_digest(rule)
    if supplied_digest != expected_digest:
        _fail(f"Rule '{rule_id}' digest does not match its semantic fields.")
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
        _admission_token=_EXPECTATION_ADMISSION_TOKEN,
    )
    _validate_expectation_domain(expectation)
    expected_digest = compute_expectation_digest(expectation)
    if supplied_digest != expected_digest:
        _fail(f"Expectation '{expectation_id}' digest does not match its semantic fields.")
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
    return ImplementationEvidenceRuleset(
        ruleset_version=SUPPORTED_SET_VERSION,
        rules=rules,
        ruleset_digest=supplied_digest,
        _admission_token=_RULESET_ADMISSION_TOKEN,
    )


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
    ruleset = verify_admitted_ruleset(ruleset)
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

    finding_links = {
        finding.finding_id: finding for finding in policy_admission.findings
    }
    for expectation in expectations:
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
        if len(expectation.expected_evidence_kinds) != len(
            set(expectation.expected_evidence_kinds)
        ):
            _fail(
                f"Expectation '{expectation.expectation_id}' expected_evidence_kinds must be unique."
            )
    expected_digest = _compute_expectation_set_digest(
        SUPPORTED_SET_VERSION, identity, expectations
    )
    supplied_digest = _require_digest(
        root["expectation_set_digest"], "expectation_set_digest"
    )
    if supplied_digest != expected_digest:
        _fail("expectation_set_digest does not match its semantic contents.")

    candidate_set = PolicyImplementationExpectationSet(
        expectation_set_version=SUPPORTED_SET_VERSION,
        policy_assessment_identity=identity,
        expectations=expectations,
        expectation_set_digest=supplied_digest,
        _admission_token=_EXPECTATION_SET_ADMISSION_TOKEN,
    )
    verify_expectation_ruleset_integrity(candidate_set, ruleset)
    return candidate_set


def admit_policy_assessment(
    assessment_path: Path | str,
    manifest_path: Path | str,
    repo_path: Path | str,
) -> PolicyAssessmentAdmission:
    """Validate an S1 assessment and its pinned corpus before ACL admission."""
    from tools.review_engine import ReviewReportOrchestrator
    from tools.validate_target_manifest import (
        parse_target_manifest,
        validate_target_manifest_file,
    )
    import yaml

    assessment_file = Path(assessment_path)
    manifest_file = Path(manifest_path)
    repository = Path(repo_path)
    try:
        report, provenance_verified = ReviewReportOrchestrator().load_and_verify(
            assessment_path=assessment_file,
            manifest_path=manifest_file,
            repo_path=repository,
            allow_unverified_provenance=False,
        )
        if not provenance_verified:
            _fail("S1 policy assessment provenance is not fully verified.")
        manifest_errors = validate_target_manifest_file(manifest_file)
        if manifest_errors:
            _fail("S1 target manifest failed validation after provenance admission.")
        manifest_data = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))
        manifest = parse_target_manifest(manifest_data)
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
        )
    except ContractInputError:
        raise
    except Exception as exc:
        raise ContractInputError(
            "S1 policy assessment admission failed closed."
        ) from exc


__all__ = [
    "CandidateQuantifier",
    "ContractInputError",
    "EvidenceAssertion",
    "ExpectedScalar",
    "ExpectedScalarKind",
    "ImplementationEvidenceRule",
    "ImplementationEvidenceRuleset",
    "InvalidRuleError",
    "MatcherKind",
    "PolicyAssessmentIdentity",
    "PolicyAssessmentAdmission",
    "PolicyFindingAuthority",
    "PolicyImplementationExpectation",
    "PolicyImplementationExpectationSet",
    "RuleApplicability",
    "RuleApplicabilityStatus",
    "load_expectation_set",
    "load_ruleset",
    "admit_policy_assessment",
    "compute_expectation_digest",
    "compute_expectation_set_semantic_digest",
    "compute_expectation_set_digest",
    "compute_rule_digest",
    "compute_ruleset_semantic_digest",
    "compute_ruleset_digest",
    "validate_assertion",
    "verify_admitted_expectation_set",
    "verify_admitted_ruleset",
    "verify_expectation_ruleset_integrity",
]