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

    def test_target_source_type_validation(self) -> None:
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

        # valid github source_type
        data["target"]["source_type"] = "github"
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

    def test_schema_missing_raises_validation_error(self) -> None:
        with self.assertRaises(TargetManifestValidationError):
            validate_target_manifest_file(SAMPLE_MANIFEST_PATH, schema_path=Path("nonexistent-schema.yaml"))

    def test_cli_invocation_passes(self) -> None:
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "tools" / "validate_target_manifest.py"), str(SAMPLE_MANIFEST_PATH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)

    def test_cli_invocation_fails(self) -> None:
        with TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad-manifest.yaml"
            bad_file.write_text("target:\n  repo: test\n", encoding="utf-8")
            res = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "validate_target_manifest.py"), str(bad_file)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 1)
            self.assertIn("FAIL", res.stderr)


if __name__ == "__main__":
    unittest.main()
