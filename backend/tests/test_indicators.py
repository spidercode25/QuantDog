# Indicator calculation tests for QuantDog

from __future__ import annotations

import pytest

from quantdog.analysis.indicators import (
    calculate_indicators,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)


def test_calculate_sma_insufficient_data():
    """Test SMA returns None when prices list is shorter than period."""
    prices = [100.0, 101.0, 102.0]
    result = calculate_sma(prices, period=5)
    assert result is None


def test_calculate_sma_valid_calculation():
    """Test SMA calculates correctly for valid input."""
    prices = [100.0, 102.0, 104.0, 106.0, 108.0]
    result = calculate_sma(prices, period=5)
    expected = sum(prices) / 5  # 520 / 5 = 104.0
    assert result == expected


def test_calculate_sma_uses_last_n_prices():
    """Test SMA uses only the last 'period' prices."""
    prices = [90.0, 95.0, 100.0, 102.0, 104.0, 106.0, 108.0]
    result = calculate_sma(prices, period=5)
    expected = sum([100.0, 102.0, 104.0, 106.0, 108.0]) / 5  # 520 / 5 = 104.0
    assert result == expected


def test_calculate_rsi_insufficient_data():
    """Test RSI returns None when prices list is shorter than period + 1."""
    prices = [100.0] * 14  # 14 prices, need 15 for period=14
    result = calculate_rsi(prices, period=14)
    assert result is None


def test_calculate_rsi_all_gains():
    """Test RSI returns 100 when all changes are gains (avg_loss = 0)."""
    prices = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]  # All gains
    result = calculate_rsi(prices, period=5)
    assert result == 100.0


def test_calculate_rsi_normal_calculation():
    """Test RSI calculates correctly with mixed gains and losses."""
    # Create prices with both gains and losses
    prices = [100.0, 102.0, 101.0, 103.0, 102.0, 104.0]
    result = calculate_rsi(prices, period=5)
    assert result is not None
    assert 0 <= result <= 100


def test_calculate_macd_insufficient_data():
    """Test MACD returns None dict when prices list is shorter than slow period."""
    prices = [100.0] * 25  # 25 prices, need 26 for slow=26
    result = calculate_macd(prices, fast=12, slow=26, signal=9)
    assert result == {"macd": None, "signal": None, "histogram": None}


def test_calculate_macd_simplified_signal():
    """Test MACD uses simplified signal line (signal = macd_line)."""
    # Create enough prices for MACD calculation
    prices = [100.0 + i * 0.5 for i in range(50)]
    result = calculate_macd(prices)
    assert result["macd"] is not None
    assert result["signal"] is not None
    assert result["histogram"] is not None
    # Current implementation: signal equals macd_line, histogram is 0
    assert result["signal"] == result["macd"]
    assert result["histogram"] == 0.0


def test_calculate_indicators_empty_bars():
    """Test calculate_indicators returns empty dict for empty bars."""
    result = calculate_indicators([])
    assert result == {}


def test_calculate_indicators_chronological_sorting():
    """Test calculate_indicators sorts bars chronologically."""
    bars = [
        {"bar_date": "2024-01-05", "close": 105.0},
        {"bar_date": "2024-01-01", "close": 100.0},
        {"bar_date": "2024-01-03", "close": 103.0},
    ]
    result = calculate_indicators(bars)
    # Should calculate based on sorted order: 100, 103, 105
    assert result["last_close"] == 105.0


def test_calculate_indicators_returns_expected_keys():
    """Test calculate_indicators returns all expected indicator keys."""
    # Create enough bars for all indicators
    bars = [
        {"bar_date": f"2024-01-{i:02d}", "close": 100.0 + i * 0.5}
        for i in range(1, 60)
    ]
    result = calculate_indicators(bars)

    expected_keys = {
        "sma20",
        "sma50",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "recent_high",
        "recent_low",
        "last_close",
    }
    assert set(result.keys()) == expected_keys


def test_calculate_indicators_recent_high_low():
    """Test recent_high and recent_low are calculated from last 20 closes."""
    # Create 30 bars with known values
    bars = [
        {"bar_date": f"2024-01-{i:02d}", "close": float(100 + i)}
        for i in range(1, 31)
    ]
    result = calculate_indicators(bars)

    # Last 20 closes are 111-130, so recent_high=130, recent_low=111
    assert result["recent_high"] == 130.0
    assert result["recent_low"] == 111.0


def test_calculate_indicators_insufficient_history():
    """Test indicators are None when insufficient history."""
    bars = [
        {"bar_date": "2024-01-01", "close": 100.0},
        {"bar_date": "2024-01-02", "close": 101.0},
    ]
    result = calculate_indicators(bars)

    # SMA20 and SMA50 should be None (need 20 and 50 bars)
    assert result["sma20"] is None
    assert result["sma50"] is None
    # RSI should be None (need 15 bars for period=14)
    assert result["rsi14"] is None
    # MACD should be None (need 26 bars)
    assert result["macd"] is None
    assert result["macd_signal"] is None
    assert result["macd_histogram"] is None
    # But recent_high/low should still work (uses all available bars)
    assert result["recent_high"] == 101.0
    assert result["recent_low"] == 100.0


def test_calculate_indicators_filters_invalid_bars():
    """Test calculate_indicators filters out bars without close price."""
    bars = [
        {"bar_date": "2024-01-01", "close": 100.0},
        {"bar_date": "2024-01-02", "invalid": "no close"},  # Should be filtered
        {"bar_date": "2024-01-03", "close": 102.0},
    ]
    result = calculate_indicators(bars)
    # Should only use bars with close prices
    assert result["last_close"] == 102.0
