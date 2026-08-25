"""Tests for new features: currency, validation, history, config."""

from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest

from webapp import app
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


def test_health_check():
    with app.test_client() as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_demo_and_exports(tmp_path):
    app.config.update(DB_PATH=tmp_path / "history.db", UPLOAD_FOLDER=tmp_path / "uploads")
    app.config["UPLOAD_FOLDER"].mkdir()
    with app.test_client() as client:
        demo_response = client.get("/api/demo")
        assert demo_response.status_code == 200
        assert demo_response.get_json()["summary"]["orders"] > 0

        for report_format, mimetype in (
            ("html", "text/html"),
            ("pdf", "application/pdf"),
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ):
            response = client.get(f"/api/export/{report_format}")
            assert response.status_code == 200
            assert response.mimetype == mimetype
            assert response.data


@pytest.mark.parametrize("platform", ["etsy", "shopify", "amazon"])
def test_sample_csv_download(platform):
    with app.test_client() as client:
        response = client.get(f"/samples/{platform}.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"


@pytest.mark.parametrize("platform", ["etsy", "shopify", "amazon"])
def test_platform_sample_upload_end_to_end(tmp_path, platform):
    app.config.update(DB_PATH=tmp_path / "history.db", UPLOAD_FOLDER=tmp_path / "uploads")
    app.config["UPLOAD_FOLDER"].mkdir()
    sample = Path("data/samples") / f"{platform}_orders.csv"
    with app.test_client() as client, sample.open("rb") as csv_file:
        check_response = client.post(
            "/api/check",
            data={"file": (csv_file, sample.name), "platform": platform},
            content_type="multipart/form-data",
        )
        assert check_response.status_code == 200
        assert check_response.get_json()["ok"] is True

    with app.test_client() as client, sample.open("rb") as csv_file:
        upload_response = client.post(
            "/api/upload",
            data={"file": (csv_file, sample.name), "platform": platform},
            content_type="multipart/form-data",
        )
        assert upload_response.status_code == 200
        assert upload_response.get_json()["summary"]["orders"] > 0
        assert client.get("/api/export/html").status_code == 200
        assert client.get("/api/export/pdf").status_code == 200
        assert client.get("/api/export/xlsx").status_code == 200


def test_upload_returns_actionable_error_inline_payload(tmp_path):
    app.config.update(DB_PATH=tmp_path / "history.db", UPLOAD_FOLDER=tmp_path / "uploads")
    app.config["UPLOAD_FOLDER"].mkdir()
    with app.test_client() as client:
        response = client.post(
            "/api/upload",
            data={"file": (BytesIO(b"Order ID,Item Name\n1,Ring"), "broken.csv"), "platform": "etsy"},
            content_type="multipart/form-data",
        )
    assert response.status_code == 400
    assert response.get_json()["error"].startswith("Missing column 'Sale Date'")
