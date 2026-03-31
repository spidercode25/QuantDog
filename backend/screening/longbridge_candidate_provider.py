from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from infra.providers.market import LongbridgeProvider

from screening.candidate_data_provider import (
    CandidateDataProvider,
    IntradayQuote,
    InstrumentMetadata,
    ProviderSnapshot,
    VolumeHistory,
)

logger = logging.getLogger(__name__)

_V1_CANDIDATE_UNIVERSE = [
    "AAPL",
    "NVDA",
    "MSFT",
    "GOOGL",
    "TSLA",
    "AMZN",
    "META",
    "LLY",
    "AVGO",
    "JPM",
    "V",
    "XOM",
    "MA",
    "PG",
    "COST",
    "HD",
    "MRK",
    "ABBV",
    "CVX",
]


class LongbridgeCandidateDataProvider(CandidateDataProvider):
    """Longbridge implementation of CandidateDataProvider using existing LongbridgeProvider."""

    def __init__(self) -> None:
        """Initialize Longbridge provider."""
        self._provider = LongbridgeProvider()

    def get_snapshot_data(
        self,
        *,
        snapshot_time_et: datetime,
        required_prior_sessions: int = 7,
    ) -> list[ProviderSnapshot]:
        """Get snapshot data from Longbridge.

        Args:
            snapshot_time_et: Target snapshot time in ET
            required_prior_sessions: Minimum prior trading sessions required

        Returns:
            List of provider snapshots
        """
        snapshots = []
        failures: list[str] = []
        snapshot_time_et = snapshot_time_et.astimezone(ZoneInfo("America/New_York"))
        fetch_time_et = datetime.now(tz=ZoneInfo("America/New_York"))

        # Calculate date range for historical data
        end_date = snapshot_time_et.date()
        start_date = end_date - timedelta(days=30)  # Get more days to ensure we have 7 trading days

        for symbol in _V1_CANDIDATE_UNIVERSE:
            try:
                # Get historical bars for the last 30 days
                bars = self._provider.fetch_bars_1d(
                    symbol=symbol,
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    adjusted=False,
                )

                if not bars or len(bars) < required_prior_sessions + 1:
                    failures.append(
                        f"{symbol}: insufficient completed sessions ({len(bars)} < {required_prior_sessions + 1})"
                    )
                    continue

                # Get the latest bar for current price
                latest_bar = bars[-1]
                latest_bar_date = _coerce_bar_date(latest_bar["bar_date"])
                if latest_bar_date != end_date:
                    failures.append(
                        f"{symbol}: latest bar date {latest_bar_date.isoformat()} does not match trading date {end_date.isoformat()}"
                    )
                    continue

                freshness = _validate_and_build_freshness_timestamp(
                    fetch_time_et=fetch_time_et,
                    snapshot_time_et=snapshot_time_et,
                    latest_bar_date=latest_bar_date,
                )
                last_price = latest_bar["close"]

                # Get prior close (second to last bar)
                prior_close = bars[-2]["close"] if len(bars) >= 2 else last_price

                # Calculate percent change
                pct_change = ((last_price - prior_close) / prior_close) * 100 if prior_close > 0 else 0.0

                # Get volume from latest bar
                cum_volume = latest_bar["volume"]

                # Extract the prior completed daily bars for RVOL calculation.
                prior_volumes = [bar["volume"] for bar in bars[-(required_prior_sessions + 1):-1]]

                # Create intraday quote
                intraday_quote = IntradayQuote(
                    symbol=symbol,
                    pct_change=round(pct_change, 2),
                    last=last_price,
                    cum_volume=cum_volume,
                    prior_close=prior_close,
                    quote_freshness_timestamp=freshness,
                )

                # Create metadata
                metadata = InstrumentMetadata(
                    symbol=symbol,
                    asset_type="common_stock",
                    is_common_stock=True,
                    is_tradable=True,
                    metadata_freshness_timestamp=freshness,
                )

                # Create volume history
                volume_history = VolumeHistory(
                    symbol=symbol,
                    prior_same_time_cum_volumes=prior_volumes,
                    history_freshness_timestamp=freshness,
                )

                # Create provider snapshot
                snapshot = ProviderSnapshot(
                    quote=intraday_quote,
                    metadata=metadata,
                    volume_history=volume_history,
                    provider_freshness_timestamp=freshness,
                )

                snapshots.append(snapshot)

            except Exception as e:
                failures.append(f"{symbol}: {e}")

        if failures:
            raise ValueError("Longbridge candidate provider coverage failed: " + "; ".join(failures))

        logger.info(f"Retrieved {len(snapshots)} snapshots from Longbridge")
        return snapshots

    def close(self) -> None:
        """Close the Longbridge connection."""
        # LongbridgeProvider doesn't have an explicit close method
        pass


def _coerce_bar_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        return date.fromisoformat(raw_value)
    raise ValueError(f"Unsupported bar_date value: {raw_value!r}")


def _validate_and_build_freshness_timestamp(
    *,
    fetch_time_et: datetime,
    snapshot_time_et: datetime,
    latest_bar_date: date,
) -> datetime:
    trading_date_et = snapshot_time_et.date()
    if latest_bar_date != trading_date_et:
        raise ValueError(
            f"latest bar date {latest_bar_date.isoformat()} does not match trading date {trading_date_et.isoformat()}"
        )
    if fetch_time_et < snapshot_time_et:
        raise ValueError(
            f"provider fetch time {fetch_time_et.isoformat()} is earlier than snapshot time {snapshot_time_et.isoformat()}"
        )
    return snapshot_time_et
