#!/usr/bin/env python3
"""Deterministic Target Manifest Validator for SSDLC Real Repo Assessments (Phase S1-A).

Enforces schema constraints, commit hash freeze (40-char hex SHA), non-empty
authoritative include surface, allowed baseline frameworks, and read-only mode.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
ALLOWED_BASELINES: dict[str, list[str]] = {
    "NIST_SP_800_218": ["1.1"],
}


class TargetManifestValidationError(ValueError):
    """Raised when target manifest validation fails closed."""


@dataclass(frozen=True)
class TargetSpec:
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


def validate_target_manifest_dict(data: Any) -> list[str]:
    """Validate a raw manifest dictionary against the S1-A Target Manifest contract.

    Returns a list of error strings. An empty list indicates successful validation.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Target manifest root must be a mapping/dictionary."]

    # 1. Required top-level sections
    required_sections = ["target", "authority_surface", "baseline", "mode"]
    for section in required_sections:
        if section not in data:
            errors.append(f"Missing required section: '{section}'.")

    if errors:
        # If required top-level sections are missing, fail fast
        return errors

    # 2. Validate 'target' section
    target = data.get("target")
    if not isinstance(target, dict):
        errors.append("Section 'target' must be a mapping.")
    else:
        repo = target.get("repo")
        if repo is None:
            errors.append("Missing required field 'repo' in 'target'.")
        elif not isinstance(repo, str):
            errors.append("Field 'repo' in 'target' must be a string.")
        elif not repo.strip():
            errors.append("Field 'repo' cannot be empty or whitespace only.")

        commit = target.get("commit")
        if commit is None:
            errors.append("Missing required field 'commit' in 'target'.")
        elif not isinstance(commit, str) or not COMMIT_SHA_PATTERN.fullmatch(commit):
            errors.append(
                f"Field 'commit' in 'target' must be a full 40-character hexadecimal SHA; got: {commit!r}."
            )

    # 3. Validate 'authority_surface' section
    authority_surface = data.get("authority_surface")
    if not isinstance(authority_surface, dict):
        errors.append("Section 'authority_surface' must be a mapping.")
    else:
        include = authority_surface.get("include")
        if include is None:
            errors.append("Missing required field 'include' in 'authority_surface'.")
        elif not isinstance(include, list) or len(include) == 0:
            errors.append("Field 'include' must be a non-empty list of glob pattern strings.")
        else:
            for item in include:
                if not isinstance(item, str) or not item.strip():
                    errors.append("Item in 'include' must be a non-blank string.")

        exclude = authority_surface.get("exclude")
        if exclude is not None:
            if not isinstance(exclude, list):
                errors.append("Field 'exclude' must be a list of strings if specified.")
            else:
                for item in exclude:
                    if not isinstance(item, str) or not item.strip():
                        errors.append("Item in 'exclude' must be a non-blank string.")

    # 4. Validate 'baseline' section
    baseline = data.get("baseline")
    if not isinstance(baseline, dict):
        errors.append("Section 'baseline' must be a mapping.")
    else:
        framework = baseline.get("framework")
        if not framework or not isinstance(framework, str):
            errors.append("Missing required field 'framework' in 'baseline'.")
        elif framework not in ALLOWED_BASELINES:
            allowed = ", ".join(ALLOWED_BASELINES.keys())
            errors.append(f"Framework '{framework}' is not supported; allowed frameworks: {allowed}.")
        else:
            allowed_versions = ALLOWED_BASELINES[framework]
            version = str(baseline.get("version", ""))
            if not version:
                errors.append("Missing required field 'version' in 'baseline'.")
            elif version not in allowed_versions:
                allowed_v_str = ", ".join(allowed_versions)
                errors.append(
                    f"Version '{version}' is not supported for framework '{framework}'; allowed versions: {allowed_v_str}."
                )

    # 5. Validate 'mode' section
    mode = data.get("mode")
    if not isinstance(mode, dict):
        errors.append("Section 'mode' must be a mapping.")
    else:
        read_only = mode.get("read_only")
        if read_only is not True:
            errors.append(f"mode.read_only must be true (boolean); got: {read_only!r}.")

    return errors


def validate_target_manifest_file(manifest_path: Path | str) -> list[str]:
    """Parse and validate a target manifest YAML file."""
    path = Path(manifest_path)
    if not path.is_file():
        return [f"File not found: {path}"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        return [f"YAML parsing error in {path}: {exc}"]
    except Exception as exc:
        return [f"Failed to read {path}: {exc}"]

    return validate_target_manifest_dict(data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate SSDLC target manifest YAML against Phase S1-A specification."
    )
    parser.add_argument("manifest_path", type=Path, help="Path to the target manifest YAML file")
    args = parser.parse_args()

    errors = validate_target_manifest_file(args.manifest_path)
    if errors:
        print(f"[FAIL] Target manifest validation failed for: {args.manifest_path}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"[PASS] Target manifest is valid: {args.manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
