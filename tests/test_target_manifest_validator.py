from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.validate_target_manifest import (
    DEFAULT_SCHEMA_PATH,
    TargetManifest,
    TargetManifestValidationError,
    load_manifest_schema,
    parse_target_manifest,
    validate_target_manifest_dict,
    validate_target_manifest_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_MANIFEST_PATH = REPO_ROOT / "fixtures" / "s1" / "sample-target-manifest.yaml"


class TargetManifestValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.maxDiff = None
        with open(SAMPLE_MANIFEST_PATH, "r", encoding="utf-8") as f:
            self.valid_manifest = yaml.safe_load(f)
        with open(DEFAULT_SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.valid_schema = yaml.safe_load(f)

    def test_sample_manifest_passes(self) -> None:
        errors = validate_target_manifest_dict(self.valid_manifest)
        self.assertEqual(errors, [])
        # 測試檔案讀取驗證
        file_errors = validate_target_manifest_file(SAMPLE_MANIFEST_PATH)
        self.assertEqual(file_errors, [])

    def test_parse_target_manifest_returns_domain_model(self) -> None:
        manifest = parse_target_manifest(self.valid_manifest)
        self.assertIsInstance(manifest, TargetManifest)
        self.assertEqual(manifest.target.source_type, "local_git")
        self.assertEqual(manifest.target.repo, "E:/Company/company-software-ssdlc")
        self.assertEqual(manifest.target.commit, "83da91f456789abcdef0123456789abcdef01234")
        self.assertEqual(manifest.authority_surface.include, ("policy/**", "process/**", "templates/**"))
        self.assertEqual(manifest.authority_surface.exclude, ("archive/**", "drafts/**", "examples/**"))
        self.assertEqual(manifest.baseline.framework, "NIST_SP_800_218")
        self.assertEqual(manifest.baseline.version, "1.1")
        self.assertTrue(manifest.mode.read_only)

    def test_missing_required_sections(self) -> None:
        for section in ["target", "authority_surface", "baseline", "mode"]:
            with self.subTest(section=section):
                data = dict(self.valid_manifest)
                del data[section]
                errors = validate_target_manifest_dict(data)
                self.assertTrue(any(f"Missing required section: '{section}'" in err for err in errors))

    def test_target_missing_or_empty_repo(self) -> None:
        # missing repo
        data = dict(self.valid_manifest)
        data["target"] = dict(self.valid_manifest["target"])
        del data["target"]["repo"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Missing required field 'repo'" in err for err in errors))

        # empty repo
        data["target"]["repo"] = "   "
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("cannot be empty" in err for err in errors))

    def test_target_source_type_and_repo_syntax_binding(self) -> None:
        # missing source_type
        data = dict(self.valid_manifest)
        data["target"] = dict(self.valid_manifest["target"])
        del data["target"]["source_type"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Missing required field 'source_type'" in err for err in errors))

        # unsupported source_type
        data["target"]["source_type"] = "gitlab_api"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("is not supported; allowed types" in err for err in errors))

        # github with invalid local path format fails closed
        data["target"]["source_type"] = "github"
        data["target"]["repo"] = "E:/Company/company-software-ssdlc"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("must match 'owner/repo' format" in err for err in errors))

        # github with valid owner/repo passes
        data["target"]["source_type"] = "github"
        data["target"]["repo"] = "Gavin0099/company-software-ssdlc"
        errors = validate_target_manifest_dict(data)
        self.assertEqual(errors, [])

        # local_git with owner/repo format fails closed
        data["target"]["source_type"] = "local_git"
        data["target"]["repo"] = "Gavin0099/company-software-ssdlc"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("is invalid for source_type 'local_git'" in err for err in errors))

        # local_git with path passes
        data["target"]["source_type"] = "local_git"
        data["target"]["repo"] = "E:/Company/company-software-ssdlc"
        errors = validate_target_manifest_dict(data)
        self.assertEqual(errors, [])

    def test_target_invalid_commit_format(self) -> None:
        invalid_commits = [
            "main",
            "HEAD",
            "83da91f",  # 7-char short hash
            "83da91f456789abcdef0123456789abcdef0123g",  # non-hex char 'g'
            "83da91f456789abcdef0123456789abcdef012345",  # 42 chars
            1234567890123456789012345678901234567890,  # non-string
        ]
        for commit in invalid_commits:
            with self.subTest(commit=commit):
                data = dict(self.valid_manifest)
                data["target"] = dict(self.valid_manifest["target"])
                data["target"]["commit"] = commit
                errors = validate_target_manifest_dict(data)
                self.assertTrue(any("must be a full 40-character hexadecimal SHA" in err for err in errors))

    def test_authority_surface_include_requirements(self) -> None:
        # missing include
        data = dict(self.valid_manifest)
        data["authority_surface"] = dict(self.valid_manifest["authority_surface"])
        del data["authority_surface"]["include"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Missing required field 'include'" in err for err in errors))

        # empty include list
        data["authority_surface"]["include"] = []
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Field 'include' must be a non-empty list" in err for err in errors))

        # include is not a list
        data["authority_surface"]["include"] = "policy/**"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Field 'include' must be a non-empty list" in err for err in errors))

    def test_authority_surface_glob_boundaries(self) -> None:
        # backslash fails
        data = dict(self.valid_manifest)
        data["authority_surface"] = dict(self.valid_manifest["authority_surface"])
        data["authority_surface"]["include"] = ["policy\\**"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("contains backslash" in err for err in errors))

        # unix absolute path fails
        data["authority_surface"]["include"] = ["/etc/policy/**"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("absolute paths prohibited" in err for err in errors))

        # windows drive absolute path fails
        data["authority_surface"]["include"] = ["C:/policy/**"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("absolute paths prohibited" in err for err in errors))

        # directory traversal '..' fails
        data["authority_surface"]["include"] = ["policy/../secret/**"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("contains parent traversal" in err for err in errors))

    def test_authority_surface_exclude_optional_and_valid(self) -> None:
        # without exclude is valid
        data = dict(self.valid_manifest)
        data["authority_surface"] = dict(self.valid_manifest["authority_surface"])
        del data["authority_surface"]["exclude"]
        errors = validate_target_manifest_dict(data)
        self.assertEqual(errors, [])

        # exclude is not a list
        data["authority_surface"]["exclude"] = "archive/**"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Field 'exclude' must be a list of strings" in err for err in errors))

        # exclude with invalid glob fails
        data["authority_surface"]["exclude"] = ["../outside/**"]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("contains parent traversal" in err for err in errors))

    def test_baseline_strict_string_type_and_numeric_fails(self) -> None:
        # YAML float 1.1 fails closed
        data = dict(self.valid_manifest)
        data["baseline"] = dict(self.valid_manifest["baseline"])
        data["baseline"]["version"] = 1.1  # float, not quoted string
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("must be a quoted string (got float" in err for err in errors))

        # YAML int 1 fails closed
        data["baseline"]["version"] = 1
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("must be a quoted string (got int" in err for err in errors))

    def test_baseline_framework_and_version_support(self) -> None:
        # invalid framework
        data = dict(self.valid_manifest)
        data["baseline"] = dict(self.valid_manifest["baseline"])
        data["baseline"]["framework"] = "ISO_27001"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Framework 'ISO_27001' is not supported" in err for err in errors))

        # invalid version string
        data["baseline"]["framework"] = "NIST_SP_800_218"
        data["baseline"]["version"] = "2.0"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Version '2.0' is not supported" in err for err in errors))

    def test_mode_read_only_enforcement(self) -> None:
        # read_only false
        data = dict(self.valid_manifest)
        data["mode"] = dict(self.valid_manifest["mode"])
        data["mode"]["read_only"] = False
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("mode.read_only must be boolean True" in err for err in errors))

        # read_only non-boolean string "true"
        data["mode"]["read_only"] = "true"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("mode.read_only must be boolean True" in err for err in errors))

    def test_schema_missing_required_definitions_fails_closed(self) -> None:
        # Verify schema itself fails closed if required definitions are missing
        rules_to_delete = [
            ("target", "commit_format"),
            ("target", "allowed_source_types"),
            ("target", "repo_formats"),
            ("authority_surface", "disallow_absolute_paths"),
            ("authority_surface", "disallow_parent_traversal"),
            ("authority_surface", "path_separator"),
            ("baseline", "allowed_versions"),
            ("mode", "required_values"),
        ]
        for section, key in rules_to_delete:
            with self.subTest(section=section, key=key):
                with TemporaryDirectory() as tmpdir:
                    bad_schema = dict(self.valid_schema)
                    bad_schema[section] = dict(self.valid_schema[section])
                    del bad_schema[section][key]
                    bad_schema_path = Path(tmpdir) / "broken-schema.yaml"
                    bad_schema_path.write_text(yaml.safe_dump(bad_schema), encoding="utf-8")

                    with self.assertRaises(TargetManifestValidationError):
                        load_manifest_schema(bad_schema_path)

    def test_cli_invocation_passes(self) -> None:
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "validate_target_manifest.py"), str(SAMPLE_MANIFEST_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)

    def test_cli_invocation_manifest_fails_gracefully(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad-manifest.yaml"
            bad_file.write_text("target:\n  repo: test\n", encoding="utf-8")
            res = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "validate_target_manifest.py"), str(bad_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("[FAIL] Target manifest validation failed", res.stderr)

    def test_cli_invocation_schema_error_fails_gracefully(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bad_schema = Path(tmpdir) / "corrupt-schema.yaml"
            bad_schema.write_text("schema_name: wrong-name\n", encoding="utf-8")
            res = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "validate_target_manifest.py"),
                    str(SAMPLE_MANIFEST_PATH),
                    "--schema",
                    str(bad_schema),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("[FAIL] Target manifest schema error", res.stderr)

    def test_local_git_repo_url_schemes_prohibited(self) -> None:
        url_schemes = [
            "https://github.com/Gavin0099/company-software-ssdlc.git",
            "http://gitlab.internal/group/repo",
            "git@github.com:Gavin0099/company-software-ssdlc.git",
            "ssh://git@host.com/project/repo.git",
            "git://github.com/project/repo.git",
        ]
        for url in url_schemes:
            with self.subTest(url=url):
                data = dict(self.valid_manifest)
                data["target"] = dict(self.valid_manifest["target"])
                data["target"]["source_type"] = "local_git"
                data["target"]["repo"] = url
                errors = validate_target_manifest_dict(data)
                self.assertTrue(
                    any("is invalid for source_type 'local_git'" in err for err in errors),
                    f"Expected rejection for URL scheme repo {url!r}, got: {errors}",
                )

    def test_schema_malformed_regex_fails_closed(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bad_schema = dict(self.valid_schema)
            bad_schema["target"] = dict(self.valid_schema["target"])
            bad_schema["target"]["commit_format"] = "[0-9"  # invalid regex
            bad_schema_path = Path(tmpdir) / "broken-regex-schema.yaml"
            bad_schema_path.write_text(yaml.safe_dump(bad_schema), encoding="utf-8")

            with self.assertRaises(TargetManifestValidationError) as ctx:
                load_manifest_schema(bad_schema_path)
            self.assertIn("invalid regular expression", str(ctx.exception).lower())

    def test_schema_malformed_boolean_flag_fails_closed(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bad_schema = dict(self.valid_schema)
            bad_schema["authority_surface"] = dict(self.valid_schema["authority_surface"])
            bad_schema["authority_surface"]["disallow_absolute_paths"] = "true"  # string, not bool
            bad_schema_path = Path(tmpdir) / "broken-bool-schema.yaml"
            bad_schema_path.write_text(yaml.safe_dump(bad_schema), encoding="utf-8")

            with self.assertRaises(TargetManifestValidationError) as ctx:
                load_manifest_schema(bad_schema_path)
            self.assertIn("must be boolean", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
