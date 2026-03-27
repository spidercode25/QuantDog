# pyright: reportMissingImports=false, reportUnknownVariableType=false

from __future__ import annotations

import os
from dataclasses import dataclass


def load_env() -> None:
    """Load a local .env file if present.

    This is intentionally opt-in (called by entrypoints) to avoid import-time
    side effects when `import quantdog` runs in verification.

    Tests can set SKIP_DOTENV=true to prevent .env file loading.
    """

    try:
        from dotenv import find_dotenv, load_dotenv  # type: ignore[import-not-found]
    except Exception:
        return

    # Allow tests to skip .env file loading by setting SKIP_DOTENV=true
    if os.getenv("SKIP_DOTENV", "").lower() in {"1", "true", "t", "yes", "y", "on"}:
        return

    env_path = find_dotenv(usecwd=True)
    if env_path:
        # Use override=False so existing environment variables take precedence.
        # This allows tests to monkeypatch environment variables and have them
        # override .env file values.
        load_dotenv(env_path, override=False)


def _parse_bool(name: str, value: str | None, default: bool) -> bool:
    if value is None:
        return default
    v = value.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off", ""}:
        return False
    raise ValueError(f"Invalid boolean for {name}: {value!r}")


def _parse_int(name: str, value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError as e:
        raise ValueError(f"Invalid integer for {name}: {value!r}") from e


@dataclass(frozen=True, slots=True)
class Settings:
    api_host: str
    api_port: int
    database_url: str | None
    enable_ai_analysis: bool
    research_enabled: bool
    worker_name: str
    worker_heartbeat_seconds: int
    log_dir: str
    news_enabled: bool
    opennews_base_url: str
    opennews_token: str | None
    news_limit: int
    news_cache_max_age_hours: int
    twitter_enabled: bool
    twitter_base_url: str
    twitter_token: str | None
    twitter_limit: int
    twelvedata_enabled: bool
    twelvedata_base_url: str
    twelvedata_api_key: str | None
    twelvedata_interval: str
    fred_base_url: str
    fred_api_key: str | None
    longbridge_app_key: str | None
    longbridge_app_secret: str | None
    longbridge_access_token: str | None
    telegram_enabled: bool
    telegram_bot_token: str | None
    telegram_api_token: str | None
    telegram_base_url: str
    telegram_poll_timeout_seconds: int
    telegram_poll_limit: int


def get_settings() -> Settings:
    # API uses API_HOST/API_PORT; keep HOST/PORT as backwards-compatible aliases.
    api_host = os.getenv("API_HOST") or os.getenv("HOST") or "0.0.0.0"
    api_port = _parse_int(
        "API_PORT",
        os.getenv("API_PORT") or os.getenv("PORT"),
        default=8000,
    )

    database_url = os.getenv("DATABASE_URL")
    enable_ai_analysis = _parse_bool(
        "ENABLE_AI_ANALYSIS", os.getenv("ENABLE_AI_ANALYSIS"), default=False
    )
    research_enabled = _parse_bool(
        "RESEARCH_ENABLED", os.getenv("RESEARCH_ENABLED"), default=False
    )

    worker_name = os.getenv("WORKER_NAME") or "quantdog-worker"
    worker_heartbeat_seconds = _parse_int(
        "WORKER_HEARTBEAT_SECONDS", os.getenv("WORKER_HEARTBEAT_SECONDS"), default=10
    )

    log_dir = os.getenv("LOG_DIR") or "/app/logs"

    news_enabled = _parse_bool("NEWS_ENABLED", os.getenv("NEWS_ENABLED"), default=True)
    opennews_base_url = os.getenv("OPENNEWS_BASE_URL") or "https://ai.6551.io"
    opennews_token = os.getenv("OPENNEWS_TOKEN")
    news_limit = _parse_int("NEWS_LIMIT", os.getenv("NEWS_LIMIT"), default=20)
    news_cache_max_age_hours = _parse_int(
        "NEWS_CACHE_MAX_AGE_HOURS",
        os.getenv("NEWS_CACHE_MAX_AGE_HOURS"),
        default=24,
    )

    twitter_enabled = _parse_bool("TWITTER_ENABLED", os.getenv("TWITTER_ENABLED"), default=True)
    twitter_base_url = os.getenv("TWITTER_BASE_URL") or "https://ai.6551.io"
    twitter_token = os.getenv("TWITTER_TOKEN")
    twitter_limit = _parse_int("TWITTER_LIMIT", os.getenv("TWITTER_LIMIT"), default=20)

    twelvedata_enabled = _parse_bool(
        "TWELVEDATA_ENABLED", os.getenv("TWELVEDATA_ENABLED"), default=False
    )
    twelvedata_base_url = os.getenv("TWELVEDATA_BASE_URL") or "https://api.twelvedata.com"
    twelvedata_api_key = os.getenv("TWELVEDATA_API_KEY")
    twelvedata_interval = (os.getenv("TWELVEDATA_INTERVAL") or "1day").strip() or "1day"

    fred_base_url = os.getenv("FRED_BASE_URL") or "https://api.stlouisfed.org/fred"
    fred_api_key = os.getenv("FRED_API_KEY")

    longbridge_app_key = os.getenv("LONGBRIDGE_APP_KEY")
    longbridge_app_secret = os.getenv("LONGBRIDGE_APP_SECRET")
    longbridge_access_token = os.getenv("LONGBRIDGE_ACCESS_TOKEN")

    telegram_enabled = _parse_bool(
        "TELEGRAM_ENABLED", os.getenv("TELEGRAM_ENABLED"), default=False
    )
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_api_token = os.getenv("TELEGRAM_API_TOKEN")
    telegram_base_url = (
        os.getenv("TELEGRAM_BASE_URL") or "https://api.telegram.org"
    ).strip() or "https://api.telegram.org"
    telegram_poll_timeout_seconds = _parse_int(
        "TELEGRAM_POLL_TIMEOUT_SECONDS",
        os.getenv("TELEGRAM_POLL_TIMEOUT_SECONDS"),
        default=30,
    )
    telegram_poll_limit = _parse_int(
        "TELEGRAM_POLL_LIMIT",
        os.getenv("TELEGRAM_POLL_LIMIT"),
        default=100,
    )

    return Settings(
        api_host=api_host,
        api_port=api_port,
        database_url=database_url,
        enable_ai_analysis=enable_ai_analysis,
        research_enabled=research_enabled,
        worker_name=worker_name,
        worker_heartbeat_seconds=worker_heartbeat_seconds,
        log_dir=log_dir,
        news_enabled=news_enabled,
        opennews_base_url=opennews_base_url,
        opennews_token=opennews_token,
        news_limit=news_limit,
        news_cache_max_age_hours=news_cache_max_age_hours,
        twitter_enabled=twitter_enabled,
        twitter_base_url=twitter_base_url,
        twitter_token=twitter_token,
        twitter_limit=twitter_limit,
        twelvedata_enabled=twelvedata_enabled,
        twelvedata_base_url=twelvedata_base_url,
        twelvedata_api_key=twelvedata_api_key,
        twelvedata_interval=twelvedata_interval,
        fred_base_url=fred_base_url,
        fred_api_key=fred_api_key,
        longbridge_app_key=longbridge_app_key,
        longbridge_app_secret=longbridge_app_secret,
        longbridge_access_token=longbridge_access_token,
        telegram_enabled=telegram_enabled,
        telegram_bot_token=telegram_bot_token,
        telegram_api_token=telegram_api_token,
        telegram_base_url=telegram_base_url,
        telegram_poll_timeout_seconds=telegram_poll_timeout_seconds,
        telegram_poll_limit=telegram_poll_limit,
    )


def validate_required_settings(settings: Settings) -> None:
    """Validate runtime settings expected to exist for a proper startup."""

    if not settings.database_url:
        raise ValueError(
            "Missing required setting: DATABASE_URL. "
            "Set it via environment variables or a local .env file."
        )
