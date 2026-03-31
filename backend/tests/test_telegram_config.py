from __future__ import annotations

from datetime import time

import pytest

from config.settings import get_settings, validate_required_settings


def test_telegram_settings_defaults(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_API_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_GROUP_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_BASE_URL", raising=False)
    monkeypatch.delenv("TELEGRAM_POLL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("TELEGRAM_POLL_LIMIT", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_ENABLED", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_CLOSE_TIME_ET", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_STALE_AFTER_SECONDS", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_MIN_GAIN_PCT", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_MAX_GAIN_PCT", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_MIN_RVOL", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_MAX_CANDIDATES", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_MIN_DOLLAR_VOLUME", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_REQUIRE_COMMON_STOCK", raising=False)
    monkeypatch.delenv("CANDIDATE_POOL_REQUIRE_TRADABLE", raising=False)

    settings = get_settings()

    assert settings.telegram_enabled is False
    assert settings.telegram_bot_token is None
    assert settings.telegram_api_token is None
    assert settings.telegram_group_id is None
    assert settings.telegram_base_url == "https://api.telegram.org"
    assert settings.telegram_poll_timeout_seconds == 30
    assert settings.telegram_poll_limit == 100
    assert settings.candidate_pool_enabled is False
    assert settings.candidate_pool_close_time_et == time(16, 5)
    assert settings.candidate_pool_stale_after_seconds == 120
    assert settings.candidate_pool_min_gain_pct == 1.0
    assert settings.candidate_pool_max_gain_pct == 5.0
    assert settings.candidate_pool_min_rvol == 2.0
    assert settings.candidate_pool_max_candidates == 20
    assert settings.candidate_pool_min_dollar_volume == 10_000_000
    assert settings.candidate_pool_require_common_stock is True
    assert settings.candidate_pool_require_tradable is True


def test_telegram_settings_custom_values(monkeypatch):
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_API_TOKEN", "service-token")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.setenv("TELEGRAM_BASE_URL", "https://telegram.example.test")
    monkeypatch.setenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("TELEGRAM_POLL_LIMIT", "25")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "false")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:15")
    monkeypatch.setenv("CANDIDATE_POOL_STALE_AFTER_SECONDS", "300")
    monkeypatch.setenv("CANDIDATE_POOL_MIN_GAIN_PCT", "1.5")
    monkeypatch.setenv("CANDIDATE_POOL_MAX_GAIN_PCT", "4.5")
    monkeypatch.setenv("CANDIDATE_POOL_MIN_RVOL", "2.5")
    monkeypatch.setenv("CANDIDATE_POOL_MAX_CANDIDATES", "10")
    monkeypatch.setenv("CANDIDATE_POOL_MIN_DOLLAR_VOLUME", "25000000")
    monkeypatch.setenv("CANDIDATE_POOL_REQUIRE_COMMON_STOCK", "false")
    monkeypatch.setenv("CANDIDATE_POOL_REQUIRE_TRADABLE", "false")

    settings = get_settings()

    assert settings.telegram_enabled is True
    assert settings.telegram_bot_token == "secret-token"
    assert settings.telegram_api_token == "service-token"
    assert settings.telegram_group_id == -1001234567890
    assert settings.telegram_base_url == "https://telegram.example.test"
    assert settings.telegram_poll_timeout_seconds == 45
    assert settings.telegram_poll_limit == 25
    assert settings.candidate_pool_enabled is False
    assert settings.candidate_pool_close_time_et == time(16, 15)
    assert settings.candidate_pool_stale_after_seconds == 300
    assert settings.candidate_pool_min_gain_pct == 1.5
    assert settings.candidate_pool_max_gain_pct == 4.5
    assert settings.candidate_pool_min_rvol == 2.5
    assert settings.candidate_pool_max_candidates == 10
    assert settings.candidate_pool_min_dollar_volume == 25_000_000
    assert settings.candidate_pool_require_common_stock is False
    assert settings.candidate_pool_require_tradable is False


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TELEGRAM_POLL_TIMEOUT_SECONDS", "bad"),
        ("TELEGRAM_POLL_LIMIT", "bad"),
        ("TELEGRAM_GROUP_ID", "bad"),
        ("CANDIDATE_POOL_STALE_AFTER_SECONDS", "bad"),
        ("CANDIDATE_POOL_MAX_CANDIDATES", "bad"),
    ],
)
def test_telegram_settings_invalid_integer(monkeypatch, name: str, value: str):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=f"Invalid integer for {name}"):
        get_settings()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("CANDIDATE_POOL_MIN_GAIN_PCT", "bad"),
        ("CANDIDATE_POOL_MAX_GAIN_PCT", "bad"),
        ("CANDIDATE_POOL_MIN_RVOL", "bad"),
        ("CANDIDATE_POOL_MIN_DOLLAR_VOLUME", "bad"),
    ],
)
def test_telegram_settings_invalid_float(monkeypatch, name: str, value: str):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=f"Invalid float for {name}"):
        get_settings()


def test_telegram_settings_invalid_close_time(monkeypatch):
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "25:99")

    with pytest.raises(ValueError, match="Invalid time for CANDIDATE_POOL_CLOSE_TIME_ET"):
        get_settings()


def test_candidate_pool_validation_requires_telegram_group(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
    monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
    monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")
    monkeypatch.delenv("TELEGRAM_GROUP_ID", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_GROUP_ID"):
        validate_required_settings(get_settings())


def test_candidate_pool_validation_requires_telegram_enabled_and_bot(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
    monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
    monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_ENABLED", "false")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_ENABLED"):
        validate_required_settings(get_settings())

    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        validate_required_settings(get_settings())


def test_candidate_pool_validation_requires_longbridge_credentials(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
    monkeypatch.delenv("LONGBRIDGE_APP_KEY", raising=False)
    monkeypatch.delenv("LONGBRIDGE_APP_SECRET", raising=False)
    monkeypatch.delenv("LONGBRIDGE_ACCESS_TOKEN", raising=False)

    with pytest.raises(ValueError, match="LONGBRIDGE_APP_KEY"):
        validate_required_settings(get_settings())
