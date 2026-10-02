#!/usr/bin/env python3
"""Deterministic typed matchers for materialized S2 implementation evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode


class InvalidRuleError(ValueError):
    """Raised when a matcher assertion or structured path is invalid."""


class InvalidEvidenceInputError(ValueError):
    """Raised when evidence content is not valid under the matcher contract."""


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


class DiscrepancyCode(str, Enum):
    NO_NODE_MATCH = "NO_NODE_MATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    UNCOMPARABLE_NODE = "UNCOMPARABLE_NODE"


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
class MatcherResult:
    passed: bool
    resolved_node_paths: tuple[str, ...]
    discrepancy_code: DiscrepancyCode | None

    def __post_init__(self) -> None:
        if type(self.passed) is not bool or type(self.resolved_node_paths) is not tuple:
            raise ValueError("Matcher result requires boolean and immutable tuple fields.")
        for path in self.resolved_node_paths:
            if not isinstance(path, str):
                raise ValueError("Resolved node paths must be JSON Pointer strings.")
            _parse_json_pointer(path)
        if self.discrepancy_code is not None and not isinstance(
            self.discrepancy_code, DiscrepancyCode
        ):
            raise ValueError("Matcher discrepancy code must be a closed enum value.")
        if self.passed and self.discrepancy_code is not None:
            raise ValueError("A passing matcher result cannot have a discrepancy code.")
        if not self.passed and self.discrepancy_code is None:
            raise ValueError("A failing matcher result requires a discrepancy code.")
        if len(set(self.resolved_node_paths)) != len(self.resolved_node_paths):
            raise ValueError("Resolved node paths must be unique in traversal order.")
        if self.discrepancy_code is DiscrepancyCode.NO_NODE_MATCH:
            if self.resolved_node_paths:
                raise ValueError("NO_NODE_MATCH cannot contain resolved node paths.")
        elif not self.passed and not self.resolved_node_paths:
            raise ValueError("A node mismatch must identify evaluated node paths.")


@dataclass(frozen=True)
class _PathStep:
    kind: str
    value: str


@dataclass(frozen=True)
class _YamlTimestamp:
    source: str


class _UniqueKeyYaml12CoreLoader(yaml.SafeLoader):
    yaml_implicit_resolvers: dict[Any, Any] = {}


# YAML 1.2 Core resolution, https://yaml.org/spec/1.2.2/#1032-tag-resolution.
_CORE_INTEGER = re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$")
_CORE_FLOAT = re.compile(
    r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
    r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
)
_CORE_BOOLEAN = re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$")
_CORE_NULL = re.compile(r"^(?:~|null|Null|NULL)?$")

_UniqueKeyYaml12CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:null", _CORE_NULL, ["~", "n", "N", ""]
)
_UniqueKeyYaml12CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    _CORE_BOOLEAN,
    ["t", "T", "f", "F"],
)
_UniqueKeyYaml12CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int",
    _CORE_INTEGER,
    list("-+0123456789"),
)
_UniqueKeyYaml12CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    _CORE_FLOAT,
    list("-+0123456789."),
)
# Frozen S2-A reserves timestamp nodes as uncomparable, an application rule
# beyond Core scalar resolution. Quoted date strings still remain strings.
for _first_character, _resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items():
    _timestamp_patterns = [
        pattern
        for tag, pattern in _resolvers
        if tag == "tag:yaml.org,2002:timestamp"
    ]
    for _timestamp_pattern in _timestamp_patterns:
        _UniqueKeyYaml12CoreLoader.add_implicit_resolver(
            "tag:yaml.org,2002:timestamp",
            _timestamp_pattern,
            [_first_character],
        )


def _construct_yaml_timestamp(
    loader: _UniqueKeyYaml12CoreLoader, node: yaml.ScalarNode
) -> _YamlTimestamp:
    return _YamlTimestamp(loader.construct_scalar(node))


_UniqueKeyYaml12CoreLoader.add_constructor(
    "tag:yaml.org,2002:timestamp", _construct_yaml_timestamp
)


def _construct_yaml_12_integer(
    loader: _UniqueKeyYaml12CoreLoader, node: yaml.ScalarNode
) -> int:
    source = loader.construct_scalar(node)
    if not _CORE_INTEGER.fullmatch(source):
        raise InvalidEvidenceInputError("YAML integer is outside Core scalar syntax.")
    if source.startswith("0o"):
        return int(source[2:], 8)
    if source.startswith("0x"):
        return int(source[2:], 16)
    return int(source, 10)


_UniqueKeyYaml12CoreLoader.add_constructor(
    "tag:yaml.org,2002:int", _construct_yaml_12_integer
)


def _construct_yaml_core_boolean(
    loader: _UniqueKeyYaml12CoreLoader, node: yaml.ScalarNode
) -> bool:
    source = loader.construct_scalar(node)
    if not _CORE_BOOLEAN.fullmatch(source):
        raise InvalidEvidenceInputError("YAML boolean is outside Core scalar syntax.")
    return source.lower() == "true"


def _construct_yaml_core_null(
    loader: _UniqueKeyYaml12CoreLoader, node: yaml.ScalarNode
) -> None:
    if not _CORE_NULL.fullmatch(loader.construct_scalar(node)):
        raise InvalidEvidenceInputError("YAML null is outside Core scalar syntax.")
    return None


def _construct_yaml_core_float(
    loader: _UniqueKeyYaml12CoreLoader, node: yaml.ScalarNode
) -> float:
    if not _CORE_FLOAT.fullmatch(loader.construct_scalar(node)):
        raise InvalidEvidenceInputError("YAML float is outside Core scalar syntax.")
    return loader.construct_yaml_float(node)


for _tag, _constructor in (
    ("bool", _construct_yaml_core_boolean),
    ("null", _construct_yaml_core_null),
    ("float", _construct_yaml_core_float),
):
    _UniqueKeyYaml12CoreLoader.add_constructor(f"tag:yaml.org,2002:{_tag}", _constructor)


def _construct_unique_yaml_mapping(
    loader: _UniqueKeyYaml12CoreLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        if key_node.tag == "tag:yaml.org,2002:merge":
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "YAML merge keys are unsupported",
                key_node.start_mark,
            )
        key = loader.construct_object(key_node, deep=deep)
        # Preserve YAML tag equality; Python otherwise merges true with 1.
        # Only literal string keys are navigable through the frozen path DSL.
        if type(key) is not str:
            canonical = ".nan" if type(key) is float and key != key else key
            key = (key_node.tag, canonical)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "mapping keys must be hashable",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "duplicate mapping key",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyYaml12CoreLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_yaml_mapping,
)


def _ensure_acyclic_yaml(value: Any) -> None:
    active: set[int] = set()

    def visit(node: Any) -> None:
        if not isinstance(node, (dict, list, tuple)):
            return
        identity = id(node)
        if identity in active:
            raise InvalidEvidenceInputError("YAML evidence contains a recursive alias.")
        active.add(identity)
        values = node.items() if isinstance(node, dict) else enumerate(node)
        for key, child in values:
            if isinstance(node, dict):
                visit(key)
            visit(child)
        active.remove(identity)

    visit(value)


def _parse_yaml_document(content: str) -> Any:
    loader = None
    try:
        loader = _UniqueKeyYaml12CoreLoader(content)
        value = loader.get_single_data()
        if loader.yaml_version not in (None, (1, 2)):
            raise InvalidEvidenceInputError("Only YAML 1.2 evidence is supported.")
        _ensure_acyclic_yaml(value)
    except (yaml.YAMLError, OverflowError, RecursionError, ValueError) as exc:
        raise InvalidEvidenceInputError("YAML evidence input is invalid.") from exc
    finally:
        if loader is not None:
            loader.dispose()
    return value


def _parse_json_document(content: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise InvalidEvidenceInputError("JSON evidence contains a duplicate key.")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise InvalidEvidenceInputError(
            f"JSON evidence contains a non-RFC numeric constant: {value}."
        )

    try:
        value = json.loads(
            content,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except InvalidEvidenceInputError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise InvalidEvidenceInputError("JSON evidence input is invalid.") from exc

    def reject_unpaired_surrogates(node: Any) -> None:
        if isinstance(node, str):
            if any(0xD800 <= ord(character) <= 0xDFFF for character in node):
                raise InvalidEvidenceInputError(
                    "JSON evidence contains a non-scalar Unicode string."
                )
        elif isinstance(node, list):
            for child in node:
                reject_unpaired_surrogates(child)
        elif isinstance(node, dict):
            for key, child in node.items():
                reject_unpaired_surrogates(key)
                reject_unpaired_surrogates(child)

    reject_unpaired_surrogates(value)
    return value


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


def _escape_pointer_token(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def _append_pointer(parent: str, token: str) -> str:
    return f"{parent}/{_escape_pointer_token(token)}"


def _evaluate_yaml_path(
    root: Any, steps: tuple[_PathStep, ...]
) -> tuple[tuple[Any, str], ...]:
    nodes: tuple[tuple[Any, str], ...] = ((root, ""),)
    for step in steps:
        next_nodes: list[tuple[Any, str]] = []
        for value, pointer in nodes:
            if step.kind == "key" and isinstance(value, dict) and step.value in value:
                next_nodes.append((value[step.value], _append_pointer(pointer, step.value)))
            elif step.kind == "index" and isinstance(value, list):
                if len(step.value) > len(str(len(value))):
                    continue
                index = int(step.value)
                if index < len(value):
                    next_nodes.append((value[index], _append_pointer(pointer, str(index))))
            elif step.kind == "wildcard" and isinstance(value, list):
                next_nodes.extend(
                    (child, _append_pointer(pointer, str(index)))
                    for index, child in enumerate(value)
                )
        nodes = tuple(next_nodes)
        if not nodes:
            break
    return nodes


def _evaluate_json_pointer(root: Any, tokens: tuple[str, ...]) -> tuple[tuple[Any, str], ...]:
    value = root
    pointer = ""
    for token in tokens:
        if isinstance(value, dict):
            if token not in value:
                return ()
            value = value[token]
        elif isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                return ()
            if len(token) > len(str(len(value))):
                return ()
            index = int(token)
            if index >= len(value):
                return ()
            value = value[index]
        else:
            return ()
        pointer = _append_pointer(pointer, token)
    return ((value, pointer),)


def _matches_expected(value: Any, expected: ExpectedScalar) -> bool:
    if expected.kind is ExpectedScalarKind.STRING:
        return type(value) is str and value == expected.value
    if expected.kind is ExpectedScalarKind.BOOLEAN:
        return type(value) is bool and value is expected.value
    if expected.kind is ExpectedScalarKind.INTEGER:
        return type(value) is int and value == expected.value
    return value is None


def _is_comparable_scalar(value: Any) -> bool:
    return type(value) in (str, bool, int) or value is None


def _result_for_nodes(
    nodes: tuple[tuple[Any, str], ...],
    *,
    exists_only: bool,
    expected: ExpectedScalar | None,
) -> MatcherResult:
    if not nodes:
        return MatcherResult(
            passed=False,
            resolved_node_paths=(),
            discrepancy_code=DiscrepancyCode.NO_NODE_MATCH,
        )
    if exists_only:
        return MatcherResult(
            passed=True,
            resolved_node_paths=tuple(pointer for _, pointer in nodes),
            discrepancy_code=None,
        )

    assert expected is not None
    matching_nodes = tuple(
        (value, pointer) for value, pointer in nodes if _matches_expected(value, expected)
    )
    if matching_nodes:
        return MatcherResult(
            passed=True,
            resolved_node_paths=tuple(pointer for _, pointer in matching_nodes),
            discrepancy_code=None,
        )
    comparable_nodes = tuple(value for value, _ in nodes if _is_comparable_scalar(value))
    return MatcherResult(
        passed=False,
        resolved_node_paths=tuple(pointer for _, pointer in nodes),
        discrepancy_code=(
            DiscrepancyCode.VALUE_MISMATCH
            if comparable_nodes
            else DiscrepancyCode.UNCOMPARABLE_NODE
        ),
    )


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


def evaluate_assertion(assertion: EvidenceAssertion, content: str) -> MatcherResult:
    """Evaluate one assertion against one already selected corpus file."""
    if not isinstance(assertion, EvidenceAssertion):
        raise InvalidRuleError("Assertion must be an EvidenceAssertion domain value.")
    if not isinstance(content, str):
        raise InvalidEvidenceInputError("Evidence content must be decoded UTF-8 text.")
    validate_assertion(assertion)

    if assertion.matcher is MatcherKind.FILE_EXISTS:
        return MatcherResult(True, (), None)

    expression = assertion.target_path_expression
    assert expression is not None
    if assertion.matcher in (
        MatcherKind.YAML_PATH_EXISTS,
        MatcherKind.YAML_PATH_EQUALS,
    ):
        steps = _parse_yaml_path(expression)
        document = _parse_yaml_document(content)
        nodes = _evaluate_yaml_path(document, steps)
        return _result_for_nodes(
            nodes,
            exists_only=assertion.matcher is MatcherKind.YAML_PATH_EXISTS,
            expected=assertion.expected_value,
        )

    tokens = _parse_json_pointer(expression)
    document = _parse_json_document(content)
    nodes = _evaluate_json_pointer(document, tokens)
    return _result_for_nodes(
        nodes,
        exists_only=assertion.matcher is MatcherKind.JSON_POINTER_EXISTS,
        expected=assertion.expected_value,
    )


__all__ = [
    "DiscrepancyCode",
    "EvidenceAssertion",
    "ExpectedScalar",
    "ExpectedScalarKind",
    "InvalidEvidenceInputError",
    "InvalidRuleError",
    "MatcherKind",
    "MatcherResult",
    "evaluate_assertion",
    "validate_assertion",
]
