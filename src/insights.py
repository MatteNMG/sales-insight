"""Heuristic business insights over UnifiedOrder data."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Dict, List, Optional, Tuple

from .metrics import (
    margin_by_product,
    revenue_by_date,
    stock_runout_days,
    total_revenue,
)
from .schema import UnifiedOrder


Insight = Dict[str, str]


def _split_periods(
    orders: List[UnifiedOrder],
    days: int = 30,
) -> Tuple[Dict[date, float], Dict[date, float]]:
    by_date = revenue_by_date(orders)
    if not by_date:
        return {}, {}
    latest = max(by_date.keys())
    cutoff = latest - timedelta(days=days)
    recent = {d: v for d, v in by_date.items() if d > cutoff}
    older = {d: v for d, v in by_date.items() if d <= cutoff}
    return recent, older


def sales_drop_insight(
    orders: List[UnifiedOrder],
    threshold: float = 0.20,
) -> List[Insight]:
    """Flag products whose recent sales dropped >= threshold vs older period."""
    if not orders:
        return []
    latest = max(o.order_date for o in orders)
    cutoff = latest - timedelta(days=30)

    recent: Dict[str, float] = defaultdict(float)
    older: Dict[str, float] = defaultdict(float)
    for o in orders:
        if o.refund:
            continue
        target = recent if o.order_date > cutoff else older
        target[o.product_name] += o.revenue

    insights: List[Insight] = []
    for product in set(recent) | set(older):
        before = older.get(product, 0.0)
        after = recent.get(product, 0.0)
        if before > 0 and (before - after) / before >= threshold:
            drop = ((before - after) / before) * 100
            insights.append(
                {
                    "type": "sales_drop",
                    "severity": "warning",
                    "message": f"{product} sales dropped {drop:.0f}% in the last 30 days",
                }
            )
    return insights


def low_margin_insight(
    orders: List[UnifiedOrder],
    threshold_percent: float = 0.15,
) -> List[Insight]:
    """Flag products with margin rate below threshold of revenue."""
    margins = margin_by_product(orders)
    if not margins:
        return []
    revenues: Dict[str, float] = defaultdict(float)
    for o in orders:
        if o.refund:
            continue
        revenues[o.product_name] += o.revenue
    insights: List[Insight] = []
    for product, margin in margins.items():
        rev = revenues.get(product, 0.0)
        if rev > 0 and margin / rev < threshold_percent:
            rate = (margin / rev) * 100
            insights.append(
                {
                    "type": "low_margin",
                    "severity": "warning",
                    "message": f"{product} margin is {rate:.1f}% (below {threshold_percent*100:.0f}% threshold)",
                }
            )
    return insights


def stock_runout_insight(
    orders: List[UnifiedOrder],
    threshold_days: float = 14.0,
) -> List[Insight]:
    """Flag products likely to run out of stock soon."""
    runouts = stock_runout_days(orders)
    insights: List[Insight] = []
    for product, days in runouts.items():
        if days is not None and days <= threshold_days:
            insights.append(
                {
                    "type": "stock_runout",
                    "severity": "critical" if days <= 7 else "warning",
                    "message": f"{product} stock may run out in {days:.0f} days",
                }
            )
    return insights


def refund_spike_insight(
    orders: List[UnifiedOrder],
    threshold: float = 0.10,
) -> List[Insight]:
    if not orders:
        return []
    refunded = sum(1 for o in orders if o.refund)
    rate = refunded / len(orders)
    if rate >= threshold:
        return [
            {
                "type": "refund_spike",
                "severity": "warning",
                "message": f"Refund rate is {rate*100:.1f}% (above {threshold*100:.0f}% threshold)",
            }
        ]
    return []


def generate_insights(orders: List[UnifiedOrder]) -> List[Insight]:
    """Return all heuristic insights."""
    insights: List[Insight] = []
    insights.extend(sales_drop_insight(orders))
    insights.extend(low_margin_insight(orders))
    insights.extend(stock_runout_insight(orders))
    insights.extend(refund_spike_insight(orders))
    return insights
