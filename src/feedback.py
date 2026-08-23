"""Local feedback storage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

FEEDBACK_FILE = Path("data/feedback.json")


def save_feedback(rating: int, comment: str, email: str = "") -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    if FEEDBACK_FILE.exists():
        try:
            entries = json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            entries = []
    entries.append(
        {
            "timestamp": datetime.now().isoformat(),
            "rating": rating,
            "comment": comment,
            "email": email,
        }
    )
    FEEDBACK_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def list_feedback() -> List[Dict[str, Any]]:
    if not FEEDBACK_FILE.exists():
        return []
    try:
        return json.loads(FEEDBACK_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
