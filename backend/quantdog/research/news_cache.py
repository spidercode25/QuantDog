from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from quantdog.infra.sqlalchemy import get_engine
from quantdog.utils.text import to_plain_text


def ensure_news_cache_table(database_url: str) -> None:
    engine = get_engine(database_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS news_items (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    headline TEXT NOT NULL,
                    source TEXT,
                    published_at TEXT,
                    ts BIGINT,
                    url TEXT,
                    signal TEXT,
                    score REAL,
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
        )


def _build_news_id(symbol: str, item: dict[str, Any]) -> str:
    base = "|".join(
        [
            symbol.upper(),
            str(item.get("ts") or ""),
            str(item.get("url") or ""),
            str(item.get("headline") or ""),
            str(item.get("source") or ""),
        ]
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def upsert_news_items(database_url: str, symbol: str, items: list[dict[str, Any]]) -> int:
    if not items:
        return 0

    ensure_news_cache_table(database_url)
    engine = get_engine(database_url)
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = []
    for item in items:
        rows.append(
            {
                "id": _build_news_id(symbol, item),
                "symbol": symbol.upper(),
                "headline": str(item.get("headline") or ""),
                "source": str(item.get("source") or ""),
                "published_at": item.get("published_at"),
                "ts": item.get("ts"),
                "url": item.get("url"),
                "signal": item.get("signal"),
                "score": item.get("score"),
                "raw_json": json.dumps(item.get("raw") if isinstance(item.get("raw"), dict) else {}),
                "created_at": now_iso,
            }
        )

    upsert_sql = text(
        """
        INSERT INTO news_items (id, symbol, headline, source, published_at, ts, url, signal, score, raw_json, created_at)
        VALUES (:id, :symbol, :headline, :source, :published_at, :ts, :url, :signal, :score, :raw_json, :created_at)
        ON CONFLICT(id) DO UPDATE SET
            headline = EXCLUDED.headline,
            source = EXCLUDED.source,
            published_at = EXCLUDED.published_at,
            ts = EXCLUDED.ts,
            url = EXCLUDED.url,
            signal = EXCLUDED.signal,
            score = EXCLUDED.score,
            raw_json = EXCLUDED.raw_json,
            created_at = EXCLUDED.created_at
        """
    )

    with engine.begin() as conn:
        conn.execute(upsert_sql, rows)
    return len(rows)


def fetch_recent_news(
    database_url: str,
    symbol: str,
    *,
    limit: int = 20,
    max_age_hours: int = 24,
) -> list[dict[str, Any]]:
    ensure_news_cache_table(database_url)
    engine = get_engine(database_url)
    threshold_iso = (datetime.now(timezone.utc) - timedelta(hours=max(1, max_age_hours))).isoformat()
    limit_value = max(1, min(limit, 100))

    query = text(
        """
        SELECT headline, source, published_at, ts, url, signal, score, raw_json
        FROM news_items
        WHERE symbol = :symbol
          AND created_at >= :threshold
        ORDER BY COALESCE(ts, 0) DESC, created_at DESC
        LIMIT :limit
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {
                "symbol": symbol.upper(),
                "threshold": threshold_iso,
                "limit": limit_value,
            },
        ).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        raw_obj: dict[str, Any] = {}
        if row[7]:
            try:
                parsed = json.loads(row[7])
                if isinstance(parsed, dict):
                    raw_obj = parsed
            except json.JSONDecodeError:
                raw_obj = {}

        out.append(
            {
                "headline": to_plain_text(row[0]),
                "source": row[1],
                "published_at": row[2],
                "ts": row[3],
                "url": row[4],
                "signal": row[5],
                "score": row[6],
                "raw": raw_obj,
            }
        )
    return out
