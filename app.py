"""Minimal drag-and-drop Streamlit UI for Sales Insight."""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from src.parser import read_csv, normalize
from src.report import render_html, write_pdf

st.set_page_config(page_title="Sales Insight", layout="wide")
st.title("Sales Insight")
st.write("Upload one or more CSV exports (Etsy, Shopify, Amazon Seller) to generate a report.")

platform = st.selectbox("Platform (auto-detect if blank)", ["Auto", "etsy", "shopify", "amazon"])
files = st.file_uploader("CSV files", type=["csv"], accept_multiple_files=True)
currency = st.text_input("Default currency", value="EUR")
generate_pdf = st.checkbox("Generate PDF", value=False)

if files and st.button("Generate report"):
    all_orders = []
    for uploaded in files:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = Path(tmp.name)
        df = read_csv(tmp_path)
        platform_arg = None if platform == "Auto" else platform
        all_orders.extend(normalize(df, platform=platform_arg, default_currency=currency))

    html = render_html(all_orders)
    st.download_button("Download HTML report", data=html, file_name="report.html", mime="text/html")

    if generate_pdf:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_path = Path(tmp.name)
        write_pdf(all_orders, pdf_path)
        st.download_button(
            "Download PDF report",
            data=pdf_path.read_bytes(),
            file_name="report.pdf",
            mime="application/pdf",
        )

    st.success(f"Report generated from {len(all_orders)} order lines.")
