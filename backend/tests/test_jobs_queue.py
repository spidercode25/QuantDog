from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from infra.sqlalchemy import get_engine
from jobs.queue import claim_job, enqueue_job, requeue_stale_jobs


def test_requeue_stale_jobs_requeues_timestamp_rows() -> None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as db_file:
        engine = get_engine(f"sqlite:///{db_file.name}")

        job_id = enqueue_job(engine, kind="example", payload={"ok": True}, dedupe_key="example:1")
        assert job_id is not None

        claimed = claim_job(engine, worker_name="worker-1")
        assert claimed is not None

        stale_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=600)
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE jobs SET heartbeat_at = :heartbeat_at, state = 'running' WHERE id = :job_id"
                ),
                {"heartbeat_at": stale_heartbeat, "job_id": job_id},
            )
            conn.commit()

        count = requeue_stale_jobs(engine, stale_seconds=300)
        assert count == 1

        with engine.connect() as conn:
            state = conn.execute(
                text("SELECT state FROM jobs WHERE id = :job_id"),
                {"job_id": job_id},
            ).scalar_one()

        assert state == "queued"
