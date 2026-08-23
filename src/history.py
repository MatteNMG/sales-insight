"""Persistent SQLite storage for ingested orders."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any, List, Optional, Sequence

from .schema import UnifiedOrder


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    order_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    product_name TEXT NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    currency TEXT NOT NULL,
    revenue REAL NOT NULL,
    fees REAL NOT NULL DEFAULT 0.0,
    shipping_cost REAL NOT NULL DEFAULT 0.0,
    refund INTEGER NOT NULL DEFAULT 0,
    country TEXT,
    base_currency TEXT,
    unit_price_base REAL,
    revenue_base REAL,
    inserted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(platform, order_id, sku)
);
CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_platform ON orders(platform);
CREATE INDEX IF NOT EXISTS idx_orders_sku ON orders(sku);
"""


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)


def _order_to_row(order: UnifiedOrder) -> tuple:
    return (
        order.platform,
        order.order_id,
        order.order_date.isoformat(),
        order.product_name,
        order.sku,
        order.quantity,
        order.unit_price,
        order.currency,
        order.revenue,
        order.fees,
        order.shipping_cost,
        int(order.refund),
        order.country,
        order.base_currency,
        order.unit_price_base,
        order.revenue_base,
    )


def _row_to_order(row: sqlite3.Row) -> UnifiedOrder:
    return UnifiedOrder(
        platform=row["platform"],
        order_id=row["order_id"],
        order_date=date.fromisoformat(row["order_date"]),
        product_name=row["product_name"],
        sku=row["sku"],
        quantity=row["quantity"],
        unit_price=row["unit_price"],
        currency=row["currency"],
        revenue=row["revenue"],
        fees=row["fees"],
        shipping_cost=row["shipping_cost"],
        refund=bool(row["refund"]),
        country=row["country"],
        base_currency=row["base_currency"] or "EUR",
        unit_price_base=row["unit_price_base"],
        revenue_base=row["revenue_base"],
    )


def upsert_orders(
    orders: Sequence[UnifiedOrder],
    db_path: Path,
) -> int:
    """Insert or replace orders in the history database. Returns number of rows."""
    init_db(db_path)
    rows = [_order_to_row(o) for o in orders]
    sql = """
        INSERT INTO orders (
            platform, order_id, order_date, product_name, sku, quantity,
            unit_price, currency, revenue, fees, shipping_cost, refund,
            country, base_currency, unit_price_base, revenue_base
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(platform, order_id, sku) DO UPDATE SET
            order_date=excluded.order_date,
            product_name=excluded.product_name,
            quantity=excluded.quantity,
            unit_price=excluded.unit_price,
            currency=excluded.currency,
            revenue=excluded.revenue,
            fees=excluded.fees,
            shipping_cost=excluded.shipping_cost,
            refund=excluded.refund,
            country=excluded.country,
            base_currency=excluded.base_currency,
            unit_price_base=excluded.unit_price_base,
            revenue_base=excluded.revenue_base,
            inserted_at=CURRENT_TIMESTAMP
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.executemany(sql, rows)
        conn.commit()
    return len(rows)


def load_orders(
    db_path: Path,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    platforms: Optional[Sequence[str]] = None,
) -> List[UnifiedOrder]:
    """Load orders from the history database with optional filters."""
    init_db(db_path)
    conditions: List[str] = []
    params: List[Any] = []
    if start_date:
        conditions.append("order_date >= ?")
        params.append(start_date.isoformat())
    if end_date:
        conditions.append("order_date <= ?")
        params.append(end_date.isoformat())
    if platforms:
        placeholders = ",".join("?" for _ in platforms)
        conditions.append(f"platform IN ({placeholders})")
        params.extend(platforms)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM orders {where} ORDER BY order_date"

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_order(row) for row in rows]
