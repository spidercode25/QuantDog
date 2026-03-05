# pyright: reportMissingImports=false, reportUnknownVariableType=false

from __future__ import annotations

import os
from dataclasses import dataclass


def load_env() -> None:
    """Load a local .env file if present.

    This is intentionally opt-in (called by entrypoints) to avoid import-time
    side effects when `import quantdog` runs in verification.
    """

    try:
        from dotenv import find_dotenv, load_dotenv  # type: ignore[import-not-found]
    except Exception:
        return

    env_path = find_dotenv(usecwd=True)
    if env_path:
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

    return Settings(
        api_host=api_host,
        api_port=api_port,
        database_url=database_url,
        enable_ai_analysis=enable_ai_analysis,
        research_enabled=research_enabled,
        worker_name=worker_name,
        worker_heartbeat_seconds=worker_heartbeat_seconds,
        log_dir=log_dir,
    )


def validate_required_settings(settings: Settings) -> None:
    """Validate runtime settings expected to exist for a proper startup."""

    if not settings.database_url:
        raise ValueError(
            "Missing required setting: DATABASE_URL. "
            "Set it via environment variables or a local .env file."
        )
