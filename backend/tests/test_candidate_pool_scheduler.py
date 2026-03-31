from __future__ import annotations

from datetime import datetime
import tempfile
from unittest.mock import patch
from zoneinfo import ZoneInfo


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_scheduler_enqueues_one_close_run_after_et_close(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = "job-close-run"

        job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 6))

    assert job_id == "job-close-run"
    _, kwargs = mock_enqueue.call_args
    assert kwargs["kind"] == "candidate_pool_close_run"
    assert kwargs["payload"]["trading_date_et"] == "2026-01-15"
    assert kwargs["dedupe_key"] == "candidate_pool_close_run:2026-01-15"


def test_scheduler_skips_before_close(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 15, 59))

    assert job_id is None
    mock_enqueue.assert_not_called()


def test_scheduler_skips_weekend(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 17, 16, 6))

    assert job_id is None
    mock_enqueue.assert_not_called()


def test_scheduler_skips_market_holiday(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 1, 16, 6))

    assert job_id is None
    mock_enqueue.assert_not_called()


def test_scheduler_enqueues_after_half_day_close(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = "job-half-day"
        job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 11, 27, 13, 6))

    assert job_id == "job-half-day"
    _, kwargs = mock_enqueue.call_args
    assert kwargs["payload"]["trading_date_et"] == "2026-11-27"


def test_scheduler_does_not_reenqueue_after_success_for_same_day(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.name}")
        monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
        monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

        from infra.sqlalchemy import get_engine
        from jobs import queue
        from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

        engine = get_engine(f"sqlite:///{db_file.name}")

        first_job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 6))
        assert first_job_id is not None

        queue.finish_job(engine, job_id=first_job_id, state="succeeded")

        second_job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 7))
        assert second_job_id is None


def test_scheduler_can_reenqueue_after_failed_close_run(monkeypatch):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.name}")
        monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
        monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

        from infra.sqlalchemy import get_engine
        from jobs import queue
        from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

        engine = get_engine(f"sqlite:///{db_file.name}")

        first_job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 6))
        assert first_job_id is not None

        queue.finish_job(engine, job_id=first_job_id, state="failed", error="provider timeout")

        second_job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 16, 7))
        assert second_job_id is not None


def test_scheduler_force_enqueues_before_close(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = "job-force"
        job_id = enqueue_candidate_pool_close_run(now_et=_dt(2026, 1, 15, 10, 0), force=True)

    assert job_id == "job-force"
    _, kwargs = mock_enqueue.call_args
    assert kwargs["payload"]["trading_date_et"] == "2026-01-15"


def test_scheduler_force_enqueues_for_explicit_trading_date(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_ENABLED", "true")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

    from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run

    with patch("jobs.candidate_pool_scheduler.enqueue_job") as mock_enqueue:
        mock_enqueue.return_value = "job-force-date"
        job_id = enqueue_candidate_pool_close_run(
            now_et=_dt(2026, 3, 31, 10, 0),
            force=True,
            trading_date_et=datetime(2026, 3, 30, 16, 0, tzinfo=ZoneInfo("America/New_York")).date(),
        )

    assert job_id == "job-force-date"
    _, kwargs = mock_enqueue.call_args
    assert kwargs["payload"]["trading_date_et"] == "2026-03-30"
