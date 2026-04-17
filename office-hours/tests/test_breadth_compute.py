"""Tests for the %>50d MA breadth computation.

Uses a fake Polygon client so we exercise the pass/fail accounting and
the 'insufficient history' skip logic without network or rate limits.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import numpy as np
import pandas as pd
import pytest

from breadth_compute import PERCENT_ABOVE_50D_METRIC, compute_percent_above_50d, refresh_percent_above_50d
from store import InMemoryStore


@dataclass
class FakePolygon:
    generator: Callable[[str], pd.Series]

    async def daily_closes(self, ticker: str, lookback_days: int = 80) -> pd.Series:
        return self.generator(ticker)


def _closes(values: list[float]) -> pd.Series:
    idx = pd.bdate_range(end="2026-04-15", periods=len(values))
    return pd.Series(values, index=idx, dtype="float64")


@pytest.mark.asyncio
async def test_percent_above_50d_counts_pass_correctly():
    # Three tickers; first two finish above their 50d SMA, third finishes below.
    above_flat = [100.0] * 50 + [110.0]  # SMA=100, close=110 -> pass
    below_flat = [100.0] * 50 + [90.0]   # SMA=100, close=90  -> fail
    mixed = [100.0] * 25 + [120.0] * 25 + [115.0]  # SMA=110, close=115 -> pass
    ticker_map = {"A": _closes(above_flat), "B": _closes(below_flat), "C": _closes(mixed)}
    polygon = FakePolygon(generator=lambda t: ticker_map[t])

    pct, passing, total = await compute_percent_above_50d(["A", "B", "C"], polygon)
    assert passing == 2
    assert total == 3
    assert pct == pytest.approx(66.666666, rel=1e-3)


@pytest.mark.asyncio
async def test_percent_above_50d_skips_short_history():
    # Ticker with <50 bars -> excluded from denominator.
    short = _closes([100.0] * 30)
    long_pass = _closes([100.0] * 50 + [110.0])
    ticker_map = {"SHORT": short, "PASS": long_pass}
    polygon = FakePolygon(generator=lambda t: ticker_map[t])

    pct, passing, total = await compute_percent_above_50d(["SHORT", "PASS"], polygon)
    assert total == 1
    assert passing == 1
    assert pct == 100.0


@pytest.mark.asyncio
async def test_percent_above_50d_handles_empty_universe():
    polygon = FakePolygon(generator=lambda t: _closes([]))
    pct, passing, total = await compute_percent_above_50d(["A"], polygon)
    assert (pct, passing, total) == (0.0, 0, 0)


@pytest.mark.asyncio
async def test_percent_above_50d_swallows_individual_errors():
    def gen(t: str) -> pd.Series:
        if t == "BAD":
            raise RuntimeError("simulated transient polygon error")
        return _closes([100.0] * 50 + [110.0])

    polygon = FakePolygon(generator=gen)
    pct, passing, total = await compute_percent_above_50d(["BAD", "OK"], polygon)
    assert total == 1
    assert passing == 1


@pytest.mark.asyncio
async def test_refresh_writes_to_store():
    polygon = FakePolygon(generator=lambda t: _closes([100.0] * 50 + [105.0]))
    store = InMemoryStore()

    pct = await refresh_percent_above_50d(
        ["A", "B"],
        polygon,
        store,  # type: ignore[arg-type]
        as_of=date(2026, 4, 15),
    )
    assert pct == 100.0

    latest = await store.latest_metric(PERCENT_ABOVE_50D_METRIC)
    assert latest == (date(2026, 4, 15), 100.0)
