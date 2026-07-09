from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from _markdown_tables import read_table


QUEUE_COLUMNS = [
    "review_id",
    "source_ref",
    "risk_category",
    "reason",
    "priority",
    "status",
    "owner",
    "review_due",
]


def collect_due(root: Path, today: date) -> list[dict[str, str]]:
    due: list[dict[str, str]] = []
    for path in root.rglob("review-queue.md"):
        for row in read_table(path, QUEUE_COLUMNS):
            if row["status"] in {"accepted", "rejected"}:
                continue
            try:
                review_due = date.fromisoformat(row["review_due"])
            except ValueError:
                row = dict(row)
                row["file"] = str(path)
                row["due_state"] = "invalid_date"
                due.append(row)
                continue
            if review_due <= today:
                row = dict(row)
                row["file"] = str(path)
                row["due_state"] = "due" if review_due == today else "overdue"
                due.append(row)
    return due


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()
    today = date.fromisoformat(args.today)
    rows = collect_due(args.root, today)
    print("| file | review_id | priority | status | review_due | due_state |")
    print("| --- | --- | --- | --- | --- | --- |")
    for row in rows:
        print(
            f"| {row['file']} | {row['review_id']} | {row['priority']} | "
            f"{row['status']} | {row['review_due']} | {row['due_state']} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
