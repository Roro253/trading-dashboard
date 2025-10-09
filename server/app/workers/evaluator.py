from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentSignal, MetricsSnapshot
from app.services.polygon_client import PolygonClient


async def evaluate_signals(
    session: AsyncSession,
    *,
    polygon_client: PolygonClient | None = None,
) -> int:
    """Grade agent signals whose evaluation horizon has elapsed."""

    now = datetime.now(timezone.utc)
    stmt = select(AgentSignal).where(
        and_(
            AgentSignal.eval_ts <= now,
            AgentSignal.outcome_label.is_(None),
        )
    )
    result = await session.execute(stmt)
    pending = result.scalars().all()

    if not pending:
        return 0

    owns_client = polygon_client is None
    client = polygon_client or PolygonClient()

    try:
        updated = 0
        for signal in pending:
            bars = await _fetch_signal_bars(client, signal)
            if bars is None or bars.empty:
                continue

            outcome = _evaluate_signal(signal, bars)
            if outcome is None:
                continue

            outcome_return, outcome_label = outcome
            signal.outcome_return = outcome_return
            signal.outcome_label = outcome_label
            updated += 1

        await session.flush()
        return updated
    finally:
        if owns_client:
            await client.close()


async def rollup_metrics(
    session: AsyncSession,
    *,
    windows: Sequence[str] = ("7d", "30d"),
    as_of: datetime | None = None,
) -> int:
    """Aggregate outcome metrics for each agent across rolling windows."""

    now = as_of or datetime.now(timezone.utc)
    total_snapshots = 0

    for window in windows:
        delta = _window_to_timedelta(window)
        window_start = now - delta

        stmt = select(AgentSignal).where(
            and_(
                AgentSignal.ts >= window_start,
                AgentSignal.outcome_label.is_not(None),
            )
        )
        result = await session.execute(stmt)
        signals = result.scalars().all()

        grouped: dict[str, list[AgentSignal]] = defaultdict(list)
        for signal in signals:
            grouped[signal.agent_key].append(signal)

        for agent_key, agent_signals in grouped.items():
            metrics = _compute_metrics(agent_signals)
            if metrics["samples"] == 0:
                continue

            snapshot = await _get_existing_snapshot(session, agent_key, window)
            if snapshot:
                snapshot.hit_rate = metrics["hit_rate"]
                snapshot.avg_R = metrics["avg_R"]
                snapshot.sharpe = metrics["sharpe"]
                snapshot.profit_factor = metrics["profit_factor"]
                snapshot.drawdown = metrics["drawdown"]
                snapshot.samples = metrics["samples"]
                snapshot.calibration_bins = metrics["calibration_bins"]
                snapshot.as_of = now
            else:
                snapshot = MetricsSnapshot(
                    agent_key=agent_key,
                    window=window,
                    hit_rate=metrics["hit_rate"],
                    avg_R=metrics["avg_R"],
                    sharpe=metrics["sharpe"],
                    profit_factor=metrics["profit_factor"],
                    drawdown=metrics["drawdown"],
                    samples=metrics["samples"],
                    calibration_bins=metrics["calibration_bins"],
                    as_of=now,
                )
                session.add(snapshot)
            total_snapshots += 1

    await session.flush()
    return total_snapshots


async def _get_existing_snapshot(session: AsyncSession, agent_key: str, window: str) -> MetricsSnapshot | None:
    stmt = (
        select(MetricsSnapshot)
        .where(
            and_(
                MetricsSnapshot.agent_key == agent_key,
                MetricsSnapshot.window == window,
            )
        )
        .order_by(MetricsSnapshot.as_of.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _window_to_timedelta(window: str) -> timedelta:
    match window:
        case "7d":
            return timedelta(days=7)
        case "30d":
            return timedelta(days=30)
        case _:
            return timedelta(days=7)


async def _fetch_signal_bars(client: PolygonClient, signal: AgentSignal) -> pd.DataFrame | None:
    resolution = signal.resolution.lower()
    multiplier, timespan = _resolution_to_polygon_args(resolution)
    lookback = signal.eval_horizon_bars + 100
    try:
        return await client.get_agg_bars(signal.symbol, timespan=timespan, multiplier=multiplier, lookback=lookback)
    except Exception:  # noqa: BLE001
        return None


def _resolution_to_polygon_args(resolution: str) -> tuple[int, str]:
    if resolution.endswith("m"):
        try:
            return int(resolution.rstrip("m")), "minute"
        except ValueError:
            return 5, "minute"
    if resolution.endswith("h"):
        try:
            return int(resolution.rstrip("h")), "hour"
        except ValueError:
            return 1, "hour"
    if resolution.endswith("d"):
        return 1, "day"
    return 5, "minute"


def _evaluate_signal(signal: AgentSignal, bars: pd.DataFrame) -> tuple[float, str] | None:
    if bars.empty:
        return None

    if "timestamp" in bars.columns:
        bars = bars.set_index("timestamp")

    indexed = bars
    if not isinstance(indexed.index, pd.DatetimeIndex):
        return None

    entry_ts = signal.ts
    eval_ts = signal.eval_ts

    entry_slice = indexed[indexed.index <= entry_ts].tail(1)
    horizon_slice = indexed[indexed.index >= eval_ts].head(1)

    if entry_slice.empty or horizon_slice.empty:
        return None

    entry_close = float(entry_slice["close"].iloc[0])
    horizon_close = float(horizon_slice["close"].iloc[0])

    if entry_close == 0:
        return None

    outcome_return = (horizon_close - entry_close) / entry_close
    outcome_label = _classify_outcome(signal.decision, outcome_return)
    return outcome_return, outcome_label


def _classify_outcome(decision: str, outcome_return: float, *, tolerance: float = 0.001) -> str:
    if decision not in {"BUY", "SELL"}:
        return "flat"

    if decision == "BUY":
        if outcome_return > tolerance:
            return "hit"
        if outcome_return < -tolerance:
            return "miss"
        return "flat"

    # SELL branch
    if outcome_return < -tolerance:
        return "hit"
    if outcome_return > tolerance:
        return "miss"
    return "flat"


def _compute_metrics(agent_signals: Iterable[AgentSignal]) -> dict[str, Any]:
    returns = [float(s.outcome_return) for s in agent_signals if s.outcome_return is not None]
    labels = [s.outcome_label for s in agent_signals if s.outcome_label]
    samples = len(returns)

    if samples == 0:
        return {
            "hit_rate": 0.0,
            "avg_R": 0.0,
            "sharpe": 0.0,
            "profit_factor": 0.0,
            "drawdown": 0.0,
            "samples": 0,
            "calibration_bins": {},
        }

    returns_array = np.array(returns)
    avg_return = float(np.mean(returns_array))
    std_return = float(np.std(returns_array, ddof=1)) if samples > 1 else 0.0
    sharpe = float(avg_return / std_return * math.sqrt(samples)) if std_return > 0 else 0.0

    gains = returns_array[returns_array > 0]
    losses = returns_array[returns_array < 0]
    profit_factor = float(gains.sum() / abs(losses.sum())) if losses.size > 0 else float(gains.sum())

    equity_curve = np.cumprod(1 + returns_array)
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = 1 - equity_curve / np.where(peak == 0, 1, peak)
    max_drawdown = float(drawdowns.max()) if drawdowns.size > 0 else 0.0

    hit_rate = float(labels.count("hit") / len(labels)) if labels else 0.0

    calibration_bins = {
        "hit": labels.count("hit"),
        "miss": labels.count("miss"),
        "flat": labels.count("flat"),
    }

    return {
        "hit_rate": hit_rate,
        "avg_R": avg_return,
        "sharpe": sharpe,
        "profit_factor": profit_factor,
        "drawdown": max_drawdown,
        "samples": samples,
        "calibration_bins": calibration_bins,
    }
