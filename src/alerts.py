"""Send threshold alerts via email or Telegram."""

from __future__ import annotations

import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage
from typing import List

from .insights import Insight
from .schema import UnifiedOrder


def send_email_alert(
    subject: str,
    body: str,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    to: str | None = None,
) -> None:
    host = smtp_host or os.getenv("SMTP_HOST")
    port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
    user = username or os.getenv("SMTP_USER")
    pw = password or os.getenv("SMTP_PASSWORD")
    recipient = to or os.getenv("ALERT_EMAIL")

    if not all([host, user, pw, recipient]):
        raise RuntimeError("Missing SMTP_HOST, SMTP_USER, SMTP_PASSWORD or ALERT_EMAIL env vars")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, pw)
        server.send_message(msg)


def send_telegram_alert(message: str, token: str | None = None, chat_id: str | None = None) -> None:
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        response.read()


def check_alerts(orders: List[UnifiedOrder], insights: List[Insight]) -> None:
    """Send alerts for any critical insights if configured."""
    critical = [i for i in insights if i.get("severity") == "critical"]
    if not critical:
        return
    text = "Critical Sales Insight alerts:\n\n" + "\n".join(f"- {i['message']}" for i in critical)

    if os.getenv("SMTP_HOST") and os.getenv("ALERT_EMAIL"):
        send_email_alert("Sales Insight: critical alert", text)
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        send_telegram_alert(text)
