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


def year_over_year_insight(orders: List[UnifiedOrder]) -> List[Insight]:
    """Compare revenue in the most recent complete month with the same month last year."""
    from collections import defaultdict

    by_month: Dict[tuple, float] = defaultdict(float)
    for o in orders:
        if o.refund:
            continue
        by_month[(o.order_date.year, o.order_date.month)] += o.effective_revenue

    if not by_month:
        return []

    latest_year, latest_month = max(by_month)
    current = by_month[(latest_year, latest_month)]
    prev_key = (latest_year - 1, latest_month)
    if prev_key not in by_month or by_month[prev_key] == 0:
        return []
    previous = by_month[prev_key]
    change = (current - previous) / previous
    direction = "up" if change >= 0 else "down"
    insights: List[Insight] = [
        {
            "type": "yoy_revenue",
            "severity": "info" if abs(change) < 0.1 else ("positive" if change >= 0 else "warning"),
            "message": (
                f"Revenue for {latest_month:02d}/{latest_year} is "
                f"{abs(change)*100:.0f}% {direction} vs {latest_month:02d}/{latest_year-1}"
            ),
        }
    ]
    return insights


def product_correlation_insight(
    orders: List[UnifiedOrder],
    min_support: int = 3,
) -> List[Insight]:
    """Find product pairs frequently bought together in the same order."""
    from collections import Counter
    from itertools import combinations

    baskets: Dict[str, set] = {}
    for o in orders:
        if o.refund:
            continue
        baskets.setdefault(o.order_id, set()).add(o.product_name)

    pair_counts: Counter[tuple] = Counter()
    product_counts: Counter[str] = Counter()
    for products in baskets.values():
        products = sorted(products)
        if len(products) < 2:
            continue
        for p in products:
            product_counts[p] += 1
        for a, b in combinations(products, 2):
            pair_counts[(a, b)] += 1

    insights: List[Insight] = []
    for (a, b), count in pair_counts.most_common(5):
        if count < min_support:
            break
        confidence_a = count / product_counts[a] if product_counts[a] else 0.0
        confidence_b = count / product_counts[b] if product_counts[b] else 0.0
        lift = (count * len(baskets)) / (product_counts[a] * product_counts[b]) if product_counts[a] and product_counts[b] else 0.0
        if lift >= 1.2 and min(confidence_a, confidence_b) >= 0.25:
            insights.append(
                {
                    "type": "product_bundle",
                    "severity": "positive",
                    "message": f"'{a}' and '{b}' are bought together in {count} orders (lift {lift:.1f}) — consider a bundle",
                }
            )
    return insights


def stock_forecast_insight(
    orders: List[UnifiedOrder],
    days_window: int = 30,
    threshold_days: float = 14.0,
) -> List[Insight]:
    """Improved stock runout using a linear trend over the recent window."""
    import statistics
    from datetime import timedelta

    if not orders:
        return []
    latest = max(o.order_date for o in orders)
    cutoff = latest - timedelta(days=days_window)

    stocks: Dict[str, Optional[int]] = {}
    for o in orders:
        if o.stock_quantity is not None:
            stocks[o.product_name] = o.stock_quantity
    if not stocks:
        return []

    daily_sales: Dict[str, List[tuple]] = {name: [] for name in stocks}
    for o in orders:
        if o.refund or o.product_name not in stocks:
            continue
        if o.order_date >= cutoff:
            daily_sales[o.product_name].append((o.order_date, o.quantity))

    insights: List[Insight] = []
    for name, stock in stocks.items():
        if stock is None or stock <= 0:
            continue
        points = sorted(daily_sales[name])
        if len(points) < 2:
            continue
        x = [(d - cutoff).days for d, _ in points]
        y = [q for _, q in points]
        try:
            import numpy as np
            slope, intercept = np.polyfit(x, y, 1)
            velocity = max(float(slope), 0.0)
        except Exception:
            velocity = statistics.mean(y) if y else 0.0
        if velocity <= 0:
            continue
        days_left = stock / velocity
        if days_left <= threshold_days:
            insights.append(
                {
                    "type": "stock_forecast",
                    "severity": "critical" if days_left <= 7 else "warning",
                    "message": f"{name} stock may run out in {days_left:.0f} days at current velocity",
                }
            )
    return insights


def generate_insights(orders: List[UnifiedOrder]) -> List[Insight]:
    """Return all heuristic insights."""
    insights: List[Insight] = []
    insights.extend(sales_drop_insight(orders))
    insights.extend(low_margin_insight(orders))
    insights.extend(stock_runout_insight(orders))
    insights.extend(stock_forecast_insight(orders))
    insights.extend(refund_spike_insight(orders))
    insights.extend(year_over_year_insight(orders))
    insights.extend(product_correlation_insight(orders))
    return insights
