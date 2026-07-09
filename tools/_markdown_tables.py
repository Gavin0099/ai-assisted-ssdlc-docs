from __future__ import annotations

from pathlib import Path


def read_table(path: Path, required_columns: list[str]) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        cells = _split_row(line)
        if cells == required_columns:
            rows: list[dict[str, str]] = []
            for row_line in lines[index + 2 :]:
                row = _split_row(row_line)
                if not row:
                    break
                if len(row) != len(required_columns):
                    raise ValueError(f"Malformed table row in {path}: {row_line}")
                rows.append(dict(zip(required_columns, row)))
            return rows
    raise ValueError(f"Required table not found in {path}: {', '.join(required_columns)}")


def _split_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]
