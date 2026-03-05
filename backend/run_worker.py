"""Worker entrypoint.

Loads local .env (if present), configures logging, validates required runtime
settings, then runs the long-lived worker loop via quantdog.jobs.runner.
"""

import logging
import sys

from quantdog.config import get_settings, load_env, validate_required_settings
from quantdog.jobs.runner import main as run_runner
from quantdog.utils import configure_logging


def main() -> int:
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
        logging.getLogger("quantdog.config").error(str(e))
        return 2

    logging.getLogger("quantdog.worker").info(
        "starting (name=%s heartbeat_seconds=%s research_enabled=%s)",
        settings.worker_name,
        settings.worker_heartbeat_seconds,
        settings.research_enabled,
    )

    return run_runner()


if __name__ == "__main__":
    raise SystemExit(main())
