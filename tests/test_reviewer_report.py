from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "reviewer-report"
PACKAGE = FIXTURE_ROOT / "package"


def run_report(package: Path, today: str = "2026-07-17") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "generate_reviewer_report.py"),
            str(package),
            "--today",
            today,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class ReviewerReportTests(unittest.TestCase):
    def test_valid_package_matches_locked_markdown_contract(self) -> None:
        result = run_report(PACKAGE)
        expected = (FIXTURE_ROOT / "expected-report.md").read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, expected)
        self.assertEqual(result.stderr, "")
        self.assertNotIn(str(PACKAGE.resolve()), result.stdout)

    def test_invalid_queue_fails_without_partial_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_package = Path(directory) / "package"
            shutil.copytree(PACKAGE, temp_package)
            queue_path = temp_package / "review-queue.md"
            queue_path.write_text(
                queue_path.read_text(encoding="utf-8").replace("| P0 |", "| P9 |", 1),
                encoding="utf-8",
            )
            result = run_report(temp_package)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("invalid priority 'P9'", result.stderr)

    def test_invalid_review_due_fails_without_partial_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_package = Path(directory) / "package"
            shutil.copytree(PACKAGE, temp_package)
            queue_path = temp_package / "review-queue.md"
            queue_path.write_text(
                queue_path.read_text(encoding="utf-8").replace(
                    "2026-07-18", "2026-99-99", 1
                ),
                encoding="utf-8",
            )
            result = run_report(temp_package)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("invalid review_due '2026-99-99'", result.stderr)

    def test_missing_input_fails_without_partial_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_package = Path(directory) / "package"
            shutil.copytree(PACKAGE, temp_package)
            (temp_package / "evidence-index.md").unlink()
            result = run_report(temp_package)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("evidence-index.md", result.stderr)

    def test_terminal_rows_render_plain_language_empty_states(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp_package = Path(directory) / "package"
            shutil.copytree(PACKAGE, temp_package)
            queue_path = temp_package / "review-queue.md"
            queue_text = queue_path.read_text(encoding="utf-8")
            for status in ("pending", "needs_changes", "accepted_with_review_due"):
                queue_text = queue_text.replace(f"| {status} |", "| accepted |")
            queue_path.write_text(queue_text, encoding="utf-8")

            evidence_path = temp_package / "evidence-index.md"
            evidence_text = evidence_path.read_text(encoding="utf-8")
            evidence_text = evidence_text.replace("| weak | pending |", "| strong | accepted |")
            evidence_text = evidence_text.replace(
                "| medium | accepted_with_review_due |", "| medium | accepted |"
            )
            evidence_path.write_text(evidence_text, encoding="utf-8")
            result = run_report(temp_package)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- review_queue_attention: 0", result.stdout)
        self.assertIn("- evidence_attention: 0", result.stdout)
        self.assertIn("No Review Queue rows require attention.", result.stdout)
        self.assertIn("No Evidence Index rows require attention.", result.stdout)
        self.assertIn("No queue-to-evidence correlation or closure is proven.", result.stdout)


if __name__ == "__main__":
    unittest.main()
