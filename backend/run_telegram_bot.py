"""Telegram bot entrypoint.

Loads local .env (if present), configures logging, validates required runtime
settings, then starts the long-poll Telegram bot runtime.
"""

from __future__ import annotations

import argparse
import logging
import sys

from config import Settings, get_settings, load_env, validate_required_settings
from infra.providers.telegram import TelegramBotClient
from jobs.telegram_poller import TelegramPoller
from services.telegram_bot import TelegramBotService
from utils import configure_logging


def _validate_telegram_settings() -> Settings:
    try:
        settings = get_settings()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    if not settings.telegram_enabled:
        logging.getLogger("telegram-bot").error(
            "Telegram bot is disabled (TELEGRAM_ENABLED=false)"
        )
        raise SystemExit(2)
    if not settings.telegram_bot_token:
        logging.getLogger("telegram-bot").error(
            "Missing required setting: TELEGRAM_BOT_TOKEN"
        )
        raise SystemExit(2)

    return settings


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantDog Telegram bot")
    parser.add_argument("--once", action="store_true", help="Process one poll cycle then exit")
    args = parser.parse_args()

    load_env()

    try:
        settings = _validate_telegram_settings()
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    if settings is None:
        return 2

    configure_logging(service_name="telegram-bot", log_dir=settings.log_dir)

    try:
        validate_required_settings(settings)
    except ValueError as exc:
        logging.getLogger("config").error(str(exc))
        return 2

    token = settings.telegram_bot_token
    if token is None:
        logging.getLogger("telegram-bot").error(
            "Missing required setting: TELEGRAM_BOT_TOKEN"
        )
        return 2

    client = TelegramBotClient(
        base_url=settings.telegram_base_url,
        token=token,
    )
    poller = TelegramPoller(
        settings=settings,
        client=client,
        bot_service=TelegramBotService(settings=settings),
    )

    try:
        if args.once:
            poller.run_once()
            return 0

        poller.run_loop()
        return 0
    except KeyboardInterrupt:
        logging.getLogger("telegram-bot").info("Telegram bot interrupted, shutting down")
        return 0
    except Exception:
        logging.getLogger("telegram-bot").exception("Telegram bot failed")
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
