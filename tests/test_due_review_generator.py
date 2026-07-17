from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "due-review-dates"


def run_generator(fixture: str, today: str = "2026-07-17") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "generate_due_reviews.py"),
            str(FIXTURES / fixture),
            "--today",
            today,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class DueReviewGeneratorTests(unittest.TestCase):
    def test_canonical_dates_render_due_nonterminal_rows(self) -> None:
        result = run_generator("valid")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("| REV-DUE-001 | P1 | pending | 2026-07-17 | due |", result.stdout)
        self.assertNotIn("REV-DUE-002", result.stdout)

    def test_noncanonical_review_due_formats_fail_without_partial_report(self) -> None:
        cases = (
            ("compact-date", "20260717"),
            ("week-date", "2026-W29-5"),
        )
        for fixture, value in cases:
            with self.subTest(value=value):
                result = run_generator(fixture)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn(f"invalid review_due {value!r}", result.stderr)
            self.assertIn("expected YYYY-MM-DD", result.stderr)

    def test_invalid_terminal_row_date_fails_before_status_filtering(self) -> None:
        result = run_generator("invalid-calendar-date")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("REV-DUE-CALENDAR", result.stderr)
        self.assertIn("invalid review_due '2026-02-30'", result.stderr)

    def test_noncanonical_today_formats_fail_without_partial_report(self) -> None:
        for value in ("20260717", "2026-W29-5"):
            with self.subTest(value=value):
                result = run_generator("valid", today=value)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn(f"invalid --today {value!r}", result.stderr)
            self.assertIn("expected YYYY-MM-DD", result.stderr)


if __name__ == "__main__":
    unittest.main()
