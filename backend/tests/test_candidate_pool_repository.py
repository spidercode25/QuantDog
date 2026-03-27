from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from screening.candidate_pool_repository import (
    CandidateMember,
    CandidatePoolRepository,
    CandidateSnapshot,
)


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_upsert_snapshot_is_idempotent() -> None:
    """Duplicate execution of the same snapshot key does not duplicate rows."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from quantdog.infra.sqlalchemy import get_engine
    from sqlalchemy import text

    engine = get_engine()

    # Create tables
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

    # First upsert
    repo.upsert_snapshot(snapshot_key, snapshot_time, provider_asof, members)

    # Count members
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM candidate_members WHERE snapshot_key = :snapshot_key"),
            {"snapshot_key": snapshot_key},
        )
        count_after_first = result.scalar()
        assert count_after_first == 2, "First upsert should create 2 members"

    # Second upsert (idempotent)
    repo.upsert_snapshot(snapshot_key, snapshot_time, provider_asof, members)

    # Count members again
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM candidate_members WHERE snapshot_key = :snapshot_key"),
            {"snapshot_key": snapshot_key},
        )
        count_after_second = result.scalar()
        assert count_after_second == 2, "Second upsert should not duplicate members"


def test_store_ranked_members_with_metrics() -> None:
    """Stored rows include rank, RVOL, percent change, dollar volume, and timestamps."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from quantdog.infra.sqlalchemy import get_engine
    from sqlalchemy import text

    engine = get_engine()

    # Create tables
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
    ]

    repo.upsert_snapshot(snapshot_key, snapshot_time, provider_asof, members)

    # Verify stored metrics
    stored_members = repo.get_snapshot_members(snapshot_key)
    assert len(stored_members) == 1

    member = stored_members[0]
    assert member.symbol == "ALFA"
    assert member.rank == 1
    assert member.rvol == 2.0
    assert member.pct_change == 3.2
    assert member.dollar_volume == 100_000_000
    assert member.last_price == 20.0
    assert member.inclusion_reason == "passed_all_filters"
    assert member.exclusion_reason is None


def test_retention_prunes_old_candidate_snapshots() -> None:
    """Old snapshots are pruned based on retention policy."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from quantdog.infra.sqlalchemy import get_engine
    from sqlalchemy import text

    engine = get_engine()

    # Create tables
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

    repo = CandidatePoolRepository(engine)

    # Create old snapshot
    old_snapshot_key = "2025-12-01_10:30:00"
    old_snapshot_time = _dt(2025, 12, 1, 10, 30)
    old_provider_asof = _dt(2025, 12, 1, 10, 30)

    # Manually insert old snapshot with old created_at
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO candidate_snapshots (snapshot_key, snapshot_time_et, provider_asof_et, created_at)
                VALUES (:snapshot_key, :snapshot_time_et, :provider_asof_et, :created_at)
            """),
            {
                "snapshot_key": old_snapshot_key,
                "snapshot_time_et": old_snapshot_time,
                "provider_asof_et": old_provider_asof,
                "created_at": datetime.utcnow() - timedelta(days=35),
            },
        )
        conn.commit()

    # Create recent snapshot
    recent_snapshot_key = "2026-01-15_10:30:00"
    recent_snapshot_time = _dt(2026, 1, 15, 10, 30)
    recent_provider_asof = _dt(2026, 1, 15, 10, 30)

    repo.upsert_snapshot(
        recent_snapshot_key,
        recent_snapshot_time,
        recent_provider_asof,
        [],
    )

    # Prune old snapshots (keep 30 days)
    deleted_count = repo.prune_old_snapshots(keep_days=30)

    assert deleted_count == 1, "Should delete 1 old snapshot"

    # Verify old snapshot is gone
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM candidate_snapshots WHERE snapshot_key = :snapshot_key"),
            {"snapshot_key": old_snapshot_key},
        )
        old_count = result.scalar()
        assert old_count == 0, "Old snapshot should be deleted"

    # Verify recent snapshot still exists
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM candidate_snapshots WHERE snapshot_key = :snapshot_key"),
            {"snapshot_key": recent_snapshot_key},
        )
        recent_count = result.scalar()
        assert recent_count == 1, "Recent snapshot should still exist"
