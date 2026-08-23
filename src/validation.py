"""Validation and warning generation for suspicious order records."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Dict, List

from .schema import UnifiedOrder


ValidationWarning = Dict[str, str]


def validate_orders(orders: List[UnifiedOrder]) -> List[ValidationWarning]:
    """Return a list of warnings for suspicious records."""
    warnings: List[ValidationWarning] = []
    seen: Counter[tuple] = Counter()

    for order in orders:
        if not order.order_id or str(order.order_id).lower() == "nan":
            warnings.append({
                "type": "missing_order_id",
                "severity": "error",
                "message": f"Record with product '{order.product_name}' has no order id",
            })
        if order.quantity <= 0:
            warnings.append({
                "type": "invalid_quantity",
                "severity": "error",
                "message": f"Order {order.order_id} / {order.product_name} has non-positive quantity {order.quantity}",
            })
        if order.unit_price <= 0:
            warnings.append({
                "type": "zero_or_negative_price",
                "severity": "warning",
                "message": f"Order {order.order_id} / {order.product_name} price is {order.unit_price}",
            })
        if order.order_date == date.min:
            warnings.append({
                "type": "missing_date",
                "severity": "warning",
                "message": f"Order {order.order_id} has an unparseable date",
            })
        if not order.product_name or str(order.product_name).lower() == "nan":
            warnings.append({
                "type": "missing_product_name",
                "severity": "error",
                "message": f"Order {order.order_id} has no product name",
            })
        if order.cost_per_unit is not None and order.cost_per_unit > order.effective_unit_price:
            warnings.append({
                "type": "negative_margin",
                "severity": "warning",
                "message": (
                    f"{order.product_name} cost per unit ({order.cost_per_unit}) "
                    f"exceeds price ({order.effective_unit_price})"
                ),
            })
        key = (order.platform, order.order_id, order.sku)
        seen[key] += 1
        if seen[key] > 1:
            warnings.append({
                "type": "duplicate_line",
                "severity": "warning",
                "message": f"Duplicate line for {key}",
            })

    return warnings
