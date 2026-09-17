#!/usr/bin/env python3
"""Deterministic Target Manifest Validator for SSDLC Real Repo Assessments (Phase S1-A-r2).

Enforces target manifest correctness strictly via schemas/target-manifest.schema.yaml
as the executable single source of truth. Zero silent fallbacks:
- Schema itself is validated for complete rule definitions (fails closed if rules missing)
- target.source_type (local_git | github) syntax-bound to repo format
- commit SHA strictly 40-character hexadecimal freeze
- baseline.version strictly quoted string (rejects float/numeric 1.1)
- authority_surface glob boundary rules driven directly by schema flags
- mode.read_only enforced strictly
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "schemas" / "target-manifest.schema.yaml"
)


class TargetManifestValidationError(ValueError):
    """Raised when target manifest validation or its driving schema fails closed."""


@dataclass(frozen=True)
class TargetSpec:
    source_type: str
    repo: str
    commit: str


@dataclass(frozen=True)
class AuthoritySurfaceSpec:
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class BaselineSpec:
    framework: str
    version: str


@dataclass(frozen=True)
class ModeSpec:
    read_only: bool


@dataclass(frozen=True)
class TargetManifest:
    target: TargetSpec
    authority_surface: AuthoritySurfaceSpec
    baseline: BaselineSpec
    mode: ModeSpec


def load_manifest_schema(schema_path: Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    """Load and strictly validate the manifest schema definition itself.

    Fails closed with TargetManifestValidationError if any required rule definition
    is missing or malformed, preventing silent Python fallback behavior.
    """
    if not schema_path.is_file():
        raise TargetManifestValidationError(f"Schema file not found: {schema_path}")

    try:
        data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TargetManifestValidationError(f"Failed to parse schema YAML {schema_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise TargetManifestValidationError(f"Schema root must be a mapping in {schema_path}")

    if data.get("schema_name") != "target-manifest":
        raise TargetManifestValidationError(
            f"Invalid schema_name: expected 'target-manifest' in {schema_path}"
        )

    # 1. Verify required top-level sections definition
    required_sections = data.get("required_sections")
    if not isinstance(required_sections, list) or not required_sections:
        raise TargetManifestValidationError(
            f"Schema {schema_path} missing or empty 'required_sections' definition."
        )

    # 2. Verify target section definition
    target_rule = data.get("target")
    if not isinstance(target_rule, dict):
        raise TargetManifestValidationError(f"Schema {schema_path} missing 'target' rule mapping.")
    for req_key in ["required_fields", "allowed_source_types", "commit_format", "repo_formats"]:
        if req_key not in target_rule:
            raise TargetManifestValidationError(
                f"Schema {schema_path} 'target' rule missing required definition: '{req_key}'."
            )
    if not isinstance(target_rule["repo_formats"], dict):
        raise TargetManifestValidationError(
            f"Schema {schema_path} 'target.repo_formats' must be a mapping of regexes."
        )
    for st in target_rule["allowed_source_types"]:
        if st not in target_rule["repo_formats"]:
            raise TargetManifestValidationError(
                f"Schema {schema_path} 'target.repo_formats' missing format regex for allowed source_type: '{st}'."
            )

    # 3. Verify authority_surface section definition
    auth_rule = data.get("authority_surface")
    if not isinstance(auth_rule, dict):
        raise TargetManifestValidationError(f"Schema {schema_path} missing 'authority_surface' rule mapping.")
    for req_key in ["required_fields", "disallow_absolute_paths", "disallow_parent_traversal", "path_separator"]:
        if req_key not in auth_rule:
            raise TargetManifestValidationError(
                f"Schema {schema_path} 'authority_surface' rule missing required definition: '{req_key}'."
            )

    # 4. Verify baseline section definition
    baseline_rule = data.get("baseline")
    if not isinstance(baseline_rule, dict):
        raise TargetManifestValidationError(f"Schema {schema_path} missing 'baseline' rule mapping.")
    for req_key in ["required_fields", "allowed_frameworks", "allowed_versions"]:
        if req_key not in baseline_rule:
            raise TargetManifestValidationError(
                f"Schema {schema_path} 'baseline' rule missing required definition: '{req_key}'."
            )
    if not isinstance(baseline_rule["allowed_versions"], dict):
        raise TargetManifestValidationError(
            f"Schema {schema_path} 'baseline.allowed_versions' must be a mapping of framework to version list."
        )

    # 5. Verify mode section definition
    mode_rule = data.get("mode")
    if not isinstance(mode_rule, dict):
        raise TargetManifestValidationError(f"Schema {schema_path} missing 'mode' rule mapping.")
    for req_key in ["required_fields", "required_values"]:
        if req_key not in mode_rule:
            raise TargetManifestValidationError(
                f"Schema {schema_path} 'mode' rule missing required definition: '{req_key}'."
            )

    return data


def _validate_glob_pattern(pattern: Any, field_name: str, auth_schema: dict[str, Any]) -> list[str]:
    """Enforce glob security and boundary semantics driven directly by schema flags."""
    errors: list[str] = []
    if not isinstance(pattern, str) or not pattern.strip():
        return [f"Item in '{field_name}' must be a non-blank string."]

    stripped = pattern.strip()

    # Rule: Path separator enforcement
    expected_separator = auth_schema["path_separator"]
    if expected_separator == "/" and "\\" in stripped:
        errors.append(
            f"Item in '{field_name}' contains backslash ('\\\\'); paths must use '{expected_separator}': {pattern!r}."
        )

    # Rule: Absolute paths disallowed
    if auth_schema["disallow_absolute_paths"]:
        if stripped.startswith("/") or re.match(r"^[a-zA-Z]:", stripped):
            errors.append(
                f"Item in '{field_name}' must be a relative path from repo root; absolute paths prohibited: {pattern!r}."
            )

    # Rule: Parent directory traversal disallowed
    if auth_schema["disallow_parent_traversal"]:
        parts = stripped.split(expected_separator)
        if ".." in parts:
            errors.append(
                f"Item in '{field_name}' contains parent traversal ('..'); directory escape prohibited: {pattern!r}."
            )

    return errors


def validate_target_manifest_dict(
    data: Any,
    schema: dict[str, Any] | None = None,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Validate raw manifest data strictly using rules loaded from the schema.

    Returns a list of error messages.
    """
    if schema is None:
        schema = load_manifest_schema(schema_path)

    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Target manifest root must be a mapping/dictionary."]

    # 1. Top-level required sections (no default fallback)
    required_sections = schema["required_sections"]
    for section in required_sections:
        if section not in data:
            errors.append(f"Missing required section: '{section}'.")

    if errors:
        return errors

    # 2. Target section validation driven strictly by schema
    target_schema = schema["target"]
    target_data = data.get("target")
    if not isinstance(target_data, dict):
        errors.append("Section 'target' must be a mapping.")
    else:
        for field in target_schema["required_fields"]:
            if field not in target_data:
                errors.append(f"Missing required field '{field}' in 'target'.")

        source_type = target_data.get("source_type")
        allowed_types = target_schema["allowed_source_types"]
        if source_type is not None:
            if not isinstance(source_type, str) or source_type not in allowed_types:
                allowed_str = ", ".join(allowed_types)
                errors.append(
                    f"target.source_type '{source_type}' is not supported; allowed types: {allowed_str}."
                )

        repo = target_data.get("repo")
        if repo is not None:
            if not isinstance(repo, str):
                errors.append("Field 'repo' in 'target' must be a string.")
            elif not repo.strip():
                errors.append("Field 'repo' in 'target' cannot be empty or whitespace only.")
            elif source_type in allowed_types:
                # Syntax binding between source_type and repo format
                repo_regex_str = target_schema["repo_formats"][source_type]
                if not re.fullmatch(repo_regex_str, repo.strip()):
                    if source_type == "github":
                        errors.append(
                            f"target.repo '{repo}' is invalid for source_type 'github'; must match 'owner/repo' format."
                        )
                    else:
                        errors.append(
                            f"target.repo '{repo}' is invalid for source_type '{source_type}'."
                        )

        commit = target_data.get("commit")
        commit_regex_str = target_schema["commit_format"]
        commit_regex = re.compile(commit_regex_str)
        if commit is not None:
            if not isinstance(commit, str) or not commit_regex.fullmatch(commit):
                errors.append(
                    f"Field 'commit' in 'target' must be a full 40-character hexadecimal SHA; got: {commit!r}."
                )

    # 3. Authority surface section validation driven strictly by schema
    auth_schema = schema["authority_surface"]
    auth_data = data.get("authority_surface")
    if not isinstance(auth_data, dict):
        errors.append("Section 'authority_surface' must be a mapping.")
    else:
        include = auth_data.get("include")
        if include is None:
            errors.append("Missing required field 'include' in 'authority_surface'.")
        elif not isinstance(include, list) or len(include) == 0:
            errors.append("Field 'include' must be a non-empty list of glob pattern strings.")
        else:
            for item in include:
                errors.extend(_validate_glob_pattern(item, "include", auth_schema))

        exclude = auth_data.get("exclude")
        if exclude is not None:
            if not isinstance(exclude, list):
                errors.append("Field 'exclude' must be a list of strings if specified.")
            else:
                for item in exclude:
                    errors.extend(_validate_glob_pattern(item, "exclude", auth_schema))

    # 4. Baseline section validation driven strictly by schema
    baseline_schema = schema["baseline"]
    baseline_data = data.get("baseline")
    if not isinstance(baseline_data, dict):
        errors.append("Section 'baseline' must be a mapping.")
    else:
        framework = baseline_data.get("framework")
        allowed_frameworks = baseline_schema["allowed_frameworks"]
        if framework is None:
            errors.append("Missing required field 'framework' in 'baseline'.")
        elif not isinstance(framework, str) or framework not in allowed_frameworks:
            allowed_fw_str = ", ".join(allowed_frameworks)
            errors.append(
                f"Framework '{framework}' is not supported; allowed frameworks: {allowed_fw_str}."
            )
        else:
            version = baseline_data.get("version")
            allowed_versions_map = baseline_schema["allowed_versions"]
            allowed_versions = allowed_versions_map.get(framework, [])

            if version is None:
                errors.append("Missing required field 'version' in 'baseline'.")
            elif not isinstance(version, str):
                # Strict string type: forbid float/numeric like 1.1
                errors.append(
                    f"baseline.version must be a quoted string (got {type(version).__name__}: {version!r}); "
                    "numeric/float values are strictly prohibited."
                )
            elif version not in allowed_versions:
                allowed_v_str = ", ".join(allowed_versions)
                errors.append(
                    f"Version '{version}' is not supported for framework '{framework}'; allowed versions: {allowed_v_str}."
                )

    # 5. Mode section validation driven strictly by schema
    mode_schema = schema["mode"]
    mode_data = data.get("mode")
    if not isinstance(mode_data, dict):
        errors.append("Section 'mode' must be a mapping.")
    else:
        read_only = mode_data.get("read_only")
        required_read_only = mode_schema["required_values"]["read_only"]
        if read_only is not required_read_only:
            errors.append(f"mode.read_only must be boolean {required_read_only}; got: {read_only!r}.")

    return errors


def parse_target_manifest(
    data: Any,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> TargetManifest:
    """Parse and return a validated, immutable TargetManifest domain object.

    Raises TargetManifestValidationError if validation fails.
    """
    errors = validate_target_manifest_dict(data, schema_path=schema_path)
    if errors:
        raise TargetManifestValidationError(
            "Target manifest validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
        )

    return TargetManifest(
        target=TargetSpec(
            source_type=data["target"]["source_type"],
            repo=data["target"]["repo"],
            commit=data["target"]["commit"],
        ),
        authority_surface=AuthoritySurfaceSpec(
            include=tuple(data["authority_surface"]["include"]),
            exclude=tuple(data["authority_surface"].get("exclude", [])),
        ),
        baseline=BaselineSpec(
            framework=data["baseline"]["framework"],
            version=data["baseline"]["version"],
        ),
        mode=ModeSpec(
            read_only=data["mode"]["read_only"],
        ),
    )


def validate_target_manifest_file(
    manifest_path: Path | str,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> list[str]:
    """Parse and validate a target manifest YAML file."""
    path = Path(manifest_path)
    if not path.is_file():
        return [f"File not found: {path}"]

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"YAML parsing error in {path}: {exc}"]
    except Exception as exc:
        return [f"Failed to read {path}: {exc}"]

    return validate_target_manifest_dict(data, schema_path=schema_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate SSDLC target manifest YAML against Phase S1-A specification."
    )
    parser.add_argument("manifest_path", type=Path, help="Path to the target manifest YAML file")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to target-manifest schema YAML (default: schemas/target-manifest.schema.yaml)",
    )
    args = parser.parse_args()

    try:
        errors = validate_target_manifest_file(args.manifest_path, schema_path=args.schema)
    except TargetManifestValidationError as exc:
        print(f"[FAIL] Target manifest schema error: {exc}", file=sys.stderr)
        return 1

    if errors:
        print(f"[FAIL] Target manifest validation failed for: {args.manifest_path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"[PASS] Target manifest is valid: {args.manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
