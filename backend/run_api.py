"""API entrypoint.

Loads local .env (if present), configures logging, validates required runtime
settings, then starts the Flask dev server.
"""

# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false

import logging
import sys

from api import create_app  # pyright: ignore[reportImplicitRelativeImport]
from config import get_settings, load_env, validate_required_settings  # pyright: ignore[reportImplicitRelativeImport]
from utils import configure_logging  # pyright: ignore[reportImplicitRelativeImport]


def main() -> int:
    load_env()

    try:
        settings = get_settings()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    configure_logging(service_name="api", log_dir=settings.log_dir)

    try:
        validate_required_settings(settings)
    except ValueError as e:
        logging.getLogger("config").error(str(e))
        return 2

    app = create_app()

    host = settings.api_host
    port = settings.api_port

    logging.getLogger("api").info(
        "starting (host=%s port=%s research_enabled=%s enable_ai_analysis=%s)",
        host,
        port,
        settings.research_enabled,
        settings.enable_ai_analysis,
    )

    # Flask dev server is sufficient for scaffold verification.
    app.run(host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
