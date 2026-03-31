"""create core tables

Revision ID: 0001
Revises: 
Create Date: 2026-03-05

"""

from __future__ import annotations

from alembic import op  # type: ignore[import-not-found]
import sqlalchemy as sa  # type: ignore[import-not-found]
from sqlalchemy.dialects import postgresql  # type: ignore[import-not-found]


# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def _timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _bool_default(value: bool) -> sa.TextClause:
    if _dialect_name() == "sqlite":
        return sa.text("1" if value else "0")
    return sa.text("true" if value else "false")


def _jobs_id_type():
    if _dialect_name() == "sqlite":
        return sa.Text()
    return postgresql.UUID(as_uuid=True)


def _json_type():
    if _dialect_name() == "sqlite":
        return sa.Text()
    return postgresql.JSONB()


def _json_default(value: str) -> sa.TextClause:
    if _dialect_name() == "sqlite":
        return sa.text(f"'{value}'")
    return sa.text(f"'{value}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("symbol", sa.Text(), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("currency", sa.Text(), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=_bool_default(True),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_timestamp_default(),
        ),
    )

    op.create_table(
        "bars_1d",
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("bar_date", sa.Date(), nullable=False),
        sa.Column("ts_utc", sa.BigInteger(), nullable=False),
        sa.Column("open", sa.Numeric(18, 6), nullable=False),
        sa.Column("high", sa.Numeric(18, 6), nullable=False),
        sa.Column("low", sa.Numeric(18, 6), nullable=False),
        sa.Column("close", sa.Numeric(18, 6), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column(
            "adjusted",
            sa.Boolean(),
            nullable=False,
            server_default=_bool_default(False),
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["symbol"],
            ["instruments.symbol"],
            name="fk_bars_1d_symbol_instruments",
        ),
        sa.UniqueConstraint(
            "symbol",
            "bar_date",
            "adjusted",
            name="uq_bars_1d_symbol_bar_date_adjusted",
        ),
    )

    op.create_table(
        "jobs",
        sa.Column("id", _jobs_id_type(), primary_key=True, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            _json_type(),
            nullable=False,
            server_default=_json_default("{}"),
        ),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("locked_by", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_timestamp_default(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_timestamp_default(),
        ),
    )

    if _dialect_name() == "postgresql":
        op.create_index(
            "uq_jobs_dedupe_key_queued_running",
            "jobs",
            ["dedupe_key"],
            unique=True,
            postgresql_where=sa.text("state IN ('queued','running')"),
        )


def downgrade() -> None:
    op.drop_index("uq_jobs_dedupe_key_queued_running", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("bars_1d")
    op.drop_table("instruments")
