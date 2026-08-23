"""Etsy API client (placeholder — requires OAuth v3)."""

from __future__ import annotations

from typing import List

from .base import get_env
from ..schema import UnifiedOrder


def get_orders() -> List[UnifiedOrder]:
    """Fetch receipts from the Etsy v3 API.

    Requires:
        ETSY_API_KEY
        ETSY_SHOP_ID
        ETSY_ACCESS_TOKEN (OAuth 2.0)
    """
    get_env("ETSY_API_KEY")
    get_env("ETSY_SHOP_ID")
    get_env("ETSY_ACCESS_TOKEN")
    raise NotImplementedError(
        "Etsy API normalization is not implemented yet. "
        "Set ETSY_API_KEY, ETSY_SHOP_ID and ETSY_ACCESS_TOKEN, "
        "then map /v3/application/shops/{shop_id}/receipts fields to UnifiedOrder."
    )
