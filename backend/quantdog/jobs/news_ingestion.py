from __future__ import annotations

import logging
from typing import Any

from quantdog.config import get_settings
from quantdog.infra.providers.news import resolve_news_provider
from quantdog.research.news_cache import upsert_news_items


logger = logging.getLogger("quantdog.jobs.news_ingestion")


def handle_news_ingestion_job(payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(payload.get("symbol") or "").strip().upper()
    limit = int(payload.get("limit") or 20)

    if not symbol:
        raise ValueError("Missing required field: symbol")

    settings = get_settings()
    if not settings.database_url:
        raise ValueError("DATABASE_URL not configured")

    resolution = resolve_news_provider(settings)
    provider = resolution.provider
    if provider is None:
        return {
            "symbol": symbol,
            "fetched": 0,
            "cached": 0,
            "status": "skipped",
            "reason": resolution.reason,
        }

    news_items = provider.fetch_news(symbol, limit=limit)
    cached_count = upsert_news_items(settings.database_url, symbol, news_items)

    logger.info("News ingested for %s: fetched=%d cached=%d", symbol, len(news_items), cached_count)
    return {
        "symbol": symbol,
        "fetched": len(news_items),
        "cached": cached_count,
        "status": "ok",
        "provider": resolution.reason,
    }
