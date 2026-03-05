import logging
import os
import signal
import time
from types import FrameType


_stop = False


def _handle_stop(_signum: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True


def run_worker() -> int:
    """Minimal worker loop.

    Scaffold behavior: stay alive and emit heartbeat logs.
    """

    _ = signal.signal(signal.SIGINT, _handle_stop)
    _ = signal.signal(signal.SIGTERM, _handle_stop)

    name = os.getenv("WORKER_NAME", "quantdog-worker")
    interval_s = int(os.getenv("WORKER_HEARTBEAT_SECONDS", "10"))

    logger = logging.getLogger("quantdog.worker")

    logger.info(
        "[%s] loop starting (research_enabled=%s)",
        name,
        os.getenv("RESEARCH_ENABLED", "false"),
    )

    i = 0
    while not _stop:
        i += 1
        logger.info("[%s] heartbeat=%s", name, i)
        time.sleep(interval_s)

    logger.info("[%s] loop stopping", name)
    return 0
