from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from _markdown_tables import read_table
from _schema_rules import load_schema, string_list
from validate_evidence_index import DEFAULT_SCHEMA as EVIDENCE_SCHEMA
from validate_evidence_index import validate as validate_evidence_index
from validate_review_queue import DEFAULT_SCHEMA as REVIEW_QUEUE_SCHEMA
from validate_review_queue import validate as validate_review_queue


TERMINAL_REVIEW_STATUSES = {"accepted", "rejected"}
EVIDENCE_ATTENTION_STATUSES = {
    "pending",
    "needs_changes",
    "accepted_with_review_due",
    "deferred",
}
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
DUE_STATE_RANK = {"overdue": 0, "due": 1, "upcoming": 2, "not_applicable": 3}
STRENGTH_RANK = {"weak": 0, "medium": 1, "strong": 2}


class ReportInputError(ValueError):
    """Raised when a reviewer report input cannot be safely rendered."""


def generate_report(package_dir: Path, today: date) -> str:
    package_dir = package_dir.resolve()
    evidence_path = package_dir / "evidence-index.md"
    queue_path = package_dir / "review-queue.md"

    validation_errors = [
        *(f"evidence-index.md: {error}" for error in validate_evidence_index(evidence_path)),
        *(f"review-queue.md: {error}" for error in validate_review_queue(queue_path)),
    ]
    if validation_errors:
        raise ReportInputError("\n".join(validation_errors))

    evidence_schema = load_schema(EVIDENCE_SCHEMA, "evidence-record")
    evidence_columns = string_list(evidence_schema, "required_fields")
    if "review_due" not in evidence_columns:
        evidence_columns.append("review_due")
    queue_schema = load_schema(REVIEW_QUEUE_SCHEMA, "review-queue")
    queue_columns = string_list(queue_schema, "required_fields")

    evidence_rows = _annotate_due_dates(
        read_table(evidence_path, evidence_columns), today, "evidence-index.md", "evidence_id"
    )
    queue_rows = _annotate_due_dates(
        read_table(queue_path, queue_columns), today, "review-queue.md", "review_id"
    )

    queue_attention = sorted(
        (row for row in queue_rows if row["status"] not in TERMINAL_REVIEW_STATUSES),
        key=lambda row: (
            PRIORITY_RANK[row["priority"]],
            DUE_STATE_RANK[row["due_state"]],
            row["_review_due_date"],
            row["review_id"],
        ),
    )
    evidence_attention = sorted(
        (
            row
            for row in evidence_rows
            if row["strength"] == "weak"
            or row["review_status"] in EVIDENCE_ATTENTION_STATUSES
        ),
        key=lambda row: (
            DUE_STATE_RANK[row["due_state"]],
            STRENGTH_RANK[row["strength"]],
            row["_review_due_date"],
            row["evidence_id"],
        ),
    )

    lines = [
        f"# Reviewer Report: {_cell(package_dir.name)}",
        "",
        "## Report Metadata",
        "",
        f"- as_of: `{today.isoformat()}`",
        "- evidence_input: `evidence-index.md`",
        "- review_queue_input: `review-queue.md`",
        "- validation: `PASS`",
        "",
        "## Summary",
        "",
        f"- review_queue_total: {len(queue_rows)}",
        f"- review_queue_attention: {len(queue_attention)}",
        f"- evidence_total: {len(evidence_rows)}",
        f"- evidence_attention: {len(evidence_attention)}",
        "",
        "## Review Queue Attention",
        "",
    ]
    if queue_attention:
        lines.extend(
            [
                "| due_state | review_id | priority | status | owner | review_due | source_ref | reason |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
                *(
                    "| "
                    + " | ".join(
                        _cell(row[column])
                        for column in (
                            "due_state",
                            "review_id",
                            "priority",
                            "status",
                            "owner",
                            "review_due",
                            "source_ref",
                            "reason",
                        )
                    )
                    + " |"
                    for row in queue_attention
                ),
            ]
        )
    else:
        lines.append("No Review Queue rows require attention.")

    lines.extend(["", "## Evidence Attention", ""])
    if evidence_attention:
        lines.extend(
            [
                "| due_state | evidence_id | strength | review_status | review_due | source_ref | artifact_type | supports_claim |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
                *(
                    "| "
                    + " | ".join(
                        _cell(row[column])
                        for column in (
                            "due_state",
                            "evidence_id",
                            "strength",
                            "review_status",
                            "review_due",
                            "source_ref",
                            "artifact_type",
                            "supports_claim",
                        )
                    )
                    + " |"
                    for row in evidence_attention
                ),
            ]
        )
    else:
        lines.append("No Evidence Index rows require attention.")

    lines.extend(
        [
            "",
            "## Aggregation Boundary",
            "",
            "- Evidence Index and Review Queue metadata were aggregated into separate sections.",
            "- No queue-to-evidence relationship was inferred; `source_ref` values remain opaque navigation references.",
            "- Source artifacts and reviewer decisions still require direct human review.",
            "",
            "## Cannot Claim",
            "",
            "- No queue-to-evidence correlation or closure is proven.",
            "- Domain correctness is not proven.",
            "- Compliance is not proven.",
            "- Remediation or vulnerability resolution is not proven.",
            "- Production safety is not proven.",
            "- Audit readiness is not proven.",
            "- Control effectiveness is not proven.",
        ]
    )
    return "\n".join(lines) + "\n"


def _annotate_due_dates(
    rows: list[dict[str, str]], today: date, filename: str, id_field: str
) -> list[dict[str, str | date]]:
    annotated: list[dict[str, str | date]] = []
    for row in rows:
        item: dict[str, str | date] = dict(row)
        raw_due = row.get("review_due", "")
        if not raw_due:
            item["due_state"] = "not_applicable"
            item["_review_due_date"] = date.max
        else:
            try:
                review_due = date.fromisoformat(raw_due)
            except ValueError as exc:
                identifier = row.get(id_field) or "missing id"
                raise ReportInputError(
                    f"{filename} ({identifier}): invalid review_due {raw_due!r}"
                ) from exc
            item["_review_due_date"] = review_due
            if review_due < today:
                item["due_state"] = "overdue"
            elif review_due == today:
                item["due_state"] = "due"
            else:
                item["due_state"] = "upcoming"
        annotated.append(item)
    return annotated


def _cell(value: str | date) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_dir", type=Path)
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args()
    try:
        today = date.fromisoformat(args.today)
        report = generate_report(args.package_dir, today)
    except (OSError, ValueError) as exc:
        print("reviewer_report: FAIL", file=sys.stderr)
        for line in str(exc).splitlines():
            print(f"- {line}", file=sys.stderr)
        return 1
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
