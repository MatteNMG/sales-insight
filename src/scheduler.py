"""Simple weekly report scheduler using the `schedule` library."""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import schedule

from .history import load_orders
from .report import write_pdf


def send_weekly_email() -> None:
    from .alerts import send_email_alert
    from .report import render_html

    db_path = Path(os.getenv("SALES_INSIGHT_DB", "data/history.db"))
    end = datetime.today().date()
    start = end - timedelta(days=7)
    orders = load_orders(db_path, start_date=start, end_date=end)

    if not orders:
        print(f"No orders between {start} and {end}; skipping weekly report.")
        return

    html = render_html(orders)
    subject = f"Weekly Sales Insight — {start} to {end}"
    body = f"See attached HTML report covering {len(orders)} order lines.\n\n{html[:500]}..."
    send_email_alert(subject, body)
    print(f"Weekly report sent for {start} to {end}")


def run_scheduler() -> None:
    schedule.every().sunday.at("09:00").do(send_weekly_email)
    print("Scheduler running. Waiting for next job...")
    while True:
        schedule.run_pending()
        time.sleep(60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sales Insight weekly scheduler")
    parser.add_argument("--run-now", action="store_true", help="Send one report immediately")
    args = parser.parse_args()

    if args.run_now:
        send_weekly_email()
        return 0
    run_scheduler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
