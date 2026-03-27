from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from api import create_app


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_latest_snapshot_success() -> None:
    """API returns latest successful candidate pool with envelope contract."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from screening.candidate_pool_repository import CandidatePoolRepository, CandidateMember
    from sqlalchemy import text

    app = create_app()
    client = app.test_client()

    # Create tables
    with app.app_context():
        from quantdog.infra.sqlalchemy import get_engine

        engine = get_engine(os.environ["DATABASE_URL"])
        with engine.connect() as conn:
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS candidate_snapshots (
                        snapshot_key TEXT PRIMARY KEY,
                        snapshot_time_et TIMESTAMP NOT NULL,
                        provider_asof_et TIMESTAMP NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                """)
            )
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS candidate_members (
                        id SERIAL PRIMARY KEY,
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
                        FOREIGN KEY (snapshot_key) REFERENCES candidate_snapshots(snapshot_key)
                    )
                """)
            )
            conn.commit()

        # Insert test data
        repo = CandidatePoolRepository(engine)
        snapshot_key = "2026-01-15_10:30:00"
        snapshot_time = _dt(2026, 1, 15, 10, 30)
        provider_asof = _dt(2026, 1, 15, 10, 30)

        members = [
            CandidateMember(
                snapshot_key=snapshot_key,
                symbol="ALFA",
                rank=1,
                rvol=2.0,
                pct_change=3.2,
                dollar_volume=100_000_000,
                last_price=20.0,
                inclusion_reason="passed_all_filters",
                exclusion_reason=None,
                created_at=datetime.utcnow(),
            ),
            CandidateMember(
                snapshot_key=snapshot_key,
                symbol="BETA",
                rank=2,
                rvol=1.8,
                pct_change=2.5,
                dollar_volume=90_000_000,
                last_price=18.0,
                inclusion_reason="passed_all_filters",
                exclusion_reason=None,
                created_at=datetime.utcnow(),
            ),
        ]

        repo.upsert_snapshot(snapshot_key, snapshot_time, provider_asof, members)

    # Test API
    response = client.get("/api/v1/candidate-pools/latest")
    assert response.status_code == 200

    data = response.get_json()
    assert data["code"] == 1
    assert data["msg"] == "success"
    assert "data" in data

    result = data["data"]
    assert result["snapshot_time"] == "10:30:00"
    assert result["timezone"] == "America/New_York"
    assert result["count"] == 2
    assert len(result["candidates"]) == 2

    # Verify candidate data
    candidates = result["candidates"]
    assert candidates[0]["symbol"] == "ALFA"
    assert candidates[0]["rank"] == 1
    assert candidates[0]["rvol"] == 2.0
    assert candidates[0]["pct_change"] == 3.2
    assert candidates[0]["dollar_volume"] == 100_000_000
    assert candidates[0]["last_price"] == 20.0


def test_empty_snapshot() -> None:
    """API handles empty snapshot with count 0."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from screening.candidate_pool_repository import CandidatePoolRepository
    from sqlalchemy import text

    app = create_app()
    client = app.test_client()

    # Create tables
    with app.app_context():
        from quantdog.infra.sqlalchemy import get_engine

        engine = get_engine(os.environ["DATABASE_URL"])
        with engine.connect() as conn:
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS candidate_snapshots (
                        snapshot_key TEXT PRIMARY KEY,
                        snapshot_time_et TIMESTAMP NOT NULL,
                        provider_asof_et TIMESTAMP NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                """)
            )
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS candidate_members (
                        id SERIAL PRIMARY KEY,
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
                        FOREIGN KEY (snapshot_key) REFERENCES candidate_snapshots(snapshot_key)
                    )
                """)
            )
            conn.commit()

        # Insert empty snapshot
        repo = CandidatePoolRepository(engine)
        snapshot_key = "2026-01-15_10:30:00"
        snapshot_time = _dt(2026, 1, 15, 10, 30)
        provider_asof = _dt(2026, 1, 15, 10, 30)

        repo.upsert_snapshot(snapshot_key, snapshot_time, provider_asof, [])

    # Test API
    response = client.get("/api/v1/candidate-pools/latest")
    assert response.status_code == 200

    data = response.get_json()
    assert data["code"] == 1
    assert data["msg"] == "success"

    result = data["data"]
    assert result["count"] == 0
    assert result["candidates"] == []


def test_no_snapshot_exists() -> None:
    """API returns 404 when no snapshot exists."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    app = create_app()
    client = app.test_client()

    # Create tables
    with app.app_context():
        from quantdog.infra.sqlalchemy import get_engine
        from sqlalchemy import text

        engine = get_engine(os.environ["DATABASE_URL"])
        with engine.connect() as conn:
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS candidate_snapshots (
                        snapshot_key TEXT PRIMARY KEY,
                        snapshot_time_et TIMESTAMP NOT NULL,
                        provider_asof_et TIMESTAMP NOT NULL,
                        created_at TIMESTAMP NOT NULL
                    )
                """)
            )
            conn.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS candidate_members (
                        id SERIAL PRIMARY KEY,
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
                        FOREIGN KEY (snapshot_key) REFERENCES candidate_snapshots(snapshot_key)
                    )
                """)
            )
            conn.commit()

    # Test API
    response = client.get("/api/v1/candidate-pools/latest")
    assert response.status_code == 404

    data = response.get_json()
    assert data["code"] == 0
    assert "No candidate snapshot found" in data["msg"]
