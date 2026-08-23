"""Streamlit dashboard for Sales Insight."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.charts import build_charts
from src.demo import generate_demo_orders
from src.metrics import (
    average_order_value,
    revenue_by_date,
    top_products,
    total_orders,
    total_revenue,
    total_units,
)
from src.parser import load_files, read_csv, normalize
from src.report import render_executive_summary, render_html, write_pdf

st.set_page_config(page_title="Sales Insight", layout="wide")
st.title("Sales Insight")
st.write("Upload CSV exports or run the demo.")

mode = st.radio("Mode", ["Upload CSV", "Demo data"], horizontal=True)

df = None
orders = []

if mode == "Demo data":
    demo_days = st.slider("Demo days", 30, 365, 180)
    orders = generate_demo_orders(days=demo_days)
else:
    uploaded = st.file_uploader("CSV files", type=["csv"], accept_multiple_files=True)
    platform = st.selectbox("Platform", ["Auto", "etsy", "shopify", "amazon"])
    currency = st.text_input("Default currency", value="EUR")
    base_currency = st.text_input("Base currency", value="EUR")
    if uploaded:
        for file in uploaded:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                tmp.write(file.getvalue())
                tmp_path = Path(tmp.name)
            df = read_csv(tmp_path)
            platform_arg = None if platform == "Auto" else platform
            orders.extend(normalize(df, platform=platform_arg, default_currency=currency, base_currency=base_currency))

if orders:
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Revenue", f"{total_revenue(orders):,.2f}")
    col2.metric("Units", total_units(orders))
    col3.metric("Orders", total_orders(orders))
    col4.metric("AOV", f"{average_order_value(orders):,.2f}")

    tab_exec, tab_trend, tab_products, tab_countries, tab_export = st.tabs(
        ["Executive summary", "Trend", "Top products", "Countries", "Export"]
    )

    charts = build_charts(orders)
    top = top_products(orders, n=10)

    with tab_exec:
        st.components.v1.html(render_executive_summary(orders), height=600, scrolling=True)

    with tab_trend:
        by_date = revenue_by_date(orders)
        trend_df = pd.DataFrame({"Date": list(by_date.keys()), "Revenue": list(by_date.values())})
        st.line_chart(trend_df.set_index("Date"))
        st.image(f"data:image/png;base64,{charts['trend']}")

    with tab_products:
        st.image(f"data:image/png;base64,{charts['top']}")
        st.dataframe(pd.DataFrame(top, columns=["Product", "Revenue"]))

    with tab_countries:
        st.image(f"data:image/png;base64,{charts['country']}")
        st.image(f"data:image/png;base64,{charts['margin']}")

    with tab_export:
        html_bytes = render_html(orders).encode("utf-8")
        st.download_button("Download HTML report", data=html_bytes, file_name="report.html", mime="text/html")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_path = Path(tmp.name)
        write_pdf(orders, pdf_path)
        st.download_button(
            "Download PDF report",
            data=pdf_path.read_bytes(),
            file_name="report.pdf",
            mime="application/pdf",
        )
else:
    st.info("Upload CSV files or switch to Demo data.")
