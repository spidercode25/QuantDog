"""add candidate pool tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-30

"""

from __future__ import annotations

from alembic import op  # type: ignore[import-not-found]
import sqlalchemy as sa  # type: ignore[import-not-found]


# revision identifiers, used by Alembic.
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _created_at_default() -> sa.TextClause:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        return sa.text("CURRENT_TIMESTAMP")
    return sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    member_id_type = sa.Integer() if dialect == "sqlite" else sa.BigInteger()

    op.create_table(
        "candidate_snapshots",
        sa.Column("snapshot_key", sa.Text(), primary_key=True, nullable=False),
        sa.Column("snapshot_time_et", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_asof_et", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_created_at_default(),
        ),
    )

    op.create_table(
        "candidate_members",
        sa.Column("id", member_id_type, primary_key=True, autoincrement=True),
        sa.Column("snapshot_key", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("rvol", sa.Float(), nullable=False),
        sa.Column("pct_change", sa.Float(), nullable=False),
        sa.Column("dollar_volume", sa.Float(), nullable=False),
        sa.Column("last_price", sa.Float(), nullable=False),
        sa.Column("inclusion_reason", sa.Text(), nullable=True),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=_created_at_default(),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_key"],
            ["candidate_snapshots.snapshot_key"],
            name="fk_candidate_members_snapshot_key_candidate_snapshots",
            ondelete="CASCADE",
        ),
    )

    op.create_index(
        "ix_candidate_snapshots_snapshot_time_et",
        "candidate_snapshots",
        ["snapshot_time_et"],
        unique=False,
    )
    op.create_index(
        "ix_candidate_members_snapshot_key_rank",
        "candidate_members",
        ["snapshot_key", "rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_candidate_members_snapshot_key_rank", table_name="candidate_members")
    op.drop_index("ix_candidate_snapshots_snapshot_time_et", table_name="candidate_snapshots")
    op.drop_table("candidate_members")
    op.drop_table("candidate_snapshots")
