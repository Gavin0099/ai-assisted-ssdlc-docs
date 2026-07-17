from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "security-decision-validation"
SECURITY_SCHEMA = ROOT / "schemas" / "security-decision.schema.yaml"
CONTROL_SCHEMA = ROOT / "schemas" / "control-mapping.schema.yaml"


def run_validator(
    fixture: str,
    schema: Path | None = None,
    control_schema: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ROOT / "tools" / "validate_security_decision.py"),
        str(FIXTURES / fixture),
    ]
    if schema is not None:
        command.extend(["--schema", str(schema)])
    if control_schema is not None:
        command.extend(["--control-schema", str(control_schema)])
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


class SecurityDecisionValidatorTests(unittest.TestCase):
    def test_valid_fixture_passes(self) -> None:
        result = run_validator("valid.md")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("security_decision: PASS", result.stdout)

    def test_forbidden_claim_outside_boundary_fails_even_when_boundary_repeats_it(
        self,
    ) -> None:
        result = run_validator("forbidden-claim-outside-boundary.md")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "forbidden claim appears outside Cannot Claim boundary: compliant",
            result.stdout,
        )

    def test_invalid_control_status_fails(self) -> None:
        result = run_validator("invalid-control-status.md")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Control Mapping row 1: invalid status 'implmented'", result.stdout)

    def test_zero_control_rows_fail(self) -> None:
        result = run_validator("zero-control-rows.md")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(
            "Control Mapping table must contain at least one data row", result.stdout
        )

    def test_missing_control_evidence_fails(self) -> None:
        result = run_validator("missing-control-evidence.md")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("Control Mapping row 1: missing evidence", result.stdout)

    def test_noncanonical_dates_fail_closed(self) -> None:
        cases = (
            ("compact-date.md", "invalid created '20260717'"),
            ("week-date.md", "invalid review_due '2026-W42-6'"),
        )
        for fixture, message in cases:
            with self.subTest(fixture=fixture):
                result = run_validator(fixture)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn(message, result.stdout)
            self.assertIn("expected YYYY-MM-DD", result.stdout)

    def test_custom_control_schema_changes_outcome(self) -> None:
        schema_text = CONTROL_SCHEMA.read_text(encoding="utf-8").replace(
            "  - accepted_exception\n", "  - accepted_exception\n  - implmented\n", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            custom_schema = Path(directory) / "control-mapping.schema.yaml"
            custom_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator(
                "invalid-control-status.md", control_schema=custom_schema
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("security_decision: PASS", result.stdout)

    def test_security_schema_condition_outside_allowed_enum_fails_before_rows(
        self,
    ) -> None:
        schema_text = SECURITY_SCHEMA.read_text(encoding="utf-8").replace(
            "review_due_required_when:\n  - pending\n",
            "review_due_required_when:\n  - pendng\n",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            invalid_schema = Path(directory) / "security-decision.schema.yaml"
            invalid_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator("zero-control-rows.md", schema=invalid_schema)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("contains values outside the allowed enum: pendng", result.stdout)
        self.assertNotIn("at least one data row", result.stdout)

    def test_control_schema_missing_validator_field_fails_closed(self) -> None:
        schema_text = CONTROL_SCHEMA.read_text(encoding="utf-8").replace(
            "  - status\n", "", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            incomplete_schema = Path(directory) / "control-mapping.schema.yaml"
            incomplete_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator("valid.md", control_schema=incomplete_schema)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing validator fields: status", result.stdout)


if __name__ == "__main__":
    unittest.main()
