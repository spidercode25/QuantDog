# Indicators API endpoints

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.analysis.indicators import calculate_indicators
from quantdog.config import get_settings
from quantdog.infra.sqlalchemy import get_engine
from sqlalchemy import text


indicators_bp = Blueprint("indicators", __name__, url_prefix="/api/v1")


@indicators_bp.get("/instruments/<symbol>/indicators")
def get_indicators(symbol: str):
    """Get technical indicators for a symbol.
    
    Query params:
    - start: start date (YYYY-MM-DD) - optional, defaults to 90 days ago
    - end: end date (YYYY-MM-DD) - optional, defaults to today
    - adjusted: true/false (default: true)
    - limit: max bars to fetch for calculation (default: 100, max: 252)
    """
    symbol = symbol.upper()
    
    start_date = request.args.get("start", "").strip()
    end_date = request.args.get("end", "").strip()
    adjusted = request.args.get("adjusted", "true").strip().lower() == "true"
    limit = min(int(request.args.get("limit", "100")), 252)  # Max ~1 year of daily bars
    
    settings = get_settings()
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    
    engine = get_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Build query for bars - need enough for SMA50 + RSI14 calculations
        query = """
            SELECT symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source
            FROM bars_1d
            WHERE symbol = :symbol AND adjusted = :adjusted
        """
        params = {"symbol": symbol, "adjusted": adjusted, "limit": limit}
        
        if start_date:
            query += " AND bar_date >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            query += " AND bar_date <= :end_date"
            params["end_date"] = end_date
        
        query += " ORDER BY bar_date ASC LIMIT :limit"
        
        result = conn.execute(text(query), params)
        rows = result.fetchall()
    
    if not rows:
        return error(
            "No bars found",
            error_type="not_found",
            detail=f"No bars found for {symbol} in the specified date range"
        )
    
    # Convert to dict format for indicator calculation
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
        for row in rows
    ]
    
    # Calculate indicators
    indicators = calculate_indicators(bars)
    
    return success({
        "symbol": symbol,
        "bars_count": len(bars),
        "indicators": indicators
    })
