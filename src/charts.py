"""Chart builders returning base64-encoded PNG images."""

from __future__ import annotations

import base64
import io
from typing import Dict, List

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .metrics import margin_by_product, revenue_by_country, revenue_by_date, top_products
from .schema import UnifiedOrder


def _to_base64(fig: matplotlib.figure.Figure) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def sales_trend_chart(orders: List[UnifiedOrder]) -> str:
    data = revenue_by_date(orders)
    if not data:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _to_base64(fig)
    dates = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(dates, values, color="steelblue")
    ax.set_title("Revenue trend")
    ax.set_xlabel("Date")
    ax.set_ylabel("Revenue")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return _to_base64(fig)


def top_products_chart(orders: List[UnifiedOrder], n: int = 8) -> str:
    data = top_products(orders, by_revenue=True, n=n)
    if not data:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _to_base64(fig)
    names = [d[0] for d in data]
    values = [d[1] for d in data]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(names[::-1], values[::-1], color="seagreen")
    ax.set_title(f"Top {n} products by revenue")
    ax.set_xlabel("Revenue")
    fig.tight_layout()
    return _to_base64(fig)


def country_chart(orders: List[UnifiedOrder]) -> str:
    data = revenue_by_country(orders)
    if not data:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _to_base64(fig)
    labels = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.set_title("Revenue by country")
    fig.tight_layout()
    return _to_base64(fig)


def margin_chart(orders: List[UnifiedOrder]) -> str:
    data = margin_by_product(orders)
    if not data:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _to_base64(fig)
    products = list(data.keys())
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["seagreen" if v >= 0 else "indianred" for v in values]
    ax.bar(products, values, color=colors)
    ax.set_title("Margin / net revenue per product")
    ax.set_ylabel("Amount")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return _to_base64(fig)


def build_charts(orders: List[UnifiedOrder]) -> Dict[str, str]:
    return {
        "trend": sales_trend_chart(orders),
        "top": top_products_chart(orders),
        "country": country_chart(orders),
        "margin": margin_chart(orders),
    }
