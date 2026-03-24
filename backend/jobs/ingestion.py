# Ingestion job handler for QuantDog

from __future__ import annotations

import logging
from typing import Any

from infra.providers import get_provider
from infra.sqlalchemy import get_engine
from config import get_settings
from sqlalchemy import text


logger = logging.getLogger("jobs.ingestion")


def handle_ingestion_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Job handler for bar ingestion.
    
    Payload should contain:
    - symbol: stock symbol
    - start_date: start date (YYYY-MM-DD)
    - end_date: end date (YYYY-MM-DD)
    - adjusted: whether to use adjusted prices
    """
    symbol = payload.get("symbol", "").upper()
    start_date = payload.get("start_date")
    end_date = payload.get("end_date")
    adjusted = payload.get("adjusted", True)
    
    if not symbol or not start_date or not end_date:
        raise ValueError("Missing required fields: symbol, start_date, end_date")
    
    logger.info("Ingesting bars for %s from %s to %s (adjusted=%s)", symbol, start_date, end_date, adjusted)
    
    # Get provider and fetch bars
    provider = get_provider()
    bars = provider.fetch_bars_1d(symbol, start_date, end_date, adjusted=adjusted)
    
    if not bars:
        logger.warning("No bars fetched for %s", symbol)
        return {"symbol": symbol, "bars_count": 0}
    
    # Upsert bars into database
    settings = get_settings()
    if settings.database_url is None:
        raise ValueError("DATABASE_URL not configured")
    
    engine = get_engine(settings.database_url)
    
    with engine.connect() as conn:
        for bar in bars:
            conn.execute(
                text("""
                    INSERT INTO bars_1d (symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source)
                    VALUES (:symbol, :bar_date, :ts_utc, :open, :high, :low, :close, :volume, :adjusted, :source)
                    ON CONFLICT (symbol, bar_date, adjusted) 
                    DO UPDATE SET 
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        source = EXCLUDED.source
                """),
                bar
            )
        conn.commit()
    
    logger.info("Ingested %d bars for %s", len(bars), symbol)
    return {"symbol": symbol, "bars_count": len(bars)}
