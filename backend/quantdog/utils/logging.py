# pyright: reportUnknownVariableType=false

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(*, service_name: str, log_dir: str, level: str = "INFO") -> None:
    """Configure process-wide logging.

    Requirements:
    - Log to stdout (container-friendly).
    - Also log to a rotating file under /app/logs (mounted volume in compose).
    """

    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(fmt=fmt)

    handlers: list[logging.Handler] = []

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    handlers.append(stream_handler)

    file_handler: logging.Handler | None = None
    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        logfile = os.path.join(log_dir, f"{service_name}.log")
        rf = RotatingFileHandler(logfile, maxBytes=10 * 1024 * 1024, backupCount=5)
        rf.setFormatter(formatter)
        file_handler = rf
    except Exception:
        file_handler = None

    if file_handler is not None:
        handlers.append(file_handler)

    logging.basicConfig(level=log_level, handlers=handlers, force=True)
