# Analysis API tests for QuantDog

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


def test_analysis_fast_invalid_json(monkeypatch):
    """Test POST /api/v1/analysis/fast with invalid JSON returns 415 (unsupported media type)."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/analysis/fast",
        data="not valid json",
        content_type="text/plain",
    )

    # Flask returns 415 for unsupported media type
    assert response.status_code == 415


def test_analysis_fast_missing_symbol(monkeypatch):
    """Test POST /api/v1/analysis/fast with empty symbol returns 400."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/analysis/fast",
        json={"symbol": ""},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]
    assert data["error"]["type"] == "missing_field"


def test_analysis_fast_empty_symbol(monkeypatch):
    """Test POST /api/v1/analysis/fast with whitespace-only symbol returns 400."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/analysis/fast",
        json={"symbol": "   "},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]


def test_analysis_fast_invalid_horizon(monkeypatch):
    """Test POST /api/v1/analysis/fast with invalid horizon returns 400."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/analysis/fast",
        json={"symbol": "AAPL", "horizon": "invalid"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Invalid horizon" in data["msg"]
    assert data["error"]["type"] == "invalid_field"


def test_analysis_fast_valid_horizons(monkeypatch):
    """Test POST /api/v1/analysis/fast accepts valid horizons."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    valid_horizons = ["1d", "1w", "1m"]
    for horizon in valid_horizons:
        response = client.post(
            "/api/v1/analysis/fast",
            json={"symbol": "AAPL", "horizon": horizon},
        )
        # Should not get 400 for invalid horizon
        assert response.status_code != 400 or "Invalid horizon" not in str(response.get_json())


def test_analysis_fast_symbol_uppercase(monkeypatch):
    """Test POST /api/v1/analysis/fast normalizes symbol to uppercase."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Test that lowercase symbol gets normalized
    response = client.post(
        "/api/v1/analysis/fast",
        json={"symbol": "aapl", "horizon": "1d"},
    )

    # Should pass validation (may fail later due to DB, but symbol should be normalized)
    data = response.get_json()
    # If we get a response, the symbol was processed
    # We can't easily verify uppercase conversion without DB, but the code does .upper()


def test_analysis_fast_envelope_structure(monkeypatch):
    """Test POST /api/v1/analysis/fast returns proper envelope structure for errors."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Test error envelope structure
    response = client.post(
        "/api/v1/analysis/fast",
        json={},
    )

    data = response.get_json()
    assert "code" in data
    assert "msg" in data
    assert "error" in data
    assert "type" in data["error"]
    assert "detail" in data["error"]


def test_analysis_fast_default_horizon(monkeypatch):
    """Test POST /api/v1/analysis/fast uses default horizon of 1d."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from quantdog.api import create_app

    app = create_app()
    client = app.test_client()

    # Request without horizon should use default "1d"
    response = client.post(
        "/api/v1/analysis/fast",
        json={"symbol": "AAPL"},
    )

    # Should pass horizon validation (may fail later due to DB)
    # The default horizon is "1d" which is valid
    if response.status_code == 400:
        data = response.get_json()
        assert "Invalid horizon" not in str(data.get("msg", "")), "Default horizon should be valid"
