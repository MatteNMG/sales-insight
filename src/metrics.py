"""Pure metric functions over a list of UnifiedOrder objects."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from .schema import UnifiedOrder


def _active(orders: List[UnifiedOrder]) -> List[UnifiedOrder]:
    return [o for o in orders if not o.refund]


def total_revenue(orders: List[UnifiedOrder]) -> float:
    return sum(o.revenue for o in _active(orders))


def total_units(orders: List[UnifiedOrder]) -> int:
    return sum(o.quantity for o in _active(orders))


def total_orders(orders: List[UnifiedOrder]) -> int:
    return len({o.order_id for o in orders})


def unique_orders_active(orders: List[UnifiedOrder]) -> int:
    return len({o.order_id for o in _active(orders)})


def average_order_value(orders: List[UnifiedOrder]) -> float:
    active = _active(orders)
    count = unique_orders_active(active)
    return total_revenue(active) / count if count else 0.0


def refund_rate(orders: List[UnifiedOrder]) -> float:
    total = len(orders)
    refunded = sum(1 for o in orders if o.refund)
    return refunded / total if total else 0.0


def revenue_by_product(orders: List[UnifiedOrder]) -> Dict[str, float]:
    result: Dict[str, float] = defaultdict(float)
    for o in _active(orders):
        result[o.product_name] += o.revenue
    return dict(result)


def units_by_product(orders: List[UnifiedOrder]) -> Dict[str, int]:
    result: Dict[str, int] = defaultdict(int)
    for o in _active(orders):
        result[o.product_name] += o.quantity
    return dict(result)


def revenue_by_date(orders: List[UnifiedOrder]) -> Dict[date, float]:
    result: Dict[date, float] = defaultdict(float)
    for o in _active(orders):
        result[o.order_date] += o.revenue
    return dict(sorted(result.items()))


def revenue_by_country(orders: List[UnifiedOrder]) -> Dict[str, float]:
    result: Dict[str, float] = defaultdict(float)
    for o in _active(orders):
        if o.country:
            result[o.country] += o.revenue
    return dict(result)


def margin_by_product(orders: List[UnifiedOrder]) -> Dict[str, float]:
    """Gross margin per product when cost_per_unit is available.

    Falls back to net revenue (revenue - fees - shipping) when no cost is known.
    """
    revenue = defaultdict(float)
    cost = defaultdict(float)
    has_cost = False
    for o in _active(orders):
        revenue[o.product_name] += o.revenue
        if o.cost_per_unit is not None:
            cost[o.product_name] += o.cost_per_unit * o.quantity
            has_cost = True
        else:
            cost[o.product_name] += o.fees + o.shipping_cost
    if has_cost:
        return {name: revenue[name] - cost[name] for name in revenue}
    return {name: revenue[name] - cost[name] for name in revenue}


def top_products(
    orders: List[UnifiedOrder],
    by_revenue: bool = True,
    n: int = 5,
) -> List[Tuple[str, float]]:
    data = revenue_by_product(orders) if by_revenue else {k: float(v) for k, v in units_by_product(orders).items()}
    return sorted(data.items(), key=lambda x: x[1], reverse=True)[:n]


def flop_products(
    orders: List[UnifiedOrder],
    by_revenue: bool = True,
    n: int = 5,
) -> List[Tuple[str, float]]:
    data = revenue_by_product(orders) if by_revenue else {k: float(v) for k, v in units_by_product(orders).items()}
    return sorted(data.items(), key=lambda x: x[1])[:n]


def stock_runout_days(
    orders: List[UnifiedOrder],
    days_window: int = 30,
) -> Dict[str, Optional[float]]:
    """Estimate days of stock remaining at recent velocity.

    Returns None for products without stock_quantity.
    """
    from datetime import timedelta

    if not orders:
        return {}
    latest = max(o.order_date for o in orders)
    cutoff = latest - timedelta(days=days_window)
    units_sold: Dict[str, int] = defaultdict(int)
    for o in _active(orders):
        if o.order_date >= cutoff:
            units_sold[o.product_name] += o.quantity
    stocks: Dict[str, int] = {o.product_name: o.stock_quantity for o in orders if o.stock_quantity is not None}
    result: Dict[str, Optional[float]] = {}
    for name, stock in stocks.items():
        sold = units_sold.get(name, 0)
        daily = sold / days_window if days_window else 0.0
        result[name] = stock / daily if daily else None
    return result


def summary(orders: List[UnifiedOrder]) -> dict:
    return {
        "total_revenue": total_revenue(orders),
        "total_units": total_units(orders),
        "total_orders": total_orders(orders),
        "active_orders": unique_orders_active(orders),
        "average_order_value": average_order_value(orders),
        "refund_rate": refund_rate(orders),
        "top_products": top_products(orders),
        "flop_products": flop_products(orders),
    }
