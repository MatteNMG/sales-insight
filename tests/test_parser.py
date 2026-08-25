"""Tests for CSV normalization."""

from io import BytesIO, StringIO

import pandas as pd
import pytest

from src.csv_checker import check_csv
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


PLATFORM_CSVS = {
    "etsy": ETSY_CSV,
    "shopify": SHOPIFY_CSV,
    "amazon": AMAZON_CSV,
}


@pytest.mark.parametrize("platform,csv_text", PLATFORM_CSVS.items())
def test_csv_checker_accepts_platform_samples(platform, csv_text):
    result = check_csv(BytesIO(csv_text.encode()), expected_platform=platform)
    assert result["ok"] is True
    assert result["platform"] == platform


@pytest.mark.parametrize("platform,csv_text", PLATFORM_CSVS.items())
@pytest.mark.parametrize("failure", ["missing", "delimiter", "empty", "encoding"])
def test_csv_checker_rejects_broken_platform_files(platform, csv_text, failure):
    if failure == "missing":
        lines = csv_text.splitlines()
        header = lines[0].split(",")
        column = {"etsy": "Sale Date", "shopify": "Created at", "amazon": "order-date"}[platform]
        index = header.index(column)
        content = "\n".join(
            ",".join(value for position, value in enumerate(line.split(",")) if position != index)
            for line in lines
        ).encode()
    elif failure == "delimiter":
        content = csv_text.replace(",", ";").encode()
    elif failure == "empty":
        content = b""
    else:
        content = b"\xff\xfe\x00\x81"

    result = check_csv(BytesIO(content), expected_platform=platform)
    assert result["ok"] is False
    assert result["error"]


def test_csv_checker_rejects_wrong_selected_platform():
    result = check_csv(BytesIO(ETSY_CSV.encode()), expected_platform="amazon")
    assert result["ok"] is False
    assert "Etsy CSV, not Amazon" in result["error"]


def test_product_cost_and_stock_from_optional_csv_columns():
    csv_text = ETSY_CSV.replace("Listing Fees", "Listing Fees,cost_per_unit,stock_quantity").replace(
        "0.40\n", "0.40,8.50,12\n"
    ).replace("0.60\n", "0.60,18.00,5\n")
    orders = normalize(read_csv(StringIO(csv_text)))
    assert orders[0].cost_per_unit == 8.5
    assert orders[0].stock_quantity == 12


def test_product_cost_and_stock_from_config_fallback():
    orders = normalize(
        read_csv(StringIO(ETSY_CSV)),
        product_overrides={"RING-01": {"cost_per_unit": 8.5, "stock_quantity": 12}},
    )
    assert orders[0].cost_per_unit == 8.5
    assert orders[0].stock_quantity == 12
