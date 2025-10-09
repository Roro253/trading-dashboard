from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

Base = declarative_base()

Decision = ("BUY", "SELL", "HOLD", "NO_TRADE")
Resolution = ("5m", "15m", "1d")
MetricsWindow = ("7d", "30d")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_symbol_ts_desc", "symbol", text("ts DESC")),
        Index("ix_alerts_portfolio_snapshot_gin", "portfolio_snapshot", postgresql_using="gin"),
        Index("ix_alerts_auditor_notes_gin", "auditor_notes", postgresql_using="gin"),
        Index("ix_alerts_rth_ticket_gin", "rth_ticket", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    overall_decision: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    risk_pass: Mapped[bool] = mapped_column(Boolean)
    method: Mapped[str] = mapped_column(String(32))
    portfolio_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    auditor_notes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rth_ticket: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class AgentSignal(Base):
    __tablename__ = "agent_signals"
    __table_args__ = (
        Index("ix_agent_signals_symbol_agent_ts_desc", "symbol", "agent_key", text("ts DESC")),
        Index("ix_agent_signals_inputs_snapshot_gin", "inputs_snapshot", postgresql_using="gin"),
        Index("ix_agent_signals_eval_ts", "eval_ts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    agent_key: Mapped[str] = mapped_column(String(64), index=True)
    resolution: Mapped[str] = mapped_column(String(8))
    decision: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    eval_horizon_bars: Mapped[int] = mapped_column(Integer)
    eval_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    outcome_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"
    __table_args__ = (
        Index("ix_metrics_snapshots_agent_key", "agent_key"),
        Index("ix_metrics_snapshots_calibration_bins_gin", "calibration_bins", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_key: Mapped[str] = mapped_column(String(64), index=True)
    window: Mapped[str] = mapped_column(String(8))
    hit_rate: Mapped[float] = mapped_column(Float)
    avg_R: Mapped[float] = mapped_column(Float)
    sharpe: Mapped[float] = mapped_column(Float)
    profit_factor: Mapped[float] = mapped_column(Float)
    drawdown: Mapped[float] = mapped_column(Float)
    samples: Mapped[int] = mapped_column(Integer)
    calibration_bins: Mapped[dict[str, Any]] = mapped_column(JSONB)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
