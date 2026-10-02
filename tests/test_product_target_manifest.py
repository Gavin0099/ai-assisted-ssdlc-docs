from __future__ import annotations

import copy
import traceback
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.validate_product_target_manifest import (
    DEFAULT_SCHEMA_PATH,
    ProductTargetManifestValidationError,
    load_product_target_manifest_schema,
    parse_product_target_manifest,
    parse_product_target_manifest_file,
    validate_product_target_manifest_dict,
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

    def test_manifest_parser_failure_has_no_source_bearing_chain(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid.yaml"
            path.write_text("manifest_version: [\nSYNTHETIC_PRIVATE_MANIFEST", encoding="utf-8")
            try:
                parse_product_target_manifest_file(path)
            except ProductTargetManifestValidationError as error:
                self.assertNotIn("SYNTHETIC_PRIVATE_MANIFEST", "".join(traceback.format_exception(error)))
            else:
                self.fail("Malformed manifest admitted")

    def test_schema_integer_one_cannot_replace_required_boolean(self) -> None:
        with TemporaryDirectory() as temp_dir:
            data = yaml.safe_load(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8"))
            data["mode"]["required_values"]["read_only"] = 1
            path = Path(temp_dir) / "bad-schema.yaml"
            path.write_text(yaml.safe_dump(data), encoding="utf-8")
            with self.assertRaises(ProductTargetManifestValidationError):
                load_product_target_manifest_schema(path)

    def test_scalar_tags_cannot_use_legacy_mapping_as_scalar_bypass(self) -> None:
        template = ('manifest_version: VERSION\ntarget:\n  source_type: local_git\n'
                    '  repo: E:/repo\n  commit: "' + 'a' * 40 + '"\n'
                    'authority_surface:\n  include: [src/**]\nmode:\n  read_only: MODE\n')
        for version, mode in (( '!!str {=: !custom "1.0"}', 'true'),
                              ('"1.0"', '!!bool {=: true}')):
            with self.subTest(version=version, mode=mode), TemporaryDirectory() as root:
                path = Path(root) / "tagged.yaml"
                path.write_text(template.replace("VERSION", version).replace("MODE", mode), encoding="utf-8")
                with self.assertRaises(ProductTargetManifestValidationError):
                    parse_product_target_manifest_file(path)

    def test_dict_validator_rejects_invalid_unicode_and_nul_like_parser(self) -> None:
        for field, value in (("include", "src/\x00file"), ("include", "src/\ud800file"),
                             ("repo", "C:/synthetic\x00root"), ("repo", "C:/synthetic\ud800root")):
            with self.subTest(field=field, value=repr(value)):
                data = copy.deepcopy(GOLDEN_MANIFEST)
                if field == "include":
                    data["authority_surface"]["include"] = [value]
                else:
                    data["target"]["repo"] = value
                self.assertTrue(validate_product_target_manifest_dict(data))
                with self.assertRaises(ProductTargetManifestValidationError):
                    parse_product_target_manifest(data)


if __name__ == "__main__":
    unittest.main()
