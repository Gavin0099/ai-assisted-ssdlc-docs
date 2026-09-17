#!/usr/bin/env python3
"""Deterministic Target Manifest Validator for SSDLC Real Repo Assessments (Phase S1-A-r1).

Loads schema rules dynamically from schemas/target-manifest.schema.yaml, enforcing:
- Target identity and source_type (local_git | github)
- Commit SHA freeze (strict 40-char hex SHA)
- Strict string types for baseline version (prohibits float/numeric drift)
- Authority surface glob boundary constraints (relative only, no '..', normalized '/')
- Read-only execution mode
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
    """Raised when target manifest validation fails closed."""


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
    """Load and validate the executable manifest schema."""
    if not schema_path.is_file():
        raise TargetManifestValidationError(f"Schema file not found: {schema_path}")

    try:
        data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TargetManifestValidationError(f"Failed to parse schema YAML {schema_path}: {exc}") from exc

    if not isinstance(data, dict) or data.get("schema_name") != "target-manifest":
        raise TargetManifestValidationError(
            f"Invalid schema: expected schema_name 'target-manifest' in {schema_path}"
        )
    return data


def _validate_glob_pattern(pattern: Any, field_name: str) -> list[str]:
    """Enforce glob security and boundary semantics."""
    errors: list[str] = []
    if not isinstance(pattern, str) or not pattern.strip():
        return [f"Item in '{field_name}' must be a non-blank string."]

    stripped = pattern.strip()

    # Rule 1: No Windows backslashes
    if "\\" in stripped:
        errors.append(
            f"Item in '{field_name}' contains backslash ('\\\\'); paths must be normalized with '/': {pattern!r}."
        )

    # Rule 2: No absolute paths (Unix '/' or Windows drive 'C:')
    if stripped.startswith("/") or re.match(r"^[a-zA-Z]:", stripped):
        errors.append(
            f"Item in '{field_name}' must be a relative path from repo root; absolute paths prohibited: {pattern!r}."
        )

    # Rule 3: No parent directory traversal '..'
    parts = stripped.split("/")
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
    """Validate raw manifest data using rules loaded from the schema.

    Returns a list of error messages.
    """
    if schema is None:
        schema = load_manifest_schema(schema_path)

    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Target manifest root must be a mapping/dictionary."]

    # 1. Top-level required sections
    required_sections = schema.get("required_sections", ["target", "authority_surface", "baseline", "mode"])
    for section in required_sections:
        if section not in data:
            errors.append(f"Missing required section: '{section}'.")

    if errors:
        return errors

    # 2. Target section validation driven by schema
    target_schema = schema.get("target", {})
    target_data = data.get("target")
    if not isinstance(target_data, dict):
        errors.append("Section 'target' must be a mapping.")
    else:
        # required fields
        for field in target_schema.get("required_fields", ["source_type", "repo", "commit"]):
            if field not in target_data:
                errors.append(f"Missing required field '{field}' in 'target'.")

        source_type = target_data.get("source_type")
        allowed_types = target_schema.get("allowed_source_types", ["local_git", "github"])
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

        commit = target_data.get("commit")
        commit_regex_str = target_schema.get("commit_format", r"^[0-9a-fA-F]{40}$")
        commit_regex = re.compile(commit_regex_str)
        if commit is not None:
            if not isinstance(commit, str) or not commit_regex.fullmatch(commit):
                errors.append(
                    f"Field 'commit' in 'target' must be a full 40-character hexadecimal SHA; got: {commit!r}."
                )

    # 3. Authority surface section validation driven by schema
    auth_schema = schema.get("authority_surface", {})
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
                errors.extend(_validate_glob_pattern(item, "include"))

        exclude = auth_data.get("exclude")
        if exclude is not None:
            if not isinstance(exclude, list):
                errors.append("Field 'exclude' must be a list of strings if specified.")
            else:
                for item in exclude:
                    errors.extend(_validate_glob_pattern(item, "exclude"))

    # 4. Baseline section validation driven by schema
    baseline_schema = schema.get("baseline", {})
    baseline_data = data.get("baseline")
    if not isinstance(baseline_data, dict):
        errors.append("Section 'baseline' must be a mapping.")
    else:
        framework = baseline_data.get("framework")
        allowed_frameworks = baseline_schema.get("allowed_frameworks", ["NIST_SP_800_218"])
        if framework is None:
            errors.append("Missing required field 'framework' in 'baseline'.")
        elif not isinstance(framework, str) or framework not in allowed_frameworks:
            allowed_fw_str = ", ".join(allowed_frameworks)
            errors.append(
                f"Framework '{framework}' is not supported; allowed frameworks: {allowed_fw_str}."
            )
        else:
            version = baseline_data.get("version")
            allowed_versions_map = baseline_schema.get("allowed_versions", {})
            allowed_versions = allowed_versions_map.get(framework, ["1.1"])

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

    # 5. Mode section validation driven by schema
    mode_schema = schema.get("mode", {})
    mode_data = data.get("mode")
    if not isinstance(mode_data, dict):
        errors.append("Section 'mode' must be a mapping.")
    else:
        read_only = mode_data.get("read_only")
        required_read_only = mode_schema.get("required_values", {}).get("read_only", True)
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

    errors = validate_target_manifest_file(args.manifest_path, schema_path=args.schema)
    if errors:
        print(f"[FAIL] Target manifest validation failed for: {args.manifest_path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"[PASS] Target manifest is valid: {args.manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
