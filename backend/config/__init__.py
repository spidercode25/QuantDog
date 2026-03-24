"""Runtime configuration.

Keep this module import-safe: it should not connect to external systems at
import time. Entry points (run_api.py / run_worker.py) are responsible for
loading dotenv and validating required settings.
"""

from .settings import Settings, get_settings, load_env, validate_required_settings

__all__ = [
    "Settings",
    "get_settings",
    "load_env",
    "validate_required_settings",
]
