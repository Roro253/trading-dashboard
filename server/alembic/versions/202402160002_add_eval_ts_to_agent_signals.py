"""add eval_ts column to agent_signals

Revision ID: 202402160002
Revises: 202402160001
Create Date: 2024-02-16 02:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202402160002"
down_revision = "202402160001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_signals",
        sa.Column("eval_ts", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE agent_signals SET eval_ts = ts")
    op.alter_column("agent_signals", "eval_ts", nullable=False)
    op.create_index("ix_agent_signals_eval_ts", "agent_signals", ["eval_ts"])


def downgrade() -> None:
    op.drop_index("ix_agent_signals_eval_ts", table_name="agent_signals")
    op.drop_column("agent_signals", "eval_ts")
