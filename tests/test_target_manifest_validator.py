from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

# 引入即將實作的驗證器函數與模型
from tools.validate_target_manifest import (
    TargetManifestValidationError,
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
        self.assertTrue(any("Field 'repo' cannot be empty" in err for err in errors))

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

        # include contains non-string or blank items
        data["authority_surface"]["include"] = ["policy/**", "  ", 123]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Item in 'include' must be a non-blank string" in err for err in errors))

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

        # exclude contains non-string or blank
        data["authority_surface"]["exclude"] = ["archive/**", ""]
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("Item in 'exclude' must be a non-blank string" in err for err in errors))

    def test_baseline_validation(self) -> None:
        # invalid framework
        data = dict(self.valid_manifest)
        data["baseline"] = dict(self.valid_manifest["baseline"])
        data["baseline"]["framework"] = "ISO_27001"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("allowed frameworks" in err for err in errors))

        # invalid version
        data["baseline"]["framework"] = "NIST_SP_800_218"
        data["baseline"]["version"] = "2.0"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("allowed versions" in err for err in errors))

    def test_mode_read_only_enforcement(self) -> None:
        # read_only false
        data = dict(self.valid_manifest)
        data["mode"] = dict(self.valid_manifest["mode"])
        data["mode"]["read_only"] = False
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("mode.read_only must be true" in err for err in errors))

        # read_only non-boolean
        data["mode"]["read_only"] = "true"
        errors = validate_target_manifest_dict(data)
        self.assertTrue(any("mode.read_only must be true" in err for err in errors))

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
