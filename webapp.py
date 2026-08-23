"""Polished Flask web app for Sales Insight."""

from __future__ import annotations

import io
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, send_file

from src.charts_interactive import build_charts, product_trend_chart
from src.config import ReportConfig
from src.demo import generate_demo_orders
from src.export_excel import export_excel
from src.history import load_orders, upsert_orders
from src.metrics import (
    average_order_value,
    revenue_by_date,
    top_products,
    total_orders,
    total_revenue,
    total_units,
)
from src.parser import normalize, read_csv
from src.report import render_executive_summary, render_html, write_pdf
from src.validation import validate_orders

app = Flask(__name__)
app.config["DB_PATH"] = Path(os.getenv("SALES_INSIGHT_DB", "data/web_history.db"))
app.config["UPLOAD_FOLDER"] = Path("data/uploads")
app.config["UPLOAD_FOLDER"].mkdir(parents=True, exist_ok=True)


DEFAULT_BASE_CURRENCY = "EUR"


def _orders_from_db(
    start: Optional[date] = None,
    end: Optional[date] = None,
    platforms: Optional[List[str]] = None,
) -> List[Any]:
    return load_orders(app.config["DB_PATH"], start_date=start, end_date=end, platforms=platforms)


def _summary(orders: List[Any]) -> Dict[str, Any]:
    if not orders:
        return {}
    total = total_revenue(orders)
    units = total_units(orders)
    orders_count = total_orders(orders)
    aov = average_order_value(orders)

    # simple delta vs first half of available date range
    by_date = revenue_by_date(orders)
    if by_date:
        dates = list(by_date.keys())
        mid = dates[len(dates) // 2]
        earlier = sum(v for d, v in by_date.items() if d < mid)
        later = sum(v for d, v in by_date.items() if d >= mid)
        revenue_delta = (later - earlier) / earlier if earlier else 0
    else:
        revenue_delta = 0

    top = top_products(orders, n=10)
    warnings = validate_orders(orders)

    return {
        "revenue": round(total, 2),
        "units": units,
        "orders": orders_count,
        "aov": round(aov, 2),
        "revenue_delta": round(revenue_delta * 100, 1),
        "top_products": [{"name": n, "revenue": round(v, 2)} for n, v in top],
        "warnings_count": len(warnings),
        "product_count": len({o.product_name for o in orders}),
    }


def _payload(orders: List[Any]) -> Dict[str, Any]:
    return {
        "summary": _summary(orders),
        "charts": build_charts(orders),
        "orders": [
            {
                "date": o.order_date.isoformat(),
                "platform": o.platform,
                "product": o.product_name,
                "sku": o.sku,
                "quantity": o.quantity,
                "revenue": round(o.effective_revenue, 2),
            }
            for o in orders[-50:]
        ],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/demo")
def demo():
    orders = generate_demo_orders(days=180)
    upsert_orders(orders, app.config["DB_PATH"])
    return jsonify(_payload(orders))


@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    platform = request.form.get("platform") or None
    currency = request.form.get("currency", "EUR")
    base = request.form.get("base_currency", DEFAULT_BASE_CURRENCY)

    df = read_csv(io.StringIO(file.stream.read().decode("utf-8")))
    orders = normalize(df, platform=platform, default_currency=currency, base_currency=base)
    upsert_orders(orders, app.config["DB_PATH"])
    return jsonify(_payload(orders))


@app.route("/api/filters")
def filters():
    start = request.args.get("start")
    end = request.args.get("end")
    platforms = request.args.getlist("platform")
    orders = _orders_from_db(
        start=date.fromisoformat(start) if start else None,
        end=date.fromisoformat(end) if end else None,
        platforms=platforms if platforms else None,
    )
    return jsonify(_payload(orders))


@app.route("/api/product/<path:product_name>/trend")
def product_trend(product_name: str):
    orders = _orders_from_db()
    chart_json = product_trend_chart(orders, product_name)
    return jsonify({"chart": json.loads(chart_json)})


@app.route("/api/export/<format>")
def export(format: str):
    orders = _orders_from_db()
    config = ReportConfig.default()
    if format == "html":
        html = render_html(orders, config)
        return send_file(
            io.BytesIO(html.encode("utf-8")),
            mimetype="text/html",
            as_attachment=True,
            download_name="report.html",
        )
    if format == "pdf":
        path = app.config["UPLOAD_FOLDER"] / "report.pdf"
        write_pdf(orders, path, config)
        return send_file(path, mimetype="application/pdf", as_attachment=True, download_name="report.pdf")
    if format == "xlsx":
        path = app.config["UPLOAD_FOLDER"] / "report.xlsx"
        export_excel(orders, path)
        return send_file(path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="report.xlsx")
    return jsonify({"error": "Unsupported format"}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
