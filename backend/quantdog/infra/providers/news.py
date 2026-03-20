from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quantdog.config import Settings

from .news_6551 import News6551Provider


class NewsProvider(Protocol):
    def fetch_news(self, symbol: str, *, limit: int = 20) -> list[dict]:
        ...


@dataclass(frozen=True, slots=True)
class NewsProviderResolution:
    provider: NewsProvider | None
    reason: str


def resolve_news_provider(settings: Settings) -> NewsProviderResolution:
    if not settings.news_enabled:
        return NewsProviderResolution(provider=None, reason="news disabled by NEWS_ENABLED=false")

    if not settings.opennews_token:
        return NewsProviderResolution(provider=None, reason="news token missing, using empty news context")

    provider = News6551Provider(
        base_url=settings.opennews_base_url,
        token=settings.opennews_token,
    )
    return NewsProviderResolution(provider=provider, reason="opennews_6551")
