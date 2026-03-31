from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from screening.longbridge_candidate_provider import (
    LongbridgeCandidateDataProvider,
    _validate_and_build_freshness_timestamp,
)


def _dt(year: int, month: int, day: int, hour: int = 16, minute: int = 5) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_provider_uses_snapshot_date_and_excludes_latest_bar_from_history() -> None:
    bars = [
        {"close": 10.0, "volume": 100, "bar_date": "2026-01-01"},
        {"close": 11.0, "volume": 110, "bar_date": "2026-01-02"},
        {"close": 12.0, "volume": 120, "bar_date": "2026-01-05"},
        {"close": 13.0, "volume": 130, "bar_date": "2026-01-06"},
        {"close": 14.0, "volume": 140, "bar_date": "2026-01-07"},
        {"close": 15.0, "volume": 150, "bar_date": "2026-01-08"},
        {"close": 16.0, "volume": 160, "bar_date": "2026-01-09"},
        {"close": 17.0, "volume": 170, "bar_date": "2026-01-12"},
    ]

    with patch("screening.longbridge_candidate_provider.LongbridgeProvider") as mock_provider_class:
        mock_provider = mock_provider_class.return_value
        mock_provider.fetch_bars_1d.return_value = bars

        provider = LongbridgeCandidateDataProvider()
        with patch(
            "screening.longbridge_candidate_provider._validate_and_build_freshness_timestamp",
            return_value=_dt(2026, 1, 12),
        ):
            snapshots = provider.get_snapshot_data(
                snapshot_time_et=_dt(2026, 1, 12),
                required_prior_sessions=7,
            )

    assert snapshots, "Expected at least one snapshot"
    first = snapshots[0]
    assert first.quote.last == 17.0
    assert first.quote.prior_close == 16.0
    assert first.quote.cum_volume == 170
    assert first.volume_history.prior_same_time_cum_volumes == [100, 110, 120, 130, 140, 150, 160]

    first_call = mock_provider.fetch_bars_1d.call_args_list[0]
    assert first_call.kwargs["end_date"] == "2026-01-12"


def test_provider_skips_symbols_without_prior_seven_completed_sessions() -> None:
    with patch("screening.longbridge_candidate_provider.LongbridgeProvider") as mock_provider_class:
        mock_provider = mock_provider_class.return_value
        mock_provider.fetch_bars_1d.return_value = [
            {"close": 10.0, "volume": 100, "bar_date": "2026-01-09"},
            {"close": 11.0, "volume": 110, "bar_date": "2026-01-12"},
            {"close": 12.0, "volume": 120, "bar_date": "2026-01-13"},
            {"close": 13.0, "volume": 130, "bar_date": "2026-01-14"},
            {"close": 14.0, "volume": 140, "bar_date": "2026-01-15"},
            {"close": 15.0, "volume": 150, "bar_date": "2026-01-16"},
            {"close": 16.0, "volume": 160, "bar_date": "2026-01-20"},
        ]

        provider = LongbridgeCandidateDataProvider()
        with patch("screening.longbridge_candidate_provider._V1_CANDIDATE_UNIVERSE", ["AAPL"]):
            try:
                provider.get_snapshot_data(
                    snapshot_time_et=_dt(2026, 1, 20),
                    required_prior_sessions=7,
                )
            except ValueError as exc:
                assert "insufficient completed sessions" in str(exc)
            else:
                raise AssertionError("Expected provider coverage failure for insufficient history")


def test_provider_rejects_latest_bar_date_mismatch() -> None:
    bars = [
        {"close": 10.0, "volume": 100, "bar_date": "2026-01-01"},
        {"close": 11.0, "volume": 110, "bar_date": "2026-01-02"},
        {"close": 12.0, "volume": 120, "bar_date": "2026-01-05"},
        {"close": 13.0, "volume": 130, "bar_date": "2026-01-06"},
        {"close": 14.0, "volume": 140, "bar_date": "2026-01-07"},
        {"close": 15.0, "volume": 150, "bar_date": "2026-01-08"},
        {"close": 16.0, "volume": 160, "bar_date": "2026-01-09"},
        {"close": 17.0, "volume": 170, "bar_date": "2026-01-10"},
    ]

    with patch("screening.longbridge_candidate_provider.LongbridgeProvider") as mock_provider_class:
        mock_provider = mock_provider_class.return_value
        mock_provider.fetch_bars_1d.return_value = bars

        provider = LongbridgeCandidateDataProvider()
        with patch("screening.longbridge_candidate_provider._V1_CANDIDATE_UNIVERSE", ["AAPL"]):
            try:
                provider.get_snapshot_data(
                    snapshot_time_et=_dt(2026, 1, 12),
                    required_prior_sessions=7,
                )
            except ValueError as exc:
                assert "does not match trading date" in str(exc)
            else:
                raise AssertionError("Expected provider coverage failure for mismatched bar date")


def test_provider_raises_when_symbol_fetch_fails() -> None:
    with patch("screening.longbridge_candidate_provider.LongbridgeProvider") as mock_provider_class:
        mock_provider = mock_provider_class.return_value
        mock_provider.fetch_bars_1d.side_effect = RuntimeError("timeout")

        provider = LongbridgeCandidateDataProvider()
        with patch("screening.longbridge_candidate_provider._V1_CANDIDATE_UNIVERSE", ["AAPL"]):
            try:
                provider.get_snapshot_data(
                    snapshot_time_et=_dt(2026, 1, 12),
                    required_prior_sessions=7,
                )
            except ValueError as exc:
                assert "timeout" in str(exc)
            else:
                raise AssertionError("Expected provider coverage failure for fetch errors")


def test_freshness_timestamp_rejects_mismatched_fetch_date() -> None:
    try:
        _validate_and_build_freshness_timestamp(
            fetch_time_et=_dt(2026, 1, 12, 15, 59),
            snapshot_time_et=_dt(2026, 1, 12),
            latest_bar_date=_dt(2026, 1, 12).date(),
        )
    except ValueError as exc:
        assert "earlier than snapshot time" in str(exc)
    else:
        raise AssertionError("Expected provider freshness validation to fail")


def test_freshness_timestamp_allows_historical_rerun_after_close() -> None:
    freshness = _validate_and_build_freshness_timestamp(
        fetch_time_et=_dt(2026, 1, 13, 9, 30),
        snapshot_time_et=_dt(2026, 1, 12),
        latest_bar_date=_dt(2026, 1, 12).date(),
    )

    assert freshness == _dt(2026, 1, 12)
