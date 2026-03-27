from __future__ import annotations

import logging
from typing import Any

import httpx


logger = logging.getLogger("infra.providers.telegram")


class TelegramError(RuntimeError):
    pass


class TelegramApiError(TelegramError):
    pass


class TelegramAuthError(TelegramError):
    pass


class TelegramForbiddenError(TelegramError):
    pass


class TelegramRetryableError(TelegramError):
    def __init__(self, message: str, *, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class TelegramBotClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = 35.0,
        http_client: httpx.Client | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = token.strip()
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=timeout_seconds)

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def delete_webhook(self, drop_pending_updates: bool) -> bool:
        payload = {"drop_pending_updates": bool(drop_pending_updates)}
        result = self._post_json("deleteWebhook", payload)
        return bool(result)

    def get_updates(
        self,
        *,
        offset: int,
        timeout_seconds: int,
        limit: int,
    ) -> list[dict[str, Any]]:
        payload = {
            "offset": int(offset),
            "timeout": int(timeout_seconds),
            "limit": max(1, min(int(limit), 100)),
            "allowed_updates": ["message"],
        }
        result = self._post_json("getUpdates", payload)
        if not isinstance(result, list):
            raise TelegramApiError("Telegram getUpdates returned invalid result payload")
        return [item for item in result if isinstance(item, dict)]

    def send_message(self, *, chat_id: int, text: str) -> dict[str, Any]:
        message_text = text.strip()
        if not message_text:
            raise ValueError("Telegram message text must not be empty")
        if len(message_text) > 4096:
            raise ValueError("Telegram message text exceeds 4096 characters")

        payload = {
            "chat_id": int(chat_id),
            "text": message_text,
        }
        result = self._post_json("sendMessage", payload)
        if not isinstance(result, dict):
            raise TelegramApiError("Telegram sendMessage returned invalid result payload")
        return result

    def _post_json(self, method_name: str, payload: dict[str, Any]) -> Any:
        url = f"{self._base_url}/bot{self._token}/{method_name}"
        try:
            response = self._http_client.post(url, json=payload)
        except httpx.HTTPError as exc:
            logger.warning("Telegram %s request failed: %s", method_name, exc)
            raise TelegramRetryableError(
                f"Telegram {method_name} request failed: network error"
            ) from exc

        data = self._decode_response_json(response, method_name)
        if response.status_code >= 500:
            raise TelegramRetryableError(
                f"Telegram {method_name} request failed: HTTP {response.status_code}"
            )

        if not isinstance(data, dict):
            raise TelegramApiError(f"Telegram {method_name} returned invalid response")

        if response.status_code == 401:
            raise TelegramAuthError(
                data.get("description") or f"Telegram {method_name} request unauthorized"
            )
        if response.status_code == 403:
            raise TelegramForbiddenError(
                data.get("description") or f"Telegram {method_name} request forbidden"
            )
        if response.status_code == 429:
            retry_after = self._extract_retry_after(data)
            raise TelegramRetryableError(
                data.get("description") or f"Telegram {method_name} rate limited",
                retry_after=retry_after,
            )
        if response.status_code >= 400:
            raise TelegramApiError(
                data.get("description") or f"Telegram {method_name} request failed"
            )

        if data.get("ok") is not True:
            retry_after = self._extract_retry_after(data)
            description = data.get("description") or f"Telegram {method_name} request failed"
            if retry_after is not None:
                raise TelegramRetryableError(description, retry_after=retry_after)
            raise TelegramApiError(description)

        return data.get("result")

    @staticmethod
    def _decode_response_json(response: httpx.Response, method_name: str) -> Any:
        try:
            return response.json()
        except ValueError as exc:
            raise TelegramApiError(
                f"Telegram {method_name} request failed: invalid JSON"
            ) from exc

    @staticmethod
    def _extract_retry_after(data: dict[str, Any]) -> int | None:
        parameters = data.get("parameters")
        if not isinstance(parameters, dict):
            return None
        retry_after = parameters.get("retry_after")
        if isinstance(retry_after, int):
            return retry_after
        return None
