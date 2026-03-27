from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IntradayQuote:
    symbol: str
    pct_change: float
    last: float
    cum_volume: int
    prior_close: float
    quote_freshness_timestamp: datetime


@dataclass(frozen=True, slots=True)
class InstrumentMetadata:
    symbol: str
    asset_type: str
    is_common_stock: bool
    is_tradable: bool
    metadata_freshness_timestamp: datetime


@dataclass(frozen=True, slots=True)
class VolumeHistory:
    symbol: str
    prior_same_time_cum_volumes: list[int]
    history_freshness_timestamp: datetime


@dataclass(frozen=True, slots=True)
class ProviderSnapshot:
    quote: IntradayQuote
    metadata: InstrumentMetadata
    volume_history: VolumeHistory
    provider_freshness_timestamp: datetime


class CandidateDataProvider(Protocol):
    def get_snapshot_data(
        self,
        *,
        snapshot_time_et: datetime,
        required_prior_sessions: int = 7,
    ) -> list[ProviderSnapshot]:
        ...


@dataclass(frozen=True, slots=True)
class FakeCandidateDataProvider:
    snapshots_by_symbol: dict[str, ProviderSnapshot]

    def get_snapshot_data(
        self,
        *,
        snapshot_time_et: datetime,
        required_prior_sessions: int = 7,
    ) -> list[ProviderSnapshot]:
        del snapshot_time_et  # deterministic fake; no runtime clock dependency
        ordered_symbols = sorted(self.snapshots_by_symbol.keys())
        snapshots = [self.snapshots_by_symbol[symbol] for symbol in ordered_symbols]

        for snapshot in snapshots:
            history_len = len(snapshot.volume_history.prior_same_time_cum_volumes)
            if history_len < required_prior_sessions:
                raise ValueError(
                    f"Symbol {snapshot.quote.symbol} requires at least "
                    f"{required_prior_sessions} completed sessions; got {history_len}."
                )

        return snapshots
