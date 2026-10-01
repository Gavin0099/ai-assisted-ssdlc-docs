#!/usr/bin/env python3
"""Strict admission and canonical digesting for S2 Product Target Manifests."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "product-target-manifest.schema.yaml"
)

_PRODUCT_MANIFEST_ADMISSION_TOKEN = object()


class ProductTargetManifestValidationError(ValueError):
    """Raised when a Product Target Manifest or its schema fails closed."""


@dataclass(frozen=True)
class ProductTargetSpec:
    source_type: str
    repo: str
    commit: str


@dataclass(frozen=True)
class ProductAuthoritySurfaceSpec:
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class ProductModeSpec:
    read_only: bool


@dataclass(frozen=True)
class ProductTargetManifest:
    manifest_version: str
    target: ProductTargetSpec
    authority_surface: ProductAuthoritySurfaceSpec
    mode: ProductModeSpec
    _admission_token: object = field(
        repr=False,
        compare=False,
        default=None,
    )

    def __post_init__(self) -> None:
        if self._admission_token is not _PRODUCT_MANIFEST_ADMISSION_TOKEN:
            raise ProductTargetManifestValidationError(
                "ProductTargetManifest must be created by parser admission."
            )

    @property
    def digest(self) -> str:
        """Return the S1-compatible JSON SHA-256 for the S2 semantic payload."""
        payload = {
            "manifest_version": self.manifest_version,
            "target": {
                "source_type": self.target.source_type,
                "repo": self.target.repo,
                "commit": self.target.commit,
            },
            "authority_surface": {
                "include": list(self.authority_surface.include),
                "exclude": list(self.authority_surface.exclude),
            },
            "mode": {"read_only": self.mode.read_only},
        }
        canonical = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: MappingNode, deep: bool = False
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
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


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def _schema_string_list(
    value: Any, label: str, *, allow_empty: bool = False
) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ProductTargetManifestValidationError(
            f"Product manifest schema field '{label}' must be a {'possibly empty ' if allow_empty else 'non-empty '}list of strings."
        )
    if any(not isinstance(item, str) or not item for item in value):
        raise ProductTargetManifestValidationError(
            f"Product manifest schema field '{label}' must contain only non-empty strings."
        )
    if len(set(value)) != len(value):
        raise ProductTargetManifestValidationError(
            f"Product manifest schema field '{label}' must not contain duplicates."
        )
    return value


def _validate_schema_object(
    schema: dict[str, Any],
    section: str,
    expected_fields: set[str],
) -> dict[str, Any]:
    value = schema.get(section)
    if not isinstance(value, dict):
        raise ProductTargetManifestValidationError(
            f"Product manifest schema section '{section}' must be a mapping."
        )
    if value.get("additional_properties") is not False:
        raise ProductTargetManifestValidationError(
            f"Product manifest schema section '{section}' must set additional_properties to false."
        )
    missing = expected_fields - value.keys()
    if missing:
        raise ProductTargetManifestValidationError(
            f"Product manifest schema section '{section}' is missing required definitions: {', '.join(sorted(missing))}."
        )
    return value


def load_product_target_manifest_schema(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Load and fail closed on incomplete Product Target Manifest rules."""
    if not schema_path.is_file():
        raise ProductTargetManifestValidationError(
            f"Product manifest schema file not found: {schema_path}"
        )
    try:
        schema = yaml.load(
            schema_path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader
        )
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProductTargetManifestValidationError(
            f"Failed to parse Product manifest schema ({type(exc).__name__})."
        ) from exc

    if not isinstance(schema, dict):
        raise ProductTargetManifestValidationError(
            "Product manifest schema root must be a mapping."
        )
    if schema.get("schema_name") != "product-target-manifest":
        raise ProductTargetManifestValidationError(
            "Invalid Product manifest schema name."
        )
    if schema.get("schema_version") != "1.0.0":
        raise ProductTargetManifestValidationError(
            "Unsupported Product manifest schema version."
        )
    if schema.get("additional_properties") is not False:
        raise ProductTargetManifestValidationError(
            "Product manifest schema root must set additional_properties to false."
        )

    root_fields = _schema_string_list(
        schema.get("required_fields"), "required_fields"
    )
    if root_fields != ["manifest_version", "target", "authority_surface", "mode"]:
        raise ProductTargetManifestValidationError(
            "Product manifest schema root fields do not match the supported contract."
        )
    versions = _schema_string_list(
        schema.get("accepted_manifest_versions"), "accepted_manifest_versions"
    )
    if versions != ["1.0"]:
        raise ProductTargetManifestValidationError(
            "Product manifest schema versions do not match the supported contract."
        )

    target = _validate_schema_object(
        schema,
        "target",
        {
            "required_fields",
            "allowed_source_types",
            "commit_format",
            "commit_normalization",
            "repo_formats",
        },
    )
    target_fields = _schema_string_list(
        target.get("required_fields"), "target.required_fields"
    )
    if target_fields != ["source_type", "repo", "commit"]:
        raise ProductTargetManifestValidationError(
            "Product manifest target fields do not match the supported contract."
        )
    source_types = _schema_string_list(
        target.get("allowed_source_types"), "target.allowed_source_types"
    )
    if source_types != ["local_git", "github"]:
        raise ProductTargetManifestValidationError(
            "Product manifest source types do not match the supported contract."
        )
    repo_formats = target.get("repo_formats")
    expected_repo_formats = {
        "github": r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$",
        "local_git": (
            r"^(?!(?:[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$|"
            r"[a-zA-Z][a-zA-Z0-9+.-]*://|git@)).+$"
        ),
    }
    if repo_formats != expected_repo_formats:
        raise ProductTargetManifestValidationError(
            "Product manifest repo format rules do not match the supported contract."
        )
    for source_type, pattern in repo_formats.items():
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ProductTargetManifestValidationError(
                f"Product manifest repo format for '{source_type}' is an invalid regex."
            ) from exc
    commit_format = target.get("commit_format")
    if commit_format != r"^[0-9a-fA-F]{40}$":
        raise ProductTargetManifestValidationError(
            "Product manifest commit format does not match the full-SHA contract."
        )
    try:
        re.compile(commit_format)
    except re.error as exc:
        raise ProductTargetManifestValidationError(
            "Product manifest commit_format is an invalid regex."
        ) from exc
    if target.get("commit_normalization") != "lowercase":
        raise ProductTargetManifestValidationError(
            "Product manifest commit normalization must be lowercase."
        )

    authority = _validate_schema_object(
        schema,
        "authority_surface",
        {
            "required_fields",
            "optional_fields",
            "disallow_absolute_paths",
            "disallow_parent_traversal",
            "path_separator",
            "unsupported_glob_characters",
        },
    )
    if _schema_string_list(
        authority.get("required_fields"), "authority_surface.required_fields"
    ) != ["include"]:
        raise ProductTargetManifestValidationError(
            "Product manifest authority required fields do not match the supported contract."
        )
    if _schema_string_list(
        authority.get("optional_fields"), "authority_surface.optional_fields"
    ) != ["exclude"]:
        raise ProductTargetManifestValidationError(
            "Product manifest authority optional fields do not match the supported contract."
        )
    for flag in ("disallow_absolute_paths", "disallow_parent_traversal"):
        if authority.get(flag) is not True:
            raise ProductTargetManifestValidationError(
                f"Product manifest schema '{flag}' must be true."
            )
    if authority.get("path_separator") != "/":
        raise ProductTargetManifestValidationError(
            "Product manifest schema path_separator must be '/'."
        )
    unsupported_glob_characters = authority.get("unsupported_glob_characters")
    if unsupported_glob_characters != "[]{}!~^":
        raise ProductTargetManifestValidationError(
            "Product manifest glob syntax does not match Supported Glob Subset v1."
        )

    mode = _validate_schema_object(
        schema, "mode", {"required_fields", "required_values"}
    )
    if _schema_string_list(mode.get("required_fields"), "mode.required_fields") != [
        "read_only"
    ]:
        raise ProductTargetManifestValidationError(
            "Product manifest mode fields do not match the supported contract."
        )
    required_values = mode.get("required_values")
    if not isinstance(required_values, dict) or required_values != {"read_only": True}:
        raise ProductTargetManifestValidationError(
            "Product manifest mode must require boolean read_only=true."
        )
    return schema


def _object_shape_errors(
    value: Any, section: str, required_fields: list[str]
) -> list[str]:
    if not isinstance(value, dict):
        return [f"Section '{section}' must be a mapping."]
    errors: list[str] = []
    if any(not isinstance(key, str) for key in value):
        errors.append(f"Section '{section}' keys must be strings.")
    for key in value:
        if isinstance(key, str) and key not in required_fields and not (
            section == "authority_surface" and key == "exclude"
        ):
            errors.append(f"Unknown field '{key}' in '{section}'.")
    for field_name in required_fields:
        if field_name not in value:
            errors.append(f"Missing required field '{field_name}' in '{section}'.")
    return errors


def _validate_glob_pattern(
    pattern: Any,
    field_name: str,
    index: int,
    authority_schema: dict[str, Any],
) -> list[str]:
    label = f"{field_name}[{index}]"
    if not isinstance(pattern, str) or not pattern.strip():
        return [f"'{label}' must be a non-blank glob pattern string."]

    stripped = pattern.strip()
    errors: list[str] = []
    if stripped != pattern:
        errors.append(f"'{label}' must not contain surrounding whitespace.")
    if "\\" in stripped:
        errors.append(f"'{label}' must use POSIX '/' separators; backslashes are prohibited.")
    if stripped.startswith("/") or re.match(r"^[a-zA-Z]:", stripped):
        errors.append(f"'{label}' must be relative; absolute paths are prohibited.")
    if ".." in stripped.split(authority_schema["path_separator"]):
        errors.append(f"'{label}' must not contain a '..' path segment.")
    if any(char in stripped for char in authority_schema["unsupported_glob_characters"]):
        errors.append(f"'{label}' uses glob syntax outside Supported Glob Subset v1.")
    return errors


def _validate_product_target_manifest_dict(
    data: Any, schema: dict[str, Any]
) -> list[str]:
    root_required = schema["required_fields"]
    errors = _object_shape_errors(data, "manifest", root_required)
    if isinstance(data, dict):
        for key in data:
            if isinstance(key, str) and key not in root_required:
                errors.append(f"Unknown field '{key}' in 'manifest'.")
        version = data.get("manifest_version")
        if not isinstance(version, str) or version not in schema["accepted_manifest_versions"]:
            errors.append("manifest_version must be the supported string '1.0'.")

        target = data.get("target")
        target_rules = schema["target"]
        errors.extend(
            _object_shape_errors(target, "target", target_rules["required_fields"])
        )
        if isinstance(target, dict):
            source_type = target.get("source_type")
            if not isinstance(source_type, str) or source_type not in target_rules[
                "allowed_source_types"
            ]:
                errors.append("target.source_type is not supported.")
            repo = target.get("repo")
            if not isinstance(repo, str) or not repo or repo != repo.strip():
                errors.append("target.repo must be a non-empty string without surrounding whitespace.")
            elif isinstance(source_type, str) and source_type in target_rules[
                "repo_formats"
            ]:
                if not re.fullmatch(target_rules["repo_formats"][source_type], repo.strip()):
                    errors.append("target.repo does not match its source_type format.")
            commit = target.get("commit")
            if not isinstance(commit, str) or not re.fullmatch(
                target_rules["commit_format"], commit
            ):
                errors.append("target.commit must be a full 40-character hexadecimal SHA.")

        authority = data.get("authority_surface")
        authority_rules = schema["authority_surface"]
        errors.extend(
            _object_shape_errors(
                authority, "authority_surface", authority_rules["required_fields"]
            )
        )
        if isinstance(authority, dict):
            include = authority.get("include")
            if not isinstance(include, list) or not include:
                errors.append("authority_surface.include must be a non-empty list.")
            else:
                if len(set(item for item in include if isinstance(item, str))) != sum(
                    isinstance(item, str) for item in include
                ):
                    errors.append("authority_surface.include must not contain duplicate selectors.")
                for index, pattern in enumerate(include):
                    errors.extend(
                        _validate_glob_pattern(
                            pattern, "authority_surface.include", index, authority_rules
                        )
                    )
            if "exclude" in authority:
                exclude = authority["exclude"]
                if not isinstance(exclude, list):
                    errors.append("authority_surface.exclude must be a list when specified.")
                else:
                    if len(set(item for item in exclude if isinstance(item, str))) != sum(
                        isinstance(item, str) for item in exclude
                    ):
                        errors.append("authority_surface.exclude must not contain duplicate selectors.")
                    for index, pattern in enumerate(exclude):
                        errors.extend(
                            _validate_glob_pattern(
                                pattern,
                                "authority_surface.exclude",
                                index,
                                authority_rules,
                            )
                        )

        mode = data.get("mode")
        mode_rules = schema["mode"]
        errors.extend(_object_shape_errors(mode, "mode", mode_rules["required_fields"]))
        if isinstance(mode, dict) and mode.get("read_only") is not mode_rules[
            "required_values"
        ]["read_only"]:
            errors.append("mode.read_only must be the boolean true.")
    return errors


def validate_product_target_manifest_dict(
    data: Any, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> list[str]:
    """Validate an in-memory Product Target Manifest without coercion."""
    schema = load_product_target_manifest_schema(schema_path)
    return _validate_product_target_manifest_dict(data, schema)


def verify_admitted_product_target_manifest(
    manifest: Any, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> ProductTargetManifest:
    """Fail closed if an admitted ProductTargetManifest violates any domain invariant."""
    if not isinstance(manifest, ProductTargetManifest):
        raise ProductTargetManifestValidationError(
            "Expected an admitted ProductTargetManifest instance."
        )
    if getattr(manifest, "_admission_token", None) is not _PRODUCT_MANIFEST_ADMISSION_TOKEN:
        raise ProductTargetManifestValidationError(
            "ProductTargetManifest has invalid or missing admission token."
        )

    schema = load_product_target_manifest_schema(schema_path)

    # 1. manifest_version
    if (
        not isinstance(manifest.manifest_version, str)
        or manifest.manifest_version != "1.0"
        or manifest.manifest_version not in schema["accepted_manifest_versions"]
    ):
        raise ProductTargetManifestValidationError(
            f"Unsupported manifest_version: {manifest.manifest_version!r}."
        )

    # 2. target
    if not isinstance(manifest.target, ProductTargetSpec):
        raise ProductTargetManifestValidationError(
            "ProductTargetManifest target must be a ProductTargetSpec instance."
        )
    target_rules = schema["target"]
    if manifest.target.source_type not in target_rules["allowed_source_types"]:
        raise ProductTargetManifestValidationError(
            f"target.source_type is not supported: {manifest.target.source_type!r}."
        )
    repo = manifest.target.repo
    if not isinstance(repo, str) or not repo or repo != repo.strip():
        raise ProductTargetManifestValidationError(
            "target.repo must be a non-empty string without surrounding whitespace."
        )
    repo_regex = target_rules["repo_formats"].get(manifest.target.source_type)
    if not repo_regex or not re.fullmatch(repo_regex, repo):
        raise ProductTargetManifestValidationError(
            f"target.repo does not match {manifest.target.source_type} format."
        )
    commit = manifest.target.commit
    if (
        not isinstance(commit, str)
        or not re.fullmatch(r"^[0-9a-f]{40}$", commit)
        or commit != commit.lower()
    ):
        raise ProductTargetManifestValidationError(
            "target.commit must be a canonical lowercase 40-character hexadecimal SHA."
        )

    # 3. authority_surface
    if not isinstance(manifest.authority_surface, ProductAuthoritySurfaceSpec):
        raise ProductTargetManifestValidationError(
            "authority_surface must be a ProductAuthoritySurfaceSpec instance."
        )
    authority_rules = schema["authority_surface"]

    include = manifest.authority_surface.include
    if not isinstance(include, tuple) or not include:
        raise ProductTargetManifestValidationError(
            "authority_surface.include must be a non-empty tuple of strings."
        )
    if len(set(include)) != len(include):
        raise ProductTargetManifestValidationError(
            "authority_surface.include must not contain duplicate selectors."
        )
    for index, pattern in enumerate(include):
        glob_errors = _validate_glob_pattern(
            pattern, "authority_surface.include", index, authority_rules
        )
        if glob_errors:
            raise ProductTargetManifestValidationError(
                f"Invalid pattern in authority_surface.include: {', '.join(glob_errors)}"
            )

    exclude = manifest.authority_surface.exclude
    if not isinstance(exclude, tuple):
        raise ProductTargetManifestValidationError(
            "authority_surface.exclude must be a tuple of strings."
        )
    if len(set(exclude)) != len(exclude):
        raise ProductTargetManifestValidationError(
            "authority_surface.exclude must not contain duplicate selectors."
        )
    for index, pattern in enumerate(exclude):
        glob_errors = _validate_glob_pattern(
            pattern, "authority_surface.exclude", index, authority_rules
        )
        if glob_errors:
            raise ProductTargetManifestValidationError(
                f"Invalid pattern in authority_surface.exclude: {', '.join(glob_errors)}"
            )

    # 4. mode
    if not isinstance(manifest.mode, ProductModeSpec):
        raise ProductTargetManifestValidationError(
            "ProductTargetManifest mode must be a ProductModeSpec instance."
        )
    if manifest.mode.read_only is not True:
        raise ProductTargetManifestValidationError(
            "mode.read_only must be strictly boolean True."
        )

    return manifest


def parse_product_target_manifest(
    data: Any, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> ProductTargetManifest:
    """Validate and return an immutable Product Target Manifest."""
    schema = load_product_target_manifest_schema(schema_path)
    errors = _validate_product_target_manifest_dict(data, schema)
    if errors:
        raise ProductTargetManifestValidationError(
            "Product Target Manifest validation failed:\n"
            + "\n".join(f"  - {error}" for error in errors)
        )

    manifest = ProductTargetManifest(
        manifest_version=data["manifest_version"],
        target=ProductTargetSpec(
            source_type=data["target"]["source_type"],
            repo=data["target"]["repo"],
            commit=data["target"]["commit"].lower(),
        ),
        authority_surface=ProductAuthoritySurfaceSpec(
            include=tuple(data["authority_surface"]["include"]),
            exclude=tuple(data["authority_surface"].get("exclude", [])),
        ),
        mode=ProductModeSpec(read_only=data["mode"]["read_only"]),
        _admission_token=_PRODUCT_MANIFEST_ADMISSION_TOKEN,
    )
    return verify_admitted_product_target_manifest(manifest, schema_path)


def parse_product_target_manifest_file(
    manifest_path: Path | str, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> ProductTargetManifest:
    """Read YAML with duplicate-key rejection, then admit the manifest."""
    path = Path(manifest_path)
    if not path.is_file():
        raise ProductTargetManifestValidationError(
            f"Product Target Manifest file not found: {path}"
        )
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ProductTargetManifestValidationError(
            f"Product Target Manifest YAML parsing failed ({type(exc).__name__})."
        ) from exc
    return parse_product_target_manifest(data, schema_path)


def validate_product_target_manifest_file(
    manifest_path: Path | str, schema_path: Path = DEFAULT_SCHEMA_PATH
) -> list[str]:
    """Return validation errors for a Product Target Manifest YAML file."""
    try:
        parse_product_target_manifest_file(manifest_path, schema_path)
    except ProductTargetManifestValidationError as exc:
        return [str(exc)]
    return []


__all__ = [
    "DEFAULT_SCHEMA_PATH",
    "ProductAuthoritySurfaceSpec",
    "ProductModeSpec",
    "ProductTargetManifest",
    "ProductTargetManifestValidationError",
    "ProductTargetSpec",
    "load_product_target_manifest_schema",
    "parse_product_target_manifest",
    "parse_product_target_manifest_file",
    "validate_product_target_manifest_dict",
    "validate_product_target_manifest_file",
    "verify_admitted_product_target_manifest",
]