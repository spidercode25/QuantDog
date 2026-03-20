from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from quantdog.infra.sqlalchemy import get_engine
from quantdog.jobs.queue import enqueue_job


def build_dedupe_window(
    phase: str,
    *,
    now_utc: datetime | None = None,
    intraday_interval_minutes: int = 15,
) -> str:
    """Build deterministic dedupe window token by scheduler phase.

    - premarket/postmarket: one token per UTC day
    - intraday: one token per interval bucket
    """
    ts = now_utc or datetime.now(timezone.utc)
    normalized_phase = phase.strip().lower()

    if normalized_phase in {"premarket", "postmarket"}:
        return f"{ts.strftime('%Y%m%d')}:{normalized_phase}"

    interval = max(1, intraday_interval_minutes)
    bucket_minute = (ts.minute // interval) * interval
    bucket = ts.replace(minute=bucket_minute, second=0, microsecond=0)
    return f"{bucket.strftime('%Y%m%d%H%M')}:intraday"


def enqueue_news_ingestion_batch(
    database_url: str,
    symbols: Iterable[str],
    *,
    limit: int = 20,
    dedupe_window: str | None = None,
) -> dict[str, int]:
    """Enqueue news ingestion jobs for a batch of symbols.

    Returns counts: {requested, enqueued, deduplicated}.
    """
    engine = get_engine(database_url)
    cleaned = []
    for symbol in symbols:
        s = symbol.strip().upper()
        if s:
            cleaned.append(s)

    if dedupe_window is None:
        dedupe_window = build_dedupe_window("intraday")

    limit_value = max(1, min(limit, 100))

    requested = len(cleaned)
    enqueued = 0

    for symbol in cleaned:
        dedupe_key = f"ingest_news:{symbol}:limit={limit_value}:window={dedupe_window}"
        job_id = enqueue_job(
            engine,
            kind="ingest_news",
            payload={"symbol": symbol, "limit": limit_value},
            dedupe_key=dedupe_key,
        )
        if job_id is not None:
            enqueued += 1

    return {
        "requested": requested,
        "enqueued": enqueued,
        "deduplicated": requested - enqueued,
    }
