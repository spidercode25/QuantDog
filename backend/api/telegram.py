# pyright: reportMissingImports=false, reportAttributeAccessIssue=false, reportArgumentType=false

from __future__ import annotations

from hmac import compare_digest

from flask import Blueprint, request

from api.envelope import error, success
from config import get_settings
from infra.sqlalchemy import get_engine
from jobs import queue


telegram_bp = Blueprint("telegram", __name__, url_prefix="/api/v1/telegram")

_INT64_MIN = -(2**63)
_INT64_MAX = (2**63) - 1


def _normalize_chat_id(raw_chat_id: object) -> int:
    if raw_chat_id is None:
        raise ValueError("chat_id is required")

    value = str(raw_chat_id).strip()
    if not value:
        raise ValueError("chat_id is required")

    try:
        chat_id = int(value)
    except ValueError as exc:
        raise ValueError("chat_id must be an integer") from exc

    if chat_id < _INT64_MIN or chat_id > _INT64_MAX:
        raise ValueError("chat_id must fit in a signed 64-bit integer")

    return chat_id


def _has_valid_api_token(expected_token: str, provided_token: str | None) -> bool:
    if provided_token is None:
        return False
    return compare_digest(expected_token, provided_token)


def _request_api_token() -> str | None:
    bearer = request.headers.get("Authorization")
    if bearer:
        scheme, _, token = bearer.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()

    header_token = request.headers.get("X-Telegram-Api-Token")
    if header_token and header_token.strip():
        return header_token.strip()

    return None


@telegram_bp.post("/messages")  # type: ignore[arg-type]
def enqueue_telegram_message():
    settings = get_settings()

    if not request.is_json:
        return error(
            "Invalid request",
            error_type="invalid_request",
            detail="Request body must be JSON",
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return error(
            "Invalid request",
            error_type="invalid_request",
            detail="Request body must be JSON",
        )

    try:
        chat_id = _normalize_chat_id(data.get("chat_id"))
    except ValueError as exc:
        return error("Invalid chat_id", error_type="invalid_field", detail=str(exc))

    raw_text = data.get("text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return error("Text is required", error_type="missing_field", detail="text field is required")
    text = raw_text.strip()
    if len(text) > 4096:
        return error(
            "Text too long",
            error_type="invalid_field",
            detail="text must be 4096 characters or fewer",
        )

    if settings.database_url is None:
        return error("Database not configured", error_type="configuration_error", detail="DATABASE_URL not set")
    if not settings.telegram_enabled:
        return error(
            "Telegram delivery is disabled",
            error_type="feature_disabled",
            detail="Set TELEGRAM_ENABLED=true to enable Telegram delivery",
        )
    if not settings.telegram_bot_token:
        return error(
            "Telegram not configured",
            error_type="configuration_error",
            detail="TELEGRAM_BOT_TOKEN not set",
        )
    if not settings.telegram_api_token:
        return error(
            "Telegram API not configured",
            error_type="configuration_error",
            detail="TELEGRAM_API_TOKEN not set",
        )
    if not _has_valid_api_token(settings.telegram_api_token, _request_api_token()):
        return error(
            "Unauthorized",
            error_type="unauthorized",
            detail="Valid Telegram API token required",
            status_code=401,
        )

    job_payload = {
        "chat_id": chat_id,
        "text": text,
    }

    idempotency_key = request.headers.get("Idempotency-Key")
    dedupe_key = None
    if idempotency_key and idempotency_key.strip():
        dedupe_key = f"telegram:send:{chat_id}:{idempotency_key.strip()}"

    try:
        engine = get_engine(settings.database_url)
        job_id = queue.enqueue_job(
            engine,
            kind="telegram_send_message",
            payload=job_payload,
            dedupe_key=dedupe_key,
        )
    except Exception as exc:
        return error(
            "Failed to enqueue telegram message",
            error_type="job_enqueue_error",
            detail=str(exc),
        )

    return success(
        {
            "job_id": job_id,
            "chat_id": chat_id,
            "dedupe_key": dedupe_key,
        },
        status_code=202,
    )
