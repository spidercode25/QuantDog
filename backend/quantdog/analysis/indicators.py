# Technical indicators for QuantDog

from __future__ import annotations

from typing import Any


def calculate_sma(prices: list[float], period: int) -> float | None:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    """Calculate Relative Strength Index."""
    if len(prices) < period + 1:
        return None
    
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return None
    
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, float | None]:
    """Calculate MACD (Moving Average Convergence Divergence).
    
    Returns dict with 'macd', 'signal', and 'histogram' keys.
    """
    if len(prices) < slow:
        return {"macd": None, "signal": None, "histogram": None}
    
    # Calculate EMAs
    def ema(data: list[float], period: int) -> float | None:
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema_val = sum(data[:period]) / period
        for price in data[period:]:
            ema_val = (price - ema_val) * multiplier + ema_val
        return ema_val
    
    fast_ema = ema(prices, fast)
    slow_ema = ema(prices, slow)
    
    if fast_ema is None or slow_ema is None:
        return {"macd": None, "signal": None, "histogram": None}
    
    macd_line = fast_ema - slow_ema
    
    # For signal line, we need MACD values over time - simplified here
    signal_line = macd_line  # Placeholder - full implementation would track MACD over time
    histogram = macd_line - signal_line if signal_line else None
    
    return {
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram
    }


def calculate_indicators(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate technical indicators from bars.
    
    Args:
        bars: List of bar dicts with 'close' key
        
    Returns:
        Dict with indicator values
    """
    if not bars:
        return {}
    
    # Get closing prices (most recent last)
    closes = [bar["close"] for bar in reversed(bars)]
    
    # Calculate indicators
    sma20 = calculate_sma(closes, 20) if len(closes) >= 20 else None
    sma50 = calculate_sma(closes, 50) if len(closes) >= 50 else None
    
    rsi14 = calculate_rsi(closes, 14)
    
    macd = calculate_macd(closes)
    
    # Support/Resistance (recent high/low)
    recent_high = max(closes[-20:]) if len(closes) >= 20 else max(closes)
    recent_low = min(closes[-20:]) if len(closes) >= 20 else min(closes)
    
    return {
        "sma20": sma20,
        "sma50": sma50,
        "rsi14": rsi14,
        "macd": macd.get("macd"),
        "macd_signal": macd.get("signal"),
        "macd_histogram": macd.get("histogram"),
        "recent_high": recent_high,
        "recent_low": recent_low,
        "last_close": closes[-1] if closes else None
    }
