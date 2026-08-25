"""Tests for metric calculations."""

from datetime import date

import pytest

from src.metrics import (
    average_order_value,
    flop_products,
    refund_rate,
    revenue_by_country,
    revenue_by_date,
    summary,
    top_products,
    total_revenue,
)
from src.schema import UnifiedOrder


def _orders():
    return [
        UnifiedOrder("etsy", "A1", date(2025, 1, 1), "Ring", "R1", 2, 10.0, "EUR", 20.0, fees=2.0, shipping_cost=3.0),
        UnifiedOrder("etsy", "A1", date(2025, 1, 1), "Ring", "R1", 1, 10.0, "EUR", 10.0, fees=1.0, shipping_cost=1.5),
        UnifiedOrder("shopify", "B1", date(2025, 1, 2), "Vase", "V1", 1, 30.0, "EUR", 30.0, fees=3.0, shipping_cost=5.0),
        UnifiedOrder("shopify", "B2", date(2025, 1, 3), "Vase", "V1", 1, 30.0, "EUR", 30.0, refund=True),
    ]


def test_total_revenue_excludes_refunds():
    orders = _orders()
    assert total_revenue(orders) == 60.0


def test_refund_rate():
    orders = _orders()
    assert refund_rate(orders) == 0.25


def test_revenue_by_date():
    orders = _orders()
    by_date = revenue_by_date(orders)
    assert by_date[date(2025, 1, 1)] == 30.0
    assert by_date[date(2025, 1, 2)] == 30.0
    assert date(2025, 1, 3) not in by_date


def test_top_products():
    orders = _orders()
    top = top_products(orders)
    assert top[0][0] == "Ring"


def test_flop_products():
    orders = _orders()
    flop = flop_products(orders)
    assert "Vase" in {name for name, _ in flop}


def test_summary_keys():
    orders = _orders()
    s = summary(orders)
    assert s["total_revenue"] == 60.0
    assert s["average_order_value"] == pytest.approx(30.0)


def test_revenue_by_country_merges_codes_and_names():
    orders = _orders()[:2]
    orders[0].country = "IT"
    orders[1].country = "Italy"
    assert revenue_by_country(orders) == {"Italy": 30.0}
