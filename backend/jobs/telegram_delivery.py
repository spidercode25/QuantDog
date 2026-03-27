from __future__ import annotations

import logging
import time
from typing import Any

from config import get_settings
from infra.providers.telegram import (
    TelegramApiError,
    TelegramBotClient,
    TelegramForbiddenError,
    TelegramRetryableError,
)


logger = logging.getLogger("jobs.telegram_delivery")

_MAX_SEND_ATTEMPTS = 3


def handle_telegram_send_message(job_payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_enabled:
        raise TelegramApiError("Telegram delivery is disabled (TELEGRAM_ENABLED=false)")
    if not settings.telegram_bot_token:
        raise TelegramApiError("Telegram bot token is not configured")

    chat_id = int(job_payload["chat_id"])
    text = str(job_payload["text"])

    client = TelegramBotClient(
        base_url=settings.telegram_base_url,
        token=settings.telegram_bot_token,
    )
    try:
        for attempt in range(1, _MAX_SEND_ATTEMPTS + 1):
            try:
                result = client.send_message(chat_id=chat_id, text=text)
                return {
                    "status": "sent",
                    "chat_id": chat_id,
                    "message_id": result.get("message_id") if isinstance(result, dict) else None,
                }
            except TelegramForbiddenError as exc:
                logger.warning("Telegram message skipped for chat_id=%s: %s", chat_id, exc)
                return {"status": "skipped", "chat_id": chat_id, "reason": str(exc)}
            except TelegramRetryableError as exc:
                if attempt >= _MAX_SEND_ATTEMPTS:
                    raise
                delay_seconds = exc.retry_after if exc.retry_after is not None else attempt
                logger.warning(
                    "Retrying telegram delivery chat_id=%s attempt=%s delay=%ss error=%s",
                    chat_id,
                    attempt,
                    delay_seconds,
                    exc,
                )
                time.sleep(delay_seconds)
    finally:
        client.close()

    raise TelegramApiError("Telegram delivery exhausted retries without a final state")
