"""Validate a CSV export before full ingestion."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from .schema import PLATFORM_SCHEMA, infer_platform


REQUIRED_FIELDS = ("order_id", "order_date", "product_name", "quantity", "unit_price")
PLATFORM_LABELS = {"etsy": "Etsy", "shopify": "Shopify", "amazon": "Amazon"}


def _column_candidates(platform: str, field: str) -> List[str]:
    column = PLATFORM_SCHEMA[platform][field]
    return column if isinstance(column, list) else [column]


def _missing_fields(columns: List[str], platform: str) -> List[str]:
    normalized = {column.lower() for column in columns}
    return [
        field
        for field in REQUIRED_FIELDS
        if not any(candidate.lower() in normalized for candidate in _column_candidates(platform, field))
    ]


def check_csv(
    file_like: Any,
    rows_preview: int = 3,
    expected_platform: Optional[str] = None,
) -> Dict[str, Any]:
    """Check a CSV file and return platform guess, missing columns and preview rows."""
    try:
        df = pd.read_csv(file_like, dtype=str, keep_default_na=True, nrows=rows_preview + 1)
    except UnicodeDecodeError:
        return {"ok": False, "error": "Could not read this file's encoding — save it as UTF-8 CSV and try again."}
    except pd.errors.EmptyDataError:
        return {"ok": False, "error": "This file appears empty."}
    except pd.errors.ParserError:
        return {"ok": False, "error": "This CSV could not be read — check that it uses commas and has one header row."}

    columns = [str(column).strip() for column in df.columns]
    if not columns or (len(columns) == 1 and any(separator in columns[0] for separator in (";", "\t", "|"))):
        return {"ok": False, "error": "This file uses the wrong delimiter — export it as a comma-separated CSV."}
    if df.empty:
        return {"ok": False, "error": "This file appears empty."}

    detected_platform = infer_platform(columns)
    platform = expected_platform or detected_platform
    if expected_platform and expected_platform not in PLATFORM_SCHEMA:
        return {"ok": False, "error": "Please select Etsy, Shopify, or Amazon."}
    if expected_platform and detected_platform and detected_platform != expected_platform:
        article = "an" if detected_platform in {"etsy", "amazon"} else "a"
        return {
            "ok": False,
            "error": f"This looks like {article} {PLATFORM_LABELS[detected_platform]} CSV, not {PLATFORM_LABELS[expected_platform]} — change the selected platform.",
            "platform": detected_platform,
        }
    if not platform:
        return {
            "ok": False,
            "error": "Could not detect platform automatically — please select it manually.",
            "detected_columns": columns,
            "supported_platforms": list(PLATFORM_SCHEMA.keys()),
        }

    missing = _missing_fields(columns, platform)
    if missing:
        first_field = missing[0]
        expected_column = _column_candidates(platform, first_field)[0]
        return {
            "ok": False,
            "error": f"Missing column '{expected_column}' — check you exported the correct report type from Etsy/Shopify/Amazon.",
            "platform": platform,
            "detected_columns": columns,
            "missing_fields": missing,
        }

    mapping = PLATFORM_SCHEMA[platform]
    preview = df.head(rows_preview).fillna("").to_dict(orient="records")
    return {
        "ok": True,
        "platform": platform,
        "detected_columns": columns,
        "required_fields": {field: mapping[field] for field in REQUIRED_FIELDS},
        "missing_fields": [],
        "present_fields": list(REQUIRED_FIELDS),
        "row_count_preview": len(preview),
        "preview": preview,
    }
