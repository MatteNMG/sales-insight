# Changelog

## 0.2.0 — 2026-08-23

### Added
- Multi-currency conversion using the free Frankfurter API with local file cache.
- Data validation module that flags zero/negative prices, negative margins, missing dates and duplicates.
- Persistent SQLite history (`history.py`) for cross-report trend analysis.
- Advanced insights: year-over-year revenue comparison, product correlation / bundle suggestions, improved stock-runout forecast.
- Excel export with live formulas in `src/export_excel.py`.
- Customizable report branding via `config/report.json`.
- Streamlit dashboard with demo mode, executive summary tab and download buttons.
- Automation scaffolding: Shopify Admin API client, email/Telegram alerts, weekly email scheduler.
- `ROADMAP.md` and updated `README.md`.

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
