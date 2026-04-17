"""Percent-of-index above 50d MA — the expensive breadth calculation.

This runs out-of-band (scheduled job, not per-request) because Polygon's
free tier rate limit makes looping 500 constituents take ~100 minutes.
The result is written to the ``breadth_cache`` store; the live pipeline
reads the cached value.

Metric key (used for the store): ``percent_above_50d``.
"""
from __future__ import annotations

import asyncio
from datetime import date
from typing import Iterable

import pandas as pd

from adapters.polygon import PolygonClient
from store import SqliteStore


PERCENT_ABOVE_50D_METRIC = "percent_above_50d"
SMA_WINDOW = 50


async def compute_percent_above_50d(
    tickers: Iterable[str],
    polygon: PolygonClient,
    *,
    max_concurrency: int = 5,
) -> tuple[float, int, int]:
    """Fetch each ticker's daily closes from Polygon and return
    (percent_above_50d, passing_count, total_evaluated).

    Tickers with insufficient history are skipped from the denominator —
    we don't want to let stale listings or IPOs distort the signal.

    ``max_concurrency`` throttles concurrent Polygon requests; the free
    tier is 5/min so the default is conservative. The caller is
    responsible for pacing if they batch through many hundreds of
    tickers — asyncio.Semaphore bounds in-flight, not total rate."""
    sem = asyncio.Semaphore(max_concurrency)

    async def _one(t: str) -> bool | None:
        async with sem:
            try:
                closes = await polygon.daily_closes(t, lookback_days=80)
            except Exception:
                return None
        if len(closes) < SMA_WINDOW + 1:
            return None
        sma = closes.rolling(SMA_WINDOW).mean()
        last_close = closes.iloc[-1]
        last_sma = sma.iloc[-1]
        if pd.isna(last_sma):
            return None
        return bool(last_close > last_sma)

    tickers = list(tickers)
    results = await asyncio.gather(*(_one(t) for t in tickers))
    evaluated = [r for r in results if r is not None]
    if not evaluated:
        return (0.0, 0, 0)
    passing = sum(1 for r in evaluated if r)
    pct = 100.0 * passing / len(evaluated)
    return (pct, passing, len(evaluated))


async def refresh_percent_above_50d(
    tickers: Iterable[str],
    polygon: PolygonClient,
    store: SqliteStore,
    *,
    as_of: date | None = None,
) -> float:
    """Compute and persist the latest ``percent_above_50d`` snapshot.
    Returns the computed percent so the caller can log it."""
    pct, _, _ = await compute_percent_above_50d(tickers, polygon)
    await store.put_metric(
        PERCENT_ABOVE_50D_METRIC,
        as_of or date.today(),
        pct,
    )
    return pct
