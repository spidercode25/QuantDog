from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from quantdog.config import Settings

from .twitter_6551 import Twitter6551Provider


class TwitterProvider(Protocol):
    def search_symbol(self, symbol: str, *, limit: int = 20) -> list[dict]:
        ...


@dataclass(frozen=True, slots=True)
class TwitterProviderResolution:
    provider: TwitterProvider | None
    reason: str


def resolve_twitter_provider(settings: Settings) -> TwitterProviderResolution:
    if not settings.twitter_enabled:
        return TwitterProviderResolution(provider=None, reason="twitter disabled by TWITTER_ENABLED=false")

    if not settings.twitter_token:
        return TwitterProviderResolution(provider=None, reason="twitter token missing")

    provider = Twitter6551Provider(
        base_url=settings.twitter_base_url,
        token=settings.twitter_token,
    )
    return TwitterProviderResolution(provider=provider, reason="twitter_6551")
