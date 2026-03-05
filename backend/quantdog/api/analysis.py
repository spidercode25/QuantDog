# Fast Analysis API endpoints

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.analysis.indicators import calculate_indicators
from quantdog.config import get_settings
from quantdog.infra.sqlalchemy import get_engine
from sqlalchemy import text


analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/v1")


def generate_baseline_analysis(symbol: str, indicators: dict) -> dict:
    """Generate a deterministic baseline analysis based on technical indicators.
    
    This is a rule-based analysis that doesn't require any external AI calls.
    It uses SMA, RSI, and price momentum to generate a BUY/SELL/HOLD signal.
    """
    # Extract indicator values
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
            "reason": "Insufficient data for analysis"
        }
    
    # Score based on multiple factors (each contributes -1 to +1)
    score = 0.0
    reasons = []
    
    # Trend analysis (SMA-based)
    if sma20 and sma50:
        if sma20 > sma50:
            score += 0.5
            reasons.append("Short-term trend is bullish (SMA20 > SMA50)")
        elif sma20 < sma50:
            score -= 0.5
            reasons.append("Short-term trend is bearish (SMA20 < SMA50)")
    
    # Price position relative to SMA
    if sma20:
        if close > sma20 * 1.05:
            score += 0.3
            reasons.append("Price is above SMA20 (upside momentum)")
        elif close < sma20 * 0.95:
            score -= 0.3
            reasons.append("Price is below SMA20 (downside momentum)")
    
    # RSI analysis
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
    
    # MACD analysis
    if macd and macd_histogram:
        if macd > 0 and macd_histogram > 0:
            score += 0.3
            reasons.append("MACD shows bullish momentum")
        elif macd < 0 and macd_histogram < 0:
            score -= 0.3
            reasons.append("MACD shows bearish momentum")
    
    # Support/Resistance analysis
    if recent_high and recent_low:
        range_pct = (recent_high - recent_low) / recent_low * 100 if recent_low > 0 else 0
        position_in_range = (close - recent_low) / (recent_high - recent_low) if recent_high > recent_low else 0.5
        
        if position_in_range > 0.8:
            score -= 0.2
            reasons.append("Price near resistance level")
        elif position_in_range < 0.2:
            score += 0.2
            reasons.append("Price near support level")
    
    # Determine decision based on score
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
            "recent_low": recent_low
        }
    }


@analysis_bp.post("/analysis/fast")
def post_fast_analysis():
    """Perform fast analysis on a symbol.
    
    Request body:
    - symbol: stock symbol (required)
    - horizon: analysis horizon - "1d", "1w", "1m" (optional, default: "1d")
    
    Always returns a baseline rule-based analysis.
    If ENABLE_AI_ANALYSIS=true, attempts AI enhancement.
    """
    data = request.get_json()
    if not data:
        return error("Invalid request", error_type="invalid_request", detail="Request body must be JSON")
    
    symbol = data.get("symbol", "").strip().upper()
    if not symbol:
        return error("Symbol is required", error_type="missing_field", detail="symbol field is required")
    
    horizon = data.get("horizon", "1d").strip()
    if horizon not in {"1d", "1w", "1m"}:
        return error("Invalid horizon", error_type="invalid_field", detail="horizon must be one of: 1d, 1w, 1m")
    
    settings = get_settings()
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    
    engine = get_engine(settings.database_url)
    
    # Determine date range based on horizon
    # We'll fetch last 100 bars for indicator calculation
    with engine.connect() as conn:
        query = """
            SELECT symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source
            FROM bars_1d
            WHERE symbol = :symbol AND adjusted = true
            ORDER BY bar_date DESC
            LIMIT 100
        """
        
        result = conn.execute(text(query), {"symbol": symbol})
        rows = result.fetchall()
    
    if not rows:
        return error(
            "No bars found",
            error_type="not_found",
            detail=f"No bars found for {symbol}. Ingest data first."
        )
    
    # Convert to dict format (reverse to get chronological order)
    bars = [
        {
            "symbol": row[0],
            "bar_date": str(row[1]),
            "ts_utc": row[2],
            "open": float(row[3]),
            "high": float(row[4]),
            "low": float(row[5]),
            "close": float(row[6]),
            "volume": row[7],
            "adjusted": row[8],
            "source": row[9]
        }
        for row in reversed(rows)
    ]
    
    # Calculate indicators
    indicators = calculate_indicators(bars)
    
    # Generate baseline analysis (always available)
    baseline = generate_baseline_analysis(symbol, indicators)
    
    # Prepare response
    response = {
        "symbol": symbol,
        "horizon": horizon,
        "analysis": baseline,
        "ai_enabled": settings.enable_ai_analysis,
        "ai_error": None,
        "baseline_used": True
    }
    
    # If AI is enabled, this is where we would call an LLM
    # For now, we just return the baseline with a note
    if settings.enable_ai_analysis:
        # In a full implementation, we would call the LLM here
        # For now, mark that we're using baseline only
        response["ai_error"] = "AI analysis not implemented in MVP"
        response["baseline_used"] = True
    
    return success(response)
