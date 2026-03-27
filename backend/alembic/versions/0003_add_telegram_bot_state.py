"""add telegram bot state

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-25

"""

from __future__ import annotations

from alembic import op  # type: ignore[import-not-found]
import sqlalchemy as sa  # type: ignore[import-not-found]


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_bot_state",
        sa.Column("bot_name", sa.Text(), primary_key=True, nullable=False),
        sa.Column(
            "last_update_id",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("telegram_bot_state")
