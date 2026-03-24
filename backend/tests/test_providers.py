# Provider tests for QuantDog

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_symbol_normalize_with_suffix():
    """Test symbol normalization keeps existing market suffix."""
    from infra.providers.market import LongbridgeProvider

    # Already has market suffix - return as-is
    assert LongbridgeProvider._normalize_symbol("AAPL.US") == "AAPL.US"
    assert LongbridgeProvider._normalize_symbol("700.HK") == "700.HK"
    assert LongbridgeProvider._normalize_symbol("000001.SZ") == "000001.SZ"


def test_symbol_normalize_without_suffix():
    """Test symbol normalization adds .US suffix for plain symbols."""
    from infra.providers.market import LongbridgeProvider

    # No market suffix - add .US by default
    assert LongbridgeProvider._normalize_symbol("AAPL") == "AAPL.US"
    assert LongbridgeProvider._normalize_symbol("MSFT") == "MSFT.US"
    assert LongbridgeProvider._normalize_symbol("TSLA") == "TSLA.US"


def test_symbol_normalize_case_insensitive():
    """Test symbol normalization is case-insensitive."""
    from infra.providers.market import LongbridgeProvider

    # Should uppercase and normalize
    assert LongbridgeProvider._normalize_symbol("aapl") == "AAPL.US"
    assert LongbridgeProvider._normalize_symbol("MsFt") == "MSFT.US"


def test_symbol_normalize_trims_whitespace():
    """Test symbol normalization removes whitespace."""
    from infra.providers.market import LongbridgeProvider

    assert LongbridgeProvider._normalize_symbol(" AAPL.US ") == "AAPL.US"
    assert LongbridgeProvider._normalize_symbol("  MSFT  ") == "MSFT.US"


def test_parse_date_valid_format():
    """Test date parsing for valid YYYY-MM-DD format."""
    from infra.providers.market import LongbridgeProvider

    result = LongbridgeProvider._parse_date("2024-01-15")
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15


def test_parse_date_invalid_format():
    """Test date parsing raises ValueError for invalid format."""
    from infra.providers.market import LongbridgeProvider

    with pytest.raises(ValueError):
        LongbridgeProvider._parse_date("01/15/2024")  # Wrong format


def test_parse_date_missing_parts():
    """Test date parsing raises ValueError for incomplete date."""
    from infra.providers.market import LongbridgeProvider

    with pytest.raises(ValueError):
        LongbridgeProvider._parse_date("2024-01")  # Missing day


def test_provider_initialization_graceful_degradation():
    """Test provider initialization handles various credential states gracefully."""
    from infra.providers.market import LongbridgeProvider

    provider = LongbridgeProvider()

    # Longbridge package is now installed, so ctx should be either:
    # - None if credentials are invalid/missing
    # - A QuoteContext object if credentials are valid
    # _AdjustType should similarly be either None or a valid enum

    # The test verifies that the provider can be created without crashing
    # even if credentials are not properly configured
    assert provider is not None


def test_fetch_bars_returns_empty_without_context():
    """Test fetch_bars returns empty list when context is not initialized."""
    from infra.providers.market import LongbridgeProvider

    provider = LongbridgeProvider()
    provider.ctx = None  # Simulate failed initialization

    result = provider.fetch_bars_1d("AAPL", "2024-01-01", "2024-01-31")
    assert result == []


def test_get_provider_returns_longbridge_provider():
    """Test get_provider() returns LongbridgeProvider instance."""
    from infra.providers import get_provider, MarketDataProvider
    from infra.providers.market import LongbridgeProvider

    provider = get_provider()
    assert isinstance(provider, MarketDataProvider)
    # Note: This will be LongbridgeProvider if credentials are set, or a provider with ctx=None otherwise
    assert isinstance(provider, LongbridgeProvider)


def test_bar_output_format():
    """Test that provider returns bars in expected format."""
    from infra.providers.market import LongbridgeProvider
    from unittest.mock import MagicMock

    # Mock the Longbridge response
    mock_candle = MagicMock()
    mock_candle.timestamp = 1704067200000  # 2024-01-01 00:00:00 UTC in ms
    mock_candle.open = 100.0
    mock_candle.high = 105.0
    mock_candle.low = 99.0
    mock_candle.close = 104.0
    mock_candle.volume = 1000000

    mock_response = MagicMock()
    mock_response.candlesticks = [mock_candle]

    # Create provider with mocked context
    provider = LongbridgeProvider()
    mock_ctx = MagicMock()
    mock_ctx.history_candlesticks_by_date = MagicMock(return_value=mock_response)
    provider.ctx = mock_ctx
    # Mock AdjustType enum
    mock_adjust_type = MagicMock()
    mock_adjust_type.ForwardAdjust = 1
    mock_adjust_type.NoAdjust = 0
    provider._AdjustType = mock_adjust_type

    # Fetch bars
    result = provider.fetch_bars_1d("AAPL", "2024-01-01", "2024-01-01")

    assert len(result) == 1
    bar = result[0]

    # Check expected keys
    expected_keys = {
        "symbol",
        "bar_date",
        "ts_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjusted",
        "source",
    }
    assert set(bar.keys()) == expected_keys

    # Check values
    assert bar["symbol"] == "AAPL"
    assert bar["bar_date"] == "2024-01-01"
    assert bar["source"] == "longbridge"
    assert bar["close"] == 104.0
    assert bar["volume"] == 1000000

    # Verify that Longbridge context was called with proper symbol format
    mock_ctx.history_candlesticks_by_date.assert_called_once()
    call_args = mock_ctx.history_candlesticks_by_date.call_args
    assert call_args.kwargs["symbol"] == "AAPL.US"  # Should add .US suffix


def test_bar_format_matches_yfinance_provider():
    """Test that LongbridgeProvider produces the same bar structure as YFinanceProvider did."""
    from infra.providers.market import LongbridgeProvider
    from unittest.mock import MagicMock

    # Mock the Longbridge response
    mock_candle = MagicMock()
    mock_candle.timestamp = 1704067200000
    mock_candle.open = 100.0
    mock_candle.high = 105.0
    mock_candle.low = 99.0
    mock_candle.close = 104.0
    mock_candle.volume = 1000000

    mock_response = MagicMock()
    mock_response.candlesticks = [mock_candle]

    provider = LongbridgeProvider()
    mock_ctx = MagicMock()
    mock_ctx.history_candlesticks_by_date = MagicMock(return_value=mock_response)
    provider.ctx = mock_ctx
    # Mock AdjustType enum
    mock_adjust_type = MagicMock()
    mock_adjust_type.ForwardAdjust = 1
    mock_adjust_type.NoAdjust = 0
    provider._AdjustType = mock_adjust_type

    result = provider.fetch_bars_1d("AAPL", "2024-01-01", "2024-01-01")
    bar = result[0]

    # These keys must match the YFinanceProvider output format
    # for compatibility with indicator calculation pipeline
    assert "symbol" in bar
    assert "bar_date" in bar
    assert "open" in bar
    assert "high" in bar
    assert "low" in bar
    assert "close" in bar
    assert "volume" in bar
    assert "adjusted" in bar
    assert "source" in bar
