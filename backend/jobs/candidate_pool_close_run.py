from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from config import get_settings
from jobs.candidate_pool_scheduler import is_us_market_half_day
from screening.candidate_pool_job import run_candidate_pool_job
from screening.longbridge_candidate_provider import LongbridgeCandidateDataProvider


def handle_candidate_pool_close_run(job_payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()

    trading_date_et = _parse_trading_date(job_payload.get("trading_date_et"))
    half_days = {trading_date_et} if is_us_market_half_day(trading_date_et) else set()
    snapshot_time_et = datetime.combine(
        trading_date_et,
        time(13, 5) if trading_date_et in half_days else settings.candidate_pool_close_time_et,
        tzinfo=ZoneInfo("America/New_York"),
    )

    provider = LongbridgeCandidateDataProvider()
    try:
        snapshot_key = run_candidate_pool_job(
            provider=provider,
            snapshot_time_et=snapshot_time_et,
            min_gain_pct=settings.candidate_pool_min_gain_pct,
            max_gain_pct=settings.candidate_pool_max_gain_pct,
            max_candidates=settings.candidate_pool_max_candidates,
            required_prior_sessions=7,
            stale_after_seconds=settings.candidate_pool_stale_after_seconds,
            half_days=half_days,
            half_day_close_et=time(13, 0),
            min_dollar_volume=settings.candidate_pool_min_dollar_volume,
            min_rvol=settings.candidate_pool_min_rvol,
            require_common_stock=settings.candidate_pool_require_common_stock,
            require_tradable=settings.candidate_pool_require_tradable,
        )
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()

    return {
        "status": "completed",
        "trading_date_et": trading_date_et.isoformat(),
        "snapshot_key": snapshot_key,
    }


def _parse_trading_date(raw_value: object) -> date:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise ValueError("trading_date_et is required")
    return date.fromisoformat(raw_value.strip())
