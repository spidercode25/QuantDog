from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class Candidate:
    symbol: str
    rvol: float
    pct_change: float
    dollar_volume: float
    last_price: float
    rank: int


def rank_top_gainer_candidates_at_snapshot(
    *,
    snapshot_time_et: datetime,
    provider_asof_et: datetime,
    intraday_rows: list[dict],
    history_cum_volume_by_symbol: Mapping[str, list[int]],
    instrument_metadata: Mapping[str, dict],
    min_gain_pct: float,
    max_gain_pct: float,
    max_candidates: int,
    required_prior_sessions: int,
    stale_after_seconds: int,
    half_days: set,
    half_day_close_et: time,
    min_dollar_volume: float,
    min_rvol: float = 2.0,
    require_common_stock: bool = True,
    require_tradable: bool = True,
) -> list[dict]:
    """Rank top gainer candidates at a fixed intraday snapshot.

    Args:
        snapshot_time_et: The target snapshot time in ET
        provider_asof_et: When the provider data was generated
        intraday_rows: List of intraday quote data
        history_cum_volume_by_symbol: Prior 7-day same-time cumulative volumes per symbol
        instrument_metadata: Instrument type and tradability metadata
        min_gain_pct: Minimum gain percentage (e.g., 1.0 for 1%)
        max_gain_pct: Maximum gain percentage (e.g., 5.0 for 5%)
        max_candidates: Maximum number of candidates to return
        required_prior_sessions: Minimum number of prior trading sessions required
        stale_after_seconds: Maximum age of provider data in seconds
        half_days: Set of dates that are half-days
        half_day_close_et: Early close time on half-days
        min_dollar_volume: Minimum dollar volume threshold
        min_rvol: Minimum RVOL threshold (default: 2.0 for 2x average volume)

    Returns:
        List of candidate dicts with symbol, rvol, pct_change, dollar_volume, last_price, rank

    Raises:
        ValueError: If provider data is stale
    """
    # Check for stale data
    staleness_seconds = (snapshot_time_et - provider_asof_et).total_seconds()
    if staleness_seconds > stale_after_seconds:
        raise ValueError(f"Provider data is stale: {staleness_seconds:.0f}s old, max {stale_after_seconds}s")

    # Check for half-day skip
    snapshot_date = snapshot_time_et.date()
    if snapshot_date in half_days and snapshot_time_et.time() >= half_day_close_et:
        return []

    # Build symbol lookup from intraday rows
    intraday_by_symbol = {row["symbol"]: row for row in intraday_rows}

    candidates = []
    for symbol, history_volumes in history_cum_volume_by_symbol.items():
        # Check required prior sessions
        if len(history_volumes) < required_prior_sessions:
            continue

        # Get intraday data
        intraday = intraday_by_symbol.get(symbol)
        if intraday is None:
            continue

        # Apply gain filter
        pct_change = intraday["pct_change"]
        if not (min_gain_pct <= pct_change <= max_gain_pct):
            continue

        # Get instrument metadata
        metadata = instrument_metadata.get(symbol, {})
        is_common_stock = metadata.get("is_common_stock", True)
        is_tradable = metadata.get("is_tradable", True)

        # Apply instrument exclusion
        if require_common_stock and not is_common_stock:
            continue
        if require_tradable and not is_tradable:
            continue

        # Calculate RVOL
        current_volume = intraday["cum_volume"]
        avg_prior_volume = sum(history_volumes) / len(history_volumes)
        rvol = current_volume / avg_prior_volume if avg_prior_volume > 0 else 0.0

        # Apply RVOL filter (must exceed 2x average volume)
        if rvol < min_rvol:
            continue

        # Calculate dollar volume
        last_price = intraday["last"]
        dollar_volume = current_volume * last_price

        # Apply liquidity guard
        if dollar_volume < min_dollar_volume:
            continue

        candidates.append(
            {
                "symbol": symbol,
                "rvol": rvol,
                "pct_change": pct_change,
                "dollar_volume": dollar_volume,
                "last_price": last_price,
            }
        )

    # Sort by ranking criteria: RVOL desc -> dollar volume desc -> percent change desc -> symbol asc
    candidates.sort(
        key=lambda c: (
            -c["rvol"],
            -c["dollar_volume"],
            -c["pct_change"],
            c["symbol"],
        )
    )

    # Truncate to max_candidates and add rank
    ranked_candidates = []
    for idx, candidate in enumerate(candidates[:max_candidates]):
        ranked_candidates.append({**candidate, "rank": idx + 1})

    return ranked_candidates
