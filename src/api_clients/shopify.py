"""Fetch orders from Shopify Admin REST API and normalize them."""

from __future__ import annotations

from datetime import date
from typing import Any, List, Optional

from .base import _request_json, get_env
from ..schema import UnifiedOrder


API_VERSION = "2024-01"


def _shop_url() -> str:
    shop = get_env("SHOPIFY_STORE")
    if ".myshopify.com" not in shop:
        shop = f"{shop}.myshopify.com"
    return f"https://{shop}/admin/api/{API_VERSION}"


def _headers() -> dict:
    return {
        "X-Shopify-Access-Token": get_env("SHOPIFY_ACCESS_TOKEN"),
        "Content-Type": "application/json",
    }


def fetch_orders(
    status: str = "any",
    limit: int = 250,
    created_at_min: Optional[str] = None,
) -> List[dict]:
    """Fetch Shopify order objects. Handles simple pagination."""
    url = f"{_shop_url()}/orders.json?status={status}&limit={limit}"
    if created_at_min:
        url += f"&created_at_min={created_at_min}"

    orders: List[dict] = []
    while url:
        data = _request_json(url, _headers())
        page = data.get("orders", [])
        orders.extend(page)
        link = data.get("link")
        url = link if isinstance(link, str) and "orders" in link else None
    return orders


def _parse_date(value: Any) -> date:
    from ..schema import _normalize_date
    return _normalize_date(value)


def normalize_shopify_orders(raw_orders: List[dict]) -> List[UnifiedOrder]:
    """Convert Shopify order JSON into UnifiedOrder objects."""
    orders: List[UnifiedOrder] = []
    for raw in raw_orders:
        order_id = str(raw.get("name") or raw.get("id"))
        order_date = _parse_date(raw.get("created_at"))
        currency = raw.get("currency", "EUR")
        for line in raw.get("line_items", []):
            quantity = int(line.get("quantity", 1))
            unit_price = float(line.get("price", 0))
            orders.append(
                UnifiedOrder(
                    platform="shopify",
                    order_id=order_id,
                    order_date=order_date,
                    product_name=line.get("title", "Unknown"),
                    sku=line.get("sku") or line.get("variant_id", ""),
                    quantity=quantity,
                    unit_price=unit_price,
                    currency=currency,
                    revenue=quantity * unit_price,
                    fees=float(raw.get("total_tax", 0)) / max(len(raw.get("line_items", [])), 1),
                    shipping_cost=float(raw.get("shipping_lines", [{}])[0].get("price", 0)) / max(len(raw.get("line_items", [])), 1),
                    refund=raw.get("financial_status") in ("refunded", "partially_refunded"),
                    country=(raw.get("shipping_address") or {}).get("country_code"),
                    base_currency=currency,
                )
            )
    return orders


def get_orders(
    status: str = "any",
    limit: int = 250,
    created_at_min: Optional[str] = None,
) -> List[UnifiedOrder]:
    raw = fetch_orders(status, limit, created_at_min)
    return normalize_shopify_orders(raw)
