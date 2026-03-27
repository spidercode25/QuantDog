from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from screening.candidate_data_provider import (
    FakeCandidateDataProvider,
    InstrumentMetadata,
    IntradayQuote,
    ProviderSnapshot,
    VolumeHistory,
)


def _dt(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo("America/New_York"))


def test_provider_contract_returns_required_fields() -> None:
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

    snapshots = provider.get_snapshot_data(snapshot_time_et=freshness, required_prior_sessions=7)
    assert len(snapshots) == 1

    item = snapshots[0]
    assert item.quote.symbol == "ALFA"
    assert item.quote.pct_change == 3.2
    assert item.quote.last == 20.0
    assert item.quote.cum_volume == 5_000_000
    assert item.quote.prior_close == 19.38

    assert item.metadata.asset_type == "common_stock"
    assert item.metadata.is_common_stock is True
    assert item.metadata.is_tradable is True

    assert item.volume_history.prior_same_time_cum_volumes == [2_500_000] * 7


def test_provider_contract_requires_seven_completed_sessions() -> None:
    freshness = _dt(2026, 1, 15, 10, 30)
    provider = FakeCandidateDataProvider(
        snapshots_by_symbol={
            "SHORT": ProviderSnapshot(
                quote=IntradayQuote(
                    symbol="SHORT",
                    pct_change=2.1,
                    last=12.0,
                    cum_volume=1_100_000,
                    prior_close=11.75,
                    quote_freshness_timestamp=freshness,
                ),
                metadata=InstrumentMetadata(
                    symbol="SHORT",
                    asset_type="common_stock",
                    is_common_stock=True,
                    is_tradable=True,
                    metadata_freshness_timestamp=freshness,
                ),
                volume_history=VolumeHistory(
                    symbol="SHORT",
                    prior_same_time_cum_volumes=[600_000] * 6,
                    history_freshness_timestamp=freshness,
                ),
                provider_freshness_timestamp=freshness,
            )
        }
    )

    with pytest.raises(ValueError, match="requires at least 7 completed sessions"):
        provider.get_snapshot_data(snapshot_time_et=freshness, required_prior_sessions=7)


def test_provider_contract_exposes_freshness_metadata() -> None:
    freshness = _dt(2026, 1, 15, 10, 30)
    provider = FakeCandidateDataProvider(
        snapshots_by_symbol={
            "BETA": ProviderSnapshot(
                quote=IntradayQuote(
                    symbol="BETA",
                    pct_change=4.0,
                    last=18.0,
                    cum_volume=5_000_000,
                    prior_close=17.31,
                    quote_freshness_timestamp=freshness,
                ),
                metadata=InstrumentMetadata(
                    symbol="BETA",
                    asset_type="common_stock",
                    is_common_stock=True,
                    is_tradable=True,
                    metadata_freshness_timestamp=freshness,
                ),
                volume_history=VolumeHistory(
                    symbol="BETA",
                    prior_same_time_cum_volumes=[2_500_000] * 7,
                    history_freshness_timestamp=freshness,
                ),
                provider_freshness_timestamp=freshness,
            )
        }
    )

    snapshots = provider.get_snapshot_data(snapshot_time_et=freshness)
    item = snapshots[0]

    assert isinstance(item.quote.quote_freshness_timestamp, datetime)
    assert isinstance(item.metadata.metadata_freshness_timestamp, datetime)
    assert isinstance(item.volume_history.history_freshness_timestamp, datetime)
    assert isinstance(item.provider_freshness_timestamp, datetime)
