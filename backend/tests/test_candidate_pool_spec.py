from __future__ import annotations

from datetime import date, datetime, time
from importlib import import_module
from zoneinfo import ZoneInfo

import pytest


def _get_ranker():
    """
    Contract target:
    screening.candidate_pool.rank_top_gainer_candidates_at_snapshot(...)
    """
    try:
        module = import_module("screening.candidate_pool")
    except Exception as exc:  # pragma: no cover - intentional contract failure path
        pytest.fail(
            "Missing module screening.candidate_pool. "
            "Implement screening/candidate_pool.py with "
            "rank_top_gainer_candidates_at_snapshot(...). "
            f"Import error: {exc!r}"
        )

    ranker = getattr(module, "rank_top_gainer_candidates_at_snapshot", None)
    if ranker is None:
        pytest.fail(
            "Missing function screening.candidate_pool.rank_top_gainer_candidates_at_snapshot. "
            "This spec expects that callable to exist."
        )
    return ranker


@pytest.fixture
def et_tz() -> ZoneInfo:
    return ZoneInfo("America/New_York")


@pytest.fixture
def snapshot_time_et(et_tz: ZoneInfo) -> datetime:
    return datetime(2026, 1, 15, 10, 30, 0, tzinfo=et_tz)


@pytest.fixture
def gain_bounds() -> tuple[float, float]:
    return (1.0, 5.0)


@pytest.fixture
def ranking_happy_path_payload(snapshot_time_et: datetime) -> dict:
    # Core tie-break set
    intraday_rows = [
        {"symbol": "ALFA", "pct_change": 3.2, "last": 20.0, "cum_volume": 5_000_000},  # rvol 2.0, $100m
        {"symbol": "AARD", "pct_change": 4.0, "last": 30.0, "cum_volume": 3_000_000},  # rvol 2.0, $90m
        {"symbol": "BETA", "pct_change": 4.0, "last": 18.0, "cum_volume": 5_000_000},  # rvol 2.0, $90m
        {"symbol": "CHAR", "pct_change": 2.0, "last": 40.0, "cum_volume": 2_000_000},  # rvol 2.0, $80m
        # Gain filter exclusions
        {"symbol": "LOWG", "pct_change": 0.8, "last": 50.0, "cum_volume": 1_000_000},  # below 1%
        {"symbol": "HIGH", "pct_change": 5.4, "last": 50.0, "cum_volume": 1_000_000},  # above 5%
    ]

    # Fill with deterministic survivors to force truncation to 20
    for idx in range(1, 24):  # 23 additional valid names
        baseline_volume = 800_000 + (idx * 5_000)
        intraday_rows.append(
            {
                "symbol": f"S{idx:02d}",
                "pct_change": 2.0 + (idx * 0.01),
                "last": 10.0 + idx,
                "cum_volume": baseline_volume * 2,
            }
        )

    history_cum_volume_by_symbol = {
        "ALFA": [2_500_000] * 7,  # avg=2.5m -> rvol 2.0
        "AARD": [1_500_000] * 7,  # avg=1.5m -> rvol 2.0
        "BETA": [2_500_000] * 7,  # avg=2.5m -> rvol 2.0
        "CHAR": [1_000_000] * 7,  # avg=1.0m -> rvol 2.0
        "LOWG": [500_000] * 7,
        "HIGH": [500_000] * 7,
    }

    for idx in range(1, 24):
        symbol = f"S{idx:02d}"
        history_cum_volume_by_symbol[symbol] = [800_000 + (idx * 5_000)] * 7

    instrument_metadata = {
        row["symbol"]: {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True}
        for row in intraday_rows
    }

    return {
        "snapshot_time_et": snapshot_time_et,
        "provider_asof_et": snapshot_time_et,
        "intraday_rows": intraday_rows,
        "history_cum_volume_by_symbol": history_cum_volume_by_symbol,
        "instrument_metadata": instrument_metadata,
    }


def test_rank_top_gainer_candidates_at_snapshot(
    ranking_happy_path_payload: dict,
    gain_bounds: tuple[float, float],
):
    ranker = _get_ranker()

    min_gain_pct, max_gain_pct = gain_bounds
    candidates = ranker(
        snapshot_time_et=ranking_happy_path_payload["snapshot_time_et"],
        provider_asof_et=ranking_happy_path_payload["provider_asof_et"],
        intraday_rows=ranking_happy_path_payload["intraday_rows"],
        history_cum_volume_by_symbol=ranking_happy_path_payload["history_cum_volume_by_symbol"],
        instrument_metadata=ranking_happy_path_payload["instrument_metadata"],
        min_gain_pct=min_gain_pct,
        max_gain_pct=max_gain_pct,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=10_000_000,
    )

    assert isinstance(candidates, list), "Expected list of candidate dicts."
    assert len(candidates) == 20, "Candidate pool must be truncated to max 20 symbols."

    # Ranking: RVOL desc -> dollar volume desc -> percent change desc -> symbol asc
    top4 = [c["symbol"] for c in candidates[:4]]
    assert top4 == ["ALFA", "AARD", "BETA", "CHAR"], (
        "Top-4 order must follow tie-break rules "
        "(RVOL desc, dollar volume desc, pct_change desc, symbol asc)."
    )

    # Same-time RVOL contract check for ALFA: 5.0m / avg(2.5m x 7) = 2.0
    alfa = next(c for c in candidates if c["symbol"] == "ALFA")
    assert pytest.approx(alfa["rvol"], rel=1e-9) == 2.0, (
        "RVOL must equal current cumulative volume divided by 7-day average "
        "cumulative volume at the same snapshot time."
    )

    assert all(min_gain_pct <= c["pct_change"] <= max_gain_pct for c in candidates), (
        "Every returned candidate must satisfy gain filter bounds [1%, 5%]."
    )


def test_exclude_non_common_or_illiquid_names(snapshot_time_et: datetime):
    ranker = _get_ranker()

    candidates = ranker(
        snapshot_time_et=snapshot_time_et,
        provider_asof_et=snapshot_time_et,
        intraday_rows=[
            {"symbol": "LIQD", "pct_change": 2.2, "last": 50.0, "cum_volume": 1_000_000},  # $50m
            {"symbol": "ETF1", "pct_change": 2.2, "last": 50.0, "cum_volume": 1_000_000},  # non-common
            {"symbol": "PENY", "pct_change": 2.2, "last": 1.0, "cum_volume": 40_000},      # $40k illiquid
        ],
        history_cum_volume_by_symbol={
            "LIQD": [500_000] * 7,
            "ETF1": [500_000] * 7,
            "PENY": [20_000] * 7,
        },
        instrument_metadata={
            "LIQD": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
            "ETF1": {"asset_type": "etf", "is_common_stock": False, "is_tradable": True},
            "PENY": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        },
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
    assert symbols == ["LIQD"], (
        "Must exclude non-common instruments when metadata exists and "
        "exclude illiquid names below minimum dollar-volume threshold."
    )


def test_skip_snapshot_after_half_day_close(et_tz: ZoneInfo):
    ranker = _get_ranker()

    half_day_snapshot = datetime(2026, 11, 27, 14, 0, 0, tzinfo=et_tz)  # 2:00 PM ET, after early close
    candidates = ranker(
        snapshot_time_et=half_day_snapshot,
        provider_asof_et=half_day_snapshot,
        intraday_rows=[
            {"symbol": "ALFA", "pct_change": 2.5, "last": 20.0, "cum_volume": 1_000_000},
        ],
        history_cum_volume_by_symbol={"ALFA": [500_000] * 7},
        instrument_metadata={"ALFA": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True}},
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days={date(2026, 11, 27)},
        half_day_close_et=time(13, 0),
        min_dollar_volume=1_000_000,
    )

    assert candidates == [], "Snapshot after half-day close must be skipped with empty candidate pool."


def test_drop_symbol_with_less_than_7_prior_sessions(snapshot_time_et: datetime):
    ranker = _get_ranker()

    candidates = ranker(
        snapshot_time_et=snapshot_time_et,
        provider_asof_et=snapshot_time_et,
        intraday_rows=[
            {"symbol": "GOOD", "pct_change": 2.5, "last": 20.0, "cum_volume": 2_000_000},
            {"symbol": "SHORT", "pct_change": 2.5, "last": 20.0, "cum_volume": 2_000_000},
        ],
        history_cum_volume_by_symbol={
            "GOOD": [1_000_000] * 7,
            "SHORT": [1_000_000] * 6,  # insufficient history
        },
        instrument_metadata={
            "GOOD": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
            "SHORT": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        },
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
    assert symbols == ["GOOD"], "Symbols with fewer than 7 prior completed sessions must be excluded."


def test_return_empty_pool_when_no_symbol_survives(snapshot_time_et: datetime):
    ranker = _get_ranker()

    candidates = ranker(
        snapshot_time_et=snapshot_time_et,
        provider_asof_et=snapshot_time_et,
        intraday_rows=[
            {"symbol": "LOW", "pct_change": 0.4, "last": 100.0, "cum_volume": 2_000_000},  # below gain floor
            {"symbol": "HIGH", "pct_change": 6.1, "last": 100.0, "cum_volume": 2_000_000}, # above gain cap
        ],
        history_cum_volume_by_symbol={
            "LOW": [1_000_000] * 7,
            "HIGH": [1_000_000] * 7,
        },
        instrument_metadata={
            "LOW": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
            "HIGH": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True},
        },
        min_gain_pct=1.0,
        max_gain_pct=5.0,
        max_candidates=20,
        required_prior_sessions=7,
        stale_after_seconds=120,
        half_days=set(),
        half_day_close_et=time(13, 0),
        min_dollar_volume=1_000_000,
    )

    assert candidates == [], "When no symbols survive filters, function must return an empty list."


def test_reject_stale_provider_data(snapshot_time_et: datetime):
    ranker = _get_ranker()

    stale_asof = snapshot_time_et.replace(minute=20)  # 10 minutes stale vs 10:30 snapshot
    with pytest.raises(ValueError, match="stale"):
        ranker(
            snapshot_time_et=snapshot_time_et,
            provider_asof_et=stale_asof,
            intraday_rows=[
                {"symbol": "ALFA", "pct_change": 2.0, "last": 20.0, "cum_volume": 1_000_000},
            ],
            history_cum_volume_by_symbol={"ALFA": [500_000] * 7},
            instrument_metadata={"ALFA": {"asset_type": "common_stock", "is_common_stock": True, "is_tradable": True}},
            min_gain_pct=1.0,
            max_gain_pct=5.0,
            max_candidates=20,
            required_prior_sessions=7,
            stale_after_seconds=120,
            half_days=set(),
            half_day_close_et=time(13, 0),
            min_dollar_volume=1_000_000,
        )
