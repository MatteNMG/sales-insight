"""HTML and PDF report generation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Template

from .charts import build_charts
from .insights import Insight, generate_insights
from .metrics import (
    average_order_value,
    refund_rate,
    top_products,
    total_orders,
    total_revenue,
    total_units,
)
from .schema import UnifiedOrder


REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sales Insight Report</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; color: #222; }
    h1 { border-bottom: 2px solid #4a90d9; padding-bottom: .5rem; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
    .kpi { background: #f7f9fb; border-radius: 8px; padding: 1rem; text-align: center; }
    .kpi .value { font-size: 1.6rem; font-weight: bold; color: #4a90d9; }
    .kpi .label { font-size: .85rem; color: #666; margin-top: .3rem; }
    .section { margin: 2rem 0; }
    .chart { margin: 1rem 0; }
    .chart img { max-width: 100%; height: auto; border: 1px solid #e3e8ed; border-radius: 8px; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid #e3e8ed; padding: .5rem; text-align: left; }
    th { background: #f7f9fb; }
    .insight { padding: .75rem; border-left: 4px solid #4a90d9; background: #f7f9fb; margin: .5rem 0; }
    .insight.critical { border-color: #d9534f; background: #fff0f0; }
    .insight.warning { border-color: #f0ad4e; background: #fff8e6; }
    .muted { color: #777; font-size: .9rem; }
  </style>
</head>
<body>
  <h1>Sales Insight Report</h1>
  <p class="muted">Generated for {{ platform }} data · {{ order_count }} orders</p>

  <div class="kpis">
    <div class="kpi"><div class="value">{{ "%.2f"|format(total_revenue) }}</div><div class="label">Revenue</div></div>
    <div class="kpi"><div class="value">{{ total_units }}</div><div class="label">Units sold</div></div>
    <div class="kpi"><div class="value">{{ "%.2f"|format(average_order_value) }}</div><div class="label">Avg order value</div></div>
    <div class="kpi"><div class="value">{{ "%.1f"|format(refund_rate*100) }}%</div><div class="label">Refund rate</div></div>
  </div>

  <div class="section">
    <h2>Insights</h2>
    {% if insights %}
      {% for insight in insights %}
        <div class="insight {{ insight.severity }}">{{ insight.message }}</div>
      {% endfor %}
    {% else %}
      <p class="muted">No notable issues detected.</p>
    {% endif %}
  </div>

  <div class="section">
    <h2>Top products</h2>
    <table>
      <tr><th>Product</th><th>Revenue</th></tr>
      {% for product, value in top_products %}
      <tr><td>{{ product }}</td><td>{{ "%.2f"|format(value) }}</td></tr>
      {% endfor %}
    </table>
  </div>

  <div class="section">
    <h2>Revenue trend</h2>
    <div class="chart"><img src="data:image/png;base64,{{ charts.trend }}" alt="Revenue trend"></div>
  </div>

  <div class="section">
    <h2>Top products by revenue</h2>
    <div class="chart"><img src="data:image/png;base64,{{ charts.top }}" alt="Top products"></div>
  </div>

  <div class="section">
    <h2>Revenue by country</h2>
    <div class="chart"><img src="data:image/png;base64,{{ charts.country }}" alt="Revenue by country"></div>
  </div>

  <div class="section">
    <h2>Margin / net revenue per product</h2>
    <div class="chart"><img src="data:image/png;base64,{{ charts.margin }}" alt="Margin per product"></div>
  </div>
</body>
</html>
"""


def build_context(orders: List[UnifiedOrder]) -> dict:
    charts = build_charts(orders)
    insights = generate_insights(orders)
    return {
        "platform": orders[0].platform if orders else "unknown",
        "order_count": total_orders(orders),
        "total_revenue": total_revenue(orders),
        "total_units": total_units(orders),
        "average_order_value": average_order_value(orders),
        "refund_rate": refund_rate(orders),
        "top_products": top_products(orders, n=10),
        "insights": insights,
        "charts": charts,
    }


def render_html(orders: List[UnifiedOrder]) -> str:
    context = build_context(orders)
    return Template(REPORT_TEMPLATE).render(**context)


def write_html(orders: List[UnifiedOrder], path: Path) -> Path:
    html = render_html(orders)
    path.write_text(html, encoding="utf-8")
    return path


def write_pdf(orders: List[UnifiedOrder], path: Path) -> Path:
    from weasyprint import HTML

    html = render_html(orders)
    HTML(string=html).write_pdf(str(path))
    return path
