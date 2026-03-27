from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from screening.candidate_pool import rank_top_gainer_candidates_at_snapshot


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_ranked_candidates() -> None:
    """Happy path returns ranked candidates with exact ordering."""
    snapshot_time = _dt(2026, 1, 15, 10, 30)

    intraday_rows = [
        {"symbol": "ALFA", "pct_change": 3.2, "last": 20.0, "cum_volume": 5_000_000},
        {"symbol": "AARD", "pct_change": 4.0, "last": 30.0, "cum_volume": 3_000_000},
        {"symbol": "BETA", "pct_change": 4.0, "last": 18.0, "cum_volume": 5_000_000},
        {"symbol": "CHAR", "pct_change": 2.0, "last": 40.0, "cum_volume": 2_000_000},
    ]

    history_cum_volume_by_symbol = {
        "ALFA": [2_500_000] * 7,
        "AARD": [1_500_000] * 7,
        "BETA": [2_500_000] * 7,
        "CHAR": [1_000_000] * 7,
    }

    instrument_metadata = {
        "ALFA": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        "AARD": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        "BETA": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        "CHAR": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
    }

    candidates = rank_top_gainer_candidates_at_snapshot(
        snapshot_time_et=snapshot_time,
        provider_asof_et=snapshot_time,
        intraday_rows=intraday_rows,
        history_cum_volume_by_symbol=history_cum_volume_by_symbol,
        instrument_metadata=instrument_metadata,
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=10_000_000,
    )

    assert len(candidates) == 4

    # Verify ranking: RVOL desc -> dollar volume desc -> percent change desc -> symbol asc
    # ALFA: rvol=2.0, $100m, 3.2%
    # AARD: rvol=2.0, $90m, 4.0%
    # BETA: rvol=2.0, $90m, 4.0%
    # CHAR: rvol=2.0, $80m, 2.0%
    assert candidates[0]["symbol"] == "ALFA"
    assert candidates[1]["symbol"] == "AARD"
    assert candidates[2]["symbol"] == "BETA"
    assert candidates[3]["symbol"] == "CHAR"

    # Verify ALFA metrics
    alfa = candidates[0]
    assert alfa["rvol"] == 2.0
    assert alfa["pct_change"] == 3.2
    assert alfa["dollar_volume"] == 100_000_000
    assert alfa["last_price"] == 20.0
    assert alfa["rank"] == 1


def test_exclude_non_common_or_illiquid() -> None:
    """Instrument and liquidity filters exclude invalid symbols."""
    snapshot_time = _dt(2026, 1, 15, 10, 30)

    intraday_rows = [
        {"symbol": "LIQD", "pct_change": 2.2, "last": 50.0, "cum_volume": 1_000_000},
        {"symbol": "ETF1", "pct_change": 2.2, "last": 50.0, "cum_volume": 1_000_000},
        {"symbol": "PENY", "pct_change": 2.2, "last": 1.0, "cum_volume": 40_000},
    ]

    history_cum_volume_by_symbol = {
        "LIQD": [500_000] * 7,
        "ETF1": [500_000] * 7,
        "PENY": [20_000] * 7,
    }

    instrument_metadata = {
        "LIQD": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        "ETF1": {"asset_type": "etf", "is_common_stock": False, "is_tradable": True},
        "PENY": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
    }

    candidates = rank_top_gainer_candidates_at_snapshot(
        snapshot_time_et=snapshot_time,
        provider_asof_et=snapshot_time,
        intraday_rows=intraday_rows,
        history_cum_volume_by_symbol=history_cum_volume_by_symbol,
        instrument_metadata=instrument_metadata,
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=5_000_000,
    )

    symbols = [c["symbol"] for c in candidates]
    assert symbols == ["LIQD"], "Only LIQD should pass all filters"


def test_drop_zero_baseline_or_insufficient_history() -> None:
    """Symbols with insufficient history are excluded."""
    snapshot_time = _dt(2026, 1, 15, 10, 30)

    intraday_rows = [
        {"symbol": "GOOD", "pct_change": 2.5, "last": 20.0, "cum_volume": 2_000_000},
        {"symbol": "SHORT", "pct_change": 2.5, "last": 20.0, "cum_volume": 2_000_000},
    ]

    history_cum_volume_by_symbol = {
        "GOOD": [1_000_000] * 7,
        "SHORT": [1_000_000] * 6,
    }

    instrument_metadata = {
        "GOOD": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        "SHORT": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
    }

    candidates = rank_top_gainer_candidates_at_snapshot(
        snapshot_time_et=snapshot_time,
        provider_asof_et=snapshot_time,
        intraday_rows=intraday_rows,
        history_cum_volume_by_symbol=history_cum_volume_by_symbol,
        instrument_metadata=instrument_metadata,
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=1_000_000,
    )

    symbols = [c["symbol"] for c in candidates]
    assert symbols == ["GOOD"], "SHORT should be excluded due to insufficient history"


def test_truncation_to_max_candidates() -> None:
    """Results are truncated to max_candidates."""
    snapshot_time = _dt(2026, 1, 15, 10, 30)

    intraday_rows = []
    history_cum_volume_by_symbol = {}
    instrument_metadata = {}

    for idx in range(1, 25):
        symbol = f"S{idx:02d}"
        intraday_rows.append(
            {"symbol": symbol, "pct_change": 2.0, "last": 10.0 + idx, "cum_volume": 1_000_000 + (idx * 10_000)}
        )
        history_cum_volume_by_symbol[symbol] = [800_000 + (idx * 5_000)] * 7
        instrument_metadata[symbol] = {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True}

    candidates = rank_top_gainer_candidates_at_snapshot(
        snapshot_time_et=snapshot_time,
        provider_asof_et=snapshot_time,
        intraday_rows=intraday_rows,
        history_cum_volume_by_symbol=history_cum_volume_by_symbol,
        instrument_metadata=instrument_metadata,
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=1_000_000,
    )

    assert len(candidates) == 20, "Should be truncated to max_candidates"
    assert all(c["rank"] == idx + 1 for idx, c in enumerate(candidates)), "Ranks should be 1-indexed"
