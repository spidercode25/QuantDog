from __future__ import annotations

from unittest.mock import patch

import pytest

from infra.providers.telegram import TelegramForbiddenError, TelegramRetryableError
from jobs.telegram_delivery import handle_telegram_send_message


def test_telegram_delivery_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")

    with patch("jobs.telegram_delivery.TelegramBotClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.send_message.return_value = {"message_id": 99}

        result = handle_telegram_send_message({"chat_id": 123, "text": "hello"})

    assert result == {"status": "sent", "chat_id": 123, "message_id": 99}
    mock_client.send_message.assert_called_once_with(chat_id=123, text="hello")
    mock_client.close.assert_called_once()


def test_telegram_delivery_forbidden_is_skipped(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")

    with patch("jobs.telegram_delivery.TelegramBotClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.send_message.side_effect = TelegramForbiddenError("blocked by user")

        result = handle_telegram_send_message({"chat_id": 123, "text": "hello"})

    assert result == {"status": "skipped", "chat_id": 123, "reason": "blocked by user"}
    mock_client.close.assert_called_once()


def test_telegram_delivery_retryable_error_retries(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")

    with patch("jobs.telegram_delivery.TelegramBotClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.send_message.side_effect = [
            TelegramRetryableError("retry later", retry_after=2),
            {"message_id": 55},
        ]

        with patch("jobs.telegram_delivery.time.sleep") as mock_sleep:
            result = handle_telegram_send_message({"chat_id": 123, "text": "hello"})

    assert result == {"status": "sent", "chat_id": 123, "message_id": 55}
    mock_sleep.assert_called_once_with(2)
    assert mock_client.send_message.call_count == 2
    mock_client.close.assert_called_once()


def test_telegram_delivery_retryable_error_exhausts(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")

    with patch("jobs.telegram_delivery.TelegramBotClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.send_message.side_effect = TelegramRetryableError("retry later")

        with patch("jobs.telegram_delivery.time.sleep") as mock_sleep:
            with pytest.raises(TelegramRetryableError, match="retry later"):
                handle_telegram_send_message({"chat_id": 123, "text": "hello"})

    assert mock_client.send_message.call_count == 3
    assert mock_sleep.call_count == 2
    mock_client.close.assert_called_once()
