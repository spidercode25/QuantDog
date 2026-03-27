from __future__ import annotations

import logging
import time
from typing import Any

from config import Settings
from infra.providers.telegram import (
    TelegramApiError,
    TelegramBotClient,
    TelegramForbiddenError,
    TelegramRetryableError,
)
from services.telegram_bot import TelegramBotService
from telegram.repository import (
    ensure_bot_state,
    get_last_update_id,
    has_bot_state,
    upsert_last_update_id,
)


logger = logging.getLogger("jobs.telegram_poller")


class TelegramPoller:
    def __init__(
        self,
        *,
        settings: Settings,
        client: TelegramBotClient,
        bot_service: TelegramBotService,
        bot_name: str = "quantdog-telegram-bot",
        sleep_func=time.sleep,
    ):
        if settings.database_url is None:
            raise ValueError("DATABASE_URL not set")

        self._settings = settings
        self._database_url = settings.database_url
        self._client = client
        self._bot_service = bot_service
        self._bot_name = bot_name
        self._sleep = sleep_func
        self._started = False

    def startup(self) -> None:
        if self._started:
            return

        state_exists = has_bot_state(self._database_url, self._bot_name)
        self._client.delete_webhook(drop_pending_updates=not state_exists)
        if not state_exists:
            ensure_bot_state(self._database_url, self._bot_name)

        self._started = True

    def run_once(self) -> dict[str, int]:
        self.startup()
        last_update_id = get_last_update_id(self._database_url, self._bot_name)
        updates = self._client.get_updates(
            offset=last_update_id + 1,
            timeout_seconds=self._settings.telegram_poll_timeout_seconds,
            limit=self._settings.telegram_poll_limit,
        )

        processed = 0
        for update in updates:
            self.process_update(update)
            processed += 1

        current_offset = get_last_update_id(self._database_url, self._bot_name)
        return {
            "updates_polled": len(updates),
            "updates_processed": processed,
            "last_update_id": current_offset,
        }

    def run_loop(self) -> None:
        self.startup()
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                raise
            except TelegramRetryableError as exc:
                delay_seconds = exc.retry_after if exc.retry_after is not None else 1
                logger.warning("Telegram poller retryable error delay=%ss error=%s", delay_seconds, exc)
                self._sleep(delay_seconds)
            except Exception:
                logger.exception("Telegram poller fatal loop error")
                self._sleep(1)

    def process_update(self, update: dict[str, Any]) -> None:
        update_id = self._extract_update_id(update)
        if update_id is None:
            return

        reply_text = self._bot_service.handle_update(update)
        if reply_text is None:
            upsert_last_update_id(self._database_url, self._bot_name, update_id)
            return

        chat_id = self._extract_chat_id(update)
        if chat_id is None:
            upsert_last_update_id(self._database_url, self._bot_name, update_id)
            return

        try:
            self._client.send_message(chat_id=chat_id, text=reply_text)
        except TelegramRetryableError:
            raise
        except (TelegramForbiddenError, TelegramApiError) as exc:
            logger.warning(
                "Telegram update permanently rejected update_id=%s chat_id=%s error=%s",
                update_id,
                chat_id,
                exc,
            )

        upsert_last_update_id(self._database_url, self._bot_name, update_id)

    @staticmethod
    def _extract_update_id(update: dict[str, Any]) -> int | None:
        raw_update_id = update.get("update_id")
        if not isinstance(raw_update_id, int):
            return None
        return raw_update_id

    @staticmethod
    def _extract_chat_id(update: dict[str, Any]) -> int | None:
        message = update.get("message")
        if not isinstance(message, dict):
            return None
        chat = message.get("chat")
        if not isinstance(chat, dict):
            return None

        raw_chat_id = chat.get("id")
        if not isinstance(raw_chat_id, int):
            return None
        return raw_chat_id
