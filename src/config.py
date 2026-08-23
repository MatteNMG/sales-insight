"""Configuration loader for report branding and behavior."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class ReportConfig:
    company_name: str = "Sales Insight"
    logo_path: Optional[Path] = None
    logo_base64: Optional[str] = None
    primary_color: str = "#4a90d9"
    accent_color: str = "#f0ad4e"
    text_color: str = "#222222"
    bg_color: str = "#ffffff"
    base_currency: str = "EUR"
    date_format: str = "%Y-%m-%d"
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "ReportConfig":
        data = json.loads(path.read_text(encoding="utf-8"))
        logo_path = data.get("logo_path")
        logo_base64 = None
        if logo_path:
            logo_path = Path(logo_path)
            if logo_path.exists():
                logo_base64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
        return cls(
            company_name=data.get("company_name", cls.company_name),
            logo_path=logo_path,
            logo_base64=logo_base64,
            primary_color=data.get("primary_color", cls.primary_color),
            accent_color=data.get("accent_color", cls.accent_color),
            text_color=data.get("text_color", cls.text_color),
            bg_color=data.get("bg_color", cls.bg_color),
            base_currency=data.get("base_currency", cls.base_currency),
            date_format=data.get("date_format", cls.date_format),
            extra={k: v for k, v in data.items() if k not in cls._field_names()},
        )

    @classmethod
    def default(cls) -> "ReportConfig":
        return cls()

    @classmethod
    def _field_names(cls) -> set:
        return {"company_name", "logo_path", "primary_color", "accent_color", "text_color", "bg_color", "base_currency", "date_format"}
