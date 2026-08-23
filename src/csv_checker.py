"""Validate a CSV export before full ingestion."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

import pandas as pd

from .schema import PLATFORM_SCHEMA, infer_platform


def check_csv(file_like: Any, rows_preview: int = 3) -> Dict[str, Any]:
    """Check a CSV file and return platform guess, missing columns and preview rows."""
    try:
        df = pd.read_csv(file_like, dtype=str, keep_default_na=True, nrows=rows_preview + 1)
    except UnicodeDecodeError as exc:
        return {"ok": False, "error": f"Encoding error: {exc}. Try saving the file as UTF-8."}
    except pd.errors.EmptyDataError:
        return {"ok": False, "error": "The CSV file appears to be empty."}
    except pd.errors.ParserError as exc:
        return {"ok": False, "error": f"Could not parse the CSV: {exc}"}

    columns = [str(c).strip() for c in df.columns]
    platform = infer_platform(columns)

    if not platform:
        return {
            "ok": False,
            "error": "Unsupported or unrecognized CSV format.",
            "detected_columns": columns,
            "supported_platforms": list(PLATFORM_SCHEMA.keys()),
        }

    mapping = PLATFORM_SCHEMA[platform]
    missing: List[str] = []
    present: List[str] = []
    for key, col in mapping.items():
        if col is None:
            continue
        candidates = col if isinstance(col, list) else [col]
        found = any(c in columns for c in candidates)
        if found:
            present.append(key)
        else:
            missing.append(key)

    preview = df.head(rows_preview).fillna("").to_dict(orient="records")

    return {
        "ok": True,
        "platform": platform,
        "detected_columns": columns,
        "required_fields": {k: v for k, v in mapping.items() if v is not None},
        "missing_fields": missing,
        "present_fields": present,
        "row_count_preview": len(preview),
        "preview": preview,
    }
