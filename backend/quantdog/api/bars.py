# Bars API endpoints

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.config import get_settings
from quantdog.infra.sqlalchemy import get_engine
from sqlalchemy import text


bars_bp = Blueprint("bars", __name__, url_prefix="/api/v1")


@bars_bp.get("/instruments/<symbol>/bars")
def get_bars(symbol: str):
    """Get daily bars for a symbol.
    
    Query params:
    - start: start date (YYYY-MM-DD)
    - end: end date (YYYY-MM-DD)
    - adjusted: true/false (default: true)
    - limit: max rows (default: 1000, max: 5000)
    """
    symbol = symbol.upper()
    
    start_date = request.args.get("start", "").strip()
    end_date = request.args.get("end", "").strip()
    adjusted = request.args.get("adjusted", "true").strip().lower() == "true"
    limit = min(int(request.args.get("limit", "1000")), 5000)
    
    settings = get_settings()
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    
    engine = get_engine(settings.database_url)
    
    with engine.connect() as conn:
        query = """
            SELECT symbol, bar_date, ts_utc, open, high, low, close, volume, adjusted, source
            FROM bars_1d
            WHERE symbol = :symbol
        """
        params = {"symbol": symbol, "adjusted": adjusted, "limit": limit}
        
        if start_date:
            query += " AND bar_date >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            query += " AND bar_date <= :end_date"
            params["end_date"] = end_date
        
        query += " ORDER BY bar_date DESC LIMIT :limit"
        
        result = conn.execute(text(query), params)
        rows = result.fetchall()
    
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
    
    return success({"bars": bars, "count": len(bars)})
