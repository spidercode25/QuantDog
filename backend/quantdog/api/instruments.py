# Instrument search and metadata endpoints

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.infra.sqlalchemy import get_engine
from quantdog.config import get_settings


instruments_bp = Blueprint("instruments", __name__, url_prefix="/api/v1")


@instruments_bp.get("/instruments/search")
def search_instruments():
    """Search for instruments by query string.
    
    If the symbol doesn't exist, create a placeholder.
    """
    query = request.args.get("query", "").strip().upper()
    
    if not query:
        return error("Query is required", error_type="invalid_request", detail="Missing query parameter")
    
    if len(query) > 10:
        return error("Invalid symbol", error_type="invalid_request", detail="Symbol too long")
    
    settings = get_settings()
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    
    engine = get_engine(settings.database_url)
    
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Check if instrument exists
        result = conn.execute(
            text("SELECT symbol, name, exchange, type, currency, active FROM instruments WHERE symbol = :symbol"),
            {"symbol": query}
        )
        row = result.fetchone()
        
        if row is None:
            # Create placeholder instrument
            conn.execute(
                text("""
                    INSERT INTO instruments (symbol, name, exchange, type, currency, active)
                    VALUES (:symbol, NULL, NULL, NULL, NULL, true)
                    ON CONFLICT (symbol) DO NOTHING
                """),
                {"symbol": query}
            )
            conn.commit()
            
            # Fetch the created/existing instrument
            result = conn.execute(
                text("SELECT symbol, name, exchange, type, currency, active FROM instruments WHERE symbol = :symbol"),
                {"symbol": query}
            )
            row = result.fetchone()
        
        if row:
            instrument = {
                "symbol": row[0],
                "name": row[1],
                "exchange": row[2],
                "type": row[3],
                "currency": row[4],
                "active": row[5]
            }
            return success({"instrument": instrument})
        
        return error("Instrument not found", error_type="not_found", detail=f"Symbol {query} not found")


@instruments_bp.get("/instruments/<symbol>")
def get_instrument(symbol: str):
    """Get instrument details by symbol."""
    symbol = symbol.upper()
    
    settings = get_settings()
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    
    engine = get_engine(settings.database_url)
    
    from sqlalchemy import text
    
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT symbol, name, exchange, type, currency, active FROM instruments WHERE symbol = :symbol"),
            {"symbol": symbol}
        )
        row = result.fetchone()
        
        if row is None:
            return error("Instrument not found", error_type="not_found", detail=f"Symbol {symbol} not found")
        
        instrument = {
            "symbol": row[0],
            "name": row[1],
            "exchange": row[2],
            "type": row[3],
            "currency": row[4],
            "active": row[5]
        }
        return success({"instrument": instrument})
