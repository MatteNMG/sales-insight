"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .config import ReportConfig
from .export_excel import export_excel
from .history import load_orders, upsert_orders
from .parser import load_files, read_csv
from .report import render_html, render_executive_summary, write_pdf


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate sales insight reports from CSV exports.")
    parser.add_argument("csv", nargs="*", help="One or more CSV files to analyze.")
    parser.add_argument("-p", "--platform", default=None, help="Platform slug (etsy, shopify, amazon).")
    parser.add_argument("-o", "--output", default="sales_report", help="Output filename stem.")
    parser.add_argument("-d", "--output-dir", default=".", help="Output directory.")
    parser.add_argument("--pdf", action="store_true", help="Also generate PDF.")
    parser.add_argument("--excel", action="store_true", help="Also generate Excel workbook.")
    parser.add_argument("--executive", action="store_true", help="Also generate executive summary HTML.")
    parser.add_argument("--currency", default="EUR", help="Default currency when not specified in CSV.")
    parser.add_argument("--base-currency", default="EUR", help="Base currency for conversion and reports.")
    parser.add_argument("--config", type=Path, default=None, help="Path to report config JSON.")
    parser.add_argument("--db", type=Path, default=Path("data/history.db"), help="SQLite history database path.")
    parser.add_argument("--no-history", action="store_true", help="Do not persist orders to history database.")
    parser.add_argument("--history-only", action="store_true", help="Generate report from database history only.")
    args = parser.parse_args(argv)

    config = ReportConfig.default()
    if args.config and args.config.exists():
        config = ReportConfig.from_file(args.config)
    config.base_currency = args.base_currency

    orders = []
    if args.history_only:
        orders = load_orders(args.db)
    elif args.csv:
        paths = [Path(p) for p in args.csv]
        for p in paths:
            if not p.exists():
                print(f"File not found: {p}", file=sys.stderr)
                return 1
        orders = load_files(
            paths,
            platform=args.platform,
            default_currency=args.currency,
            base_currency=args.base_currency,
        )
    else:
        parser.print_help()
        return 1

    if not orders:
        print("No orders found.", file=sys.stderr)
        return 1

    if not args.no_history:
        upsert_orders(orders, args.db)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{args.output}.html"
    html_path.write_text(render_html(orders, config), encoding="utf-8")
    print(f"HTML report written to {html_path}")

    if args.executive:
        exec_path = output_dir / f"{args.output}_executive.html"
        exec_path.write_text(render_executive_summary(orders, config), encoding="utf-8")
        print(f"Executive summary written to {exec_path}")

    if args.pdf:
        pdf_path = output_dir / f"{args.output}.pdf"
        write_pdf(orders, pdf_path, config)
        print(f"PDF report written to {pdf_path}")

    if args.excel:
        xlsx_path = output_dir / f"{args.output}.xlsx"
        export_excel(orders, xlsx_path)
        print(f"Excel report written to {xlsx_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
