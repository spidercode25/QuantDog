# Job queue operations for QuantDog

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text


logger = logging.getLogger("quantdog.jobs.queue")


def _ensure_jobs_table(engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    state TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    locked_by TEXT,
                    locked_at TIMESTAMP,
                    heartbeat_at TIMESTAMP,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    last_error TEXT,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
        )
        conn.commit()


def enqueue_job(engine, *, kind: str, payload: dict[str, Any], dedupe_key: str | None = None) -> str | None:
    """Enqueue a new job.
    
    Returns job_id if created, or None if deduplicated.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    if dedupe_key is None:
        dedupe_key = f"{kind}:{job_id}"

    _ensure_jobs_table(engine)
    
    # Convert payload to JSON string for SQLite compatibility
    payload_str = json.dumps(payload)
    
    with engine.connect() as conn:
        # Check for existing job with same dedupe_key in queued/running state
        result = conn.execute(
            text("SELECT id FROM jobs WHERE dedupe_key = :dk AND state IN ('queued', 'running')"),
            {"dk": dedupe_key}
        )
        if result.fetchone() is not None:
            logger.info("Job deduplicated: %s", dedupe_key)
            return None
        
        conn.execute(
            text("""
                INSERT INTO jobs (id, kind, payload, state, dedupe_key, created_at, updated_at)
                VALUES (:id, :kind, :payload, 'queued', :dedupe_key, :now, :now)
            """),
            {
                "id": job_id,
                "kind": kind,
                "payload": payload_str,
                "dedupe_key": dedupe_key,
                "now": now
            }
        )
        conn.commit()
    
    logger.info("Job enqueued: %s (%s)", job_id, kind)
    return job_id


def claim_job(engine, *, worker_name: str, max_attempts: int = 3) -> dict[str, Any] | None:
    """Claim a queued job.
    
    Returns job dict if claimed, None if no jobs available.
    Note: Uses FOR UPDATE SKIP LOCKED for PostgreSQL. Falls back to simple
    SELECT for SQLite (no locking - not safe for concurrent workers).
    """
    now = datetime.now(timezone.utc)
    
    with engine.connect() as conn:
        # Check if PostgreSQL (supports SKIP LOCKED)
        dialect = engine.dialect.name
        
        if dialect == "postgresql":
            # PostgreSQL: Use FOR UPDATE SKIP LOCKED
            result = conn.execute(
                text("""
                    SELECT id, kind, payload, attempts, max_attempts
                    FROM jobs
                    WHERE state = 'queued' AND attempts < max_attempts
                    ORDER BY created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                """)
            )
        else:
            # SQLite/Other: Simple claim without locking
            result = conn.execute(
                text("""
                    SELECT id, kind, payload, attempts, max_attempts
                    FROM jobs
                    WHERE state = 'queued' AND attempts < max_attempts
                    ORDER BY created_at ASC
                    LIMIT 1
                """)
            )
        
        row = result.fetchone()
        
        if row is None:
            return None
        
        job_id, kind, payload, attempts, max_attempts = row
        
        # Update job to running
        if dialect == "postgresql":
            conn.execute(
                text("""
                    UPDATE jobs
                    SET state = 'running',
                        locked_by = :worker,
                        locked_at = :now,
                        heartbeat_at = :now,
                        attempts = attempts + 1,
                        updated_at = :now
                    WHERE id = :id
                """),
                {"worker": worker_name, "now": now, "id": job_id}
            )
        else:
            # SQLite: Simple update
            conn.execute(
                text("""
                    UPDATE jobs
                    SET state = 'running',
                        locked_by = :worker,
                        locked_at = :now,
                        heartbeat_at = :now,
                        attempts = attempts + 1,
                        updated_at = :now
                    WHERE id = :id
                """),
                {"worker": worker_name, "now": now, "id": job_id}
            )
        conn.commit()
    
    logger.info("Job claimed: %s (%s)", job_id, kind)
    return {
        "id": job_id,
        "kind": kind,
        "payload": json.loads(payload) if isinstance(payload, str) else payload,
        "attempts": attempts + 1,
        "max_attempts": max_attempts
    }


def heartbeat_job(engine, *, job_id: str, worker_name: str) -> None:
    """Update heartbeat for a running job."""
    now = datetime.now(timezone.utc)
    
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE jobs
                SET heartbeat_at = :now, updated_at = :now
                WHERE id = :id AND locked_by = :worker
            """),
            {"now": now, "id": job_id, "worker": worker_name}
        )
        conn.commit()


def finish_job(engine, *, job_id: str, state: str = "succeeded", error: str | None = None) -> None:
    """Mark a job as finished (succeeded or failed)."""
    now = datetime.now(timezone.utc)
    
    with engine.connect() as conn:
        conn.execute(
            text("""
                UPDATE jobs
                SET state = :state,
                    last_error = :error,
                    locked_by = NULL,
                    locked_at = NULL,
                    heartbeat_at = NULL,
                    updated_at = :now
                WHERE id = :id
            """),
            {"state": state, "error": error, "now": now, "id": job_id}
        )
        conn.commit()
    
    logger.info("Job finished: %s (%s)", job_id, state)


def requeue_stale_jobs(engine, *, stale_seconds: int = 300) -> int:
    """Requeue jobs that have stale heartbeats.
    
    Returns number of jobs requeued.
    """
    now = datetime.now(timezone.utc)
    
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                UPDATE jobs
                SET state = 'queued',
                    locked_by = NULL,
                    locked_at = NULL,
                    heartbeat_at = NULL,
                    updated_at = :now
                WHERE state = 'running'
                  AND heartbeat_at < :threshold
            """),
            {"now": now, "threshold": datetime.now(timezone.utc).timestamp() - stale_seconds}
        )
        conn.commit()
    
    if result.rowcount > 0:
        logger.info("Requeued %d stale jobs", result.rowcount)
    
    return result.rowcount
