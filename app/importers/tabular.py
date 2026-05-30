from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd


class ImportValidationError(ValueError):
    """Raised when an uploaded CSV/XLSX file does not match the expected shape."""


def parse_tabular_upload(
    *,
    filename: str,
    content: bytes,
    required_columns: dict[str, str],
    optional_columns: dict[str, str],
) -> list[dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    buffer = BytesIO(content)
    if suffix == ".csv":
        frame = pd.read_csv(buffer)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(buffer)
    else:
        raise ImportValidationError(f"Unsupported file type: {suffix}")

    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ImportValidationError(f"Missing required columns: {', '.join(missing)}")

    column_map = required_columns | {
        source: target for source, target in optional_columns.items() if source in frame.columns
    }
    normalized = frame[list(column_map.keys())].rename(columns=column_map)
    normalized = normalized.where(pd.notnull(normalized), None)
    return [_clean_row(row) for row in normalized.to_dict(orient="records")]


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if hasattr(value, "item"):
            value = value.item()
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        cleaned[key] = value
    return cleaned
