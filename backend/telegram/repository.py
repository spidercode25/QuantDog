from __future__ import annotations

from sqlalchemy import text

from infra.sqlalchemy import get_engine


def has_bot_state(database_url: str, bot_name: str) -> bool:
    engine = get_engine(database_url)

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT 1 FROM telegram_bot_state WHERE bot_name = :bot_name LIMIT 1"
            ),
            {"bot_name": bot_name},
        )
        return result.fetchone() is not None


def ensure_bot_state(database_url: str, bot_name: str) -> None:
    engine = get_engine(database_url)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO telegram_bot_state (bot_name, last_update_id, created_at, updated_at)
                VALUES (:bot_name, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (bot_name) DO NOTHING
                """
            ),
            {"bot_name": bot_name},
        )
        conn.commit()


def get_last_update_id(database_url: str, bot_name: str) -> int:
    engine = get_engine(database_url)

    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT last_update_id
                FROM telegram_bot_state
                WHERE bot_name = :bot_name
                """
            ),
            {"bot_name": bot_name},
        )
        row = result.fetchone()

    if row is None or row[0] is None:
        return 0

    return int(row[0])


def upsert_last_update_id(database_url: str, bot_name: str, last_update_id: int) -> None:
    engine = get_engine(database_url)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO telegram_bot_state (bot_name, last_update_id, created_at, updated_at)
                VALUES (:bot_name, :last_update_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (bot_name)
                DO UPDATE SET
                    last_update_id = EXCLUDED.last_update_id,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "bot_name": bot_name,
                "last_update_id": int(last_update_id),
            },
        )
        conn.commit()
