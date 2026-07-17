from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from _markdown_tables import read_table
from _strict_dates import parse_strict_date


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
TERMINAL_STATUSES = {"accepted", "rejected"}


def collect_due(root: Path, today: date) -> list[dict[str, str]]:
    due: list[dict[str, str]] = []
    paths = sorted(root.rglob("review-queue.md"), key=lambda item: item.as_posix())
    for path in paths:
        for row in read_table(path, QUEUE_COLUMNS):
            identifier = row.get("review_id") or "missing id"
            review_due = parse_strict_date(
                row["review_due"], f"{path} ({identifier})", "review_due"
            )
            if row["status"] in TERMINAL_STATUSES:
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
    try:
        today = parse_strict_date(args.today, "command line", "--today")
        rows = collect_due(args.root, today)
    except (OSError, ValueError) as exc:
        print("due_reviews: FAIL", file=sys.stderr)
        for line in str(exc).splitlines():
            print(f"- {line}", file=sys.stderr)
        return 1
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
