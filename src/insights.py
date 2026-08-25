"""Heuristic business insights over UnifiedOrder data."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import math
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
    """Compare the latest week with the same weekdays in the prior four weeks."""
    if not orders:
        return []
    latest = max(o.order_date for o in orders)
    recent_start = latest - timedelta(days=6)
    baseline_start = recent_start - timedelta(days=28)
    if min(o.order_date for o in orders) > baseline_start:
        return []

    daily: Dict[str, Dict[date, float]] = defaultdict(lambda: defaultdict(float))
    for order in orders:
        if not order.refund:
            daily[order.product_name][order.order_date] += order.effective_revenue

    insights: List[Insight] = []
    for product, values in daily.items():
        recent = sum(values.get(recent_start + timedelta(days=offset), 0.0) for offset in range(7))
        expected = 0.0
        for offset in range(7):
            weekday = recent_start + timedelta(days=offset)
            expected += mean([values.get(weekday - timedelta(days=7 * week), 0.0) for week in range(1, 5)])
        if expected > 0 and recent <= expected * (1 - threshold):
            drop = (expected - recent) / expected * 100
            insights.append({
                "type": "seasonal_sales_drop",
                "severity": "warning",
                "message": f"{product} sales are {drop:.0f}% below the usual level for these weekdays",
            })
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
    total_rev = sum(revenues.values())
    portfolio_rate = sum(margins.values()) / total_rev if total_rev else 0.0
    insights: List[Insight] = []
    for product, margin in margins.items():
        rev = revenues.get(product, 0.0)
        if rev <= 0:
            continue
        rate = margin / rev
        if rate < threshold_percent or rate < portfolio_rate - 0.10:
            insights.append({
                "type": "low_margin",
                "severity": "critical" if rate < 0 else "warning",
                "message": f"{product} margin is {rate*100:.1f}% versus {portfolio_rate*100:.1f}% across the portfolio",
            })
    return insights


def stock_runout_insight(
    orders: List[UnifiedOrder],
    threshold_days: float = 14.0,
) -> List[Insight]:
    """Flag products likely to run out of stock soon."""
    runouts = stock_runout_days(orders)
    latest = max((order.order_date for order in orders), default=date.today())
    insights: List[Insight] = []
    for product, days in runouts.items():
        if days is not None and days <= threshold_days:
            runout_date = latest + timedelta(days=max(1, round(days)))
            insights.append(
                {
                    "type": "stock_runout",
                    "severity": "critical" if days <= 7 else "warning",
                    "message": f"At the current sales pace, {product} will run out in {days:.0f} days ({runout_date.isoformat()})",
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
    current_notes = sorted({
        order.event_note for order in orders
        if order.order_date.year == latest_year and order.order_date.month == latest_month and order.event_note
    })
    previous_notes = sorted({
        order.event_note for order in orders
        if order.order_date.year == latest_year - 1 and order.order_date.month == latest_month and order.event_note
    })
    context = ""
    if current_notes:
        context += f"; current-period context: {', '.join(current_notes)}"
    if previous_notes:
        context += f"; prior-year context: {', '.join(previous_notes)}"
    insights: List[Insight] = [
        {
            "type": "yoy_revenue",
            "severity": "info" if abs(change) < 0.1 else ("positive" if change >= 0 else "warning"),
            "message": (
                f"Revenue for {latest_month:02d}/{latest_year} is "
                f"{abs(change)*100:.0f}% {direction} vs {latest_month:02d}/{latest_year-1}{context}"
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
                    "message": f"Real-order pattern: customers bought '{a}' with '{b}' in {count} orders (lift {lift:.1f}) — consider a bundle",
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


def price_scenario(
    orders: List[UnifiedOrder],
    product_name: str,
    price_change_percent: float,
) -> Optional[dict]:
    product_orders = [order for order in orders if not order.refund and order.product_name == product_name]
    prices = sorted({round(order.effective_unit_price, 2) for order in product_orders if order.effective_unit_price > 0})
    if len(product_orders) < 20 or len(prices) < 3:
        return None

    grouped: Dict[float, List[float]] = defaultdict(lambda: [0.0, 0.0])
    for order in product_orders:
        grouped[round(order.effective_unit_price, 2)][0] += order.quantity
        grouped[round(order.effective_unit_price, 2)][1] += order.effective_revenue
    x = [math.log(price) for price in grouped]
    y = [math.log(values[0]) for values in grouped.values() if values[0] > 0]
    if len(x) != len(y):
        return None
    x_mean, y_mean = mean(x), mean(y)
    denominator = sum((value - x_mean) ** 2 for value in x)
    if denominator == 0:
        return None
    elasticity = sum((px - x_mean) * (qy - y_mean) for px, qy in zip(x, y)) / denominator
    elasticity = min(0.0, max(-3.0, elasticity))
    change = price_change_percent / 100
    current_revenue = sum(order.effective_revenue for order in product_orders)
    projected_revenue = current_revenue * (1 + change) * max(0.0, 1 + elasticity * change)
    confidence = "medium" if len(product_orders) >= 50 and len(prices) >= 4 else "low"
    return {
        "product": product_name,
        "price_change_percent": price_change_percent,
        "current_revenue": round(current_revenue, 2),
        "projected_revenue": round(projected_revenue, 2),
        "elasticity": round(elasticity, 2),
        "confidence": confidence,
        "caveat": "Directional estimate from historical price and unit changes; it does not include traffic, promotions, or competitor activity.",
    }


def price_scenario_insight(orders: List[UnifiedOrder]) -> List[Insight]:
    products = sorted({order.product_name for order in orders})
    scenarios = [price_scenario(orders, product, 10.0) for product in products]
    scenarios = [scenario for scenario in scenarios if scenario]
    if not scenarios:
        return []
    scenario = max(scenarios, key=lambda value: value["current_revenue"])
    return [{
        "type": "price_scenario",
        "severity": "info",
        "message": f"Cautious scenario: a 10% price increase for {scenario['product']} projects revenue of {scenario['projected_revenue']:.2f} versus {scenario['current_revenue']:.2f} ({scenario['confidence']} confidence; historical correlation, not a causal forecast)",
    }]


def cross_platform_performance_insight(orders: List[UnifiedOrder]) -> List[Insight]:
    performance: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    names: Dict[str, str] = {}
    for order in orders:
        if order.refund:
            continue
        key = order.sku or order.product_name.casefold()
        names[key] = order.product_name
        performance[key][order.platform][0] += order.net_revenue
        performance[key][order.platform][1] += order.quantity

    insights: List[Insight] = []
    for key, platforms in performance.items():
        if len(platforms) < 2:
            continue
        per_unit = {platform: totals[0] / totals[1] for platform, totals in platforms.items() if totals[1]}
        if len(per_unit) < 2:
            continue
        best = max(per_unit, key=per_unit.get)
        worst = min(per_unit, key=per_unit.get)
        if per_unit[worst] > 0 and per_unit[best] >= per_unit[worst] * 1.10:
            difference = (per_unit[best] / per_unit[worst] - 1) * 100
            insights.append({
                "type": "cross_platform_performance",
                "severity": "info",
                "message": f"{names[key]} earns {difference:.0f}% more net per unit on {best.title()} than {worst.title()} after fees and shipping",
            })
    return insights


def fee_anomaly_insight(orders: List[UnifiedOrder], threshold: float = 0.20) -> List[Insight]:
    if not orders:
        return []
    latest = max(order.order_date for order in orders)
    recent_start = latest - timedelta(days=29)
    previous_start = recent_start - timedelta(days=30)
    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for order in orders:
        if order.refund or order.order_date < previous_start:
            continue
        period = "recent" if order.order_date >= recent_start else "previous"
        totals[order.platform][f"{period}_fees"] += order.fees
        totals[order.platform][f"{period}_revenue"] += order.effective_revenue

    insights: List[Insight] = []
    for platform, values in totals.items():
        previous_revenue = values["previous_revenue"]
        recent_revenue = values["recent_revenue"]
        if not previous_revenue or not recent_revenue:
            continue
        previous_rate = values["previous_fees"] / previous_revenue
        recent_rate = values["recent_fees"] / recent_revenue
        if recent_rate >= previous_rate * (1 + threshold) and recent_rate - previous_rate >= 0.02:
            insights.append({
                "type": "fee_anomaly",
                "severity": "warning",
                "message": f"{platform.title()} fees rose from {previous_rate*100:.1f}% to {recent_rate*100:.1f}% of revenue in the last 30 days",
            })
    return insights


def generate_insights(orders: List[UnifiedOrder]) -> List[Insight]:
    """Return all heuristic insights."""
    insights: List[Insight] = []
    insights.extend(sales_drop_insight(orders))
    insights.extend(low_margin_insight(orders))
    insights.extend(stock_runout_insight(orders))
    insights.extend(refund_spike_insight(orders))
    insights.extend(cross_platform_performance_insight(orders))
    insights.extend(fee_anomaly_insight(orders))
    insights.extend(price_scenario_insight(orders))
    insights.extend(year_over_year_insight(orders))
    insights.extend(product_correlation_insight(orders))
    return insights
