from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _markdown_tables import read_table


COLUMNS = [
    "evidence_id",
    "source_ref",
    "artifact_type",
    "supports_claim",
    "strength",
    "review_status",
    "review_due",
]

ALLOWED_STRENGTH = {"strong", "medium", "weak"}
ALLOWED_REVIEW_STATUS = {
    "pending",
    "needs_changes",
    "accepted",
    "accepted_with_review_due",
    "deferred",
    "rejected",
}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    rows = read_table(path, COLUMNS)
    for number, row in enumerate(rows, start=1):
        prefix = f"row {number} ({row.get('evidence_id') or 'missing id'})"
        for column in COLUMNS[:-1]:
            if not row[column]:
                errors.append(f"{prefix}: missing {column}")
        if row["strength"] not in ALLOWED_STRENGTH:
            errors.append(f"{prefix}: invalid strength {row['strength']!r}")
        if row["review_status"] not in ALLOWED_REVIEW_STATUS:
            errors.append(f"{prefix}: invalid review_status {row['review_status']!r}")
        if (row["strength"] == "weak" or row["review_status"] in {"pending", "needs_changes", "accepted_with_review_due", "deferred"}) and not row["review_due"]:
            errors.append(f"{prefix}: review_due required for weak or open evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        print("evidence_index: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("evidence_index: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
