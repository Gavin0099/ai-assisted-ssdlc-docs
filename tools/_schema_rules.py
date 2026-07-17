from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


class SchemaDefinitionError(ValueError):
    """Raised when a validator schema is missing or malformed."""


def load_schema(path: Path, expected_name: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SchemaDefinitionError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise SchemaDefinitionError(f"schema must be a mapping: {path}")
    schema_name = payload.get("schema_name")
    if schema_name != expected_name:
        raise SchemaDefinitionError(
            f"schema_name must be {expected_name!r}, got {schema_name!r}: {path}"
        )
    return payload


def string_list(schema: Mapping[str, Any], key: str) -> list[str]:
    value = schema.get(key)
    if not isinstance(value, list) or not value:
        raise SchemaDefinitionError(f"schema key {key!r} must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise SchemaDefinitionError(f"schema key {key!r} must contain non-empty strings")
    if len(set(value)) != len(value):
        raise SchemaDefinitionError(f"schema key {key!r} must not contain duplicates")
    return list(value)


def require_fields(schema_name: str, fields: list[str], required: set[str]) -> None:
    missing = sorted(required - set(fields))
    if missing:
        raise SchemaDefinitionError(
            f"schema {schema_name!r} is missing validator fields: {', '.join(missing)}"
        )


def compile_condition(
    schema: Mapping[str, Any],
    rule_key: str,
    allowed_values_by_field: Mapping[str, set[str]],
) -> dict[str, set[str]]:
    conditions = schema.get(rule_key)
    if not isinstance(conditions, Mapping) or not conditions:
        raise SchemaDefinitionError(f"schema key {rule_key!r} must be a non-empty mapping")
    compiled: dict[str, set[str]] = {}
    for field, values in conditions.items():
        if not isinstance(field, str):
            raise SchemaDefinitionError(f"schema key {rule_key!r} has a non-string field")
        if field not in allowed_values_by_field:
            raise SchemaDefinitionError(
                f"schema condition {rule_key!r} references unknown field {field!r}"
            )
        if not isinstance(values, list) or not values or any(
            not isinstance(item, str) or not item.strip() for item in values
        ):
            raise SchemaDefinitionError(
                f"schema condition {rule_key!r}.{field} must be a non-empty string list"
            )
        condition_values = set(values)
        unsupported = sorted(condition_values - allowed_values_by_field[field])
        if unsupported:
            raise SchemaDefinitionError(
                f"schema condition {rule_key!r}.{field} contains values outside "
                f"the allowed enum: {', '.join(unsupported)}"
            )
        compiled[field] = condition_values
    return compiled


def condition_matches(
    row: Mapping[str, str], conditions: Mapping[str, set[str]]
) -> bool:
    return any(row.get(field) in values for field, values in conditions.items())
