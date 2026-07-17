from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from _schema_rules import load_schema, require_fields, string_list


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = ROOT / "schemas" / "security-decision.schema.yaml"
DEFAULT_CONTROL_SCHEMA = ROOT / "schemas" / "control-mapping.schema.yaml"


def validate(
    path: Path,
    schema_path: Path = DEFAULT_SCHEMA,
    control_schema_path: Path = DEFAULT_CONTROL_SCHEMA,
) -> list[str]:
    rules = _load_rules(schema_path, control_schema_path)
    text = path.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    errors: list[str] = []

    required_frontmatter = rules["required_frontmatter"]
    for field in required_frontmatter:
        if field not in frontmatter:
            errors.append(f"missing frontmatter field: {field}")
        elif field != "review_due" and _empty(frontmatter[field]):
            errors.append(f"empty frontmatter field: {field}")

    status = _scalar(frontmatter.get("status"))
    if status and status not in rules["allowed_status"]:
        errors.append(f"invalid status: {status!r}")

    review_due = _scalar(frontmatter.get("review_due"))
    if status in rules["review_due_required_when"] and not review_due:
        errors.append(f"review_due required for status {status!r}")

    for field in rules["date_fields"]:
        value = _scalar(frontmatter.get(field))
        if value:
            _validate_strict_date(value, field, errors)

    for section in rules["required_sections"]:
        if _section_span(text, section) is None:
            errors.append(f"missing section: {section}")

    cannot_claim = _section(text, "Cannot Claim")
    if not cannot_claim.strip():
        errors.append("Cannot Claim section is empty")

    outside_boundary = _without_section(text, "Cannot Claim").casefold()
    for claim in rules["forbidden_claims"]:
        if claim.casefold() in outside_boundary:
            errors.append(
                f"forbidden claim appears outside Cannot Claim boundary: {claim}"
            )

    control_section = _section(text, "Control Mapping")
    if control_section:
        rows = _control_rows(control_section, rules["control_required_fields"])
        if not rows:
            errors.append("Control Mapping table must contain at least one data row")
        for number, row in enumerate(rows, start=1):
            prefix = f"Control Mapping row {number}"
            for field in rules["control_required_fields"]:
                if not row[field]:
                    errors.append(f"{prefix}: missing {field}")
            control_status = row.get("status", "")
            if control_status and control_status not in rules["control_allowed_status"]:
                errors.append(f"{prefix}: invalid status {control_status!r}")

    return errors


def _load_rules(schema_path: Path, control_schema_path: Path) -> dict[str, Any]:
    schema = load_schema(schema_path, "security-decision")
    required_frontmatter = string_list(schema, "required_frontmatter")
    require_fields(
        "security-decision",
        required_frontmatter,
        {"decision_id", "status", "created", "review_due"},
    )
    allowed_status = set(string_list(schema, "allowed_status"))
    review_due_required_when = set(string_list(schema, "review_due_required_when"))
    unsupported_due_statuses = sorted(review_due_required_when - allowed_status)
    if unsupported_due_statuses:
        raise ValueError(
            "schema condition 'review_due_required_when' contains values outside "
            f"the allowed enum: {', '.join(unsupported_due_statuses)}"
        )
    date_fields = string_list(schema, "date_fields")
    require_fields("security-decision dates", date_fields, {"created", "review_due"})
    unknown_date_fields = sorted(set(date_fields) - set(required_frontmatter))
    if unknown_date_fields:
        raise ValueError(
            "schema key 'date_fields' references fields outside required_frontmatter: "
            + ", ".join(unknown_date_fields)
        )
    required_sections = string_list(schema, "required_sections")
    require_fields(
        "security-decision sections",
        required_sections,
        {"Control Mapping", "Cannot Claim"},
    )
    forbidden_claims = string_list(schema, "forbidden_claims")

    control_schema = load_schema(control_schema_path, "control-mapping")
    control_required_fields = string_list(control_schema, "required_fields")
    require_fields(
        "control-mapping",
        control_required_fields,
        {"control", "status", "evidence"},
    )
    control_allowed_status = set(string_list(control_schema, "allowed_status"))

    return {
        "required_frontmatter": required_frontmatter,
        "allowed_status": allowed_status,
        "review_due_required_when": review_due_required_when,
        "date_fields": date_fields,
        "required_sections": required_sections,
        "forbidden_claims": forbidden_claims,
        "control_required_fields": control_required_fields,
        "control_allowed_status": control_allowed_status,
    }


def _frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as exc:
        raise ValueError("frontmatter closing delimiter not found") from exc
    try:
        payload = yaml.load("\n".join(lines[1:end]), Loader=yaml.BaseLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid frontmatter YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("frontmatter must be a mapping")
    return payload


def _empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not value
    return False


def _scalar(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _validate_strict_date(value: str, field: str, errors: list[str]) -> None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"invalid {field} {value!r}; expected YYYY-MM-DD")
        return
    if parsed.isoformat() != value:
        errors.append(f"invalid {field} {value!r}; expected YYYY-MM-DD")


def _section_span(text: str, name: str) -> tuple[int, int] | None:
    marker = f"## {name}"
    start = text.find(marker)
    if start < 0:
        return None
    end = text.find("\n## ", start + len(marker))
    if end < 0:
        end = len(text)
    return start, end


def _section(text: str, name: str) -> str:
    span = _section_span(text, name)
    if span is None:
        return ""
    start, end = span
    return text[start + len(f"## {name}") : end]


def _without_section(text: str, name: str) -> str:
    span = _section_span(text, name)
    if span is None:
        return text
    start, end = span
    return text[:start] + text[end:]


def _control_rows(section: str, required_fields: list[str]) -> list[dict[str, str]]:
    expected_header = [field.title() for field in required_fields]
    lines = section.splitlines()
    for index, line in enumerate(lines):
        cells = _split_row(line)
        if cells == expected_header:
            rows: list[dict[str, str]] = []
            for row_line in lines[index + 2 :]:
                row = _split_row(row_line)
                if not row:
                    break
                if len(row) != len(required_fields):
                    raise ValueError(f"Malformed Control Mapping row: {row_line}")
                rows.append(dict(zip(required_fields, row)))
            return rows
    raise ValueError(
        "Required Control Mapping table not found: " + ", ".join(expected_header)
    )


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--control-schema", type=Path, default=DEFAULT_CONTROL_SCHEMA)
    args = parser.parse_args()
    try:
        errors = validate(args.path, args.schema, args.control_schema)
    except (OSError, ValueError) as exc:
        print("security_decision: FAIL")
        print(f"- schema/document error: {exc}")
        return 1
    if errors:
        print("security_decision: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("security_decision: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
