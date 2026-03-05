# pyright: reportMissingImports=false, reportUnknownVariableType=false

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class DbCheckResult:
    ok: bool
    error_type: str | None = None
    detail: str | None = None


def check_db_connectivity(database_url: str | None, *, timeout_seconds: float = 1.0) -> DbCheckResult:
    """Best-effort DB connectivity check.

    - For Postgres URLs: tries psycopg (v3) first, then psycopg2.
    - For sqlite URLs: uses stdlib sqlite3.

    The check is intentionally lightweight: connect + `SELECT 1`.
    """

    if not database_url or database_url.strip() == "":
        return DbCheckResult(
            ok=False,
            error_type="missing_database_url",
            detail="DATABASE_URL is not set",
        )

    url = database_url.strip()
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    if scheme == "sqlite":
        return _check_sqlite(url, timeout_seconds=timeout_seconds)

    if scheme in {"postgres", "postgresql"}:
        return _check_postgres(url, timeout_seconds=timeout_seconds)

    return DbCheckResult(
        ok=False,
        error_type="unsupported_database_scheme",
        detail=f"Unsupported DATABASE_URL scheme: {scheme!r}",
    )


def _check_sqlite(database_url: str, *, timeout_seconds: float) -> DbCheckResult:
    # Accepted forms:
    # - sqlite:///:memory:
    # - sqlite:////absolute/path.db
    # - sqlite:///relative/path.db
    prefix = "sqlite:///"
    path = database_url
    if database_url.startswith(prefix):
        path = database_url[len(prefix) :]
    elif database_url.startswith("sqlite://"):
        # sqlite://<weird> - treat as invalid for now.
        return DbCheckResult(
            ok=False,
            error_type="invalid_sqlite_url",
            detail=f"Invalid sqlite DATABASE_URL: {database_url!r}",
        )

    try:
        conn = sqlite3.connect(path, timeout=timeout_seconds)
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        finally:
            conn.close()
        return DbCheckResult(ok=True)
    except Exception as e:
        return DbCheckResult(ok=False, error_type="db_unavailable", detail=str(e))


def _check_postgres(database_url: str, *, timeout_seconds: float) -> DbCheckResult:
    # Avoid hard dependency at import time; Docker image installs the driver.
    timeout_int = max(1, int(timeout_seconds))

    try:
        import psycopg  # type: ignore[import-not-found]

        try:
            conn = psycopg.connect(database_url, connect_timeout=timeout_int)
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            finally:
                conn.close()
            return DbCheckResult(ok=True)
        except Exception as e:
            return DbCheckResult(ok=False, error_type="db_unavailable", detail=str(e))
    except Exception:
        pass

    try:
        import psycopg2  # type: ignore[import-not-found]

        try:
            conn = psycopg2.connect(database_url, connect_timeout=timeout_int)
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchone()
            finally:
                conn.close()
            return DbCheckResult(ok=True)
        except Exception as e:
            return DbCheckResult(ok=False, error_type="db_unavailable", detail=str(e))
    except Exception as e:
        return DbCheckResult(
            ok=False,
            error_type="db_driver_missing",
            detail=f"Postgres driver not installed (psycopg/psycopg2). {e}",
        )
