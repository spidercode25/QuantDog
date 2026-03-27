from __future__ import annotations

import pytest

from config.settings import get_settings


def test_telegram_settings_defaults(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_API_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BASE_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_POLL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("TELEGRAM_POLL_LIMIT", raising=False)

    settings = get_settings()

    assert settings.telegram_enabled is False
    assert settings.telegram_bot_token is None
    assert settings.telegram_api_token is None
    assert settings.telegram_base_url == "https://api.telegram.org"
    assert settings.telegram_poll_timeout_seconds == 30
    assert settings.telegram_poll_limit == 100


def test_telegram_settings_custom_values(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "service-token")
    monkeypatch.setenv("TELEGRAM_BASE_URL", "https://telegram.example.test")
    monkeypatch.setenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("TELEGRAM_POLL_LIMIT", "25")

    settings = get_settings()

    assert settings.telegram_enabled is True
    assert settings.telegram_bot_token == "secret-token"
    assert settings.telegram_api_token == "service-token"
    assert settings.telegram_base_url == "https://telegram.example.test"
    assert settings.telegram_poll_timeout_seconds == 45
    assert settings.telegram_poll_limit == 25


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TELEGRAM_POLL_TIMEOUT_SECONDS", "bad"),
        ("TELEGRAM_POLL_LIMIT", "bad"),
    ],
)
def test_telegram_settings_invalid_integer(monkeypatch, name: str, value: str):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=f"Invalid integer for {name}"):
        get_settings()
