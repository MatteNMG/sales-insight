"""HTML and PDF report generation."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Template

from .charts import build_charts
from .config import ReportConfig
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
from .validation import ValidationWarning, validate_orders


REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ config.company_name }} — Sales Insight Report</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      margin: 2rem;
      color: {{ config.text_color }};
      background: {{ config.bg_color }};
    }
    h1 { border-bottom: 2px solid {{ config.primary_color }}; padding-bottom: .5rem; }
    h2 { color: {{ config.primary_color }}; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
    .kpi { background: #f7f9fb; border-radius: 8px; padding: 1rem; text-align: center; border-top: 4px solid {{ config.primary_color }}; }
    .kpi .value { font-size: 1.6rem; font-weight: bold; color: {{ config.primary_color }}; }
    .kpi .label { font-size: .85rem; color: #666; margin-top: .3rem; }
    .section { margin: 2rem 0; }
    .chart { margin: 1rem 0; }
    .chart img { max-width: 100%; height: auto; border: 1px solid #e3e8ed; border-radius: 8px; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border: 1px solid #e3e8ed; padding: .5rem; text-align: left; }
    th { background: #f7f9fb; }
    .insight { padding: .75rem; border-left: 4px solid {{ config.primary_color }}; background: #f7f9fb; margin: .5rem 0; }
    .insight.critical { border-color: #d9534f; background: #fff0f0; }
    .insight.warning { border-color: {{ config.accent_color }}; background: #fff8e6; }
    .insight.positive { border-color: #5cb85c; background: #f0fff0; }
    .insight.info { border-color: #5bc0de; background: #f0f9ff; }
    .warning { padding: .5rem; border-left: 4px solid #d9534f; background: #fff0f0; margin: .25rem 0; }
    .muted { color: #777; font-size: .9rem; }
    .header { display: flex; align-items: center; gap: 1rem; }
    .header img { max-height: 60px; }
  </style>
</head>
<body>
  <div class="header">
    {% if config.logo_base64 %}<img src="data:image/png;base64,{{ config.logo_base64 }}" alt="logo">{% endif %}
    <div>
      <h1>{{ config.company_name }} — Sales Insight Report</h1>
      <p class="muted">{{ order_count }} orders · base currency {{ config.base_currency }}</p>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="value">{{ "%.2f"|format(total_revenue) }}</div><div class="label">Revenue</div></div>
    <div class="kpi"><div class="value">{{ total_units }}</div><div class="label">Units sold</div></div>
    <div class="kpi"><div class="value">{{ "%.2f"|format(average_order_value) }}</div><div class="label">Avg order value</div></div>
    <div class="kpi"><div class="value">{{ "%.1f"|format(refund_rate*100) }}%</div><div class="label">Refund rate</div></div>
  </div>

  {% if validation_warnings %}
  <div class="section">
    <h2>Data quality warnings</h2>
    {% for w in validation_warnings %}
      <div class="warning">{{ w.message }}</div>
    {% endfor %}
  </div>
  {% endif %}

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

EXECUTIVE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ config.company_name }} — Executive Summary</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 2rem; color: {{ config.text_color }}; background: {{ config.bg_color }}; }
    h1 { border-bottom: 2px solid {{ config.primary_color }}; }
    .kpis { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin: 1.5rem 0; }
    .kpi { background: #f7f9fb; border-radius: 8px; padding: 1rem; border-top: 4px solid {{ config.primary_color }}; }
    .kpi .value { font-size: 1.4rem; font-weight: bold; color: {{ config.primary_color }}; }
    .kpi .label { font-size: .85rem; color: #666; }
    ul { line-height: 1.6; }
    .muted { color: #777; }
  </style>
</head>
<body>
  <h1>{{ config.company_name }} — Executive Summary</h1>
  <p class="muted">{{ order_count }} orders · {{ insights|length }} insights</p>
  <div class="kpis">
    <div class="kpi"><div class="value">{{ "%.2f"|format(total_revenue) }}</div><div class="label">Revenue</div></div>
    <div class="kpi"><div class="value">{{ total_units }}</div><div class="label">Units sold</div></div>
    <div class="kpi"><div class="value">{{ "%.2f"|format(average_order_value) }}</div><div class="label">Avg order value</div></div>
    <div class="kpi"><div class="value">{{ "%.1f"|format(refund_rate*100) }}%</div><div class="label">Refund rate</div></div>
  </div>
  <h2>Key takeaways</h2>
  <ul>
    {% for insight in insights[:5] %}
      <li>{{ insight.message }}</li>
    {% else %}
      <li class="muted">No major insights.</li>
    {% endfor %}
  </ul>
  <h2>Top products</h2>
  <ul>
    {% for product, value in top_products[:5] %}
      <li>{{ product }} — {{ "%.2f"|format(value) }}</li>
    {% endfor %}
  </ul>
</body>
</html>
"""


def build_context(
    orders: List[UnifiedOrder],
    config: ReportConfig,
) -> dict:
    charts = build_charts(orders)
    insights = generate_insights(orders)
    validation_warnings = validate_orders(orders)
    return {
        "config": config,
        "platform": orders[0].platform if orders else "unknown",
        "order_count": total_orders(orders),
        "total_revenue": total_revenue(orders),
        "total_units": total_units(orders),
        "average_order_value": average_order_value(orders),
        "refund_rate": refund_rate(orders),
        "top_products": top_products(orders, n=10),
        "insights": insights,
        "validation_warnings": validation_warnings,
        "charts": charts,
    }


def render_html(
    orders: List[UnifiedOrder],
    config: Optional[ReportConfig] = None,
) -> str:
    config = config or ReportConfig.default()
    context = build_context(orders, config)
    return Template(REPORT_TEMPLATE).render(**context)


def render_executive_summary(
    orders: List[UnifiedOrder],
    config: Optional[ReportConfig] = None,
) -> str:
    config = config or ReportConfig.default()
    context = build_context(orders, config)
    return Template(EXECUTIVE_TEMPLATE).render(**context)


def write_html(
    orders: List[UnifiedOrder],
    path: Path,
    config: Optional[ReportConfig] = None,
) -> Path:
    html = render_html(orders, config)
    path.write_text(html, encoding="utf-8")
    return path


def write_executive_html(
    orders: List[UnifiedOrder],
    path: Path,
    config: Optional[ReportConfig] = None,
) -> Path:
    html = render_executive_summary(orders, config)
    path.write_text(html, encoding="utf-8")
    return path


def write_pdf(
    orders: List[UnifiedOrder],
    path: Path,
    config: Optional[ReportConfig] = None,
) -> Path:
    from weasyprint import HTML

    html = render_html(orders, config)
    HTML(string=html).write_pdf(str(path))
    return path
