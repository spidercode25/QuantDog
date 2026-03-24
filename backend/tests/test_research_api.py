# Research API tests for QuantDog

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

import pytest


def test_research_runs_feature_disabled(monkeypatch):
    """Test POST /api/v1/research/runs returns 404 when feature is disabled."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "false")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/research/runs",
        json={"symbol": "AAPL", "horizon": "1w"},
    )

    assert response.status_code == 404
    data = response.get_json()
    assert data["code"] == 0
    assert "Research feature is not enabled" in data["msg"]
    assert data["error"]["type"] == "feature_disabled"


def test_research_runs_invalid_json(monkeypatch):
    """Test POST /api/v1/research/runs with invalid JSON returns 415 (unsupported media type)."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/research/runs",
        data="not valid json",
        content_type="text/plain",
    )

    # Flask returns 415 for unsupported media type
    assert response.status_code == 415


def test_research_runs_missing_symbol(monkeypatch):
    """Test POST /api/v1/research/runs with empty symbol returns 400."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/research/runs",
        json={"symbol": ""},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]
    assert data["error"]["type"] == "missing_field"


def test_research_runs_empty_symbol(monkeypatch):
    """Test POST /api/v1/research/runs with empty symbol returns 400."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/research/runs",
        json={"symbol": "   "},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Symbol is required" in data["msg"]


def test_research_runs_invalid_horizon(monkeypatch):
    """Test POST /api/v1/research/runs with invalid horizon returns 400."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/research/runs",
        json={"symbol": "AAPL", "horizon": "invalid"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert "Invalid horizon" in data["msg"]
    assert data["error"]["type"] == "invalid_field"


def test_research_runs_valid_horizons(monkeypatch):
    """Test POST /api/v1/research/runs accepts valid horizons."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    valid_horizons = ["1d", "1w", "1m", "3m", "6m", "1y"]
    for horizon in valid_horizons:
        response = client.post(
            "/api/v1/research/runs",
            json={"symbol": "AAPL", "horizon": horizon},
        )
        # Should not get 400 for invalid horizon
        assert response.status_code != 400 or "Invalid horizon" not in str(response.get_json())


def test_research_runs_database_not_configured(monkeypatch):
    """Test POST /api/v1/research/runs with no database returns configuration error."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    # Mock get_settings to return None for database_url
    with patch("api.research.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.database_url = None
        mock_settings.research_enabled = True
        mock_get_settings.return_value = mock_settings

        response = client.post(
            "/api/v1/research/runs",
            json={"symbol": "AAPL", "horizon": "1w"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["code"] == 0
        assert "Database not configured" in data["msg"]
        assert data["error"]["type"] == "configuration_error"


def test_research_runs_enqueue_exception(monkeypatch):
    """Test POST /api/v1/research/runs handles enqueue exception."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    # Mock queue.enqueue_job to raise exception
    # Also need to mock get_engine since it's called before enqueue
    with patch("api.research.get_engine") as mock_get_engine:
        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        with patch("api.research.queue.enqueue_job") as mock_enqueue:
            mock_enqueue.side_effect = Exception("Queue connection failed")

            response = client.post(
                "/api/v1/research/runs",
                json={"symbol": "AAPL", "horizon": "1w"},
            )

            # The API returns 400 for job_enqueue_error, not 500
            assert response.status_code == 400
            data = response.get_json()
            assert data["code"] == 0
            assert "Failed to enqueue research run" in data["msg"]
            assert data["error"]["type"] == "job_enqueue_error"


def test_research_runs_success(monkeypatch):
    """Test POST /api/v1/research/runs returns 202 with run_id on success."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    # Mock uuid and queue
    fixed_uuid = "12345678-1234-1234-1234-123456789abc"
    with patch("api.research.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value = uuid.UUID(fixed_uuid)

        with patch("api.research.queue.enqueue_job") as mock_enqueue:
            mock_enqueue.return_value = None

            response = client.post(
                "/api/v1/research/runs",
                json={"symbol": "aapl", "horizon": "1w"},
            )

            assert response.status_code == 202
            data = response.get_json()
            assert data["code"] == 1
            assert data["msg"] == "success"
            assert "data" in data
            assert data["data"]["run_id"] == fixed_uuid
            assert data["data"]["symbol"] == "AAPL"  # Normalized to uppercase
            assert data["data"]["horizon"] == "1w"
            assert data["data"]["status"] == "PENDING"


def test_research_runs_success_with_idempotency_key(monkeypatch):
    """Test POST /api/v1/research/runs accepts idempotency key header."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    fixed_uuid = "12345678-1234-1234-1234-123456789abc"
    with patch("api.research.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value = uuid.UUID(fixed_uuid)

        with patch("api.research.queue.enqueue_job") as mock_enqueue:
            mock_enqueue.return_value = None

            response = client.post(
                "/api/v1/research/runs",
                json={"symbol": "AAPL", "horizon": "1w"},
                headers={"Idempotency-Key": "test-key-123"},
            )

            assert response.status_code == 202
            data = response.get_json()
            assert data["code"] == 1
            assert data["data"]["run_id"] == fixed_uuid


def test_research_runs_envelope_structure(monkeypatch):
    """Test POST /api/v1/research/runs returns proper envelope structure."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("RESEARCH_ENABLED", "true")

    from api import create_app

    app = create_app()
    client = app.test_client()

    # Test error envelope structure
    response = client.post(
        "/api/v1/research/runs",
        json={},
    )

    data = response.get_json()
    assert "code" in data
    assert "msg" in data
    assert "error" in data
    assert "type" in data["error"]
    assert "detail" in data["error"]
