from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Dict, Iterable, List

import numpy as np
import pandas as pd
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import (
    EnsembleResponseSchema,
    HistoryResponseSchema,
    PerformanceResponseSchema,
    RunResponseSchema,
)
from app.db.models import AgentSignal, Alert, MetricsSnapshot
from app.db.session import get_session
from app.services.agents.base import Agent
from app.services.agents.rth_playbook import RTHPlaybookAgent
from app.services.agents.technical import TechnicalAgent
from app.services.orchestrator import StrategyOrchestrator, run_all_agents
from app.services.polygon_client import PolygonClient
from app.services.stream import get_stream_broker

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/api/run/{ticker}", response_model=RunResponseSchema)
async def trigger_run(ticker: str, session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    ticker = ticker.upper()
    agents: Iterable[Agent] = [TechnicalAgent(), RTHPlaybookAgent()]
    agent_map = {agent.key: agent for agent in agents}

    async with PolygonClient() as polygon_client:
        orchestrator = StrategyOrchestrator(polygon_client)
        market = await orchestrator.build_market(ticker)
        overall, results, risk = await run_all_agents(
            market,
            agents,
            orchestrator.risk_manager,
            orchestrator.portfolio_manager,
            orchestrator.auditor,
        )

    await _persist_decisions(session, ticker, market, overall, results, risk, agent_map)

    return {"overall": overall, "results": results, "risk": risk}


@router.get("/api/ensemble/{ticker}", response_model=EnsembleResponseSchema)
async def get_ensemble(ticker: str, session: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    ticker = ticker.upper()

    stmt = select(Alert).where(Alert.symbol == ticker).order_by(Alert.ts.desc()).limit(1)
    result = await session.execute(stmt)
    alert = result.scalar_one_or_none()

    if alert is None:
        raise HTTPException(status_code=404, detail=f"No ensemble results for {ticker}")

    portfolio_snapshot = alert.portfolio_snapshot or {}

    return {
        "symbol": alert.symbol,
        "overall_decision": alert.overall_decision,
        "confidence": alert.confidence,
        "method": alert.method,
        "portfolio_snapshot": portfolio_snapshot,
        "risk_pass": alert.risk_pass,
        "rth_ticket": alert.rth_ticket,
    }


@router.get("/api/performance", response_model=PerformanceResponseSchema)
async def get_performance(
    agent_key: str | None = Query(default=None),
    window: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    stmt = select(MetricsSnapshot)
    if agent_key:
        stmt = stmt.where(MetricsSnapshot.agent_key == agent_key)
    if window:
        stmt = stmt.where(MetricsSnapshot.window == window)
    stmt = stmt.order_by(MetricsSnapshot.as_of.desc())

    result = await session.execute(stmt)
    snapshots = result.scalars().all()

    return {"metrics": snapshots}


@router.get("/api/history", response_model=HistoryResponseSchema)
async def get_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=5, le=100),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    filters = []
    if start:
        filters.append(Alert.ts >= start)
    if end:
        filters.append(Alert.ts <= end)

    total_stmt = select(func.count(Alert.id))
    for condition in filters:
        total_stmt = total_stmt.where(condition)
    total_result = await session.execute(total_stmt)
    total = total_result.scalar_one()

    stmt = (
        select(Alert)
        .where(*filters)
        .order_by(Alert.ts.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    alerts = result.scalars().all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": alerts,
    }


async def ticker_event_stream(ticker: str) -> AsyncIterator[Dict[str, Any]]:
    channel = ticker.upper()
    broker = get_stream_broker()
    heartbeat_seconds = 15

    async with broker.subscribe(channel) as queue:
        yield {"event": "heartbeat", "data": json.dumps({"ts": datetime.now(timezone.utc).isoformat()})}
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except asyncio.TimeoutError:
                heartbeat = json.dumps({"ts": datetime.now(timezone.utc).isoformat()})
                yield {"event": "heartbeat", "data": heartbeat}
                continue
            yield {"event": "update", "data": message}


@router.get("/api/stream/{ticker}")
async def stream_ticker_updates(ticker: str) -> EventSourceResponse:
    return EventSourceResponse(ticker_event_stream(ticker))


async def _persist_decisions(
    session: AsyncSession,
    ticker: str,
    market: Dict[str, Any],
    overall: Dict[str, Any],
    results: Dict[str, Any],
    risk: Dict[str, Any],
    agent_map: Dict[str, Agent],
) -> None:
    try:
        await _persist_agent_signals(session, ticker, market, results, agent_map)
        if risk.get("pass"):
            await _persist_alert(session, ticker, market, overall, results, risk)
        await session.commit()
        payload = {
            "ticker": ticker,
            "overall": _jsonable(overall),
            "agents": _jsonable(results),
            "risk": _jsonable(risk),
            "ts": _last_timestamp(market.get("bars_5m")).isoformat(),
        }
        await get_stream_broker().publish(ticker, payload)
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        logger.exception("api.run.persist_failed", ticker=ticker, error=str(exc))
        raise


async def _persist_agent_signals(
    session: AsyncSession,
    ticker: str,
    market: Dict[str, Any],
    results: Dict[str, Any],
    agent_map: Dict[str, Agent],
) -> None:
    bars: pd.DataFrame | None = market.get("bars_5m")
    event_ts = _last_timestamp(bars)

    for agent_key, output in results.items():
        agent = agent_map.get(agent_key)
        resolution = getattr(agent, "resolution", "5m") if agent else "5m"
        horizon_bars = _resolve_horizon_bars(output)
        horizon_bars = max(horizon_bars, 1)
        eval_ts = _calculate_eval_ts(event_ts, resolution, horizon_bars)

        payload = AgentSignal(
            symbol=ticker,
            agent_key=agent_key,
            resolution=resolution,
            decision=output["decision"],
            confidence=float(output["confidence"]),
            inputs_snapshot=_jsonable(output["inputs"]),
            eval_horizon_bars=horizon_bars,
            eval_ts=eval_ts,
            outcome_return=None,
            outcome_label=None,
            ts=event_ts,
        )
        session.add(payload)
    await session.flush()


async def _persist_alert(
    session: AsyncSession,
    ticker: str,
    market: Dict[str, Any],
    overall: Dict[str, Any],
    results: Dict[str, Any],
    risk: Dict[str, Any],
) -> None:
    bars: pd.DataFrame | None = market.get("bars_5m")
    event_ts = _last_timestamp(bars)

    raw_auditor_notes = overall.get("auditor_notes") or {}
    if overall.get("method") == "auditor_override":
        raw_auditor_notes = {
            **raw_auditor_notes,
            "risk_reasons": risk.get("reasons", []),
        }

    auditor_summary = _summarize_auditor_checks(raw_auditor_notes)
    contributors = overall.get("contributors") or {}
    side_scores = overall.get("side_scores") or {}

    snapshot = {
        "overall": _jsonable(
            {
                "decision": overall.get("decision"),
                "confidence": overall.get("confidence"),
                "method": overall.get("method"),
                "side_scores": side_scores,
                "contributors": contributors,
                "auditor_notes": raw_auditor_notes,
            }
        ),
        "contributors": _jsonable(contributors),
        "agents": _jsonable(results),
        "risk": _jsonable(risk),
        "market": {
            "previous_close": _transform_previous_close(market.get("previous_close")),
            "options_snapshot": _jsonable(market.get("options_snapshot")),
            "latest_bar": _last_bar_snapshot(bars),
        },
        "auditor_notes": {"checks": auditor_summary},
    }

    rth_ticket = _extract_rth_ticket(overall, results)

    alert = Alert(
        symbol=ticker,
        ts=event_ts,
        overall_decision=overall["decision"],
        confidence=float(overall["confidence"]),
        risk_pass=bool(risk.get("pass", True)),
        method=overall.get("method", "weighted"),
        portfolio_snapshot=snapshot,
        auditor_notes=_jsonable({"checks": auditor_summary}),
        rth_ticket=_jsonable(rth_ticket),
    )

    session.add(alert)
    await session.flush()


def _summarize_auditor_checks(notes: Dict[str, Any]) -> List[Dict[str, Any]]:
    failure_modes = set(notes.get("failure_modes", []))
    implied = notes.get("implied_volatility")
    realized = notes.get("realized_vol_5d")
    ratio = notes.get("implied_realized_diff_ratio")

    if isinstance(implied, (int, float)) and isinstance(realized, (int, float)):
        if isinstance(ratio, (int, float)):
            vol_detail = f"implied {implied:.2f} vs realized {realized:.2f} (ratio={ratio:.2f})"
        else:
            vol_detail = f"implied {implied:.2f} vs realized {realized:.2f}"
    else:
        vol_detail = str(notes.get("implied_move_check", "insufficient_data"))

    data_issue = next(
        (mode for mode in failure_modes if mode in {"missing_bars", "non_monotonic_prices", "nan_in_market_data"}),
        None,
    )
    agent_issue = "nan_in_agent_output" if "nan_in_agent_output" in failure_modes else None

    checks: List[Dict[str, Any]] = [
        {
            "name": "volatility_alignment",
            "status": "fail" if "implied_move_outlier" in failure_modes else "pass",
            "detail": vol_detail,
        },
        {
            "name": "market_data_integrity",
            "status": "fail" if data_issue else "pass",
            "detail": data_issue or "ok",
        },
        {
            "name": "agent_output_sanity",
            "status": "fail" if agent_issue else "pass",
            "detail": agent_issue or "ok",
        },
    ]

    return checks[:3]


def _last_timestamp(bars: pd.DataFrame | None) -> datetime:
    if isinstance(bars, pd.DataFrame) and not bars.empty:
        ts = bars.index[-1]
        if hasattr(ts, "to_pydatetime"):
            return ts.to_pydatetime()
        if isinstance(ts, datetime):
            return ts
    return datetime.now(timezone.utc)


def _last_bar_snapshot(bars: pd.DataFrame | None) -> Dict[str, Any] | None:
    if not isinstance(bars, pd.DataFrame) or bars.empty:
        return None

    last_ts = bars.index[-1]
    last_row = bars.iloc[-1].to_dict()
    snapshot = {key: _python_scalar(value) for key, value in last_row.items()}
    if hasattr(last_ts, "to_pydatetime"):
        snapshot["timestamp"] = last_ts.to_pydatetime().isoformat()
    elif isinstance(last_ts, datetime):
        snapshot["timestamp"] = last_ts.isoformat()
    else:
        snapshot["timestamp"] = str(last_ts)
    return snapshot


def _transform_previous_close(value: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    transformed = {key: _python_scalar(val) for key, val in value.items()}
    timestamp = transformed.get("timestamp")
    if isinstance(timestamp, datetime):
        transformed["timestamp"] = timestamp.isoformat()
    return transformed


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _python_scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _resolve_horizon_bars(output: Dict[str, Any]) -> int:
    if not isinstance(output, dict):
        return 12

    if "eval_horizon_bars" in output:
        try:
            return int(output["eval_horizon_bars"])
        except (TypeError, ValueError):
            pass

    inputs = output.get("inputs")
    if isinstance(inputs, dict) and "eval_horizon_bars" in inputs:
        try:
            return int(inputs["eval_horizon_bars"])
        except (TypeError, ValueError):
            pass

    return 12


def _calculate_eval_ts(event_ts: datetime, resolution: str, horizon_bars: int) -> datetime:
    horizon_bars = max(horizon_bars, 1)
    res = (resolution or "5m").lower()

    if res.endswith("m"):
        try:
            minutes = int(res.rstrip("m"))
        except ValueError:
            minutes = 5
        delta = timedelta(minutes=minutes * horizon_bars)
    elif res.endswith("h"):
        try:
            hours = int(res.rstrip("h"))
        except ValueError:
            hours = 1
        delta = timedelta(hours=hours * horizon_bars)
    elif res.endswith("d"):
        delta = timedelta(days=horizon_bars)
    else:
        delta = timedelta(minutes=5 * horizon_bars)

    return event_ts + delta


def _extract_rth_ticket(overall: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any] | None:
    if overall.get("decision") not in {"BUY", "SELL"}:
        return None

    for output in results.values():
        if not isinstance(output, dict):
            continue
        if output.get("decision") != overall["decision"]:
            continue
        inputs = output.get("inputs")
        if isinstance(inputs, dict) and "rth_ticket" in inputs:
            return inputs["rth_ticket"]
    return None
