from __future__ import annotations

from datetime import date


def parse_strict_date(value: str, context: str, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{context}: invalid {field} {value!r}; expected YYYY-MM-DD"
        ) from exc
    if parsed.isoformat() != value:
        raise ValueError(
            f"{context}: invalid {field} {value!r}; expected YYYY-MM-DD"
        )
    return parsed
