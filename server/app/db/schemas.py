from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal["BUY", "SELL", "HOLD", "NO_TRADE"]
Resolution = Literal["5m", "15m", "1d"]
MetricsWindow = Literal["7d", "30d"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AlertBase(BaseModel):
    symbol: str
    ts: datetime = Field(default_factory=utc_now)
    overall_decision: Decision
    confidence: float
    risk_pass: bool
    method: str
    portfolio_snapshot: dict[str, Any]
    auditor_notes: dict[str, Any] | None = None
    rth_ticket: dict[str, Any] | None = None


class AlertCreate(AlertBase):
    pass


class AlertRead(AlertBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class AgentSignalBase(BaseModel):
    symbol: str
    agent_key: str
    resolution: Resolution
    decision: Decision
    confidence: float
    inputs_snapshot: dict[str, Any]
    eval_horizon_bars: int
    eval_ts: datetime
    outcome_return: float | None = None
    outcome_label: str | None = None
    ts: datetime = Field(default_factory=utc_now)


class AgentSignalCreate(AgentSignalBase):
    pass


class AgentSignalRead(AgentSignalBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class MetricsSnapshotBase(BaseModel):
    agent_key: str
    window: MetricsWindow
    hit_rate: float
    avg_R: float
    sharpe: float
    profit_factor: float
    drawdown: float
    samples: int
    calibration_bins: dict[str, Any]
    as_of: datetime = Field(default_factory=utc_now)


class MetricsSnapshotCreate(MetricsSnapshotBase):
    pass


class MetricsSnapshotRead(MetricsSnapshotBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
