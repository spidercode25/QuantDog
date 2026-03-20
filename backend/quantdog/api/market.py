# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false

from __future__ import annotations

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.config import get_settings
from quantdog.services.market_intel import MarketIntelService


market_bp = Blueprint("market", __name__, url_prefix="/api/v1/market")


def _service() -> MarketIntelService:
    return MarketIntelService(settings=get_settings())


@market_bp.post("/technical")  # type: ignore[arg-type]
def technical_analysis():
    data = request.get_json() or {}
    symbol = str(data.get("symbol") or "").strip().upper()
    horizon = str(data.get("horizon") or "1d").strip()
    if not symbol:
        return error("Symbol is required", error_type="missing_field", detail="symbol field is required")

    try:
        result = _service().get_technical_analysis(symbol, horizon=horizon)
    except ValueError as exc:
        return error("Technical analysis failed", error_type="invalid_request", detail=str(exc))

    return success(result)


@market_bp.post("/intel")  # type: ignore[arg-type]
def intel_analysis():
    data = request.get_json() or {}
    symbol = str(data.get("symbol") or "").strip().upper()
    limit = int(data.get("limit") or 20)
    if not symbol:
        return error("Symbol is required", error_type="missing_field", detail="symbol field is required")

    result = _service().get_news_twitter_analysis(symbol, limit=limit)
    return success(result)


@market_bp.post("/macro")  # type: ignore[arg-type]
def macro_analysis():
    data = request.get_json() or {}
    symbol = str(data.get("symbol") or "").strip().upper()
    limit = int(data.get("limit") or 20)
    if not symbol:
        return error("Symbol is required", error_type="missing_field", detail="symbol field is required")

    result = _service().get_macro_analysis(symbol, limit=limit)
    return success(result)


# Strategy/monitor routes moved to /api/v1/stocks/... resource-style API.
