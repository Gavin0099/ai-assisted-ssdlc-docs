from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.validate_product_target_manifest import (
    DEFAULT_SCHEMA_PATH,
    ProductAuthoritySurfaceSpec,
    ProductModeSpec,
    ProductTargetManifest,
    ProductTargetManifestValidationError,
    ProductTargetSpec,
    load_product_target_manifest_schema,
    parse_product_target_manifest,
    parse_product_target_manifest_file,
    validate_product_target_manifest_dict,
    verify_admitted_product_target_manifest,
)

GOLDEN_MANIFEST = {
    "manifest_version": "1.0",
    "target": {
        "source_type": "local_git",
        "repo": "E:/repo",
        "commit": "a" * 40,
    },
    "authority_surface": {"include": ["src/**"]},
    "mode": {"read_only": True},
}
GOLDEN_DIGEST = "7c9fad2bdb6088cd18510532874773d587b3eb04b64a9b5402e7fcc4de47540c"
UNICODE_GOLDEN_DIGEST = "66c0e3425ff017cbe18f74d44fcad8431035c3d471eaa382e6133bb5e4a72cd9"


class ProductTargetManifestTests(unittest.TestCase):
    def test_valid_manifest_defaults_exclude_and_matches_golden_digest(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)

        self.assertEqual(manifest.authority_surface.exclude, ())
        self.assertEqual(manifest.target.commit, "a" * 40)
        self.assertEqual(manifest.digest, GOLDEN_DIGEST)

    def test_missing_exclude_matches_explicit_empty_exclude_digest(self) -> None:
        without_exclude = copy.deepcopy(GOLDEN_MANIFEST)
        with_empty_exclude = copy.deepcopy(GOLDEN_MANIFEST)
        with_empty_exclude["authority_surface"]["exclude"] = []

        manifest_without = parse_product_target_manifest(without_exclude)
        manifest_with_empty = parse_product_target_manifest(with_empty_exclude)

        self.assertEqual(manifest_without.digest, manifest_with_empty.digest)
        self.assertEqual(manifest_without.authority_surface.exclude, ())
        self.assertEqual(manifest_with_empty.authority_surface.exclude, ())

    def test_commit_is_normalized_to_lowercase_before_digest(self) -> None:
        data = copy.deepcopy(GOLDEN_MANIFEST)
        data["target"]["commit"] = "A" * 40

        manifest = parse_product_target_manifest(data)

        self.assertEqual(manifest.target.commit, "a" * 40)
        self.assertEqual(manifest.digest, GOLDEN_DIGEST)

    def test_digest_preserves_author_order_for_authority_paths(self) -> None:
        first = copy.deepcopy(GOLDEN_MANIFEST)
        first["authority_surface"]["include"] = ["src/**", "config/**"]
        second = copy.deepcopy(first)
        second["authority_surface"]["include"].reverse()

        self.assertNotEqual(
            parse_product_target_manifest(first).digest,
            parse_product_target_manifest(second).digest,
        )

    def test_digest_matches_python_default_ascii_escaping_for_unicode_paths(self) -> None:
        data = copy.deepcopy(GOLDEN_MANIFEST)
        data["authority_surface"]["include"].append("配置/**")

        self.assertEqual(
            parse_product_target_manifest(data).digest, UNICODE_GOLDEN_DIGEST
        )

    def test_unknown_fields_are_rejected_at_each_manifest_level(self) -> None:
        mutations = (
            ("root", lambda data: data.update(baseline={"framework": "ignored"})),
            ("target", lambda data: data["target"].update(extra="ignored")),
            (
                "authority_surface",
                lambda data: data["authority_surface"].update(extra="ignored"),
            ),
            ("mode", lambda data: data["mode"].update(extra="ignored")),
        )
        for section, mutate in mutations:
            with self.subTest(section=section):
                data = copy.deepcopy(GOLDEN_MANIFEST)
                mutate(data)
                errors = validate_product_target_manifest_dict(data)
                self.assertTrue(any("Unknown field" in error for error in errors))

    def test_manifest_version_must_be_supported_string(self) -> None:
        for version in (1.0, "2.0"):
            with self.subTest(version=version):
                data = copy.deepcopy(GOLDEN_MANIFEST)
                data["manifest_version"] = version
                errors = validate_product_target_manifest_dict(data)
                self.assertTrue(any("manifest_version" in error for error in errors))

    def test_source_type_repo_commit_and_read_only_are_strict(self) -> None:
        invalid_mutations = (
            lambda data: data["target"].update(source_type="gitlab"),
            lambda data: data["target"].update(repo="owner/repo"),
            lambda data: data["target"].update(
                repo="https://github.com/owner/repo.git"
            ),
            lambda data: data["target"].update(repo=" E:/repo "),
            lambda data: data["target"].update(commit="a" * 39),
            lambda data: data["target"].update(commit=7),
            lambda data: data["mode"].update(read_only=1),
            lambda data: data["mode"].update(read_only=False),
        )
        for mutate in invalid_mutations:
            with self.subTest(mutation=mutate):
                data = copy.deepcopy(GOLDEN_MANIFEST)
                mutate(data)
                self.assertNotEqual(validate_product_target_manifest_dict(data), [])

    def test_github_owner_repo_is_accepted(self) -> None:
        data = copy.deepcopy(GOLDEN_MANIFEST)
        data["target"].update(source_type="github", repo="Gavin0099/product-repo")

        self.assertEqual(validate_product_target_manifest_dict(data), [])

    def test_authority_surface_requires_include_and_rejects_unsafe_patterns(self) -> None:
        invalid_values = (
            [],
            "src/**",
            [""],
            ["/etc/**"],
            ["C:/src/**"],
            ["src/../secret/**"],
            ["src\\**"],
            ["src/[ab].py"],
            [" src/** "],
        )
        for include in invalid_values:
            with self.subTest(include=include):
                data = copy.deepcopy(GOLDEN_MANIFEST)
                data["authority_surface"]["include"] = include
                self.assertNotEqual(validate_product_target_manifest_dict(data), [])

    def test_exclude_must_be_a_list_when_present(self) -> None:
        data = copy.deepcopy(GOLDEN_MANIFEST)
        data["authority_surface"]["exclude"] = None

        errors = validate_product_target_manifest_dict(data)

        self.assertTrue(any("exclude must be a list" in error for error in errors))

    def test_duplicate_include_or_exclude_selectors_are_rejected(self) -> None:
        for field in ("include", "exclude"):
            with self.subTest(field=field):
                data = copy.deepcopy(GOLDEN_MANIFEST)
                data["authority_surface"][field] = ["src/**", "src/**"]
                errors = validate_product_target_manifest_dict(data)
                self.assertTrue(any("duplicate selectors" in error for error in errors))

    def test_schema_missing_required_rule_fails_closed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            schema = yaml.safe_load(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
            del schema["target"]["commit_format"]
            schema_path = Path(temp_dir) / "broken-product-schema.yaml"
            schema_path.write_text(yaml.safe_dump(schema), encoding="utf-8")

            with self.assertRaises(ProductTargetManifestValidationError):
                load_product_target_manifest_schema(schema_path)

    def test_schema_cannot_weaken_commit_or_repo_identity_rules(self) -> None:
        mutations = (
            lambda schema: schema["target"].update(commit_format=".*"),
            lambda schema: schema["target"]["repo_formats"].update(github=".*"),
            lambda schema: schema["target"].update(allowed_source_types=["local_git"]),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                with TemporaryDirectory() as temp_dir:
                    schema = yaml.safe_load(
                        DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8")
                    )
                    mutate(schema)
                    schema_path = Path(temp_dir) / "weakened-product-schema.yaml"
                    schema_path.write_text(yaml.safe_dump(schema), encoding="utf-8")

                    with self.assertRaises(ProductTargetManifestValidationError):
                        load_product_target_manifest_schema(schema_path)

    def test_yaml_duplicate_keys_fail_closed(self) -> None:
        duplicate_yaml = (
            'manifest_version: "1.0"\n'
            'manifest_version: "1.0"\n'
            'target:\n'
            '  source_type: local_git\n'
            '  repo: E:/repo\n'
            f'  commit: {"a" * 40}\n'
            'authority_surface:\n'
            '  include:\n'
            '    - src/**\n'
            'mode:\n'
            '  read_only: true\n'
        )
        with TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "duplicate-product-manifest.yaml"
            manifest_path.write_text(duplicate_yaml, encoding="utf-8")

            with self.assertRaises(ProductTargetManifestValidationError):
                parse_product_target_manifest_file(manifest_path)

    def test_direct_construction_without_admission_token_fails_closed(self) -> None:
        with self.assertRaises(ProductTargetManifestValidationError):
            ProductTargetManifest(
                manifest_version="1.0",
                target=ProductTargetSpec(
                    source_type="github",
                    repo="owner/repo",
                    commit="a" * 40,
                ),
                authority_surface=ProductAuthoritySurfaceSpec(
                    include=("src/**",),
                    exclude=(),
                ),
                mode=ProductModeSpec(read_only=True),
            )

    def test_admitted_manifest_revalidation_rejects_tampered_read_only(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)
        tampered = replace(manifest, mode=ProductModeSpec(read_only=False))

        with self.assertRaises(ProductTargetManifestValidationError):
            verify_admitted_product_target_manifest(tampered)

    def test_admitted_manifest_revalidation_rejects_tampered_uppercase_commit(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)
        tampered_target = replace(manifest.target, commit="A" * 40)
        tampered = replace(manifest, target=tampered_target)

        with self.assertRaises(ProductTargetManifestValidationError):
            verify_admitted_product_target_manifest(tampered)

    def test_admitted_manifest_revalidation_rejects_tampered_include_traversal(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)
        tampered_authority = replace(
            manifest.authority_surface, include=("../escape/**",)
        )
        tampered = replace(manifest, authority_surface=tampered_authority)

        with self.assertRaises(ProductTargetManifestValidationError):
            verify_admitted_product_target_manifest(tampered)

    def test_admitted_manifest_revalidation_rejects_tampered_manifest_version(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)
        tampered = replace(manifest, manifest_version="2.0")

        with self.assertRaises(ProductTargetManifestValidationError):
            verify_admitted_product_target_manifest(tampered)

    def test_admitted_manifest_revalidation_rejects_tampered_duplicate_include(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)
        tampered_authority = replace(
            manifest.authority_surface, include=("src/**", "src/**")
        )
        tampered = replace(manifest, authority_surface=tampered_authority)

        with self.assertRaises(ProductTargetManifestValidationError):
            verify_admitted_product_target_manifest(tampered)

    def test_admitted_manifest_revalidation_rejects_tampered_repo_format(self) -> None:
        manifest = parse_product_target_manifest(GOLDEN_MANIFEST)
        tampered_target = replace(manifest.target, repo="owner/repo")
        tampered = replace(manifest, target=tampered_target)

        with self.assertRaises(ProductTargetManifestValidationError):
            verify_admitted_product_target_manifest(tampered)


if __name__ == "__main__":
    unittest.main()