"""create core tables

Revision ID: 202402160001
Revises: 
Create Date: 2024-02-16 00:01:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202402160001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("overall_decision", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("risk_pass", sa.Boolean(), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("portfolio_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("auditor_notes", postgresql.JSONB(), nullable=True),
        sa.Column("rth_ticket", postgresql.JSONB(), nullable=True),
    )
    op.create_index(
        "ix_alerts_symbol_ts_desc",
        "alerts",
        ["symbol", sa.text("ts DESC")],
        unique=False,
    )
    op.create_index(
        "ix_alerts_portfolio_snapshot_gin",
        "alerts",
        ["portfolio_snapshot"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_alerts_auditor_notes_gin",
        "alerts",
        ["auditor_notes"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_alerts_rth_ticket_gin",
        "alerts",
        ["rth_ticket"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "agent_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("agent_key", sa.String(length=64), nullable=False),
        sa.Column("resolution", sa.String(length=8), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("inputs_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("eval_horizon_bars", sa.Integer(), nullable=False),
        sa.Column("outcome_return", sa.Float(), nullable=True),
        sa.Column("outcome_label", sa.String(length=32), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_agent_signals_symbol",
        "agent_signals",
        ["symbol"],
        unique=False,
    )
    op.create_index(
        "ix_agent_signals_agent_key",
        "agent_signals",
        ["agent_key"],
        unique=False,
    )
    op.create_index(
        "ix_agent_signals_symbol_agent_ts_desc",
        "agent_signals",
        ["symbol", "agent_key", sa.text("ts DESC")],
        unique=False,
    )
    op.create_index(
        "ix_agent_signals_inputs_snapshot_gin",
        "agent_signals",
        ["inputs_snapshot"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "metrics_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("agent_key", sa.String(length=64), nullable=False),
        sa.Column("window", sa.String(length=8), nullable=False),
        sa.Column("hit_rate", sa.Float(), nullable=False),
        sa.Column("avg_R", sa.Float(), nullable=False),
        sa.Column("sharpe", sa.Float(), nullable=False),
        sa.Column("profit_factor", sa.Float(), nullable=False),
        sa.Column("drawdown", sa.Float(), nullable=False),
        sa.Column("samples", sa.Integer(), nullable=False),
        sa.Column("calibration_bins", postgresql.JSONB(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_metrics_snapshots_agent_key",
        "metrics_snapshots",
        ["agent_key"],
        unique=False,
    )
    op.create_index(
        "ix_metrics_snapshots_calibration_bins_gin",
        "metrics_snapshots",
        ["calibration_bins"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_metrics_snapshots_as_of",
        "metrics_snapshots",
        ["as_of"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_metrics_snapshots_as_of", table_name="metrics_snapshots")
    op.drop_index("ix_metrics_snapshots_calibration_bins_gin", table_name="metrics_snapshots")
    op.drop_index("ix_metrics_snapshots_agent_key", table_name="metrics_snapshots")
    op.drop_table("metrics_snapshots")

    op.drop_index("ix_agent_signals_inputs_snapshot_gin", table_name="agent_signals")
    op.drop_index("ix_agent_signals_symbol_agent_ts_desc", table_name="agent_signals")
    op.drop_index("ix_agent_signals_agent_key", table_name="agent_signals")
    op.drop_index("ix_agent_signals_symbol", table_name="agent_signals")
    op.drop_table("agent_signals")

    op.drop_index("ix_alerts_rth_ticket_gin", table_name="alerts")
    op.drop_index("ix_alerts_auditor_notes_gin", table_name="alerts")
    op.drop_index("ix_alerts_portfolio_snapshot_gin", table_name="alerts")
    op.drop_index("ix_alerts_symbol_ts_desc", table_name="alerts")
    op.drop_table("alerts")
