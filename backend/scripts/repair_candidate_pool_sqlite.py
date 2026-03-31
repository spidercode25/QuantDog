from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_settings, load_env, validate_required_settings
from infra.sqlalchemy import get_engine


def main() -> int:
    load_env()
    settings = get_settings()
    validate_required_settings(settings)

    if settings.database_url is None:
        raise ValueError("DATABASE_URL not set")

    engine = get_engine(settings.database_url)
    if engine.dialect.name != "sqlite":
        raise ValueError("repair_candidate_pool_sqlite.py only supports sqlite databases")

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS candidate_members"))
        conn.execute(
            text(
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
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_candidate_members_snapshot_key_rank
                ON candidate_members (snapshot_key, rank)
                """
            )
        )
        conn.commit()

    print("Rebuilt sqlite candidate_members table with INTEGER PRIMARY KEY AUTOINCREMENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
