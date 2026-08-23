"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .parser import load_files, normalize, read_csv
from .report import write_html, write_pdf


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate sales insight reports from CSV exports.")
    parser.add_argument("csv", nargs="+", help="One or more CSV files to analyze.")
    parser.add_argument("-p", "--platform", default=None, help="Platform slug (etsy, shopify, amazon).")
    parser.add_argument("-o", "--output", default="sales_report", help="Output filename stem.")
    parser.add_argument("-d", "--output-dir", default=".", help="Output directory.")
    parser.add_argument("--pdf", action="store_true", help="Also generate PDF.")
    parser.add_argument("--currency", default="EUR", help="Default currency when not specified in CSV.")
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.csv]
    for p in paths:
        if not p.exists():
            print(f"File not found: {p}", file=sys.stderr)
            return 1

    orders = load_files(paths, platform=args.platform, default_currency=args.currency)
    if not orders:
        print("No orders found in the provided files.", file=sys.stderr)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    html_path = output_dir / f"{args.output}.html"
    write_html(orders, html_path)
    print(f"HTML report written to {html_path}")

    if args.pdf:
        pdf_path = output_dir / f"{args.output}.pdf"
        write_pdf(orders, pdf_path)
        print(f"PDF report written to {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
