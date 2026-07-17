from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _markdown_tables import read_table
from _schema_rules import load_schema, require_fields, string_list


DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "review-queue.schema.yaml"


def validate(path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    schema = load_schema(schema_path, "review-queue")
    required_fields = string_list(schema, "required_fields")
    require_fields("review-queue", required_fields, {"review_id", "priority", "status"})
    allowed_priority = set(string_list(schema, "allowed_priority"))
    allowed_status = set(string_list(schema, "allowed_status"))

    errors: list[str] = []
    rows = read_table(path, required_fields)
    for number, row in enumerate(rows, start=1):
        prefix = f"row {number} ({row.get('review_id') or 'missing id'})"
        for column in required_fields:
            if not row[column]:
                errors.append(f"{prefix}: missing {column}")
        if row["priority"] not in allowed_priority:
            errors.append(f"{prefix}: invalid priority {row['priority']!r}")
        if row["status"] not in allowed_status:
            errors.append(f"{prefix}: invalid status {row['status']!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        errors = validate(args.path, args.schema)
    except (OSError, ValueError) as exc:
        print("review_queue: FAIL")
        print(f"- schema/table error: {exc}")
        return 1
    if errors:
        print("review_queue: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("review_queue: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
