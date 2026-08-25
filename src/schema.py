"""Unified sales-data schema and per-platform column maps."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


@dataclass
class UnifiedOrder:
    """One sale line after normalization."""

    platform: str
    order_id: str
    order_date: date
    product_name: str
    sku: str
    quantity: int
    unit_price: float
    currency: str
    revenue: float
    cost_per_unit: Optional[float] = None
    fees: float = 0.0
    shipping_cost: float = 0.0
    refund: bool = False
    country: Optional[str] = None
    stock_quantity: Optional[int] = None
    base_currency: str = "EUR"
    unit_price_base: Optional[float] = None
    revenue_base: Optional[float] = None

    @property
    def effective_revenue(self) -> float:
        return self.revenue_base if self.revenue_base is not None else self.revenue

    @property
    def effective_unit_price(self) -> float:
        return self.unit_price_base if self.unit_price_base is not None else self.unit_price

    @property
    def net_revenue(self) -> float:
        return self.effective_revenue - self.fees - self.shipping_cost

    @property
    def gross_margin(self) -> float:
        if self.cost_per_unit is None:
            return 0.0
        return (self.effective_unit_price - self.cost_per_unit) * self.quantity


# Columns expected in each platform export. None means "not available / infer".
PLATFORM_SCHEMA: Dict[str, Dict[str, Any]] = {
    "etsy": {
        "order_id": "Order ID",
        "order_date": "Sale Date",
        "product_name": "Item Name",
        "sku": "SKU",
        "quantity": "Quantity",
        "unit_price": "Price",
        "currency": "Currency",
        "fees": ["Card Processing Fees", "Transaction Fees", "Listing Fees"],
        "shipping_cost": "Shipping",
        "refund": None,
        "country": "Delivery Country",
        "cost_per_unit": "cost_per_unit",
        "stock_quantity": "stock_quantity",
    },
    "shopify": {
        "order_id": "Name",
        "order_date": "Created at",
        "product_name": "Lineitem name",
        "sku": "Lineitem sku",
        "quantity": "Lineitem quantity",
        "unit_price": "Lineitem price",
        "currency": None,
        "fees": ["Taxes"],
        "shipping_cost": "Shipping",
        "refund": "Financial Status",
        "country": "Shipping Country",
        "cost_per_unit": "cost_per_unit",
        "stock_quantity": "stock_quantity",
    },
    "amazon": {
        "order_id": "order-id",
        "order_date": "order-date",
        "product_name": "product-name",
        "sku": "sku",
        "quantity": "quantity",
        "unit_price": "item-price",
        "currency": "currency",
        "fees": ["amazon-fee"],
        "shipping_cost": ["shipping-fee"],
        "refund": "item-status",
        "country": "ship-country",
        "cost_per_unit": "cost_per_unit",
        "stock_quantity": "stock_quantity",
    },
}


KNOWN_PLATFORMS: set[str] = set(PLATFORM_SCHEMA.keys())


def infer_platform(columns: Sequence[str]) -> Optional[str]:
    """Return platform slug whose schema best matches the given columns."""
    cols = set(str(c).strip().lower() for c in columns)
    scores: Dict[str, int] = {}
    for platform, mapping in PLATFORM_SCHEMA.items():
        required = [mapping["order_id"], mapping["order_date"], mapping["product_name"]]
        if platform == "shopify":
            required = ["Name", "Created at", "Lineitem name"]
        elif platform == "amazon":
            required = ["order-id", "order-date", "product-name"]
        elif platform == "etsy":
            required = ["Order ID", "Sale Date", "Item Name"]
        scores[platform] = sum(1 for col in required if col.lower() in cols)
    if not scores:
        return None
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] >= 2 else None


def _coerce_money(value: Any) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, str):
        value = value.replace("$", "").replace("€", "").replace(",", "").strip()
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _coerce_quantity(value: Any) -> int:
    if pd.isna(value):
        return 0
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def _parse_refund(value: Any) -> bool:
    if pd.isna(value):
        return False
    s = str(value).lower()
    return any(
        keyword in s
        for keyword in ("refund", "refunded", "return", "cancelled", "canceled", "returned")
    )


def _sum_fee_columns(row: pd.Series, keys: List[str]) -> float:
    total = 0.0
    for key in keys:
        if key in row:
            total += _coerce_money(row[key])
    return total


def _normalize_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, pd.Timestamp):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return date.min
    return parsed.date()
