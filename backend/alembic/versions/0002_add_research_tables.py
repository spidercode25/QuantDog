"""add research tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-05

"""

from __future__ import annotations

from alembic import op  # type: ignore[import-not-found]
import sqlalchemy as sa  # type: ignore[import-not-found]
from sqlalchemy.dialects import postgresql  # type: ignore[import-not-found]


# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Research runs table
    op.create_table(
        "research_runs",
        sa.Column("run_id", sa.Text(), primary_key=True, nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("final_decision", sa.Text(), nullable=True),
        sa.Column("final_confidence", sa.Integer(), nullable=True),
        sa.Column(
            "baseline_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "config_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    
    # Research agent outputs table
    op.create_table(
        "research_agent_outputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("phase", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=True),
        sa.Column(
            "output_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "validation_errors_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Unique constraint to enforce idempotency
        sa.UniqueConstraint(
            "run_id",
            "phase",
            "agent_name",
            name="uq_research_agent_outputs_run_phase_agent",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_runs.run_id"],
            name="fk_research_agent_outputs_run_id",
        ),
    )
    
    # Index for querying runs by status
    op.create_index(
        "ix_research_runs_status",
        "research_runs",
        ["status"],
    )
    
    # Index for querying outputs by run_id
    op.create_index(
        "ix_research_agent_outputs_run_id",
        "research_agent_outputs",
        ["run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_agent_outputs_run_id", table_name="research_agent_outputs")
    op.drop_index("ix_research_runs_status", table_name="research_runs")
    op.drop_table("research_agent_outputs")
    op.drop_table("research_runs")
