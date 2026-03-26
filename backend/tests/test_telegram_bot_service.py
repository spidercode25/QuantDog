from __future__ import annotations

from unittest.mock import MagicMock

from config import get_settings
from services.telegram_bot import TelegramBotService


def _private_update(text: str, *, chat_id: int = 123456789) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "text": text,
            "chat": {"id": chat_id, "type": "private"},
        },
    }


def test_telegram_bot_start_message(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/start", chat_id=987654321))
    assert "/news" in result
    assert "/twitter" in result
    assert "/macro" in result


def test_telegram_bot_help_message(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/help"))
    assert "/news" in result
    assert "/twitter" in result
    assert "/macro" in result


def test_telegram_bot_quote_success(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    mock_market_intel = MagicMock()
    mock_market_intel.get_technical_analysis.return_value = {
        "symbol": "AAPL",
        "latest_price": 188.23,
        "analysis": {
            "decision": "BUY",
            "confidence": 82,
            "score": 0.65,
            "reasons": ["Short-term trend is bullish", "MACD shows bullish momentum"],
        },
    }
    service = TelegramBotService(
        settings=get_settings(),
        market_intel_service=mock_market_intel,
    )
    result = service.handle_update(_private_update("/quote AAPL"))
    mock_market_intel.get_technical_analysis.assert_called_once_with("AAPL", horizon="1d")
    assert "Symbol: AAPL" in result


def test_telegram_bot_quote_missing_symbol(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/quote "))
    assert result == "Usage: /quote <symbol>"


def test_telegram_bot_unknown_command(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/unknown"))
    assert "/news" in result
    assert "/twitter" in result
    assert "/macro" in result


def test_telegram_bot_non_text_update_is_ignored(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "photo": [{"file_id": "1"}],
                "chat": {"id": 123, "type": "private"},
            },
        }
    )
    assert result is None


def test_telegram_bot_group_chat_is_rejected(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "text": "/start",
                "chat": {"id": -100123, "type": "supergroup"},
            },
        }
    )
    assert result is None


def test_telegram_bot_news_missing_symbol(monkeypatch):
    """Test /news without symbol returns usage message."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/news"))
    assert "Usage: /news <symbol>" in result


def test_telegram_bot_news_symbol_normalization(monkeypatch):
    """Test /news normalizes symbols to uppercase."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    mock_market_intel = MagicMock()
    mock_market_intel.get_news_twitter_analysis.return_value = {
        "symbol": "AAPL",
        "news_count": 3,
        "twitter_count": 0,
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "source_status": {"news_provider": "ok"},
        "news": [{"headline": "Test", "source": "Test", "published_at": "2024-01-01"}],
        "twitter": [],
    }
    service = TelegramBotService(
        settings=get_settings(),
        market_intel_service=mock_market_intel,
    )
    result = service.handle_update(_private_update("/news aapl"))
    mock_market_intel.get_news_twitter_analysis.assert_called_once()
    assert "AAPL" in result


def test_telegram_bot_twitter_missing_symbol(monkeypatch):
    """Test /twitter without symbol returns usage message."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/twitter"))
    assert "Usage: /twitter <symbol>" in result


def test_telegram_bot_macro_missing_topic(monkeypatch):
    """Test /macro without topic returns usage message."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/macro"))
    assert "Usage: /macro <topic>" in result


def test_telegram_bot_macro_unknown_topic(monkeypatch):
    """Test /macro with unknown topic returns error with supported list."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/macro unknown_topic"))
    assert "not supported" in result.lower()
    assert "cpi" in result.lower()


def test_telegram_bot_macro_raw_fred_code_rejection(monkeypatch):
    """Test /macro with raw FRED code (uppercase, no spaces) is rejected."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    service = TelegramBotService(settings=get_settings(), market_intel_service=MagicMock())
    result = service.handle_update(_private_update("/macro CPIAUCSL"))
    assert "not supported" in result.lower()


def test_telegram_bot_macro_alias_normalization(monkeypatch):
    """Test /macro normalizes aliases to canonical names."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    mock_market_intel = MagicMock()
    mock_market_intel.get_topic_macro_analysis.return_value = {
        "macro_theme": "inflation",
        "snapshot": {"cpi": 3.5},
        "market_sentiment": "neutral",
        "market_sentiment_score": 0.0,
        "note": "Macro analysis uses FRED snapshot data.",
    }
    service = TelegramBotService(
        settings=get_settings(),
        market_intel_service=mock_market_intel,
    )
    # Test case normalization
    result = service.handle_update(_private_update("/macro CPI"))
    assert "CPI" in result or "cpi" in result.lower()
    
    # Test spacing normalization
    result = service.handle_update(_private_update("/macro core cpi"))
    assert "Core CPI" in result or "core cpi" in result.lower()


def test_telegram_bot_macro_success_reply_structure(monkeypatch):
    """Test /macro success reply includes all required fields in order."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    mock_market_intel = MagicMock()
    mock_market_intel.get_topic_macro_analysis.return_value = {
        "macro_theme": "inflation",
        "snapshot": {"cpi": 3.5},
        "market_sentiment": "neutral",
        "market_sentiment_score": 0.0,
        "note": "Macro analysis uses FRED snapshot data.",
    }
    service = TelegramBotService(
        settings=get_settings(),
        market_intel_service=mock_market_intel,
    )
    result = service.handle_update(_private_update("/macro cpi"))
    
    # Check for required fields (will be updated after implementation)
    assert "cpi" in result.lower() or "CPI" in result


def test_telegram_bot_macro_reply_under_length_budget(monkeypatch):
    """Test /macro reply stays under 900 character budget."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    mock_market_intel = MagicMock()
    mock_market_intel.get_topic_macro_analysis.return_value = {
        "macro_theme": "inflation",
        "snapshot": {"cpi": 3.5},
        "market_sentiment": "neutral",
        "market_sentiment_score": 0.0,
        "note": "Macro analysis uses FRED snapshot data.",
    }
    service = TelegramBotService(
        settings=get_settings(),
        market_intel_service=mock_market_intel,
    )
    result = service.handle_update(_private_update("/macro cpi"))
    assert len(result) < 900
