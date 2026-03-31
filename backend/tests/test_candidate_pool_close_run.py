from __future__ import annotations

from datetime import time
from unittest.mock import patch


def test_close_run_handler_builds_snapshot_time_and_calls_job(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

    from jobs.candidate_pool_close_run import handle_candidate_pool_close_run

    with patch("jobs.candidate_pool_close_run.LongbridgeCandidateDataProvider") as mock_provider_class, patch(
        "jobs.candidate_pool_close_run.run_candidate_pool_job"
    ) as mock_run_job:
        mock_run_job.return_value = "2026-01-15_16:05:00"

        result = handle_candidate_pool_close_run({"trading_date_et": "2026-01-15"})

    assert result["snapshot_key"] == "2026-01-15_16:05:00"
    _, kwargs = mock_run_job.call_args
    assert kwargs["snapshot_time_et"].strftime("%Y-%m-%d %H:%M") == "2026-01-15 16:05"
    assert kwargs["provider"] is mock_provider_class.return_value
    assert kwargs["half_day_close_et"] == time(13, 0)


def test_runner_registers_close_run_handler():
    from jobs.runner import JOB_HANDLERS

    assert "candidate_pool_close_run" in JOB_HANDLERS


def test_close_run_handler_uses_half_day_snapshot_time(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("CANDIDATE_POOL_CLOSE_TIME_ET", "16:05")

    from jobs.candidate_pool_close_run import handle_candidate_pool_close_run

    with patch("jobs.candidate_pool_close_run.LongbridgeCandidateDataProvider") as mock_provider_class, patch(
        "jobs.candidate_pool_close_run.run_candidate_pool_job"
    ) as mock_run_job:
        mock_run_job.return_value = "2026-11-27_13:05:00"

        result = handle_candidate_pool_close_run({"trading_date_et": "2026-11-27"})

    assert result["snapshot_key"] == "2026-11-27_13:05:00"
    _, kwargs = mock_run_job.call_args
    assert kwargs["snapshot_time_et"].strftime("%Y-%m-%d %H:%M") == "2026-11-27 13:05"
    assert kwargs["half_days"] == {kwargs["snapshot_time_et"].date()}
