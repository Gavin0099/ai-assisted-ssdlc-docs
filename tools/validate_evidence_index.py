from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _markdown_tables import read_table
from _schema_rules import condition_matches, load_schema, require_fields, string_list


DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "evidence-record.schema.yaml"


def validate(path: Path, schema_path: Path = DEFAULT_SCHEMA) -> list[str]:
    schema = load_schema(schema_path, "evidence-record")
    required_fields = string_list(schema, "required_fields")
    require_fields(
        "evidence-record", required_fields, {"evidence_id", "strength", "review_status"}
    )
    allowed_strength = set(string_list(schema, "allowed_strength"))
    allowed_review_status = set(string_list(schema, "allowed_review_status"))
    columns = list(required_fields)
    if "review_due" not in columns:
        columns.append("review_due")

    errors: list[str] = []
    rows = read_table(path, columns)
    for number, row in enumerate(rows, start=1):
        prefix = f"row {number} ({row.get('evidence_id') or 'missing id'})"
        for column in required_fields:
            if not row[column]:
                errors.append(f"{prefix}: missing {column}")
        if row["strength"] not in allowed_strength:
            errors.append(f"{prefix}: invalid strength {row['strength']!r}")
        if row["review_status"] not in allowed_review_status:
            errors.append(f"{prefix}: invalid review_status {row['review_status']!r}")
        if condition_matches(row, schema, "review_due_required_when") and not row["review_due"]:
            errors.append(f"{prefix}: review_due required for weak or open evidence")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        errors = validate(args.path, args.schema)
    except (OSError, ValueError) as exc:
        print("evidence_index: FAIL")
        print(f"- schema/table error: {exc}")
        return 1
    if errors:
        print("evidence_index: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("evidence_index: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
