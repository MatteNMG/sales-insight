"""Generate synthetic demo data for the Streamlit preview."""

from __future__ import annotations

from datetime import date, timedelta
from random import choice, randint, uniform
from typing import List

from .schema import UnifiedOrder


PRODUCTS = [
    ("Handmade Silver Ring", "RING-01", 25.0, 8.0),
    ("Personalized Leather Wallet", "WALL-02", 45.0, 18.0),
    ("Macrame Plant Hanger", "PLNT-03", 18.0, 6.0),
    ("Custom Dog Bandana", "DOG-04", 12.0, 3.5),
    ("Minimalist Ceramic Vase", "VASE-101", 34.0, 12.0),
    ("Wooden Coaster Set", "CSTR-102", 15.0, 4.0),
    ("Linen Tote Bag", "TOTE-103", 22.0, 7.0),
]

COUNTRIES = ["IT", "FR", "DE", "ES", "NL", "BE"]


def generate_demo_orders(days: int = 180, orders_per_day: int = 5) -> List[UnifiedOrder]:
    """Generate plausible demo orders for the past N days."""
    end = date.today()
    start = end - timedelta(days=days)
    orders: List[UnifiedOrder] = []
    order_counter = 1000
    for i in range(days):
        current = start + timedelta(days=i)
        n_orders = randint(max(0, orders_per_day - 2), orders_per_day + 2)
        for _ in range(n_orders):
            order_counter += 1
            product, sku, price, cost = choice(PRODUCTS)
            quantity = randint(1, 3)
            unit_price = round(uniform(price * 0.9, price * 1.1), 2)
            fees = round(unit_price * quantity * uniform(0.08, 0.15), 2)
            shipping = round(uniform(3.0, 7.0), 2)
            refund = uniform(0, 1) < 0.03
            stock = randint(5, 200)
            orders.append(
                UnifiedOrder(
                    platform=choice(["etsy", "shopify", "amazon"]),
                    order_id=f"DEMO-{order_counter}",
                    order_date=current,
                    product_name=product,
                    sku=sku,
                    quantity=quantity,
                    unit_price=unit_price,
                    currency="EUR",
                    revenue=round(unit_price * quantity, 2),
                    cost_per_unit=round(cost, 2),
                    fees=fees,
                    shipping_cost=shipping,
                    refund=refund,
                    country=choice(COUNTRIES),
                    stock_quantity=stock,
                    base_currency="EUR",
                    unit_price_base=unit_price,
                    revenue_base=round(unit_price * quantity, 2),
                )
            )
    return orders
