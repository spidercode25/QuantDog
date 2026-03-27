from __future__ import annotations

import json

import httpx
import pytest

from infra.providers.telegram import (
    TelegramApiError,
    TelegramAuthError,
    TelegramBotClient,
    TelegramForbiddenError,
    TelegramRetryableError,
)


def test_telegram_client_happy_get_updates_and_send_message():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content.decode("utf-8"))

        if request.url.path.endswith("/getUpdates"):
            assert body == {
                "offset": 124,
                "timeout": 30,
                "limit": 100,
                "allowed_updates": ["message"],
            }
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [{"update_id": 124, "message": {"text": "/start"}}],
                },
            )

        assert request.url.path.endswith("/sendMessage")
        assert body == {"chat_id": 1234567890123, "text": "hello"}
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 7}})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    updates = client.get_updates(offset=124, timeout_seconds=30, limit=200)
    result = client.send_message(chat_id=1234567890123, text="hello")

    assert updates == [{"update_id": 124, "message": {"text": "/start"}}]
    assert result == {"message_id": 7}
    assert requests[0].url.path == "/bottest-token/getUpdates"
    assert requests[1].url.path == "/bottest-token/sendMessage"


def test_telegram_client_delete_webhook_happy():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert request.url.path.endswith("/deleteWebhook")
        assert body == {"drop_pending_updates": True}
        return httpx.Response(200, json={"ok": True, "result": True})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    assert client.delete_webhook(True) is True


def test_telegram_client_send_message_rejects_empty_text():
    client = TelegramBotClient(base_url="https://api.telegram.org", token="test-token")

    with pytest.raises(ValueError, match="must not be empty"):
        client.send_message(chat_id=1, text="   ")

    client.close()


def test_telegram_client_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"ok": False, "description": "Unauthorized"},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="bad-token",
        http_client=http_client,
    )

    with pytest.raises(TelegramAuthError, match="Unauthorized"):
        client.get_updates(offset=1, timeout_seconds=30, limit=10)


def test_telegram_client_forbidden_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"ok": False, "description": "Forbidden: bot was blocked by the user"},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    with pytest.raises(TelegramForbiddenError, match="blocked"):
        client.send_message(chat_id=1, text="hello")


def test_telegram_client_rate_limit_error_exposes_retry_after():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "ok": False,
                "description": "Too Many Requests: retry after 3",
                "parameters": {"retry_after": 3},
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    with pytest.raises(TelegramRetryableError) as exc_info:
        client.send_message(chat_id=1, text="hello")

    assert exc_info.value.retry_after == 3


def test_telegram_client_network_error_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    with pytest.raises(TelegramRetryableError, match="network error") as exc_info:
        client.get_updates(offset=1, timeout_seconds=30, limit=10)

    assert exc_info.value.retry_after is None


def test_telegram_client_server_error_is_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, json={"ok": False, "description": "Bad Gateway"})

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    with pytest.raises(TelegramRetryableError, match="HTTP 502"):
        client.get_updates(offset=1, timeout_seconds=30, limit=10)


def test_telegram_client_unexpected_bad_request_is_permanent():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"ok": False, "description": "Bad Request: chat not found"},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = TelegramBotClient(
        base_url="https://api.telegram.org",
        token="test-token",
        http_client=http_client,
    )

    with pytest.raises(TelegramApiError, match="chat not found"):
        client.send_message(chat_id=1, text="hello")
