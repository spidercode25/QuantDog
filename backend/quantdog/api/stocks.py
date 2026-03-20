# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false

from __future__ import annotations

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.config import get_settings
from quantdog.services.market_intel import MarketIntelService


stocks_bp = Blueprint("stocks", __name__, url_prefix="/api/v1/stocks")


def _service() -> MarketIntelService:
    return MarketIntelService(settings=get_settings())


@stocks_bp.post("/<symbol>/strategy")  # type: ignore[arg-type]
def stock_strategy(symbol: str):
    data = request.get_json() or {}
    horizon = str(data.get("horizon") or "1d").strip()
    limit = int(data.get("limit") or 20)

    try:
        result = _service().get_strategy(symbol.strip().upper(), horizon=horizon, limit=limit)
    except ValueError as exc:
        return error("Strategy analysis failed", error_type="invalid_request", detail=str(exc))

    return success(result)


@stocks_bp.get("/<symbol>/monitor")  # type: ignore[arg-type]
def stock_monitor(symbol: str):
    horizon = str(request.args.get("horizon") or "1d").strip()
    limit = int(request.args.get("limit") or 20)

    result = _service().get_monitoring([symbol.strip().upper()], horizon=horizon, limit=limit)
    item = result["results"][0] if result["results"] else {"symbol": symbol.strip().upper(), "error": "no result"}

    payload = {
        "symbol": symbol.strip().upper(),
        "snapshot": item,
        "has_alert": any(a.get("symbol") == symbol.strip().upper() for a in result.get("alerts", [])),
    }
    return success(payload)


@stocks_bp.post("/monitor")  # type: ignore[arg-type]
def stocks_monitor_batch():
    data = request.get_json() or {}
    symbols = data.get("symbols") or []
    if not isinstance(symbols, list) or not symbols:
        return error("symbols is required", error_type="missing_field", detail="symbols must be non-empty list")

    horizon = str(data.get("horizon") or "1d").strip()
    limit = int(data.get("limit") or 20)
    result = _service().get_monitoring(symbols, horizon=horizon, limit=limit)
    return success(result)
