from __future__ import annotations

import argparse
import sys
from pathlib import Path


REQUIRED_FRONTMATTER = {
    "decision_id",
    "title",
    "status",
    "owner",
    "created",
    "review_due",
    "risk_categories",
    "source_refs",
    "evidence_refs",
}

REQUIRED_SECTIONS = {
    "Decision",
    "Context",
    "Risk",
    "Control Mapping",
    "Cannot Claim",
}

ALLOWED_STATUS = {
    "pending",
    "needs_changes",
    "accepted",
    "accepted_with_review_due",
    "deferred",
    "rejected",
}

FORBIDDEN_CLAIMS = {
    "compliant",
    "production safe",
    "production-safe",
    "remediated",
    "vulnerability fixed",
    "risk eliminated",
    "audit ready",
}


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    frontmatter = _frontmatter(text)
    for field in sorted(REQUIRED_FRONTMATTER):
        if field not in frontmatter:
            errors.append(f"missing frontmatter field: {field}")
    status = frontmatter.get("status", "")
    if status and status not in ALLOWED_STATUS:
        errors.append(f"invalid status: {status!r}")
    for section in sorted(REQUIRED_SECTIONS):
        if f"## {section}" not in text:
            errors.append(f"missing section: {section}")
    cannot_claim = _section(text, "Cannot Claim").lower()
    if not cannot_claim.strip():
        errors.append("Cannot Claim section is empty")
    body_lower = text.lower()
    for claim in sorted(FORBIDDEN_CLAIMS):
        if claim in body_lower and claim not in cannot_claim:
            errors.append(f"forbidden claim appears outside Cannot Claim boundary: {claim}")
    return errors


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    values: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def _section(text: str, name: str) -> str:
    marker = f"## {name}"
    start = text.find(marker)
    if start < 0:
        return ""
    next_start = text.find("\n## ", start + len(marker))
    if next_start < 0:
        return text[start + len(marker) :]
    return text[start + len(marker) : next_start]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate(args.path)
    if errors:
        print("security_decision: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("security_decision: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
