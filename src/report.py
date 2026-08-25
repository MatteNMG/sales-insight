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
    @page { size: A4; margin: 16mm; background: #faf9f5; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      color: #1b1a17;
      background: #faf9f5;
      font-size: 12px;
    }
    h1, h2 { font-family: Georgia, serif; font-weight: 500; }
    h1 { margin: 0; font-size: 25px; letter-spacing: -.02em; }
    h2 { margin: 0 0 14px; color: #1b1a17; font-size: 17px; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; margin: 22px 0; border: 1px solid #e3e0d6; border-radius: 8px; overflow: hidden; }
    .kpi { background: #faf9f5; padding: 16px 10px; text-align: left; }
    .kpi .value { font-family: monospace; font-size: 19px; color: #1b1a17; }
    .kpi .label { margin-top: 6px; color: #8c877a; font-size: 9px; letter-spacing: .08em; text-transform: uppercase; }
    .section { margin: 18px 0; padding: 18px; border: 1px solid #e3e0d6; border-radius: 8px; break-inside: avoid; }
    .chart { margin: 0; }
    .chart img { display: block; width: 100%; height: auto; border-radius: 6px; }
    table { width: 100%; border-collapse: collapse; font-family: monospace; }
    th, td { padding: 9px 0; border-bottom: 1px solid #e3e0d6; text-align: left; }
    th { color: #8c877a; font-family: sans-serif; font-size: 9px; font-weight: 500; letter-spacing: .07em; text-transform: uppercase; }
    th:last-child, td:last-child { text-align: right; }
    .insight { margin: 6px 0; padding: 10px 12px; border-left: 3px solid #2f6f5e; background: #f1efe7; }
    .insight.critical { border-color: #b0433a; background: #fff0f0; }
    .insight.warning { border-color: #b8872e; background: #fff8e6; }
    .insight.positive { border-color: #2f6f5e; background: #eef7f4; }
    .insight.info { border-color: #577590; background: #f0f6f8; }
    .warning { margin: 5px 0; padding: 9px 11px; border-left: 3px solid #b0433a; background: #fff0f0; }
    .muted { color: #8c877a; font-size: 10px; }
    .header { display: flex; align-items: center; gap: 14px; padding-bottom: 16px; border-bottom: 1px solid #e3e0d6; }
    .header img { max-height: 52px; }
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
