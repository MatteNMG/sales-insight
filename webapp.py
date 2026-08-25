"""Polished Flask web app for Sales Insight."""

from __future__ import annotations

import io
import json
import os
import tempfile
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Flask, jsonify, render_template, request, send_file

from src.charts_interactive import build_charts, product_trend_chart
from src.config import ReportConfig
from src.csv_checker import check_csv
from src.demo import generate_demo_orders
from src.export_excel import export_excel
from src.feedback import list_feedback, save_feedback
from src.history import load_orders, upsert_orders
from src.metrics import (
    average_order_value,
    revenue_by_date,
    top_products,
    total_orders,
    total_revenue,
    total_units,
)
from src.parser import load_files, normalize, read_csv
from src.report import render_executive_summary, render_html, write_pdf
from src.validation import validate_orders

app = Flask(__name__)
is_production = os.getenv("FLASK_ENV") == "production" or bool(os.getenv("RAILWAY_ENVIRONMENT"))
runtime_dir = Path(tempfile.gettempdir()) / "sales-insight" if is_production else Path("data")
app.config["DB_PATH"] = Path(os.getenv("SALES_INSIGHT_DB", runtime_dir / "web_history.db"))
app.config["UPLOAD_FOLDER"] = runtime_dir / "uploads"
app.config["DEBUG"] = False
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


def _payload(orders: List[Any], include_orders: bool = True) -> Dict[str, Any]:
    summary = _summary(orders)
    return {
        "summary": summary,
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
            for o in (orders[-50:] if len(orders) > 50 else orders)
        ] if include_orders else [],
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/api/demo")
def demo():
    orders = generate_demo_orders(days=180)
    upsert_orders(orders, app.config["DB_PATH"])
    return jsonify(_payload(orders))


@app.route("/api/check", methods=["POST"])
def check():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "Choose a CSV file to continue."}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "Choose a CSV file to continue."}), 400
    platform = request.form.get("platform") or None
    result = check_csv(io.BytesIO(file.stream.read()), expected_platform=platform)
    return jsonify(result)


@app.route("/samples/<platform>.csv")
def sample_csv(platform: str):
    sample_files = {
        "etsy": "etsy_orders.csv",
        "shopify": "shopify_orders.csv",
        "amazon": "amazon_orders.csv",
    }
    if platform not in sample_files:
        return jsonify({"error": "Sample not found."}), 404
    return send_file(
        Path("data/samples") / sample_files[platform],
        mimetype="text/csv",
        as_attachment=True,
        download_name=sample_files[platform],
    )


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
    content = file.stream.read()
    validation = check_csv(io.BytesIO(content), expected_platform=platform)
    if not validation["ok"]:
        return jsonify({"error": validation["error"]}), 400

    try:
        df = read_csv(io.BytesIO(content))
        orders = normalize(
            df,
            platform=platform or validation["platform"],
            default_currency=currency,
            base_currency=base,
        )
    except Exception:
        return jsonify({"error": "We could not process this CSV — verify the file format and try again."}), 400

    upsert_orders(orders, app.config["DB_PATH"])
    return jsonify(_payload(orders))


@app.route("/api/filters")
def filters():
    start = request.args.get("start")
    end = request.args.get("end")
    platforms = request.args.getlist("platform")
    try:
        orders = _orders_from_db(
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
            platforms=platforms if platforms else None,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(_payload(orders))


@app.route("/api/latest")
def latest():
    """Return the most recent data stored in the local history."""
    orders = _orders_from_db()
    return jsonify(_payload(orders, include_orders=False))


@app.route("/api/history")
def history():
    """Return available date ranges and platforms in local history."""
    import sqlite3

    init_db = True
    if not app.config["DB_PATH"].exists():
        return jsonify({"batches": []})
    with sqlite3.connect(app.config["DB_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT MIN(order_date) as min_date, MAX(order_date) as max_date, COUNT(DISTINCT platform) as platforms, COUNT(*) as rows FROM orders"
        ).fetchall()
    batches = [
        {
            "min_date": r["min_date"],
            "max_date": r["max_date"],
            "platforms": r["platforms"],
            "rows": r["rows"],
        }
        for r in rows
        if r["rows"]
    ]
    return jsonify({"batches": batches})


@app.route("/api/product/<path:product_name>/trend")
def product_trend(product_name: str):
    orders = _orders_from_db()
    chart_json = product_trend_chart(orders, product_name)
    return jsonify({"chart": json.loads(chart_json)})


@app.route("/api/feedback", methods=["POST"])
def feedback():
    data = request.get_json(silent=True) or {}
    rating = data.get("rating", 0)
    comment = data.get("comment", "")
    email = data.get("email", "")
    if not comment or not (1 <= int(rating) <= 5):
        return jsonify({"error": "Rating (1-5) and comment are required"}), 400
    save_feedback(int(rating), comment, email)
    return jsonify({"ok": True})


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
    app.run(host="127.0.0.1", port=5000, debug=False)
