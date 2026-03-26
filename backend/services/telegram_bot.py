from __future__ import annotations

from typing import Any

from config import Settings, get_settings
from services.market_intel import MarketIntelService


class TelegramBotService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        market_intel_service: MarketIntelService | None = None,
    ):
        self._settings = settings or get_settings()
        self._market_intel_service = market_intel_service or MarketIntelService(
            settings=self._settings
        )

    def handle_update(self, update: dict[str, Any]) -> str | None:
        message = update.get("message")
        if not isinstance(message, dict):
            return None

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            return None

        chat = message.get("chat")
        if not isinstance(chat, dict):
            return None

        chat_type = str(chat.get("type") or "").strip().lower()
        if chat_type != "private":
            return None

        chat_id = self._chat_id(chat)
        if chat_id is None:
            return None

        command_text = text.strip()
        command, _, remainder = command_text.partition(" ")
        command_name = command.split("@", 1)[0].lower()
        args = remainder.strip()

        if command_name == "/start":
            return self._start_message(chat_id)
        if command_name == "/help":
            return self._help_message()
        if command_name == "/quote":
            return self._quote_message(args)
        if command_name == "/news":
            return self._news_message(args)
        if command_name == "/twitter":
            return self._twitter_message(args)
        if command_name == "/macro":
            return self._macro_message(args)

        return self._help_message()

    @staticmethod
    def _start_message(chat_id: int) -> str:
        return (
            "Welcome to QuantDog Telegram bot.\n"
            "Supported commands: /start, /help, /quote <symbol>, /news <symbol>, /twitter <symbol>, /macro <topic>\n"
            f"Chat ID: {chat_id}"
        )

    @staticmethod
    def _chat_id(chat: dict[str, Any]) -> int | None:
        raw_chat_id = chat.get("id")
        if not isinstance(raw_chat_id, int):
            return None
        return raw_chat_id

    @staticmethod
    def _help_message() -> str:
        return (
            "Available commands:\n"
            "/start - show welcome text and chat id\n"
            "/help - show this help\n"
            "/quote <symbol> - get a technical snapshot\n"
            "/news <symbol> - get latest news for a stock\n"
            "/twitter <symbol> - get Twitter sentiment for a stock\n"
            "/macro <topic> - get macroeconomic indicators\n"
            "Macro topics: cpi, core cpi, fed rate, dxy, yield spread, 10y yield, 2y yield, breakeven, copper gold, tips 10y"
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip()
        if normalized.startswith("$"):
            normalized = normalized[1:]
        return normalized.upper()

    def _quote_message(self, symbol: str) -> str:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            return "Usage: /quote <symbol>"

        try:
            result = self._market_intel_service.get_technical_analysis(
                normalized_symbol,
                horizon="1d",
            )
        except ValueError as exc:
            if "no bars" in str(exc).lower():
                return (
                    f"Quote lookup failed: no market data is available for {normalized_symbol}."
                )
            return f"Quote lookup failed: {exc}"

        analysis = result.get("analysis") if isinstance(result, dict) else {}
        if not isinstance(analysis, dict):
            analysis = {}

        reasons = analysis.get("reasons")
        reason_lines = []
        if isinstance(reasons, list):
            for reason in reasons[:2]:
                if isinstance(reason, str) and reason.strip():
                    reason_lines.append(reason.strip())

        latest_price = result.get("latest_price") if isinstance(result, dict) else None
        lines = [
            f"Symbol: {normalized_symbol}",
            f"Latest Price: {latest_price if latest_price is not None else 'n/a'}",
            f"Decision: {analysis.get('decision', 'HOLD')}",
            f"Confidence: {analysis.get('confidence', 0)}",
            f"Score: {analysis.get('score', 0)}",
        ]
        lines.extend(f"Reason: {reason}" for reason in reason_lines)
        return "\n".join(lines)

    def _news_message(self, symbol: str) -> str:
        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            return "Usage: /news <symbol>"

        try:
            result = self._market_intel_service.get_news_twitter_analysis(
                normalized_symbol,
                limit=20,
            )
        except Exception as exc:
            return f"News lookup failed: {exc}"

        source_status = result.get("source_status", {})
        news_provider_status = source_status.get("news_provider", "")

        if "disabled" in news_provider_status.lower() or "unavailable" in news_provider_status.lower():
            return f"News service is currently unavailable for {normalized_symbol}."

        news_count = result.get("news_count", 0)
        if news_count == 0:
            return f"No news available for {normalized_symbol}."

        news_items = result.get("news", [])
        lines = [f"News for {normalized_symbol} ({news_count} items):"]

        for item in news_items[:3]:
            headline = item.get("headline", "")
            source = item.get("source", "")
            if headline:
                lines.append(f"- {headline[:80]}{'...' if len(headline) > 80 else ''}")
                if source:
                    lines.append(f"  Source: {source}")

        return "\n".join(lines)

    def _twitter_message(self, symbol: str) -> str:
        normalized_symbol = self._normalize_symbol(symbol)
        if not normalized_symbol:
            return "Usage: /twitter <symbol>"

        try:
            result = self._market_intel_service.get_news_twitter_analysis(
                normalized_symbol,
                limit=20,
            )
        except Exception as exc:
            return f"Twitter lookup failed: {exc}"

        source_status = result.get("source_status", {})
        twitter_provider_status = source_status.get("twitter_provider", "")

        if "disabled" in twitter_provider_status.lower() or "unavailable" in twitter_provider_status.lower():
            return f"Twitter service is currently unavailable for {normalized_symbol}."

        twitter_count = result.get("twitter_count", 0)
        sentiment = result.get("sentiment", "neutral")
        sentiment_score = result.get("sentiment_score", 0)

        if twitter_count == 0:
            return f"No tweets available for {normalized_symbol}."

        twitter_items = result.get("twitter", [])
        lines = [
            f"Twitter sentiment for {normalized_symbol}: {sentiment} (score: {sentiment_score})",
            f"Found {twitter_count} tweets",
        ]

        for item in twitter_items[:2]:
            user = item.get("user", "")
            text = item.get("text", "")
            if text:
                lines.append(f"@{user}: {text[:100]}{'...' if len(text) > 100 else ''}")

        return "\n".join(lines)

    def _macro_message(self, topic: str) -> str:
        if not topic.strip():
            return (
                "Usage: /macro <topic>\n"
                "Examples: /macro cpi, /macro fed rate, /macro dxy\n"
                "Supported topics: cpi, core cpi, fed rate, dxy, yield spread, 10y yield, 2y yield, breakeven, copper gold, tips 10y"
            )

        macro_aliases = {
            "cpi": "CPI",
            "core cpi": "Core CPI",
            "fed rate": "Fed Rate",
            "dxy": "DXY",
            "yield spread": "Yield Spread",
         
            "10y yield": "10Y Yield",
            "2y yield": "2Y Yield",
            "breakeven": "Breakeven",
            "copper gold": "Copper/Gold",
            "tips 10y": "TIPS 10Y",
        }

        normalized_topic = topic.strip().lower()

        if topic.isupper() and len(topic) > 4 and " " not in topic:
            return (
                f"Topic '{topic}' is not supported.\n"
                "Supported topics: cpi, core cpi, fed rate, dxy, yield spread, 10y yield, 2y yield, breakeven, copper gold, tips 10y"
            )

        if normalized_topic not in macro_aliases:
            return (
                f"Topic '{topic}' is not supported.\n"
                "Supported topics: cpi, core cpi, fed rate, dxy, yield spread, 10y yield, 2y yield, breakeven, copper gold, tips 10y"
            )

        display_name = macro_aliases[normalized_topic]
        return (
            f"Macro indicator: {display_name}\n"
            "Note: Detailed macro analysis will be available in a future update.\n"
            "Current snapshot data can be accessed via the API directly."
        )
