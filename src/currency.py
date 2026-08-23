"""Currency conversion using the free Frankfurter API with local file cache."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Dict, Optional

CACHE_DIR = Path("data/cache")
CACHE_FILE = CACHE_DIR / "exchange_rates.json"
API_BASE = "https://api.frankfurter.app"


def _load_cache() -> Dict[str, float]:
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            return data.get("rates", {})
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(rates: Dict[str, float]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"rates": rates}
    CACHE_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _fetch_rate(base: str, target: str, as_of: Optional[date] = None) -> Optional[float]:
    date_part = as_of.isoformat() if as_of else "latest"
    url = f"{API_BASE}/{date_part}?from={base.upper()}&to={target.upper()}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["rates"].get(target.upper())
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError):
        return None


def get_rate(
    base: str,
    target: str = "EUR",
    as_of: Optional[date] = None,
    use_cache: bool = True,
) -> Optional[float]:
    """Return exchange rate from base to target, fetching from API if not cached."""
    base = base.upper()
    target = target.upper()
    if base == target:
        return 1.0

    key = f"{base}_{target}_{as_of.isoformat() if as_of else 'latest'}"
    cache = _load_cache() if use_cache else {}
    if key in cache:
        return cache[key]

    rate = _fetch_rate(base, target, as_of)
    if rate is not None and use_cache:
        cache[key] = rate
        _save_cache(cache)
    return rate


def convert(amount: float, base: str, target: str = "EUR", as_of: Optional[date] = None) -> Optional[float]:
    rate = get_rate(base, target, as_of)
    if rate is None:
        return None
    return amount * rate
