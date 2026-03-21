# Market and Stocks API tests for QuantDog

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


def test_market_technical_success(monkeypatch):
    """Test POST /api/v1/market/technical returns success with stubbed service."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Mock the MarketIntelService
    with patch("quantdog.api.market.MarketIntelService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_technical_analysis.return_value = {
            "symbol": "AAPL",
            "technical": {"sma20": 150.0, "rsi14": 65.0},
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/v1/market/technical",
            json={"symbol": "AAPL", "horizon": "1d"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["code"] == 1
        assert data["msg"] == "success"
        assert "data" in data


def test_market_technical_missing_symbol(monkeypatch):
    """Test POST /api/v1/market/technical returns 400 when symbol is missing."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/market/technical",
        json={},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]
    assert data["error"]["type"] == "missing_field"


def test_market_intel_success(monkeypatch):
    """Test POST /api/v1/market/intel returns success with stubbed service."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Mock the MarketIntelService
    with patch("quantdog.api.market.MarketIntelService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_news_twitter_analysis.return_value = {
            "symbol": "AAPL",
            "sentiment": "positive",
            "mentions": 150,
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/v1/market/intel",
            json={"symbol": "AAPL", "limit": 20},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["code"] == 1
        assert data["msg"] == "success"
        assert "data" in data


def test_market_intel_missing_symbol(monkeypatch):
    """Test POST /api/v1/market/intel returns 400 when symbol is missing."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/market/intel",
        json={},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]


def test_market_macro_success(monkeypatch):
    """Test POST /api/v1/market/macro returns success with stubbed service."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Mock the MarketIntelService
    with patch("quantdog.api.market.MarketIntelService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_macro_analysis.return_value = {
            "symbol": "AAPL",
            "macro_indicators": {"gdp_growth": 2.5, "inflation": 3.1},
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/v1/market/macro",
            json={"symbol": "AAPL", "limit": 20},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["code"] == 1
        assert data["msg"] == "success"
        assert "data" in data


def test_market_macro_missing_symbol(monkeypatch):
    """Test POST /api/v1/market/macro returns 400 when symbol is missing."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/market/macro",
        json={},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]


def test_stocks_strategy_success(monkeypatch):
    """Test POST /api/v1/stocks/<symbol>/strategy returns success with stubbed service."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Mock the MarketIntelService
    with patch("quantdog.api.stocks.MarketIntelService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_strategy.return_value = {
            "symbol": "AAPL",
            "recommendation": "BUY",
            "confidence": 75,
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/v1/stocks/AAPL/strategy",
            json={"horizon": "1d", "limit": 20},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["code"] == 1
        assert data["msg"] == "success"
        assert "data" in data


def test_stocks_strategy_value_error(monkeypatch):
    """Test POST /api/v1/stocks/<symbol>/strategy handles ValueError from service."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Mock the MarketIntelService to raise ValueError
    with patch("quantdog.api.stocks.MarketIntelService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_strategy.side_effect = ValueError("Invalid symbol")
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/v1/stocks/INVALID/strategy",
            json={"horizon": "1d"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["code"] == 0
        assert "Strategy analysis failed" in data["msg"]


def test_stocks_monitor_batch_success(monkeypatch):
    """Test POST /api/v1/stocks/monitor returns success with valid symbols list."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Mock the MarketIntelService
    with patch("quantdog.api.stocks.MarketIntelService") as mock_service_class:
        mock_service = MagicMock()
        mock_service.get_monitoring.return_value = {
            "results": [
                {"symbol": "AAPL", "price": 150.0},
                {"symbol": "GOOGL", "price": 2800.0},
            ],
            "alerts": [],
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/v1/stocks/monitor",
            json={"symbols": ["AAPL", "GOOGL"], "horizon": "1d"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["code"] == 1
        assert data["msg"] == "success"
        assert "data" in data


def test_stocks_monitor_batch_empty_symbols(monkeypatch):
    """Test POST /api/v1/stocks/monitor returns 400 when symbols is empty list."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/stocks/monitor",
        json={"symbols": []},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "symbols is required" in data["msg"]
    assert "non-empty list" in data["error"]["detail"]


def test_stocks_monitor_batch_missing_symbols(monkeypatch):
    """Test POST /api/v1/stocks/monitor returns 400 when symbols field is missing."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/stocks/monitor",
        json={},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "symbols is required" in data["msg"]


def test_stocks_monitor_batch_not_a_list(monkeypatch):
    """Test POST /api/v1/stocks/monitor returns 400 when symbols is not a list."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/stocks/monitor",
        json={"symbols": "AAPL"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "symbols is required" in data["msg"]
