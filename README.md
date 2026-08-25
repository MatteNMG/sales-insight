# Sales Insight

CLI tool and dashboard that turn e-commerce CSV exports (Etsy, Shopify, Amazon Seller) into HTML/PDF/Excel reports with charts and heuristic insights.

## Features

- **Multi-platform CSV normalization** for Etsy, Shopify, Amazon Seller.
- **Multi-currency support** with free Frankfurter exchange-rate API and local cache.
- **Core metrics**: revenue, units sold, average order value, refund rate, top/flop products.
- **Persistent SQLite history** to accumulate data and analyze long-term trends.
- **Smart insights**: sales drops, low margins, stock-runout forecast, refund spikes, YoY comparison, product bundles.
- **Custom branding** via JSON config (logo, colors, company name).
- **Multiple exports**: HTML, PDF, Excel with live formulas, executive summary.
- **Flask web app** with custom design, dark mode, dynamic filters, drill-down and demo mode.
- Optional Streamlit UI (`app.py`).
- **Automation scaffolding**: Shopify Admin API client, weekly email scheduler, Telegram/email alerts.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## CLI usage

Generate HTML + PDF + Excel from CSV files:

```bash
python -m src.cli data/samples/etsy_orders.csv -o etsy_report --pdf --excel --executive
python -m src.cli data/samples/shopify_orders.csv data/samples/amazon_orders.csv -o combined --pdf --excel --config config/report.json --db data/history.db
```

Platform is auto-detected. Add optional `cost_per_unit` and `stock_quantity` columns to any platform CSV, or define SKU fallbacks in `config/report.json` under `product_overrides` (for example, `"RING-01": {"cost_per_unit": 8.5, "stock_quantity": 12}`). These values enable real-margin and dated stock-runout insights.

Options:
- `--platform etsy|shopify|amazon` — force platform
- `--currency EUR` — default currency when missing
- `--base-currency EUR` — convert all amounts to this currency
- `--db data/history.db` — persist orders to SQLite history
- `--history-only` — generate report from accumulated history

## Flask web app

Run the polished dashboard:

```bash
python -m flask --app webapp run
```

Features: dark mode, drag-and-drop CSV upload with format check, demo data, dynamic date/platform filters, drill-down on products, guided tour, loading/empty states, mobile-responsive tables, PDF/Excel export and local feedback form.

Privacy note: CSV files are processed by the local Flask server. No sales data is sent to external services; currency conversion uses the free Frankfurter API for exchange rates only.

## Streamlit dashboard (alternative)

```bash
streamlit run app.py
```

Choose **Demo data** to explore the dashboard without uploading real files.

## Automation

Weekly email report (requires SMTP env vars):

```bash
python -m src.scheduler --run-now
```

Environment variables for alerting/APIs:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `SHOPIFY_STORE`, `SHOPIFY_ACCESS_TOKEN`
- `ETSY_API_KEY`, `ETSY_SHOP_ID`, `ETSY_ACCESS_TOKEN`

## Custom branding

Edit `config/report.json` to change company name, logo, colors and base currency.

## Project structure

```
├── src/
│   ├── schema.py           # unified data model and platform column maps
│   ├── parser.py           # CSV ingestion + currency conversion
│   ├── metrics.py          # pure metric functions
│   ├── charts.py           # matplotlib chart builders (PDF/HTML)
│   ├── charts_interactive.py # Plotly chart builders (web app)
│   ├── insights.py         # heuristic insight rules
│   ├── validation.py       # data-quality warnings
│   ├── csv_checker.py      # pre-upload CSV format validator
│   ├── feedback.py         # local feedback storage
│   ├── history.py          # SQLite persistence
│   ├── currency.py         # Frankfurter exchange-rate client
│   ├── config.py           # report branding config
│   ├── export_excel.py     # Excel export with formulas
│   ├── report.py           # HTML/PDF report generation
│   ├── cli.py              # command-line entry point
│   ├── demo.py             # synthetic demo data generator
│   ├── scheduler.py        # weekly email scheduler
│   ├── alerts.py           # email/Telegram alerting
│   └── api_clients/        # Etsy / Shopify API clients
├── templates/              # Flask HTML templates
├── static/                 # CSS / JS assets
├── tests/                  # pytest suite
├── data/samples/           # synthetic CSV samples
├── config/report.json      # branding config
├── app.py                  # Streamlit UI
├── webapp.py               # polished Flask dashboard
├── ROADMAP.md              # public roadmap
└── pyproject.toml
```

## Tests

```bash
pytest
```

## License

MIT
