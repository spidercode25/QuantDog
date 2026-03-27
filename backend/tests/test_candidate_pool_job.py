from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from screening.candidate_pool_job import is_market_open, run_candidate_pool_job


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_job_publishes_single_snapshot() -> None:
    """Job publishes once on a valid trading day."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from screening.candidate_data_provider import (
        FakeCandidateDataProvider,
        InstrumentMetadata,
        IntradayQuote,
        ProviderSnapshot,
        VolumeHistory,
    )
    from screening.candidate_pool_repository import CandidatePoolRepository
    from sqlalchemy import text

    # Create tables
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

    # Create fake provider
    freshness = _dt(2026, 1, 15, 10, 30)
    provider = FakeCandidateDataProvider(
        snapshots_by_symbol={
            "ALFA": ProviderSnapshot(
                quote=IntradayQuote(
                    symbol="ALFA",
                    pct_change=3.2,
                    last=20.0,
                    cum_volume=5_000_000,
                    prior_close=19.38,
                    quote_freshness_timestamp=freshness,
                ),
                metadata=InstrumentMetadata(
                    symbol="ALFA",
                    asset_type="common_stock",
                    is_common_stock=True,
                    is_tradable=True,
                    metadata_freshness_timestamp=freshness,
                ),
                volume_history=VolumeHistory(
                    symbol="ALFA",
                    prior_same_time_cum_volumes=[2_500_000] * 7,
                    history_freshness_timestamp=freshness,
                ),
                provider_freshness_timestamp=freshness,
            )
        }
    )

    # Run job
    snapshot_time = _dt(2026, 1, 15, 10, 30)
    snapshot_key = run_candidate_pool_job(
        provider=provider,
        snapshot_time_et=snapshot_time,
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=10_000_000,
    )

    # Verify snapshot was created
    repo = CandidatePoolRepository(engine)
    snapshot = repo.get_latest_snapshot()
    assert snapshot is not None
    assert snapshot.snapshot_key == snapshot_key

    # Verify members were stored
    members = repo.get_snapshot_members(snapshot_key)
    assert len(members) == 1
    assert members[0].symbol == "ALFA"
    assert members[0].rank == 1


def test_job_skips_when_market_closed() -> None:
    """Job skips on weekends and outside market hours."""
    # Saturday - should be closed
    saturday = _dt(2026, 1, 17, 10, 30)  # Saturday
    assert not is_market_open(snapshot_time_et=saturday)

    # Sunday - should be closed
    sunday = _dt(2026, 1, 18, 10, 30)  # Sunday
    assert not is_market_open(snapshot_time_et=sunday)

    # Before market open - should be closed
    before_open = _dt(2026, 1, 15, 9, 0)  # 9:00 AM
    assert not is_market_open(snapshot_time_et=before_open)

    # After market close - should be closed
    after_close = _dt(2026, 1, 15, 16, 30)  # 4:30 PM
    assert not is_market_open(snapshot_time_et=after_close)

    # During market hours - should be open
    during_hours = _dt(2026, 1, 15, 10, 30)  # 10:30 AM
    assert is_market_open(snapshot_time_et=during_hours)


def test_job_skips_after_half_day_close() -> None:
    """Job skips snapshot after early close on half-days."""
    half_days = {date(2026, 11, 27)}
    half_day_close = time(13, 0)

    # Before early close - should be open
    before_close = _dt(2026, 11, 27, 12, 30)
    assert is_market_open(
        snapshot_time_et=before_close,
        half_days=half_days,
        half_day_close_et=half_day_close,
    )

    # After early close - should be closed
    after_close = _dt(2026, 11, 27, 14, 0)
    assert not is_market_open(
        snapshot_time_et=after_close,
        half_days=half_days,
        half_day_close_et=half_day_close,
    )


def test_job_fails_when_provider_data_is_stale() -> None:
    """Job fails when provider data is stale."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from screening.candidate_data_provider import (
        FakeCandidateDataProvider,
        InstrumentMetadata,
        IntradayQuote,
        ProviderSnapshot,
        VolumeHistory,
    )

    # Create fake provider with stale data
    freshness = _dt(2026, 1, 15, 10, 20)  # 10:20 AM
    provider = FakeCandidateDataProvider(
        snapshots_by_symbol={
            "ALFA": ProviderSnapshot(
                quote=IntradayQuote(
                    symbol="ALFA",
                    pct_change=3.2,
                    last=20.0,
                    cum_volume=5_000_000,
                    prior_close=19.38,
                    quote_freshness_timestamp=freshness,
                ),
                metadata=InstrumentMetadata(
                    symbol="ALFA",
                    asset_type="common_stock",
                    is_common_stock=True,
                    is_tradable=True,
                    metadata_freshness_timestamp=freshness,
                ),
                volume_history=VolumeHistory(
                    symbol="ALFA",
                    prior_same_time_cum_volumes=[2_500_000] * 7,
                    history_freshness_timestamp=freshness,
                ),
                provider_freshness_timestamp=freshness,
            )
        }
    )

    # Run job with snapshot time 10:30 AM (10 minutes stale)
    snapshot_time = _dt(2026, 1, 15, 10, 30)

    with pytest.raises(ValueError, match="stale"):
        run_candidate_pool_job(
            provider=provider,
            snapshot_time_et=snapshot_time,
            stale_after_seconds=120,  # 2 minutes max staleness
        )


def test_job_does_not_duplicate_same_snapshot_key() -> None:
    """Job is idempotent - duplicate execution does not create duplicate rows."""
    import os

    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    from screening.candidate_data_provider import (
        FakeCandidateDataProvider,
        InstrumentMetadata,
        IntradayQuote,
        ProviderSnapshot,
        VolumeHistory,
    )
    from screening.candidate_pool_repository import CandidatePoolRepository
    from sqlalchemy import text

    # Create tables
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

    # Create fake provider
    freshness = _dt(2026, 1, 15, 10, 30)
    provider = FakeCandidateDataProvider(
        snapshots_by_symbol={
            "ALFA": ProviderSnapshot(
                quote=IntradayQuote(
                    symbol="ALFA",
                    pct_change=3.2,
                    last=20.0,
                    cum_volume=5_000_000,
                    prior_close=19.38,
                    quote_freshness_timestamp=freshness,
                ),
                metadata=InstrumentMetadata(
                    symbol="ALFA",
                    asset_type="common_stock",
                    is_common_stock=True,
                    is_tradable=True,
                    metadata_freshness_timestamp=freshness,
                ),
                volume_history=VolumeHistory(
                    symbol="ALFA",
                    prior_same_time_cum_volumes=[2_500_000] * 7,
                    history_freshness_timestamp=freshness,
                ),
                provider_freshness_timestamp=freshness,
            )
        }
    )

    # Run job twice
    snapshot_time = _dt(2026, 1, 15, 10, 30)
    snapshot_key_1 = run_candidate_pool_job(
        provider=provider,
        snapshot_time_et=snapshot_time,
    )
    snapshot_key_2 = run_candidate_pool_job(
        provider=provider,
        snapshot_time_et=snapshot_time,
    )

    # Verify same snapshot key
    assert snapshot_key_1 == snapshot_key_2

    # Verify no duplicate members
    repo = CandidatePoolRepository(engine)
    members = repo.get_snapshot_members(snapshot_key_1)
    assert len(members) == 1, "Should only have one member, not duplicates"
