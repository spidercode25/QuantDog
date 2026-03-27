from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from infra.sqlalchemy import get_engine
from telegram.repository import (
    ensure_bot_state,
    get_last_update_id,
    has_bot_state,
    upsert_last_update_id,
)


def _create_telegram_bot_state_table(database_url: str) -> None:
    engine = get_engine(database_url)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE telegram_bot_state (
                    bot_name TEXT PRIMARY KEY,
                    last_update_id INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.commit()


def _sqlite_database_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'telegram-test.db'}"


def test_telegram_repository_ensure_and_read(tmp_path: Path):
    database_url = _sqlite_database_url(tmp_path)
    _create_telegram_bot_state_table(database_url)

    assert has_bot_state(database_url, "quantdog-bot") is False

    ensure_bot_state(database_url, "quantdog-bot")

    assert has_bot_state(database_url, "quantdog-bot") is True
    assert get_last_update_id(database_url, "quantdog-bot") == 0


def test_telegram_repository_upsert_last_update_id(tmp_path: Path):
    database_url = _sqlite_database_url(tmp_path)
    _create_telegram_bot_state_table(database_url)

    ensure_bot_state(database_url, "quantdog-bot")
    upsert_last_update_id(database_url, "quantdog-bot", 123)

    assert get_last_update_id(database_url, "quantdog-bot") == 123

    upsert_last_update_id(database_url, "quantdog-bot", 456)

    assert get_last_update_id(database_url, "quantdog-bot") == 456


def test_telegram_repository_missing_row_returns_zero(tmp_path: Path):
    database_url = _sqlite_database_url(tmp_path)
    _create_telegram_bot_state_table(database_url)

    assert get_last_update_id(database_url, "missing-bot") == 0
