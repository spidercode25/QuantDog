# Research job handler

import logging

from config import get_settings
from research import (
    Horizon,
    create_orchestrator,
)
from research.repository import get_research_run

logger = logging.getLogger(__name__)


def handle_research_run(job_payload: dict) -> dict:
    """Handle research_run job execution.
    
    Job payload:
    {
        "run_id": "uuid",
        "symbol": "AAPL",
        "horizon": "1w"
    }
    """
    settings = get_settings()
    
    if not settings.research_enabled:
        return {
            "success": False,
            "error": "Research feature is disabled (RESEARCH_ENABLED=false)",
        }
    
    run_id = job_payload.get("run_id")
    symbol = job_payload.get("symbol")
    horizon_str = job_payload.get("horizon", "1w")
    
    if not run_id or not symbol:
        return {
            "success": False,
            "error": "Missing required fields: run_id, symbol",
        }
    
    # Parse horizon
    try:
        horizon = Horizon(horizon_str)
    except ValueError:
        horizon = Horizon.ONE_WEEK
    
    # Verify run exists
    run = get_research_run(settings.database_url, run_id)
    if not run:
        return {
            "success": False,
            "error": f"Research run not found: {run_id}",
        }
    
    # Create orchestrator
    orchestrator = create_orchestrator(
        database_url=settings.database_url,
        use_stub=not settings.enable_ai_analysis,
    )
    
    # Execute research
    try:
        result = orchestrator.run_research(
            symbol=symbol,
            horizon=horizon,
        )
        return {
            "success": True,
            "run_id": run_id,
            "result": result,
        }
    except Exception as e:
        logger.exception(f"Research run failed: {run_id}")
        return {
            "success": False,
            "run_id": run_id,
            "error": str(e),
        }
