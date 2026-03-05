# Research API endpoints

import uuid
from datetime import datetime

from flask import Blueprint, request

from quantdog.api.envelope import error, success
from quantdog.config import get_settings
from quantdog.jobs.queue import enqueue_job
from quantdog.research import (
    Horizon,
    ResearchRunStatus,
)
from quantdog.research.repository import (
    get_research_run,
    get_agent_outputs,
)


research_bp = Blueprint("research", __name__, url_prefix="/api/v1/research")


@research_bp.post("/runs")
def create_research_run():
    """Create a new research run.
    
    Request body:
    - symbol: stock symbol (required)
    - horizon: "1d", "1w", "1m", "3m", "6m", "1y" (optional, default: "1w")
    
    Returns 202 with run_id if successful.
    """
    settings = get_settings()
    
    # Check if research is enabled
    if not settings.research_enabled:
        return error(
            "Research feature is not enabled",
            error_type="feature_disabled",
            detail="Set RESEARCH_ENABLED=true to enable this feature",
            status_code=404,
        )
    
    data = request.get_json()
    if not data:
        return error("Invalid request", error_type="invalid_request", detail="Request body must be JSON")
    
    symbol = data.get("symbol", "").strip().upper()
    if not symbol:
        return error("Symbol is required", error_type="missing_field", detail="symbol field is required")
    
    horizon_str = data.get("horizon", "1w").strip()
    try:
        horizon = Horizon(horizon_str)
    except ValueError:
        return error(
            "Invalid horizon",
            error_type="invalid_field",
            detail="horizon must be one of: 1d, 1w, 1m, 3m, 6m, 1y"
        )
    
    # Check idempotency key from header
    idempotency_key = request.headers.get("Idempotency-Key")
    dedupe_key = f"research:{symbol}:{horizon.value}"
    if idempotency_key:
        dedupe_key = f"{dedupe_key}:{idempotency_key}"
    
    # Create run_id
    run_id = str(uuid.uuid4())
    
    # Enqueue the job
    job_payload = {
        "run_id": run_id,
        "symbol": symbol,
        "horizon": horizon.value,
    }
    
    try:
        enqueue_job(
            database_url=settings.database_url,
            kind="research_run",
            payload=job_payload,
            dedupe_key=dedupe_key,
        )
    except Exception as e:
        return error(
            "Failed to enqueue research run",
            error_type="job_enqueue_error",
            detail=str(e)
        )
    
    return success({
        "run_id": run_id,
        "symbol": symbol,
        "horizon": horizon.value,
        "status": ResearchRunStatus.PENDING.value,
    }), 202


@research_bp.get("/runs/<run_id>")
def get_research_run_status(run_id: str):
    """Get research run status and progress.
    
    Returns run status, timestamps, and agent progress.
    """
    settings = get_settings()
    
    # Check if research is enabled
    if not settings.research_enabled:
        return error(
            "Research feature is not enabled",
            error_type="feature_disabled",
            detail="Set RESEARCH_ENABLED=true to enable this feature",
            status_code=404,
        )
    
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error")
    
    # Get run from DB
    run = get_research_run(settings.database_url, run_id)
    
    if not run:
        return error(
            "Research run not found",
            error_type="not_found",
            detail=f"No research run found with id: {run_id}"
        )
    
    # Get agent outputs for progress
    agent_outputs = get_agent_outputs(settings.database_url, run_id)
    
    # Build progress info
    progress = {
        "phase1_complete": any(o.phase == 1 for o in agent_outputs),
        "phase2_complete": any(o.phase == 2 for o in agent_outputs),
        "phase3_complete": any(o.phase == 3 for o in agent_outputs),
        "agents_completed": len(agent_outputs),
    }
    
    return success({
        "run_id": run.run_id,
        "symbol": run.symbol,
        "status": run.status.value,
        "requested_at": run.requested_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "baseline_used": run.baseline_used,
        "quality_score": run.quality_score,
        "error_summary": run.error_summary,
        "progress": progress,
    })


@research_bp.get("/runs/<run_id>/result")
def get_research_run_result(run_id: str):
    """Get research run final result.
    
    Returns the final decision and all agent outputs.
    """
    settings = get_settings()
    
    # Check if research is enabled
    if not settings.research_enabled:
        return error(
            "Research feature is not enabled",
            error_type="feature_disabled",
            detail="Set RESEARCH_ENABLED=true to enable this feature",
            status_code=404,
        )
    
    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error")
    
    # Get run from DB
    run = get_research_run(settings.database_url, run_id)
    
    if not run:
        return error(
            "Research run not found",
            error_type="not_found",
            detail=f"No research run found with id: {run_id}"
        )
    
    # Get all agent outputs
    agent_outputs = get_agent_outputs(settings.database_url, run_id)
    
    # Build result
    result = {
        "run_id": run.run_id,
        "symbol": run.symbol,
        "status": run.status.value,
        "final_decision": run.final_decision,
        "final_confidence": run.final_confidence,
        "baseline_used": run.baseline_used,
        "quality_score": run.quality_score,
        "requested_at": run.requested_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_summary": run.error_summary,
        "agent_outputs": [
            {
                "phase": o.phase,
                "agent_name": o.agent_name,
                "status": o.status.value,
                "output": o.output,
                "validation_errors": o.validation_errors,
                "duration_ms": o.duration_ms,
                "model_id": o.model_id,
            }
            for o in agent_outputs
        ],
    }
    
    return success(result)
