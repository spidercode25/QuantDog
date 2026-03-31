from __future__ import annotations

import argparse
import logging
import time as time_module
from datetime import date

from config import get_settings, load_env, validate_required_settings
from jobs.candidate_pool_scheduler import enqueue_candidate_pool_close_run
from utils import configure_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantDog candidate pool scheduler")
    parser.add_argument("--once", action="store_true", help="Enqueue at most one close-run job and exit")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force enqueue for testing even before market close or on non-trading days",
    )
    parser.add_argument(
        "--trading-date-et",
        type=str,
        help="Override the target ET trading date (YYYY-MM-DD) for testing latest completed close data",
    )
    parser.add_argument("--poll-interval", type=int, default=60, help="Seconds between schedule checks")
    args = parser.parse_args()

    trading_date_et = date.fromisoformat(args.trading_date_et) if args.trading_date_et else None

    load_env()
    settings = get_settings()
    validate_required_settings(settings)
    configure_logging(service_name="candidate-pool-scheduler", log_dir=settings.log_dir)

    if args.once:
        enqueue_candidate_pool_close_run(force=args.force, trading_date_et=trading_date_et)
        return 0

    logger = logging.getLogger("candidate-pool-scheduler")
    while True:
        enqueue_candidate_pool_close_run(force=args.force, trading_date_et=trading_date_et)
        logger.info("candidate pool scheduler heartbeat")
        time_module.sleep(max(1, args.poll_interval))


if __name__ == "__main__":
    raise SystemExit(main())
