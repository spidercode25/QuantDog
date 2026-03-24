# pyright: reportMissingImports=false, reportUnknownVariableType=false

from __future__ import annotations


def normalize_database_url_for_sqlalchemy(database_url: str) -> str:
    """Normalize DATABASE_URL so SQLAlchemy uses psycopg (v3) for Postgres.

    Docker compose wires DATABASE_URL as e.g. `postgresql://...`.
    SQLAlchemy defaults that scheme to psycopg2 unless a driver is specified.
    The scaffold installs psycopg (v3), so we rewrite to `postgresql+psycopg://...`.
    """

    url = (database_url or "").strip()
    if url == "":
        return url

    if url.startswith("postgresql+psycopg://"):
        return url

    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]

    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]

    return url


def get_engine(database_url: str, *, echo: bool = False):
    """Create a SQLAlchemy engine.

    - Safe to import: no connection is created at import time.
    - The engine itself connects lazily on first use.
    """

    url = normalize_database_url_for_sqlalchemy(database_url)
    if url.strip() == "":
        raise ValueError("DATABASE_URL is required")

    # Avoid hard dependency at import time; the Docker image installs SQLAlchemy.
    import sqlalchemy  # type: ignore[import-not-found]

    return sqlalchemy.create_engine(url, echo=echo, pool_pre_ping=True)
