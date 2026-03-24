# Health endpoint tests for QuantDog API

import os
import pytest


def test_v1_health_envelope():
    """Test /api/v1/health returns correct envelope."""
    # Set fake DATABASE_URL before importing app
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.get_json()
    assert data["code"] == 1
    assert data["msg"] == "success"
    assert data["data"]["status"] == "ok"

    # Cleanup
    os.environ.pop("DATABASE_URL", None)


def test_openapi_has_version():
    """Test /api/v1/openapi.json returns valid OpenAPI doc."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    data = response.get_json()
    assert "openapi" in data
    assert data["openapi"].startswith("3.")

    os.environ.pop("DATABASE_URL", None)


def test_readyz_ok_with_sqlite_memory(monkeypatch):
    """Test /api/v1/readyz returns 200 with sqlite memory db."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.get("/api/v1/readyz")

    assert response.status_code == 200
    data = response.get_json()
    assert data["code"] == 1
    assert data["data"]["status"] == "ok"
