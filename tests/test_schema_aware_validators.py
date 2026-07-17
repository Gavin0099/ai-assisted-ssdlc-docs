from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "schema-validation"


def run_validator(
    tool: str, fixture: str, schema: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return run_validator_path(tool, FIXTURES / fixture, schema)


def run_validator_path(
    tool: str, artifact: Path, schema: Path | None = None
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / "tools" / tool), str(artifact)]
    if schema is not None:
        command.extend(["--schema", str(schema)])
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


class SchemaAwareValidatorTests(unittest.TestCase):
    def test_valid_evidence_fixture_passes(self) -> None:
        result = run_validator("validate_evidence_index.py", "evidence-valid.md")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("evidence_index: PASS", result.stdout)

    def test_invalid_evidence_strength_fails(self) -> None:
        result = run_validator("validate_evidence_index.py", "evidence-invalid.md")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("invalid strength 'experimental'", result.stdout)

    def test_valid_review_queue_fixture_passes(self) -> None:
        result = run_validator("validate_review_queue.py", "review-queue-valid.md")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("review_queue: PASS", result.stdout)

    def test_invalid_review_priority_fails(self) -> None:
        result = run_validator("validate_review_queue.py", "review-queue-invalid.md")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("invalid priority 'P9'", result.stdout)

    def test_custom_schema_changes_evidence_outcome(self) -> None:
        default_schema = ROOT / "schemas" / "evidence-record.schema.yaml"
        schema_text = default_schema.read_text(encoding="utf-8").replace(
            "  - weak\n", "  - weak\n  - experimental\n", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            custom_schema = Path(directory) / "evidence-record.schema.yaml"
            custom_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator(
                "validate_evidence_index.py", "evidence-invalid.md", custom_schema
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("evidence_index: PASS", result.stdout)

    def test_malformed_schema_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            malformed_schema = Path(directory) / "evidence-record.schema.yaml"
            malformed_schema.write_text(
                "schema_name: evidence-record\n"
                "required_fields:\n"
                "  - evidence_id\n"
                "  - source_ref\n"
                "  - artifact_type\n"
                "  - supports_claim\n"
                "  - strength\n"
                "  - review_status\n",
                encoding="utf-8",
            )
            result = run_validator(
                "validate_evidence_index.py", "evidence-valid.md", malformed_schema
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("schema key 'allowed_strength'", result.stdout)

    def test_schema_missing_validator_field_fails_closed(self) -> None:
        default_schema = ROOT / "schemas" / "evidence-record.schema.yaml"
        schema_text = default_schema.read_text(encoding="utf-8").replace(
            "  - strength\n", "", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            incomplete_schema = Path(directory) / "evidence-record.schema.yaml"
            incomplete_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator(
                "validate_evidence_index.py", "evidence-valid.md", incomplete_schema
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("missing validator fields: strength", result.stdout)

    def test_schema_condition_unknown_field_fails_closed(self) -> None:
        default_schema = ROOT / "schemas" / "evidence-record.schema.yaml"
        schema_text = default_schema.read_text(encoding="utf-8").replace(
            "  strength:\n", "  strenght:\n", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            invalid_schema = Path(directory) / "evidence-record.schema.yaml"
            invalid_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator(
                "validate_evidence_index.py", "evidence-valid.md", invalid_schema
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("references unknown field 'strenght'", result.stdout)

    def test_schema_condition_value_outside_allowed_enum_fails_closed(self) -> None:
        default_schema = ROOT / "schemas" / "evidence-record.schema.yaml"
        schema_text = default_schema.read_text(encoding="utf-8").replace(
            "review_due_required_when:\n  strength:\n    - weak\n",
            "review_due_required_when:\n  strength:\n    - wek\n",
            1,
        )
        with tempfile.TemporaryDirectory() as directory:
            invalid_schema = Path(directory) / "evidence-record.schema.yaml"
            invalid_schema.write_text(schema_text, encoding="utf-8")
            result = run_validator(
                "validate_evidence_index.py", "evidence-valid.md", invalid_schema
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("contains values outside the allowed enum: wek", result.stdout)

    def test_schema_condition_validation_runs_for_zero_row_table(self) -> None:
        default_schema = ROOT / "schemas" / "evidence-record.schema.yaml"
        schema_text = default_schema.read_text(encoding="utf-8").replace(
            "  strength:\n", "  strenght:\n", 1
        )
        with tempfile.TemporaryDirectory() as directory:
            temp_dir = Path(directory)
            invalid_schema = temp_dir / "evidence-record.schema.yaml"
            invalid_schema.write_text(schema_text, encoding="utf-8")
            empty_artifact = temp_dir / "evidence-empty.md"
            empty_artifact.write_text(
                "| evidence_id | source_ref | artifact_type | supports_claim | "
                "strength | review_status | review_due |\n"
                "| --- | --- | --- | --- | --- | --- | --- |\n",
                encoding="utf-8",
            )
            result = run_validator_path(
                "validate_evidence_index.py", empty_artifact, invalid_schema
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("references unknown field 'strenght'", result.stdout)


if __name__ == "__main__":
    unittest.main()
