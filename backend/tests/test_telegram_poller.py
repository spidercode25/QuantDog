from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from config import get_settings
from infra.providers.telegram import TelegramRetryableError
from jobs.telegram_poller import TelegramPoller


def _message_update(update_id: int, text: str, *, chat_id: int = 123456789) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "text": text,
            "chat": {"id": chat_id, "type": "private"},
        },
    }


def test_telegram_poller_first_boot_clears_webhook_and_persists_offset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    settings = get_settings()

    client = MagicMock()
    client.get_updates.return_value = [_message_update(10, "/start")]
    bot_service = MagicMock()
    bot_service.handle_update.return_value = "hello"

    with patch("jobs.telegram_poller.has_bot_state", return_value=False), patch(
        "jobs.telegram_poller.ensure_bot_state"
    ) as mock_ensure, patch(
        "jobs.telegram_poller.get_last_update_id", side_effect=[0, 10]
    ), patch("jobs.telegram_poller.upsert_last_update_id") as mock_upsert:
        poller = TelegramPoller(settings=settings, client=client, bot_service=bot_service)

        result = poller.run_once()

    client.delete_webhook.assert_called_once_with(drop_pending_updates=True)
    client.get_updates.assert_called_once_with(offset=1, timeout_seconds=30, limit=100)
    client.send_message.assert_called_once_with(chat_id=123456789, text="hello")
    mock_ensure.assert_called_once()
    mock_upsert.assert_called_once_with("sqlite:///:memory:", "quantdog-telegram-bot", 10)
    assert result == {"updates_polled": 1, "updates_processed": 1, "last_update_id": 10}


def test_telegram_poller_resumed_boot_keeps_backlog(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    settings = get_settings()

    client = MagicMock()
    client.get_updates.return_value = []
    bot_service = MagicMock()

    with patch("jobs.telegram_poller.has_bot_state", return_value=True), patch(
        "jobs.telegram_poller.get_last_update_id", side_effect=[10, 10]
    ):
        poller = TelegramPoller(settings=settings, client=client, bot_service=bot_service)
        result = poller.run_once()

    client.delete_webhook.assert_called_once_with(drop_pending_updates=False)
    client.get_updates.assert_called_once_with(offset=11, timeout_seconds=30, limit=100)
    assert result == {"updates_polled": 0, "updates_processed": 0, "last_update_id": 10}


def test_telegram_poller_non_text_update_advances_offset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    settings = get_settings()

    client = MagicMock()
    client.get_updates.return_value = [
        {"update_id": 12, "message": {"chat": {"id": 123, "type": "private"}, "photo": []}}
    ]
    bot_service = MagicMock()
    bot_service.handle_update.return_value = None

    with patch("jobs.telegram_poller.has_bot_state", return_value=True), patch(
        "jobs.telegram_poller.get_last_update_id", side_effect=[11, 12]
    ), patch("jobs.telegram_poller.upsert_last_update_id") as mock_upsert:
        poller = TelegramPoller(settings=settings, client=client, bot_service=bot_service)
        poller.run_once()

    client.send_message.assert_not_called()
    mock_upsert.assert_called_once_with("sqlite:///:memory:", "quantdog-telegram-bot", 12)


def test_telegram_poller_retryable_send_does_not_advance_offset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    settings = get_settings()

    client = MagicMock()
    client.get_updates.return_value = [_message_update(13, "/help")]
    client.send_message.side_effect = TelegramRetryableError("retry later")
    bot_service = MagicMock()
    bot_service.handle_update.return_value = "hello"

    with patch("jobs.telegram_poller.has_bot_state", return_value=True), patch(
        "jobs.telegram_poller.get_last_update_id", side_effect=[12]
    ), patch("jobs.telegram_poller.upsert_last_update_id") as mock_upsert:
        poller = TelegramPoller(settings=settings, client=client, bot_service=bot_service)

        with pytest.raises(TelegramRetryableError, match="retry later"):
            poller.run_once()

        mock_upsert.assert_not_called()


def test_telegram_poller_malformed_chat_payload_advances_offset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    settings = get_settings()

    client = MagicMock()
    client.get_updates.return_value = [
        {
            "update_id": 14,
            "message": {
                "message_id": 14,
                "text": "/start",
                "chat": {"id": "bad-id", "type": "private"},
            },
        }
    ]
    bot_service = MagicMock()
    bot_service.handle_update.return_value = None

    with patch("jobs.telegram_poller.has_bot_state", return_value=True), patch(
        "jobs.telegram_poller.get_last_update_id", side_effect=[13, 14]
    ), patch("jobs.telegram_poller.upsert_last_update_id") as mock_upsert:
        poller = TelegramPoller(settings=settings, client=client, bot_service=bot_service)
        poller.run_once()

    client.send_message.assert_not_called()
    mock_upsert.assert_called_once_with("sqlite:///:memory:", "quantdog-telegram-bot", 14)


def test_run_telegram_bot_once(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setattr("sys.argv", ["run_telegram_bot.py", "--once"])

    from run_telegram_bot import main

    with patch("run_telegram_bot.TelegramBotClient") as mock_client_class, patch(
        "run_telegram_bot.TelegramPoller"
    ) as mock_poller_class, patch("run_telegram_bot.configure_logging"):
        mock_poller = mock_poller_class.return_value

        result = main()

    assert result == 0
    mock_poller.run_once.assert_called_once()
    mock_client_class.return_value.close.assert_called_once()
