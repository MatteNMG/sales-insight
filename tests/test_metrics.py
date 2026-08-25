"""Tests for metric calculations."""

from datetime import date, timedelta

import pytest

from src.insights import (
    cross_platform_performance_insight,
    fee_anomaly_insight,
    low_margin_insight,
    sales_drop_insight,
    stock_runout_insight,
)
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


def _daily_order(day, revenue=100.0, platform="etsy", fees=0.0, stock=None, cost=None):
    return UnifiedOrder(
        platform, f"{platform}-{day}", day, "Ring", "R1", 1, revenue, "EUR", revenue,
        cost_per_unit=cost, fees=fees, stock_quantity=stock,
    )


def test_sales_drop_uses_same_weekday_baseline():
    orders = [_daily_order(date(2025, 1, 1) + timedelta(days=offset)) for offset in range(28)]
    orders.extend(_daily_order(date(2025, 1, 29) + timedelta(days=offset), revenue=20.0) for offset in range(7))
    insights = sales_drop_insight(orders)
    assert insights and "usual level for these weekdays" in insights[0]["message"]


def test_real_margin_includes_material_fees_and_shipping():
    order = _daily_order(date(2025, 1, 1), cost=80.0, fees=10.0)
    order.shipping_cost = 5.0
    insight = low_margin_insight([order])[0]
    assert "5.0%" in insight["message"]


def test_stock_runout_reports_days_and_date():
    orders = [_daily_order(date(2025, 1, 1) + timedelta(days=offset), stock=9) for offset in range(30)]
    insight = stock_runout_insight(orders)[0]
    assert "9 days" in insight["message"]
    assert "2025-02-08" in insight["message"]


def test_cross_platform_compares_net_per_unit():
    etsy = _daily_order(date(2025, 1, 1), platform="etsy", fees=20.0)
    shopify = _daily_order(date(2025, 1, 1), platform="shopify", fees=5.0)
    insight = cross_platform_performance_insight([etsy, shopify])[0]
    assert "Shopify" in insight["message"] and "Etsy" in insight["message"]


def test_fee_anomaly_compares_recent_period():
    orders = []
    for offset in range(60):
        day = date(2025, 1, 1) + timedelta(days=offset)
        orders.append(_daily_order(day, fees=15.0 if offset >= 30 else 5.0))
    insight = fee_anomaly_insight(orders)[0]
    assert "5.0% to 15.0%" in insight["message"]
