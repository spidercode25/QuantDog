from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings, load_env, validate_required_settings
from infra.sqlalchemy import get_engine


def _table_exists(conn, table_name: str) -> bool:
    dialect = conn.engine.dialect.name

    if dialect == "sqlite":
        result = conn.execute(
            text(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = :table_name
                """
            ),
            {"table_name": table_name},
        )
        return result.fetchone() is not None

    result = conn.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = :table_name
            """
        ),
        {"table_name": table_name},
    )
    return result.fetchone() is not None


def _delete_if_exists(conn, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    result = conn.execute(text(f"DELETE FROM {table_name}"))
    return result.rowcount or 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear QuantDog test data")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Also clear telegram bot state / polling state tables if present",
    )
    args = parser.parse_args()

    load_env()
    settings = get_settings()
    validate_required_settings(settings)

    if settings.database_url is None:
        raise ValueError("DATABASE_URL not set")

    engine = get_engine(settings.database_url)

    tables = [
        "candidate_members",
        "candidate_snapshots",
        "jobs",
    ]
    if args.all:
        tables.extend(
            [
                "telegram_chat_state",
                "telegram_update_state",
                "telegram_message_log",
            ]
        )

    deleted: dict[str, int] = {}
    with engine.connect() as conn:
        for table_name in tables:
            deleted[table_name] = _delete_if_exists(conn, table_name)
        conn.commit()

    print("Cleared test data:")
    for table_name in tables:
        print(f"- {table_name}: {deleted[table_name]} rows")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
