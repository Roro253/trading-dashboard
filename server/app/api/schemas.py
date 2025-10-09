from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.schemas import Decision, MetricsWindow


class AgentResultSchema(BaseModel):
    decision: Decision
    confidence: float
    inputs: Dict[str, Any]
    notes: str


class RiskSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    passed: bool = Field(alias="pass")
    reasons: List[str]


class OverallDecisionSchema(BaseModel):
    decision: Decision
    confidence: float
    method: str
    side_scores: Dict[str, float] | None = None
    auditor_notes: Dict[str, Any] | None = None
    reasons: List[str] | None = None
    risk_reasons: List[str] | None = None


class RunResponseSchema(BaseModel):
    overall: OverallDecisionSchema
    results: Dict[str, AgentResultSchema]
    risk: RiskSchema


class EnsembleResponseSchema(BaseModel):
    symbol: str
    overall_decision: Decision
    confidence: float
    method: str
    portfolio_snapshot: Dict[str, Any]
    risk_pass: bool
    rth_ticket: Dict[str, Any] | None = None


class MetricsSnapshotSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_key: str
    window: MetricsWindow
    hit_rate: float
    avg_R: float
    sharpe: float
    profit_factor: float
    drawdown: float
    samples: int
    calibration_bins: Dict[str, Any]
    as_of: datetime


class PerformanceResponseSchema(BaseModel):
    metrics: List[MetricsSnapshotSchema]


class AlertRecordSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    symbol: str
    ts: datetime
    overall_decision: Decision
    confidence: float
    method: str
    risk_pass: bool
    portfolio_snapshot: Dict[str, Any]
    auditor_notes: Dict[str, Any] | None = None
    rth_ticket: Dict[str, Any] | None = None


class HistoryResponseSchema(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[AlertRecordSchema]
