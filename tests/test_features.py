"""Tests for new features: currency, validation, history, config."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import ReportConfig
from src.currency import convert, get_rate
from src.history import init_db, load_orders, upsert_orders
from src.schema import UnifiedOrder
from src.validation import validate_orders


@pytest.fixture
def sample_order():
    return UnifiedOrder(
        platform="etsy",
        order_id="ET-1",
        order_date=date(2025, 1, 1),
        product_name="Ring",
        sku="R1",
        quantity=2,
        unit_price=25.0,
        currency="USD",
        revenue=50.0,
    )


def test_validate_orders_catches_zero_price(sample_order):
    sample_order.unit_price = 0
    warnings = validate_orders([sample_order])
    assert any(w["type"] == "zero_or_negative_price" for w in warnings)


def test_validate_orders_ok(sample_order):
    assert validate_orders([sample_order]) == []


def test_history_roundtrip(tmp_path, sample_order):
    db = tmp_path / "test.db"
    upsert_orders([sample_order], db)
    loaded = load_orders(db)
    assert len(loaded) == 1
    assert loaded[0].order_id == "ET-1"


def test_currency_conversion_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("src.currency.CACHE_FILE", tmp_path / "rates.json")
    with patch("src.currency._fetch_rate", return_value=0.9) as mock_fetch:
        assert convert(100, "USD", "EUR") == pytest.approx(90.0)
        assert convert(100, "USD", "EUR") == pytest.approx(90.0)
    mock_fetch.assert_called_once()


def test_report_config_default():
    cfg = ReportConfig.default()
    assert cfg.base_currency == "EUR"
    assert cfg.primary_color == "#4a90d9"
