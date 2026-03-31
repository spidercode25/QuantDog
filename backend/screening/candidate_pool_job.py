from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING

from zoneinfo import ZoneInfo

from config import get_settings
from screening.candidate_pool_close_message import build_candidate_pool_close_message

if TYPE_CHECKING:
    from screening.candidate_data_provider import CandidateDataProvider
    from sqlalchemy.engine import Engine


def run_candidate_pool_job(
    *,
    provider: CandidateDataProvider,
    snapshot_time_et: datetime,
    min_gain_pct: float = 1.0,
    max_gain_pct: float = 5.0,
    max_candidates: int = 20,
    required_prior_sessions: int = 7,
    stale_after_seconds: int = 120,
    half_days: set[date] | None = None,
    half_day_close_et: time | None = None,
    min_dollar_volume: float = 10_000_000,
    min_rvol: float = 2.0,
    require_common_stock: bool = True,
    require_tradable: bool = True,
    engine: Engine | None = None,
) -> str:
    """Run the candidate pool job for a given snapshot time.

    Args:
        provider: Data provider for intraday quotes and history
        snapshot_time_et: Target snapshot time in ET
        min_gain_pct: Minimum gain percentage
        max_gain_pct: Maximum gain percentage
        max_candidates: Maximum number of candidates to return
        required_prior_sessions: Minimum prior trading sessions required
        stale_after_seconds: Maximum age of provider data in seconds
        half_days: Set of dates that are half-days
        half_day_close_et: Early close time on half-days
        min_dollar_volume: Minimum dollar volume threshold
        min_rvol: Minimum RVOL threshold (default: 2.0 for 2x average volume)
        engine: Optional SQLAlchemy engine for testing

    Returns:
        Snapshot key for the created snapshot

    Raises:
        ValueError: If provider data is stale or other validation fails
    """
    from screening.candidate_pool import rank_top_gainer_candidates_at_snapshot
    from screening.candidate_pool_repository import CandidatePoolRepository, CandidateMember

    # Set defaults
    half_days = half_days or set()
    half_day_close_et = half_day_close_et or time(13, 0)

    # Get provider data
    snapshots = provider.get_snapshot_data(
        snapshot_time_et=snapshot_time_et,
        required_prior_sessions=required_prior_sessions,
    )
    if not snapshots:
        raise ValueError("Provider returned no snapshots for candidate pool close run")

    # Convert provider snapshots to screening service format
    intraday_rows = []
    history_cum_volume_by_symbol = {}
    instrument_metadata = {}

    for snapshot in snapshots:
        symbol = snapshot.quote.symbol
        intraday_rows.append(
            {
                "symbol": symbol,
                "pct_change": snapshot.quote.pct_change,
                "last": snapshot.quote.last,
                "cum_volume": snapshot.quote.cum_volume,
            }
        )
        history_cum_volume_by_symbol[symbol] = snapshot.volume_history.prior_same_time_cum_volumes
        instrument_metadata[symbol] = {
            "asset_type": snapshot.metadata.asset_type,
            "is_common_stock": snapshot.metadata.is_common_stock,
            "is_tradable": snapshot.metadata.is_tradable,
        }

    # Run screening
    candidates = rank_top_gainer_candidates_at_snapshot(
        snapshot_time_et=snapshot_time_et,
        provider_asof_et=snapshots[0].provider_freshness_timestamp if snapshots else snapshot_time_et,
        intraday_rows=intraday_rows,
        history_cum_volume_by_symbol=history_cum_volume_by_symbol,
        instrument_metadata=instrument_metadata,
        min_gain_pct=min_gain_pct,
        max_gain_pct=max_gain_pct,
        max_candidates=max_candidates,
        required_prior_sessions=required_prior_sessions,
        stale_after_seconds=stale_after_seconds,
        half_days=half_days,
        half_day_close_et=half_day_close_et,
        min_dollar_volume=min_dollar_volume,
        min_rvol=min_rvol,
        require_common_stock=require_common_stock,
        require_tradable=require_tradable,
    )

    from jobs.queue import has_job_with_dedupe_key

    # Create snapshot key
    snapshot_key = snapshot_time_et.strftime("%Y-%m-%d_%H:%M:%S")
    repo = CandidatePoolRepository(engine=engine)
    trading_date_et = snapshot_time_et.astimezone(ZoneInfo("America/New_York")).date()
    telegram_dedupe_key = f"candidate-pool-close:{trading_date_et.isoformat()}"
    should_enqueue_notification = not has_job_with_dedupe_key(
        repo._engine,
        dedupe_key=telegram_dedupe_key,
        states=("queued", "running", "succeeded"),
    )

    # Convert candidates to repository format
    members = [
        CandidateMember(
            snapshot_key=snapshot_key,
            symbol=c["symbol"],
            rank=c["rank"],
            rvol=c["rvol"],
            pct_change=c["pct_change"],
            dollar_volume=c["dollar_volume"],
            last_price=c["last_price"],
            inclusion_reason="passed_all_filters",
            exclusion_reason=None,
            created_at=datetime.now(UTC),
        )
        for c in candidates
    ]

    # Persist snapshot
    repo.upsert_snapshot(
        snapshot_key=snapshot_key,
        snapshot_time_et=snapshot_time_et,
        provider_asof_et=snapshots[0].provider_freshness_timestamp if snapshots else snapshot_time_et,
        members=members,
    )

    settings = get_settings()
    if should_enqueue_notification and settings.telegram_group_id is not None:
        from jobs import queue

        message_text = build_candidate_pool_close_message(
            trading_date_et=trading_date_et,
            snapshot_time_et=snapshot_time_et,
            candidates=candidates,
        )
        queue.enqueue_job(
            repo._engine,
            kind="telegram_send_message",
            payload={
                "chat_id": settings.telegram_group_id,
                "text": message_text,
            },
            dedupe_key=telegram_dedupe_key,
        )

    return snapshot_key


def is_market_open(
    *,
    snapshot_time_et: datetime,
    half_days: set[date] | None = None,
    half_day_close_et: time | None = None,
) -> bool:
    """Check if the market is open at the given snapshot time.

    Args:
        snapshot_time_et: Target snapshot time in ET
        half_days: Set of dates that are half-days
        half_day_close_et: Early close time on half-days

    Returns:
        True if market is open, False otherwise
    """
    # Check if it's a weekend
    if snapshot_time_et.weekday() >= 5:  # Saturday or Sunday
        return False

    # Check if it's a half-day and after close
    half_days = half_days or set()
    half_day_close_et = half_day_close_et or time(13, 0)

    if snapshot_time_et.date() in half_days:
        return snapshot_time_et.time() < half_day_close_et

    # Regular session: 9:30 AM - 4:00 PM ET
    market_open = time(9, 30)
    market_close = time(16, 0)

    return market_open <= snapshot_time_et.time() < market_close
