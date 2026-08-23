# Changelog

## 0.1.0 — 2026-08-23

### Added
- Unified CSV schema for Etsy, Shopify and Amazon Seller exports.
- Parser that auto-detects platform and normalizes orders.
- Core metrics: revenue, units, average order value, refund rate, top/flop products, revenue by date and country.
- Matplotlib charts embedded as base64 PNG for HTML and PDF compatibility.
- Heuristic insights: sales drops, low margins, stock runout risk, refund spikes.
- CLI: `python -m src.cli <csv> -o <name> --pdf`.
- Optional Streamlit drag-and-drop UI in `app.py`.
- Sample CSVs for all three platforms.
- pytest test suite for parser and metrics.
- `pyproject.toml`, `requirements.txt` and `README.md`.
