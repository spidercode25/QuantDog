# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from unittest.mock import patch


def test_telegram_messages_success(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    with patch("api.telegram.queue.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = "job-123"

        response = client.post(
            "/api/v1/telegram/messages",
            json={"chat_id": "1234567890123", "text": "hello telegram"},
            headers={"Authorization": "Bearer api-token"},
        )

    assert response.status_code == 202
    data = response.get_json()
    assert data["code"] == 1
    assert data["data"]["job_id"] == "job-123"
    assert data["data"]["chat_id"] == 1234567890123
    assert data["data"]["dedupe_key"] is None


def test_telegram_messages_success_with_idempotency_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    with patch("api.telegram.queue.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = None

        response = client.post(
            "/api/v1/telegram/messages",
            json={"chat_id": 123, "text": "hello telegram"},
            headers={"Idempotency-Key": "abc-123", "Authorization": "Bearer api-token"},
        )

    assert response.status_code == 202
    data = response.get_json()
    assert data["code"] == 1
    assert data["data"]["job_id"] is None
    assert data["data"]["dedupe_key"] == "telegram:send:123:abc-123"


def test_telegram_messages_missing_json(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        data="not valid json",
        content_type="text/plain",
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "invalid_request"


def test_telegram_messages_json_array_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json=[{"chat_id": 123, "text": "hello"}],
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "invalid_request"


def test_telegram_messages_invalid_chat_id(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": "not-a-number", "text": "hello"},
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "invalid_field"


def test_telegram_messages_missing_text(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": 123, "text": "   "},
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "missing_field"


def test_telegram_messages_non_string_text_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": 123, "text": {"body": "hello"}},
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "missing_field"


def test_telegram_messages_text_too_long(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": 123, "text": "x" * 4097},
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "invalid_field"


def test_telegram_messages_enqueue_failure(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    with patch("api.telegram.queue.enqueue_job") as mock_enqueue:
        mock_enqueue.side_effect = Exception("Queue down")

        response = client.post(
            "/api/v1/telegram/messages",
            json={"chat_id": 123, "text": "hello"},
            headers={"Authorization": "Bearer api-token"},
        )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "job_enqueue_error"


def test_telegram_messages_chat_id_out_of_range(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": str(2**63), "text": "hello"},
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "invalid_field"


def test_telegram_messages_disabled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": 123, "text": "hello"},
        headers={"Authorization": "Bearer api-token"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "feature_disabled"


def test_telegram_messages_missing_api_token_config(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("SKIP_DOTENV", "true")  # Skip .env file loading
    monkeypatch.delenv("TELEGRAM_API_TOKEN", raising=False)

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": 123, "text": "hello"},
    )

    assert response.status_code == 400
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "configuration_error"


def test_telegram_messages_invalid_api_token(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "api-token")

    from api import create_app

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/v1/telegram/messages",
        json={"chat_id": 123, "text": "hello"},
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    data = response.get_json()
    assert data["code"] == 0
    assert data["error"]["type"] == "unauthorized"
