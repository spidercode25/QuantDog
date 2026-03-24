# Baseline analysis tests for QuantDog

from __future__ import annotations

from analysis.baseline import generate_baseline_analysis


def test_baseline_insufficient_data():
    """Test baseline returns HOLD with zero confidence when close is None."""
    indicators = {"last_close": None}
    result = generate_baseline_analysis("AAPL", indicators)

    assert result["symbol"] == "AAPL"
    assert result["decision"] == "HOLD"
    assert result["confidence"] == 0
    assert "Insufficient data" in result["reason"]


def test_baseline_buy_scenario():
    """Test BUY decision when score >= 0.5.

    Conditions for BUY:
    - sma20 > sma50: +0.5
    - close > sma20 * 1.05: +0.3
    - rsi14 < 30: +0.4
    Total score: +1.2 -> BUY
    """
    indicators = {
        "last_close": 110.0,
        "sma20": 100.0,
        "sma50": 95.0,  # sma20 > sma50: +0.5
        "rsi14": 25.0,  # rsi < 30: +0.4
        "macd": 1.0,
        "macd_histogram": 0.5,  # macd > 0 and histogram > 0: +0.3
        "recent_high": 120.0,
        "recent_low": 90.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    assert result["symbol"] == "AAPL"
    assert result["decision"] == "BUY"
    assert result["score"] >= 0.5
    assert result["confidence"] > 0
    assert "confidence" in result
    assert "score" in result
    assert "reasons" in result
    assert "indicators_snapshot" in result
    assert isinstance(result["reasons"], list)


def test_baseline_sell_scenario():
    """Test SELL decision when score <= -0.5.

    Conditions for SELL:
    - sma20 < sma50: -0.5
    - close < sma20 * 0.95: -0.3
    - rsi14 > 70: -0.4
    Total score: -1.2 -> SELL
    """
    indicators = {
        "last_close": 85.0,
        "sma20": 100.0,
        "sma50": 105.0,  # sma20 < sma50: -0.5
        "rsi14": 75.0,  # rsi > 70: -0.4
        "macd": -1.0,
        "macd_histogram": -0.5,  # macd < 0 and histogram < 0: -0.3
        "recent_high": 120.0,
        "recent_low": 80.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    assert result["symbol"] == "AAPL"
    assert result["decision"] == "SELL"
    assert result["score"] <= -0.5
    assert result["confidence"] > 0
    assert "confidence" in result
    assert "score" in result
    assert "reasons" in result
    assert "indicators_snapshot" in result


def test_baseline_hold_scenario():
    """Test HOLD decision when score is between -0.5 and 0.5.

    Neutral conditions:
    - sma20 == sma50: no score change
    - close near sma20: no score change
    - rsi14 around 50: small score change
    """
    indicators = {
        "last_close": 100.0,
        "sma20": 100.0,
        "sma50": 100.0,  # sma20 == sma50: no change
        "rsi14": 50.0,  # neutral RSI
        "macd": 0.0,
        "macd_histogram": 0.0,
        "recent_high": 110.0,
        "recent_low": 90.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    assert result["symbol"] == "AAPL"
    assert result["decision"] == "HOLD"
    assert -0.5 < result["score"] < 0.5
    assert "confidence" in result
    assert "score" in result
    assert "reasons" in result
    assert "indicators_snapshot" in result


def test_baseline_output_fields():
    """Test all expected output fields are present."""
    indicators = {
        "last_close": 100.0,
        "sma20": 100.0,
        "sma50": 100.0,
        "rsi14": 50.0,
        "macd": 0.0,
        "macd_histogram": 0.0,
        "recent_high": 110.0,
        "recent_low": 90.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    # Check all required fields
    assert "symbol" in result
    assert "decision" in result
    assert "confidence" in result
    assert "score" in result
    assert "reasons" in result
    assert "indicators_snapshot" in result

    # Check indicators_snapshot fields
    snapshot = result["indicators_snapshot"]
    assert "close" in snapshot
    assert "sma20" in snapshot
    assert "sma50" in snapshot
    assert "rsi14" in snapshot
    assert "macd" in snapshot
    assert "macd_histogram" in snapshot
    assert "recent_high" in snapshot
    assert "recent_low" in snapshot


def test_baseline_confidence_calculation():
    """Test confidence is calculated correctly for BUY decision."""
    indicators = {
        "last_close": 110.0,
        "sma20": 100.0,
        "sma50": 95.0,
        "rsi14": 25.0,
        "macd": 1.0,
        "macd_histogram": 0.5,
        "recent_high": 120.0,
        "recent_low": 90.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    # Confidence should be calculated as min(int((score / 2.0) * 100), 95)
    assert result["decision"] == "BUY"
    assert 0 <= result["confidence"] <= 95


def test_baseline_reasons_not_empty():
    """Test reasons list is not empty when signals are present."""
    indicators = {
        "last_close": 110.0,
        "sma20": 100.0,
        "sma50": 95.0,
        "rsi14": 25.0,
        "macd": 1.0,
        "macd_histogram": 0.5,
        "recent_high": 120.0,
        "recent_low": 90.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    assert len(result["reasons"]) > 0
    assert all(isinstance(r, str) for r in result["reasons"])


def test_baseline_score_rounded():
    """Test score is rounded to 2 decimal places."""
    indicators = {
        "last_close": 100.0,
        "sma20": 100.0,
        "sma50": 100.0,
        "rsi14": 50.0,
        "macd": 0.0,
        "macd_histogram": 0.0,
        "recent_high": 110.0,
        "recent_low": 90.0,
    }
    result = generate_baseline_analysis("AAPL", indicators)

    # Score should be a float rounded to 2 decimal places
    assert isinstance(result["score"], float)
    # Check it has at most 2 decimal places
    assert result["score"] == round(result["score"], 2)
