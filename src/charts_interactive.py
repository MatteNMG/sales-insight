"""Plotly chart builders returning JSON for the interactive web app."""

from __future__ import annotations

import json
from typing import Dict, List

import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

from .metrics import (
    margin_by_product,
    revenue_by_country,
    revenue_by_date,
    top_products,
)
from .schema import UnifiedOrder


def _to_json(fig: go.Figure) -> str:
    return json.dumps(fig, cls=PlotlyJSONEncoder)


def sales_trend_chart(orders: List[UnifiedOrder]) -> str:
    data = revenue_by_date(orders)
    if not data:
        return _to_json(go.Figure())
    fig = px.bar(
        x=list(data.keys()),
        y=list(data.values()),
        labels={"x": "Date", "y": "Revenue"},
        title="Revenue trend",
    )
    fig.update_layout(margin=dict(l=40, r=40, t=50, b=40), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return _to_json(fig)


def top_products_chart(orders: List[UnifiedOrder], n: int = 8) -> str:
    data = top_products(orders, by_revenue=True, n=n)
    if not data:
        return _to_json(go.Figure())
    names = [d[0] for d in data]
    values = [d[1] for d in data]
    fig = px.bar(
        x=names,
        y=values,
        labels={"x": "Product", "y": "Revenue"},
        title=f"Top {n} products",
    )
    fig.update_layout(margin=dict(l=40, r=40, t=50, b=40), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return _to_json(fig)


def country_chart(orders: List[UnifiedOrder]) -> str:
    data = revenue_by_country(orders)
    if not data:
        return _to_json(go.Figure())
    fig = px.pie(
        names=list(data.keys()),
        values=list(data.values()),
        title="Revenue by country",
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        hovertemplate="%{label}<br>Revenue: %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    fig.update_layout(
        margin=dict(l=40, r=40, t=50, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        uniformtext_minsize=11,
        uniformtext_mode="hide",
        legend_title_text="Country",
    )
    return _to_json(fig)


def product_trend_chart(orders: List[UnifiedOrder], product_name: str) -> str:
    from collections import defaultdict

    data: Dict[str, float] = defaultdict(float)
    for o in orders:
        if o.refund or o.product_name != product_name:
            continue
        data[str(o.order_date)] += o.effective_revenue
    if not data:
        return _to_json(go.Figure())
    sorted_data = dict(sorted(data.items()))
    fig = px.line(
        x=list(sorted_data.keys()),
        y=list(sorted_data.values()),
        labels={"x": "Date", "y": "Revenue"},
        title=f"Trend — {product_name}",
    )
    fig.update_layout(margin=dict(l=40, r=40, t=50, b=40), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return _to_json(fig)


def build_charts(orders: List[UnifiedOrder]) -> Dict[str, str]:
    return {
        "trend": sales_trend_chart(orders),
        "top": top_products_chart(orders),
        "country": country_chart(orders),
    }
