from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from quantdog.utils.text import to_plain_text


logger = logging.getLogger("quantdog.infra.providers.twitter")


class Twitter6551Provider:
    """Fetch Twitter/X posts from 6551 Twitter endpoints."""

    def __init__(self, *, base_url: str, token: str, timeout_seconds: float = 15.0):
        self._base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._timeout_seconds = timeout_seconds

    def search_symbol(self, symbol: str, *, limit: int = 20) -> list[dict[str, Any]]:
        query_symbol = symbol.strip().upper()
        if not query_symbol:
            return []

        payload = {
            "keywords": f"{query_symbol} OR {query_symbol} stock",
            "product": "Latest",
            "maxResults": max(1, min(limit, 100)),
            "excludeReplies": True,
            "excludeRetweets": True,
        }

        request = Request(
            f"{self._base_url}/open/twitter_search",
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
            logger.warning("Twitter request failed status=%s body=%s", exc.code, detail[:300])
            raise RuntimeError(f"Twitter request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            logger.warning("Twitter request failed: %s", exc)
            raise RuntimeError("Twitter request failed: network error") from exc

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Twitter request failed: invalid JSON") from exc

        data = decoded.get("data") if isinstance(decoded, dict) else None
        if not isinstance(data, list):
            return []

        return [self._normalize_item(item) for item in data if isinstance(item, dict)]

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        tweet_id = item.get("id")
        user = item.get("userScreenName")
        text = to_plain_text(item.get("text") or "")
        return {
            "id": tweet_id,
            "user": user,
            "text": text,
            "created_at": item.get("createdAt"),
            "likes": item.get("favoriteCount"),
            "retweets": item.get("retweetCount"),
            "replies": item.get("replyCount"),
            "view_count": item.get("viewCount"),
            "url": f"https://x.com/{user}/status/{tweet_id}" if user and tweet_id else None,
            "raw": item,
        }
