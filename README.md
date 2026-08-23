# Sales Insight

CLI tool that turns e-commerce CSV exports (Etsy, Shopify, Amazon Seller) into a clean HTML/PDF sales report with charts and heuristic insights.

## Features

- Normalizes CSV exports from Etsy, Shopify and Amazon Seller into one unified schema.
- Computes core metrics: revenue, units sold, average order value, refund rate, top/flop products.
- Generates charts: revenue trend, top products, revenue by country, margin/net revenue per product.
- Surfaces automatic insights: sales drops, low margins, stock runout risk, refund spikes.
- Produces a single HTML report (and optional PDF) with one command.
- Optional drag-and-drop Streamlit UI.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

Generate HTML + PDF report from one or more CSV files:

```bash
python -m src.cli data/samples/etsy_orders.csv -o etsy_report --pdf
python -m src.cli data/samples/shopify_orders.csv data/samples/amazon_orders.csv -o combined --pdf
```

Platform is auto-detected from the CSV headers. You can force it with `--platform etsy|shopify|amazon`.

Run the Streamlit UI:

```bash
streamlit run app.py
```

## Supported platforms & columns

| Field | Etsy | Shopify | Amazon |
|---|---|---|---|
| Order ID | `Order ID` | `Name` | `order-id` |
| Date | `Sale Date` | `Created at` | `order-date` |
| Product | `Item Name` | `Lineitem name` | `product-name` |
| SKU | `SKU` | `Lineitem sku` | `sku` |
| Quantity | `Quantity` | `Lineitem quantity` | `quantity` |
| Price | `Price` | `Lineitem price` | `item-price` |
| Currency | `Currency` | default `--currency` | `currency` |
| Fees | processing/transaction/listing | `Taxes` | `amazon-fee` |
| Shipping | `Shipping` | `Shipping` | `shipping-fee` |
| Refund | not detected | `Financial Status` | `item-status` |

## Project structure

```
├── src/
│   ├── schema.py     # unified data model and platform column maps
│   ├── parser.py     # CSV ingestion
│   ├── metrics.py    # pure metric functions
│   ├── charts.py     # matplotlib chart builders
│   ├── insights.py   # heuristic insight rules
│   ├── report.py     # HTML/PDF report generation
│   └── cli.py        # command-line entry point
├── tests/            # pytest suite
├── data/samples/     # synthetic CSV samples
├── app.py            # optional Streamlit UI
└── pyproject.toml
```

## Tests

```bash
pytest
```

## License

MIT
