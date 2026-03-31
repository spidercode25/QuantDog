# Worker runner for QuantDog jobs

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from typing import Any, Callable

from config import get_settings, load_env, validate_required_settings
from infra.sqlalchemy import get_engine
from jobs import queue
from utils import configure_logging


logger = logging.getLogger("runner")

# Global engine for job handlers
_engine = None


# Registry of job handlers: kind -> callable(job_payload) -> result
JOB_HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {}


# Import and register job handlers
from jobs.ingestion import handle_ingestion_job
from jobs.news_ingestion import handle_news_ingestion_job
from jobs.research import handle_research_run
from jobs.candidate_pool_close_run import handle_candidate_pool_close_run
from jobs.telegram_delivery import handle_telegram_send_message

# Register handlers
JOB_HANDLERS["ingest_bars"] = handle_ingestion_job
JOB_HANDLERS["ingest_news"] = handle_news_ingestion_job
JOB_HANDLERS["research_run"] = handle_research_run
JOB_HANDLERS["candidate_pool_close_run"] = handle_candidate_pool_close_run
JOB_HANDLERS["telegram_send_message"] = handle_telegram_send_message


def register_job_handler(kind: str):
    """Decorator to register a job handler."""
    def decorator(func):
        JOB_HANDLERS[kind] = func
        return func
    return decorator


def _get_engine():
    """Get the global engine instance."""
    global _engine
    return _engine


def run_job_handler(job: dict[str, Any]) -> None:
    """Run the appropriate handler for a job."""
    global _engine
    
    kind = job["kind"]
    payload = job["payload"]
    job_id = job["id"]
    engine = _get_engine()
    
    handler = JOB_HANDLERS.get(kind)
    if handler is None:
        logger.warning("Unknown job kind: %s", kind)
        queue.finish_job(engine, job_id=job_id, state="failed", error=f"Unknown kind: {kind}")
        return
    
    try:
        result = handler(payload)
        queue.finish_job(engine, job_id=job_id, state="succeeded")
        logger.info("Job succeeded: %s", job_id)
    except Exception as e:
        logger.exception("Job failed: %s", job_id)
        queue.finish_job(engine, job_id=job_id, state="failed", error=str(e))


def run_once(worker_name: str, engine) -> bool:
    """Process one job and return True if a job was processed."""
    global _engine
    _engine = engine
    
    job = queue.claim_job(engine, worker_name=worker_name)
    
    if job is None:
        return False
    
    # Update heartbeat before running
    queue.heartbeat_job(engine, job_id=job["id"], worker_name=worker_name)
    
    # Run the job
    run_job_handler(job)
    
    return True


def run_loop(worker_name: str, engine, poll_interval: int = 5) -> None:
    """Main worker loop."""
    global _engine
    _engine = engine
    
    logger.info("Worker loop starting: %s (poll_interval=%ds)", worker_name, poll_interval)
    
    while True:
        try:
            # Try to claim and run a job
            if run_once(worker_name, engine):
                # Job ran, immediately try again
                continue
            
            # No job available, sleep
            time.sleep(poll_interval)
            
        except KeyboardInterrupt:
            logger.info("Worker interrupted, shutting down")
            break
        except Exception:
            logger.exception("Worker loop error")
            time.sleep(poll_interval)


def main() -> int:
    """Entry point for worker."""
    load_env()
    
    try:
        settings = get_settings()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2
    
    configure_logging(service_name="worker", log_dir=settings.log_dir)
    
    try:
        validate_required_settings(settings)
    except ValueError as e:
        logging.getLogger("config").error(str(e))
        return 2
    
    db_url = settings.database_url
    if db_url is None:
        print("DATABASE_URL is required", file=sys.stderr)
        return 2
    
    engine = get_engine(db_url)
    worker_name = settings.worker_name
    
    # Parse CLI args
    parser = argparse.ArgumentParser(description="QuantDog worker")
    parser.add_argument("--once", action="store_true", help="Process one job then exit")
    parser.add_argument("--poll-interval", type=int, default=5, help="Seconds between job polls")
    args = parser.parse_args()
    
    logger.info("Starting worker: %s (once=%s, poll_interval=%ds)", 
               worker_name, args.once, args.poll_interval)
    
    # Setup signal handlers
    def handle_signal(sig, frame):
        logger.info("Received signal %s, shutting down", sig)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    if args.once:
        # Run one job and exit
        if run_once(worker_name, engine):
            logger.info("Processed one job and exiting")
            return 0
        else:
            logger.info("No jobs available, exiting")
            return 0
    else:
        # Run forever
        run_loop(worker_name, engine, poll_interval=args.poll_interval)
        return 0


if __name__ == "__main__":
    sys.exit(main())
