#!/usr/bin/env python3
"""Deterministic S2 rule evaluation over admitted immutable Product snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum

from tools.implementation_contracts import (
    CandidateQuantifier,
    ImplementationEvidenceRule,
    PolicyImplementationExpectation,
    PolicyImplementationExpectationSet,
    PILOT_TASKS,
    verify_admitted_expectation_set,
    verify_admitted_ruleset,
)
from tools.implementation_matchers import (
    DiscrepancyCode,
    InvalidEvidenceInputError,
    InvalidRuleError,
    MatcherKind,
    _parse_json_pointer,
    _parse_yaml_path,
    evaluate_assertion,
)
from tools.product_corpus_resolver import (
    CorpusResolverError,
    ProductCorpusSnapshot,
    verify_admitted_product_snapshot,
    _relative_path,
)
from tools.repo_corpus_resolver import glob_to_regex

_DISCREPANCY_CODES = {code.value for code in DiscrepancyCode}


class EvaluatorInputError(ValueError):
    """Raised when an evaluator input is invalid or not an admitted artifact."""


class ImplementationEvidenceVerdict(str, Enum):
    EVIDENCE_FOUND = "EVIDENCE_FOUND"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_DISCREPANCY = "EVIDENCE_DISCREPANCY"
    RULE_NOT_APPLICABLE = "RULE_NOT_APPLICABLE"


def _text(value: object, *, nonempty: bool = False) -> None:
    if type(value) is not str or (nonempty and not value):
        raise ValueError("Verification metadata must use Unicode strings.")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError:
        raise ValueError("Verification metadata contains invalid Unicode.") from None


def _sha256(value: object) -> None:
    if (type(value) is not str or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)):
        raise ValueError("Verification digest must be lowercase SHA-256.")


@dataclass(frozen=True)
class EvidenceLocator:
    kind: str
    value: str

    def __post_init__(self) -> None:
        _text(self.kind, nonempty=True)
        _text(self.value)
        try:
            if self.kind == "file_existence":
                _relative_path(self.value)
            elif self.kind == "yaml_path":
                _parse_yaml_path(self.value)
            elif self.kind == "json_pointer":
                _parse_json_pointer(self.value)
            else:
                raise ValueError("Unsupported evidence locator kind.")
        except (CorpusResolverError, InvalidRuleError, UnicodeError):
            raise ValueError("Evidence locator expression is invalid.") from None


@dataclass(frozen=True)
class EvidenceRef:
    repo_path: str
    content_digest: str
    locator: EvidenceLocator
    resolved_node_paths: tuple[str, ...] = ()
    matched_snippet: str | None = None

    def __post_init__(self) -> None:
        try:
            _relative_path(self.repo_path)
        except (CorpusResolverError, UnicodeError):
            raise ValueError("EvidenceRef path must be normalized relative POSIX.") from None
        _sha256(self.content_digest)
        if type(self.locator) is not EvidenceLocator:
            raise ValueError("EvidenceRef requires a strict EvidenceLocator.")
        self.locator.__post_init__()
        if type(self.resolved_node_paths) is not tuple:
            raise ValueError("Node paths must be an immutable tuple.")
        for path in self.resolved_node_paths:
            _text(path)
            try:
                _parse_json_pointer(path)
            except InvalidRuleError:
                raise ValueError("Node paths must be RFC 6901 pointers.") from None
        if len(set(self.resolved_node_paths)) != len(self.resolved_node_paths):
            raise ValueError("Node paths must be unique in traversal order.")
        if self.locator.kind == "file_existence" and (
                self.locator.value != self.repo_path or self.resolved_node_paths):
            raise ValueError("File locator must match its path with no node paths.")
        if self.matched_snippet is not None:
            raise ValueError("Pilot matched_snippet must be null.")


def evidence_ref_sort_key(ref: EvidenceRef) -> tuple:
    return (ref.repo_path, ref.locator.kind, ref.locator.value, ref.resolved_node_paths)


@dataclass(frozen=True)
class ImplementationVerificationItem:
    expectation_id: str
    expectation_digest: str
    task_id: str
    rule_id: str
    rule_digest: str
    verdict: ImplementationEvidenceVerdict
    evidence_refs: tuple[EvidenceRef, ...]
    discrepancy_details: str | None = None
    applicability_reason: str | None = None
    explanation: str = ""

    def __post_init__(self) -> None:
        for value in (self.expectation_id, self.task_id, self.rule_id):
            _text(value, nonempty=True)
        _text(self.explanation)
        if self.task_id not in PILOT_TASKS or type(self.verdict) is not ImplementationEvidenceVerdict:
            raise ValueError("Unsupported item task or verdict.")
        _sha256(self.expectation_digest)
        _sha256(self.rule_digest)
        if (type(self.evidence_refs) is not tuple
                or any(type(ref) is not EvidenceRef for ref in self.evidence_refs)):
            raise ValueError("Item refs must be an immutable domain tuple.")
        for ref in self.evidence_refs:
            ref.__post_init__()
        paths = tuple(ref.repo_path for ref in self.evidence_refs)
        if len(set(paths)) != len(paths):
            raise ValueError("Each candidate must have exactly one ref.")
        if self.evidence_refs != tuple(sorted(self.evidence_refs, key=evidence_ref_sort_key)):
            raise ValueError("Item refs must use canonical order.")
        if self.verdict is ImplementationEvidenceVerdict.EVIDENCE_FOUND:
            if (not self.evidence_refs or self.discrepancy_details is not None
                    or self.applicability_reason is not None):
                raise ValueError("EVIDENCE_FOUND field invariants are violated.")
            if any(ref.locator.kind != "file_existence" and not ref.resolved_node_paths
                   for ref in self.evidence_refs):
                raise ValueError("Structured matches must identify a node.")
        elif self.verdict is ImplementationEvidenceVerdict.EVIDENCE_MISSING:
            if self.evidence_refs or self.discrepancy_details is not None or self.applicability_reason is not None:
                raise ValueError("EVIDENCE_MISSING field invariants are violated.")
        elif self.verdict is ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY:
            if not self.evidence_refs or self.applicability_reason is not None:
                raise ValueError("EVIDENCE_DISCREPANCY field invariants are violated.")
            _validate_sanitized_discrepancy(self.discrepancy_details, self.evidence_refs)
        else:
            if (self.evidence_refs or self.discrepancy_details is not None
                    or type(self.applicability_reason) is not str or not self.applicability_reason.strip()):
                raise ValueError("RULE_NOT_APPLICABLE field invariants are violated.")
            _text(self.applicability_reason, nonempty=True)


def _validate_sanitized_discrepancy(value: object, refs: tuple[EvidenceRef, ...]) -> None:
    _text(value, nonempty=True)
    try:
        payload = json.loads(value)
    except (ValueError, RecursionError):
        raise ValueError("discrepancy_details must be a JSON array.") from None
    if type(payload) is not list or not payload:
        raise ValueError("discrepancy_details must be a non-empty JSON array.")
    if json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) != value:
        raise ValueError("discrepancy_details must use compact sorted-key JSON.")
    if len(payload) != len(refs):
        raise ValueError("Discrepancies must map exactly to failing refs.")
    for entry, ref in zip(payload, refs):
        if (type(entry) is not dict or set(entry) != {"repo_path", "code"}
                or type(entry["repo_path"]) is not str or entry["repo_path"] != ref.repo_path
                or type(entry["code"]) is not str or entry["code"] not in _DISCREPANCY_CODES
                or ref.locator.kind == "file_existence"):
            raise ValueError("Discrepancy code/path must match its structured ref.")
        no_nodes = entry["code"] == DiscrepancyCode.NO_NODE_MATCH.value
        if no_nodes != (not ref.resolved_node_paths):
            raise ValueError("Discrepancy code and node paths disagree.")


def _candidate_paths(
    selectors: tuple[str, ...], snapshot: ProductCorpusSnapshot
) -> tuple[str, ...]:
    try:
        compiled = tuple(glob_to_regex(selector) for selector in selectors)
    except CorpusResolverError as exc:
        raise EvaluatorInputError("An admitted selector cannot be compiled.") from None
    paths = {
        path
        for path in snapshot.paths()
        if any(pattern.fullmatch(path) for pattern in compiled)
    }
    return tuple(sorted(paths))


def _locator_for(rule: ImplementationEvidenceRule, path: str) -> EvidenceLocator:
    matcher = rule.assertion.matcher
    if matcher is MatcherKind.FILE_EXISTS:
        return EvidenceLocator(kind="file_existence", value=path)
    if matcher in (MatcherKind.YAML_PATH_EXISTS, MatcherKind.YAML_PATH_EQUALS):
        return EvidenceLocator(kind="yaml_path", value=rule.assertion.target_path_expression or "")
    return EvidenceLocator(kind="json_pointer", value=rule.assertion.target_path_expression or "")


def _discrepancy_json(
    failures: list[tuple[str, DiscrepancyCode]],
) -> str:
    payload = [
        {"repo_path": path, "code": code.value}
        for path, code in sorted(failures, key=lambda item: item[0])
    ]
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _evaluate_rule(
    expectation: PolicyImplementationExpectation,
    rule: ImplementationEvidenceRule,
    snapshot: ProductCorpusSnapshot,
) -> ImplementationVerificationItem:
    """Internal evaluation; the only public entry validates the complete bound context."""
    if rule.applicability.status.value == "NOT_APPLICABLE":
        return ImplementationVerificationItem(
            expectation_id=expectation.expectation_id,
            expectation_digest=expectation.expectation_digest,
            task_id=expectation.task_id,
            rule_id=rule.rule_id,
            rule_digest=rule.rule_digest,
            verdict=ImplementationEvidenceVerdict.RULE_NOT_APPLICABLE,
            evidence_refs=(),
            applicability_reason=rule.applicability.reason,
        )

    candidate_paths = _candidate_paths(rule.candidate_selectors, snapshot)
    if not candidate_paths:
        return ImplementationVerificationItem(
            expectation_id=expectation.expectation_id,
            expectation_digest=expectation.expectation_digest,
            task_id=expectation.task_id,
            rule_id=rule.rule_id,
            rule_digest=rule.rule_digest,
            verdict=ImplementationEvidenceVerdict.EVIDENCE_MISSING,
            evidence_refs=(),
        )

    matching: list[EvidenceRef] = []
    failing: list[EvidenceRef] = []
    discrepancy_codes: list[tuple[str, DiscrepancyCode]] = []
    for path in candidate_paths:
        corpus_file = snapshot.get_file(path)
        if corpus_file is None:
            raise EvaluatorInputError("Resolved candidate is missing from the admitted snapshot.")
        try:
            result = evaluate_assertion(rule.assertion, corpus_file.content)
        except (InvalidRuleError, InvalidEvidenceInputError) as exc:
            raise EvaluatorInputError("Candidate assertion or evidence input is invalid.") from None
        ref = EvidenceRef(
            repo_path=path,
            content_digest=corpus_file.content_hash,
            locator=_locator_for(rule, path),
            resolved_node_paths=result.resolved_node_paths,
        )
        if result.passed:
            matching.append(ref)
        else:
            failing.append(ref)
            assert result.discrepancy_code is not None
            discrepancy_codes.append((path, result.discrepancy_code))

    if rule.candidate_quantifier is CandidateQuantifier.ANY:
        selected_refs = tuple(matching) if matching else tuple(failing)
        passed = bool(matching)
    else:
        passed = not failing
        selected_refs = tuple(candidate for candidate in matching + failing) if passed else tuple(failing)

    if passed:
        return ImplementationVerificationItem(
            expectation_id=expectation.expectation_id,
            expectation_digest=expectation.expectation_digest,
            task_id=expectation.task_id,
            rule_id=rule.rule_id,
            rule_digest=rule.rule_digest,
            verdict=ImplementationEvidenceVerdict.EVIDENCE_FOUND,
            evidence_refs=tuple(sorted(selected_refs, key=lambda item: item.repo_path)),
        )
    return ImplementationVerificationItem(
        expectation_id=expectation.expectation_id,
        expectation_digest=expectation.expectation_digest,
        task_id=expectation.task_id,
        rule_id=rule.rule_id,
        rule_digest=rule.rule_digest,
        verdict=ImplementationEvidenceVerdict.EVIDENCE_DISCREPANCY,
        evidence_refs=tuple(sorted(selected_refs, key=lambda item: item.repo_path)),
        discrepancy_details=_discrepancy_json(discrepancy_codes),
    )


def evaluate_expectation_set(
    expectation_set: PolicyImplementationExpectationSet,
    ruleset: object,
    snapshot: ProductCorpusSnapshot,
) -> tuple[ImplementationVerificationItem, ...]:
    """Evaluate every explicit expectation/rule link without task-level roll-up."""
    from tools.implementation_contracts import ContractInputError

    try:
        verify_admitted_ruleset(ruleset)
        verify_admitted_expectation_set(expectation_set, ruleset=ruleset)
        verify_admitted_product_snapshot(snapshot)
    except (ContractInputError, CorpusResolverError, AttributeError, TypeError, ValueError):
        raise EvaluatorInputError("Expectation set or ruleset failed integrity verification.") from None

    rules_by_id = {rule.rule_id: rule for rule in ruleset.rules}
    results = [
        _evaluate_rule(
            expectation,
            rules_by_id[rule_id],
            snapshot,
        )
        for expectation in expectation_set.expectations
        for rule_id in expectation.verification_rule_ids
    ]
    return tuple(
        sorted(
            results,
            key=lambda item: (item.task_id, item.expectation_id, item.rule_id),
        )
    )


__all__ = [
    "EvidenceLocator",
    "EvidenceRef",
    "EvaluatorInputError",
    "ImplementationEvidenceVerdict",
    "ImplementationVerificationItem",
    "evaluate_expectation_set",
]