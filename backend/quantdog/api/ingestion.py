# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false

# Ingestion API endpoints

from datetime import datetime

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.config import get_settings
from quantdog.infra.sqlalchemy import get_engine
from quantdog.jobs import queue


ingestion_bp = Blueprint("ingestion", __name__, url_prefix="/api/v1")


@ingestion_bp.post("/ingestions")  # type: ignore
def create_ingestion():
    """Enqueue a bar ingestion job.
    
    Request body (JSON):
    {
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "adjusted": true
    }
    """
    data = request.get_json()
    if not data:
        return error("Request body required", error_type="invalid_request", detail="Missing JSON body")
    
    symbol = data.get("symbol", "").strip().upper()
    start_date = data.get("start_date", "").strip()
    end_date = data.get("end_date", "").strip()
    adjusted = data.get("adjusted", True)
    
    # Validation
    if not symbol:
        return error("Symbol required", error_type="invalid_request", detail="Missing symbol")
    
    if not start_date or not end_date:
        return error("Dates required", error_type="invalid_request", detail="Missing start_date or end_date")
    
    # Validate dates format (simple check)
    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        return error("Invalid date format", error_type="invalid_request", detail="Use YYYY-MM-DD format")
    
    # Enqueue job
    settings = get_settings()
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    
    engine = get_engine(settings.database_url)
    
    # Generate dedupe key
    dedupe_key = f"ingest:{symbol}:1d:{start_date}:{end_date}:adjusted={adjusted}"
    
    payload = {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "adjusted": adjusted
    }
    
    job_id = queue.enqueue_job(
        engine,
        kind="ingest_bars",
        payload=payload,
        dedupe_key=dedupe_key
    )
    
    if job_id is None:
        # Job was deduplicated
        return success({
            "message": "Job already exists",
            "dedupe_key": dedupe_key
        }, msg="Job enqueued (or deduplicated)")
    
    return success({
        "job_id": job_id,
        "dedupe_key": dedupe_key
    }, msg="Job enqueued")
