from __future__ import annotations


def generate_baseline_analysis(symbol: str, indicators: dict) -> dict:
    """Generate a deterministic baseline analysis based on technical indicators."""
    close = indicators.get("last_close")
    sma20 = indicators.get("sma20")
    sma50 = indicators.get("sma50")
    rsi14 = indicators.get("rsi14")
    macd = indicators.get("macd")
    macd_histogram = indicators.get("macd_histogram")
    recent_high = indicators.get("recent_high")
    recent_low = indicators.get("recent_low")

    if close is None:
        return {
            "symbol": symbol,
            "decision": "HOLD",
            "confidence": 0,
            "reason": "Insufficient data for analysis",
        }

    score = 0.0
    reasons = []

    if sma20 and sma50:
        if sma20 > sma50:
            score += 0.5
            reasons.append("Short-term trend is bullish (SMA20 > SMA50)")
        elif sma20 < sma50:
            score -= 0.5
            reasons.append("Short-term trend is bearish (SMA20 < SMA50)")

    if sma20:
        if close > sma20 * 1.05:
            score += 0.3
            reasons.append("Price is above SMA20 (upside momentum)")
        elif close < sma20 * 0.95:
            score -= 0.3
            reasons.append("Price is below SMA20 (downside momentum)")

    if rsi14:
        if rsi14 > 70:
            score -= 0.4
            reasons.append(f"RSI is overbought ({rsi14:.1f})")
        elif rsi14 < 30:
            score += 0.4
            reasons.append(f"RSI is oversold ({rsi14:.1f})")
        elif rsi14 > 50:
            score += 0.2
            reasons.append(f"RSI indicates bullish momentum ({rsi14:.1f})")
        elif rsi14 < 50:
            score -= 0.2
            reasons.append(f"RSI indicates bearish momentum ({rsi14:.1f})")

    if macd and macd_histogram:
        if macd > 0 and macd_histogram > 0:
            score += 0.3
            reasons.append("MACD shows bullish momentum")
        elif macd < 0 and macd_histogram < 0:
            score -= 0.3
            reasons.append("MACD shows bearish momentum")

    if recent_high and recent_low:
        position_in_range = (close - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0.5
        if position_in_range > 0.8:
            score -= 0.2
            reasons.append("Price near resistance level")
        elif position_in_range < 0.2:
            score += 0.2
            reasons.append("Price near support level")

    if score >= 0.5:
        decision = "BUY"
        confidence = min(int((score / 2.0) * 100), 95)
    elif score <= -0.5:
        decision = "SELL"
        confidence = min(int((abs(score) / 2.0) * 100), 95)
    else:
        decision = "HOLD"
        confidence = max(0, 50 - int(abs(score) * 25))

    return {
        "symbol": symbol,
        "decision": decision,
        "confidence": confidence,
        "score": round(score, 2),
        "reasons": reasons if reasons else ["No strong signals detected"],
        "indicators_snapshot": {
            "close": close,
            "sma20": sma20,
            "sma50": sma50,
            "rsi14": rsi14,
            "macd": macd,
            "macd_histogram": macd_histogram,
            "recent_high": recent_high,
            "recent_low": recent_low,
        },
    }
