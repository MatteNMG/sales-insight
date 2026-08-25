"""CSV ingestion and normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

import pandas as pd

from .currency import convert
from .schema import (
    PLATFORM_SCHEMA,
    UnifiedOrder,
    _coerce_money,
    _coerce_quantity,
    _normalize_date,
    _parse_refund,
    _sum_fee_columns,
    infer_platform,
)


PathLike = Union[str, Path]


def read_csv(path: PathLike) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=True)


def normalize(
    df: pd.DataFrame,
    platform: Optional[str] = None,
    default_currency: str = "EUR",
    base_currency: str = "EUR",
    product_overrides: Optional[dict] = None,
) -> List[UnifiedOrder]:
    """Convert a platform DataFrame into a list of UnifiedOrder objects."""
    if platform is None:
        platform = infer_platform(df.columns)
        if platform is None:
            raise ValueError("Could not infer platform from columns: " + ", ".join(df.columns))

    mapping = PLATFORM_SCHEMA[platform]
    rows: List[UnifiedOrder] = []
    for _, row in df.iterrows():
        order = _row_to_order(row, platform, mapping, default_currency, base_currency)
        override = (product_overrides or {}).get(order.sku) or (product_overrides or {}).get(order.product_name) or {}
        if order.cost_per_unit is None and override.get("cost_per_unit") is not None:
            order.cost_per_unit = _coerce_money(override["cost_per_unit"])
        if order.stock_quantity is None and override.get("stock_quantity") is not None:
            order.stock_quantity = _coerce_quantity(override["stock_quantity"])
        rows.append(order)
    return rows


def _row_to_order(
    row: pd.Series,
    platform: str,
    mapping: dict,
    default_currency: str,
    base_currency: str = "EUR",
) -> UnifiedOrder:
    def get(key: str):
        col = mapping.get(key)
        if col is None:
            return None
        if isinstance(col, list):
            return _sum_fee_columns(row, col)
        return row.get(col)

    quantity = _coerce_quantity(get("quantity"))
    unit_price = _coerce_money(get("unit_price"))
    revenue = quantity * unit_price
    order_date = _normalize_date(get("order_date"))

    currency = get("currency")
    if currency is None or (isinstance(currency, float) and pd.isna(currency)):
        currency = default_currency
    currency = str(currency).strip().upper()

    shipping = _coerce_money(get("shipping_cost"))
    fees = _coerce_money(get("fees"))
    cost_value = get("cost_per_unit")
    stock_value = get("stock_quantity")
    cost_per_unit = _coerce_money(cost_value) if cost_value is not None and not pd.isna(cost_value) else None
    stock_quantity = _coerce_quantity(stock_value) if stock_value is not None and not pd.isna(stock_value) else None

    refund_value = get("refund")
    refund = _parse_refund(refund_value)
    if refund_value is not None and not isinstance(refund_value, (int, float)):
        try:
            refund_amount = _coerce_money(refund_value)
        except Exception:
            refund_amount = 0.0
        if refund_amount > 0:
            refund = True

    country = get("country")
    country = str(country).strip() if country is not None else None

    unit_price_base = convert(unit_price, currency, base_currency, order_date)
    revenue_base = convert(revenue, currency, base_currency, order_date)

    return UnifiedOrder(
        platform=platform,
        order_id=str(get("order_id")),
        order_date=order_date,
        product_name=str(get("product_name")),
        sku=str(get("sku")),
        quantity=quantity,
        unit_price=unit_price,
        currency=currency,
        revenue=revenue,
        cost_per_unit=cost_per_unit,
        fees=fees,
        shipping_cost=shipping,
        refund=refund,
        country=country if country and country.lower() != "nan" else None,
        stock_quantity=stock_quantity,
        base_currency=base_currency,
        unit_price_base=unit_price_base,
        revenue_base=revenue_base,
    )


def load_files(
    paths: Iterable[PathLike],
    platform: Optional[str] = None,
    default_currency: str = "EUR",
    base_currency: str = "EUR",
) -> List[UnifiedOrder]:
    orders: List[UnifiedOrder] = []
    for path in paths:
        df = read_csv(path)
        orders.extend(
            normalize(
                df,
                platform=platform,
                default_currency=default_currency,
                base_currency=base_currency,
            )
        )
    return orders
