"""Tests for CSV normalization."""

from io import StringIO

import pandas as pd
import pytest

from src.parser import normalize, read_csv
from src.schema import UnifiedOrder, infer_platform


ETSY_CSV = """Sale Date,Order ID,Item Name,Quantity,Price,Shipping,Currency,Delivery Country,SKU,Card Processing Fees,Transaction Fees,Listing Fees
2025-01-05,ET-1,Ring,2,25.00,4.50,EUR,IT,RING-01,1.20,1.50,0.40
2025-01-06,ET-2,Wallet,1,45.00,5.00,EUR,FR,WALL-02,2.10,2.70,0.60
"""

SHOPIFY_CSV = """Name,Created at,Lineitem quantity,Lineitem name,Lineitem sku,Lineitem price,Shipping,Taxes,Financial Status,Shipping Country
#1001,2025-01-02 09:12:00,1,Vase,VASE-101,34.00,5.00,3.40,paid,NL
#1002,2025-01-04 14:33:00,2,Bag,TOTE-103,22.00,6.00,4.40,refunded,BE
"""

AMAZON_CSV = """order-id,order-date,product-name,sku,quantity,item-price,currency,item-status,ship-country,amazon-fee,shipping-fee
AZ-1,2025-01-03,Mask,SLEP-201,2,29.99,EUR,Shipped,IT,5.40,4.50
AZ-2,2025-01-06,Stand,STND-202,1,14.99,EUR,Cancelled,FR,0.00,0.00
"""


def test_infer_platform():
    df = read_csv(StringIO(ETSY_CSV))
    assert infer_platform(df.columns) == "etsy"
    df = read_csv(StringIO(SHOPIFY_CSV))
    assert infer_platform(df.columns) == "shopify"
    df = read_csv(StringIO(AMAZON_CSV))
    assert infer_platform(df.columns) == "amazon"


def test_normalize_etsy():
    df = read_csv(StringIO(ETSY_CSV))
    orders = normalize(df)
    assert len(orders) == 2
    assert orders[0].revenue == 50.0
    assert orders[0].fees == pytest.approx(3.10)
    assert orders[0].shipping_cost == pytest.approx(4.50)


def test_normalize_shopify_refund():
    df = read_csv(StringIO(SHOPIFY_CSV))
    orders = normalize(df)
    assert len(orders) == 2
    assert orders[1].refund is True


def test_normalize_amazon_cancelled():
    df = read_csv(StringIO(AMAZON_CSV))
    orders = normalize(df)
    assert orders[1].refund is True


def test_revenue_calculation():
    df = read_csv(StringIO(AMAZON_CSV))
    orders = normalize(df)
    assert orders[0].revenue == pytest.approx(59.98)
