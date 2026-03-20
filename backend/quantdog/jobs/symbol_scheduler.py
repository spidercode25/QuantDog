from __future__ import annotations

from datetime import date
from typing import Iterable

from quantdog.infra.sqlalchemy import get_engine
from quantdog.jobs.queue import enqueue_job


def enqueue_symbol_ingestion_batch(
    database_url: str,
    symbols: Iterable[str],
    *,
    start_date: date,
    end_date: date,
    adjusted: bool = True,
) -> dict[str, int]:
    """Enqueue ingest_bars jobs for a symbol batch.

    Returns counts: {requested, enqueued, deduplicated}.
    """
    engine = get_engine(database_url)
    cleaned = []
    for symbol in symbols:
        s = symbol.strip().upper()
        if s:
            cleaned.append(s)

    requested = len(cleaned)
    enqueued = 0
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    for symbol in cleaned:
        dedupe_key = f"ingest:{symbol}:1d:{start_str}:{end_str}:adjusted={adjusted}"
        job_id = enqueue_job(
            engine,
            kind="ingest_bars",
            payload={
                "symbol": symbol,
                "start_date": start_str,
                "end_date": end_str,
                "adjusted": adjusted,
            },
            dedupe_key=dedupe_key,
        )
        if job_id is not None:
            enqueued += 1

    return {
        "requested": requested,
        "enqueued": enqueued,
        "deduplicated": requested - enqueued,
    }
