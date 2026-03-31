from __future__ import annotations

import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

from jobs import queue


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_worker_processes_close_run_and_persists_snapshot(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
        database_url = f"sqlite:///{db_file.name}"
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
        monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
        monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
        monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
        monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")

        from infra.sqlalchemy import get_engine
        from jobs.runner import run_once
        from screening.candidate_data_provider import (
            FakeCandidateDataProvider,
            InstrumentMetadata,
            IntradayQuote,
            ProviderSnapshot,
            VolumeHistory,
        )
        from screening.candidate_pool_repository import CandidatePoolRepository
        from sqlalchemy import text

        engine = get_engine(database_url)
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

        freshness = _dt(2026, 1, 15, 16, 5)
        fake_provider = FakeCandidateDataProvider(
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

        job_id = queue.enqueue_job(
            engine,
            kind="candidate_pool_close_run",
            payload={"trading_date_et": "2026-01-15"},
            dedupe_key="candidate_pool_close_run:2026-01-15",
        )
        assert job_id is not None

        from unittest.mock import patch

        with patch("jobs.candidate_pool_close_run.LongbridgeCandidateDataProvider", return_value=fake_provider):
            processed = run_once("test-worker", engine)

        assert processed is True

        repo = CandidatePoolRepository(engine)
        snapshot = repo.get_latest_snapshot()
        assert snapshot is not None
        assert snapshot.snapshot_key == "2026-01-15_16:05:00"
        members = repo.get_snapshot_members(snapshot.snapshot_key)
        assert [member.symbol for member in members] == ["ALFA"]

        with engine.connect() as conn:
            close_run_state = conn.execute(
                text("SELECT state FROM jobs WHERE id = :job_id"),
                {"job_id": job_id},
            ).scalar_one()
            telegram_jobs = conn.execute(
                text("SELECT kind, state, dedupe_key FROM jobs WHERE kind = 'telegram_send_message'"),
            ).fetchall()

        assert close_run_state == "succeeded"
        assert len(telegram_jobs) == 1
        assert telegram_jobs[0][2] == "candidate-pool-close:2026-01-15"


def test_failed_close_run_can_be_reenqueued_same_day(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
        database_url = f"sqlite:///{db_file.name}"
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
        monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")
        monkeypatch.setenv("TELEGRAM_ENABLED", "true")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")
        monkeypatch.setenv("TELEGRAM_GROUP_ID", "-1001234567890")
        monkeypatch.setenv("LONGBRIDGE_APP_KEY", "key")
        monkeypatch.setenv("LONGBRIDGE_APP_SECRET", "secret")
        monkeypatch.setenv("LONGBRIDGE_ACCESS_TOKEN", "token")

        from infra.sqlalchemy import get_engine
        from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run
        from jobs.runner import run_once
        from sqlalchemy import text

        engine = get_engine(database_url)
        first_job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 6))
        assert first_job_id is not None

        class FailingProvider:
            def get_snapshot_data(self, **_kwargs):
                raise ValueError("provider unavailable")

            def close(self):
                return None

        from unittest.mock import patch

        with patch("jobs.candidate_pool_close_run.LongbridgeCandidateDataProvider", return_value=FailingProvider()):
            processed = run_once("test-worker", engine)

        assert processed is True

        with engine.connect() as conn:
            first_state = conn.execute(
                text("SELECT state FROM jobs WHERE id = :job_id"),
                {"job_id": first_job_id},
            ).scalar_one()

        assert first_state == "failed"

        second_job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 7))
        assert second_job_id is not None
