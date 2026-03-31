from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings, load_env, validate_required_settings
from infra.sqlalchemy import get_engine
from jobs.queue import _ensure_jobs_table


def _repair_sqlite_candidate_members(engine) -> None:
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("DROP TABLE IF EXISTS candidate_members")
        conn.exec_driver_sql(
            """
            CREATE TABLE candidate_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_key TEXT NOT NULL,
                symbol TEXT NOT NULL,
                rank INTEGER NOT NULL,
                rvol REAL NOT NULL,
                pct_change REAL NOT NULL,
                dollar_volume REAL NOT NULL,
                last_price REAL NOT NULL,
                inclusion_reason TEXT,
                exclusion_reason TEXT,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (snapshot_key) REFERENCES candidate_snapshots(snapshot_key) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE INDEX IF NOT EXISTS ix_candidate_members_snapshot_key_rank
            ON candidate_members (snapshot_key, rank)
            """
        )
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.commit()


def main() -> int:
    load_env()
    settings = get_settings()
    validate_required_settings(settings)

    if settings.database_url is None:
        raise ValueError("DATABASE_URL not set")

    alembic_cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")

    engine = get_engine(settings.database_url)
    _ensure_jobs_table(engine)

    if engine.dialect.name == "sqlite":
        _repair_sqlite_candidate_members(engine)
        print("SQLite candidate_members table repaired for AUTOINCREMENT compatibility")

    print("Database initialized successfully")
    print(f"- database_url: {settings.database_url}")
    print("- alembic upgrade: head")
    print("- jobs table: ensured")
    print("- candidate pool tables: ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
