from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _markdown_tables import read_table


COLUMNS = [
    "review_id",
    "source_ref",
    "risk_category",
    "reason",
    "priority",
    "status",
    "owner",
    "review_due",
]

ALLOWED_PRIORITY = {"P0", "P1", "P2", "P3"}
ALLOWED_STATUS = {
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
        prefix = f"row {number} ({row.get('review_id') or 'missing id'})"
        for column in COLUMNS:
            if not row[column]:
                errors.append(f"{prefix}: missing {column}")
        if row["priority"] not in ALLOWED_PRIORITY:
            errors.append(f"{prefix}: invalid priority {row['priority']!r}")
        if row["status"] not in ALLOWED_STATUS:
            errors.append(f"{prefix}: invalid status {row['status']!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        print("review_queue: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("review_queue: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
