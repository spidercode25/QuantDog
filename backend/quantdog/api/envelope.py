# pyright: reportMissingImports=false, reportUnknownVariableType=false, reportReturnType=false

from __future__ import annotations

from typing import Any

from flask import jsonify
from flask.typing import ResponseReturnValue


def success(data: Any, *, msg: str = "success", status_code: int = 200) -> ResponseReturnValue:
    """Return the standard success envelope."""

    return jsonify({"code": 1, "msg": msg, "data": data}), status_code


def error(
    msg: str,
    *,
    error_type: str,
    detail: str,
    status_code: int = 400,
) -> ResponseReturnValue:
    """Return the standard error envelope."""

    return (
        jsonify(
            {
                "code": 0,
                "msg": msg,
                "error": {"type": error_type, "detail": detail},
            }
        ),
        status_code,
    )
