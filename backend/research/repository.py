# Research Run Repository

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from infra.sqlalchemy import get_engine
from research.models import (
    ResearchRun,
    ResearchRunStatus,
    AgentOutput,
    AgentStatus,
)
from sqlalchemy import text


def create_research_run(
    database_url: str,
    symbol: str,
    config: dict[str, Any],
) -> ResearchRun:
    """Create a new research run record."""
    run_id = str(uuid.uuid4())
    requested_at = datetime.utcnow()
    
    # Convert config to JSON for SQLite
    config_json = json.dumps(config)
    
    engine = get_engine(database_url)
    
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO research_runs 
                (run_id, symbol, requested_at, status, config_json)
                VALUES (:run_id, :symbol, :requested_at, :status, :config)
            """),
            {
                "run_id": run_id,
                "symbol": symbol,
                "requested_at": requested_at,
                "status": ResearchRunStatus.PENDING.value,
                "config": config_json,
            },
        )
        conn.commit()
    
    return ResearchRun(
        run_id=run_id,
        symbol=symbol,
        requested_at=requested_at.isoformat(),
        status=ResearchRunStatus.PENDING,
        config=config,
    )


def get_research_run(database_url: str, run_id: str) -> ResearchRun | None:
    """Get a research run by ID."""
    engine = get_engine(database_url)
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT run_id, symbol, requested_at, started_at, completed_at,
                       status, final_decision, final_confidence, baseline_used,
                       quality_score, error_summary, config_json
                FROM research_runs
                WHERE run_id = :run_id
            """),
            {"run_id": run_id},
        )
        row = result.fetchone()
    
    if not row:
        return None
    
    return ResearchRun(
        run_id=row[0],
        symbol=row[1],
        requested_at=str(row[2]),
        started_at=str(row[3]) if row[3] else None,
        completed_at=str(row[4]) if row[4] else None,
        status=ResearchRunStatus(row[5]),
        final_decision=row[6],
        final_confidence=row[7],
        baseline_used=bool(row[8]),
        quality_score=row[9],
        error_summary=row[10],
        config=row[11] or {},
    )


def update_research_run_status(
    database_url: str,
    run_id: str,
    status: ResearchRunStatus,
    final_decision: str | None = None,
    final_confidence: int | None = None,
    baseline_used: bool | None = None,
    quality_score: int | None = None,
    error_summary: str | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> None:
    """Update research run status."""
    engine = get_engine(database_url)
    
    # Build dynamic update
    updates = ["status = :status"]
    params: dict[str, Any] = {"run_id": run_id, "status": status.value}
    
    if final_decision is not None:
        updates.append("final_decision = :final_decision")
        params["final_decision"] = final_decision
    
    if final_confidence is not None:
        updates.append("final_confidence = :final_confidence")
        params["final_confidence"] = final_confidence
    
    if baseline_used is not None:
        updates.append("baseline_used = :baseline_used")
        params["baseline_used"] = baseline_used
    
    if quality_score is not None:
        updates.append("quality_score = :quality_score")
        params["quality_score"] = quality_score
    
    if error_summary is not None:
        updates.append("error_summary = :error_summary")
        params["error_summary"] = error_summary
    
    if started_at is not None:
        updates.append("started_at = :started_at")
        params["started_at"] = started_at
    
    if completed_at is not None:
        updates.append("completed_at = :completed_at")
        params["completed_at"] = completed_at
    
    query = f"""
        UPDATE research_runs
        SET {', '.join(updates)}
        WHERE run_id = :run_id
    """
    
    with engine.connect() as conn:
        conn.execute(text(query), params)
        conn.commit()


def save_agent_output(
    database_url: str,
    run_id: str,
    phase: int,
    agent_name: str,
    status: AgentStatus,
    output: dict[str, Any],
    validation_errors: list[str],
    duration_ms: int | None,
    model_id: str | None,
    schema_version: str | None = None,
) -> str:
    """Save agent output (upsert on conflict)."""
    output_id = str(uuid.uuid4())
    
    # Convert to JSON for SQLite
    output_json = json.dumps(output)
    validation_errors_json = json.dumps(validation_errors)
    
    engine = get_engine(database_url)
    
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO research_agent_outputs
                (id, run_id, phase, agent_name, status, schema_version,
                 output_json, validation_errors_json, duration_ms, model_id)
                VALUES (:id, :run_id, :phase, :agent_name, :status, :schema_version,
                        :output, :validation_errors, :duration_ms, :model_id)
                ON CONFLICT (run_id, phase, agent_name)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    output_json = EXCLUDED.output_json,
                    validation_errors_json = EXCLUDED.validation_errors_json,
                    duration_ms = EXCLUDED.duration_ms,
                    model_id = EXCLUDED.model_id
            """),
            {
                "id": output_id,
                "run_id": run_id,
                "phase": phase,
                "agent_name": agent_name,
                "status": status.value,
                "schema_version": schema_version,
                "output": output_json,
                "validation_errors": validation_errors_json,
                "duration_ms": duration_ms,
                "model_id": model_id,
            },
        )
        conn.commit()
    
    return output_id


def get_agent_outputs(
    database_url: str,
    run_id: str,
) -> list[AgentOutput]:
    """Get all agent outputs for a run."""
    engine = get_engine(database_url)
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT phase, agent_name, status, schema_version,
                       output_json, validation_errors_json, duration_ms, model_id
                FROM research_agent_outputs
                WHERE run_id = :run_id
                ORDER BY phase, agent_name
            """),
            {"run_id": run_id},
        )
        rows = result.fetchall()
    
    outputs = []
    for row in rows:
        # Parse JSON fields
        output_data = json.loads(row[4]) if row[4] else {}
        validation_errors = json.loads(row[5]) if row[5] else []

        outputs.append(
            AgentOutput(
                phase=row[0],
                agent_name=row[1],
                status=AgentStatus(row[2]),
                output=output_data,
                validation_errors=validation_errors,
                duration_ms=row[6],
                model_id=row[7],
            )
        )

    return outputs
