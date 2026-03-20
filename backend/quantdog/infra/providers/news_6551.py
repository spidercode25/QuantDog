from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from quantdog.utils.text import to_plain_text


logger = logging.getLogger("quantdog.infra.providers.news")


class News6551Provider:
    """Fetch market news from 6551 OpenNews API."""

    def __init__(self, *, base_url: str, token: str, timeout_seconds: float = 15.0):
        self._base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._timeout_seconds = timeout_seconds

    def fetch_news(self, symbol: str, *, limit: int = 20) -> list[dict[str, Any]]:
        query_symbol = symbol.strip().upper()
        if not query_symbol:
            return []

        limit_value = max(1, min(limit, 100))
        payload = {
            "q": f"{query_symbol} OR {query_symbol} stock",
            "limit": limit_value,
            "page": 1,
        }

        request = Request(
            f"{self._base_url}/open/news_search",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            logger.warning("OpenNews request failed status=%s body=%s", exc.code, detail[:300])
            raise RuntimeError(f"OpenNews request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            logger.warning("OpenNews request failed: %s", exc)
            raise RuntimeError("OpenNews request failed: network error") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("OpenNews response is not valid JSON")
            raise RuntimeError("OpenNews request failed: invalid JSON") from exc

        data = decoded.get("data") if isinstance(decoded, dict) else None
        if not isinstance(data, list):
            return []

        return [self._normalize_item(item) for item in data if isinstance(item, dict)]

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        ai_rating_raw = item.get("aiRating")
        ai_rating: dict[str, Any] = ai_rating_raw if isinstance(ai_rating_raw, dict) else {}
        timestamp_ms = item.get("ts")
        published_at = None

        if isinstance(timestamp_ms, (int, float)):
            published_at = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc).isoformat()

        return {
            "headline": to_plain_text(item.get("text") or ""),
            "source": item.get("newsType") or item.get("engineType") or "unknown",
            "ts": item.get("ts"),
            "published_at": published_at,
            "url": item.get("link"),
            "signal": ai_rating.get("signal"),
            "score": ai_rating.get("score"),
            "raw": item,
        }
