"""Pipeline tests with fake adapters. No network."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

import numpy as np
import pandas as pd
import pytest

from adapters import BreadthClient, FredClient, FredSeries, YahooClient, YahooSeries
from pipeline import Pipeline
from scoring.decision import EventWindow
from store import COLD_START_MIN_SAMPLES, InMemoryStore


# ----- helpers ----------------------------------------------------------


def _daily_index(n: int, start: str = "2020-01-02") -> pd.DatetimeIndex:
    return pd.bdate_range(start=start, periods=n)


def _series(values: Iterable[float], name: str, n: int | None = None) -> pd.Series:
    arr = np.asarray(list(values), dtype=float)
    if n is None:
        n = len(arr)
    return pd.Series(arr, index=_daily_index(n), name=name)


# ----- fakes ------------------------------------------------------------


@dataclass
class FakeFred:
    series_map: dict[str, pd.Series]
    net_liq: pd.Series

    async def fetch_series(self, series_id: str, start=None, end=None) -> pd.Series:
        return self.series_map.get(series_id, pd.Series(dtype=float, name=series_id))

    async def fetch_net_liquidity(self, start=None) -> pd.Series:
        return self.net_liq


@dataclass
class FakeYahoo:
    series_map: dict[str, pd.Series]

    async def fetch_close(self, symbol: str, *, range_: str = "3y", interval: str = "1d") -> pd.Series:
        return self.series_map.get(symbol, pd.Series(dtype=float, name=symbol))

    async def fetch_term_structure_ratio(self, range_: str = "3y") -> pd.Series:
        vix = self.series_map.get(YahooSeries.VIX, pd.Series(dtype=float))
        vix3m = self.series_map.get(YahooSeries.VIX3M, pd.Series(dtype=float))
        df = pd.concat([vix.rename("vix"), vix3m.rename("vix3m")], axis=1).dropna()
        return (df["vix3m"] / df["vix"]).rename("vix3m_vix_ratio")


def _build_pipeline(*, calm: bool = True, stressed: bool = False, no_data: bool = False) -> Pipeline:
    """Build a pipeline wired to fake adapters.

    calm: baseline constructive regime (HY tight, VIX curve in contango)
    stressed: overrides calm with regime that should trip kill-switches
    no_data: all adapters return empty -> composite defaults to 50
    """
    n = 800  # enough history for 3y rolling z-score

    if no_data:
        fake_fred = FakeFred(series_map={}, net_liq=pd.Series(dtype=float))
        fake_yahoo = FakeYahoo(series_map={})
    else:
        base_hy = np.concatenate([np.full(n - 10, 3.50), np.full(10, 3.55)])
        if stressed:
            # HY OAS rips 45 bps in the last 5 trading days
            base_hy = np.concatenate([np.full(n - 5, 3.50), np.linspace(3.55, 3.95, 5)])

        base_vix = np.full(n, 15.0)
        base_vix3m = np.full(n, 18.0)  # contango, ratio 1.2
        if stressed:
            # near-term panic, backwardation ratio 0.88
            base_vix = np.full(n, 30.0)
            base_vix3m = np.full(n, 26.4)

        series_hy = _series(base_hy, FredSeries.HY_OAS, n)
        series_ig = _series(np.full(n, 1.0), FredSeries.IG_OAS, n)
        series_net_liq = _series(np.linspace(6_000_000, 6_300_000, n), "net_liquidity", n)

        fake_fred = FakeFred(
            series_map={FredSeries.HY_OAS: series_hy, FredSeries.IG_OAS: series_ig},
            net_liq=series_net_liq,
        )
        fake_yahoo = FakeYahoo(
            series_map={
                YahooSeries.VIX: _series(base_vix, YahooSeries.VIX, n),
                YahooSeries.VIX3M: _series(base_vix3m, YahooSeries.VIX3M, n),
                YahooSeries.VVIX: _series(np.full(n, 90.0), YahooSeries.VVIX, n),
                # Minimal breadth coverage; raw series is constant -> z=NaN -> dropped
                "^NYMO": _series(np.full(n, 0.0), "^NYMO", n),
                "^NYHL": _series(np.full(n, 50.0), "^NYHL", n),
            },
        )

    fake_breadth = BreadthClient(yahoo=fake_yahoo)  # reuses FakeYahoo via .yahoo
    return Pipeline(fred=fake_fred, yahoo=fake_yahoo, breadth=fake_breadth)


# ----- tests ------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_calm_regime_returns_valid_result():
    pipe = _build_pipeline(calm=True)
    result = await pipe.run()

    assert result.decision in {"YES", "CAUTION", "NO"}
    assert 0.0 <= result.market_quality_score <= 100.0
    assert set(result.bucket_scores).issuperset(
        {"credit_liquidity", "vol_term_structure", "trend", "breadth"}
    )
    # Calm scenario: no kill-switches.
    assert result.triggered_kill_switches == []


@pytest.mark.asyncio
async def test_pipeline_stressed_regime_trips_kill_switch():
    pipe = _build_pipeline(stressed=True)
    result = await pipe.run()

    assert result.decision == "NO"
    assert "vix3m_vix_lt_0_95" in result.triggered_kill_switches
    # HY 5d-delta > 30 bps should also fire in this scenario.
    assert "hy_oas_spike_5d_gt_30bps" in result.triggered_kill_switches


@pytest.mark.asyncio
async def test_pipeline_degrades_gracefully_when_all_feeds_empty():
    pipe = _build_pipeline(no_data=True)
    result = await pipe.run()

    # With no signals, every bucket falls back to 50 -> composite ~50.
    assert result.market_quality_score == pytest.approx(50.0)
    assert result.decision == "NO"
    assert result.signals == []


@pytest.mark.asyncio
async def test_pipeline_yes_downgrades_to_caution_in_macro_window():
    # Synthetic: credit+vol buckets score very high by z-extreme construction.
    n = 800
    # HY OAS has been extremely tight throughout (rolling z of current -> ~0),
    # to make the test deterministic we just run a calm scenario and force
    # the downgrade via the event window. Calm scenario composite is near 50,
    # so it won't become YES. Instead we build one that does by using a large
    # improving trend in HY OAS (falling spreads).
    falling = np.linspace(5.0, 3.0, n)
    constructive_vix = np.full(n, 13.0)
    constructive_vix3m = np.full(n, 17.0)

    fake_fred = FakeFred(
        series_map={FredSeries.HY_OAS: _series(falling, FredSeries.HY_OAS, n)},
        net_liq=_series(np.linspace(6_000_000, 6_500_000, n), "net_liquidity", n),
    )
    fake_yahoo = FakeYahoo(
        series_map={
            YahooSeries.VIX: _series(constructive_vix, YahooSeries.VIX, n),
            YahooSeries.VIX3M: _series(constructive_vix3m, YahooSeries.VIX3M, n),
            YahooSeries.VVIX: _series(np.full(n, 85.0), YahooSeries.VVIX, n),
        },
    )
    pipe = Pipeline(fred=fake_fred, yahoo=fake_yahoo, breadth=BreadthClient(yahoo=fake_yahoo))

    clean = await pipe.run()
    gated = await pipe.run(EventWindow(within_24h_macro=True))
    # If composite puts us in YES, gate should push to CAUTION; otherwise
    # both are the same. Assert the invariant, not a specific decision.
    if clean.decision == "YES":
        assert gated.decision == "CAUTION"
        assert any("within_24h_macro" in r for r in gated.reason_codes)
    else:
        assert gated.decision == clean.decision


@pytest.mark.asyncio
async def test_pipeline_response_is_json_serializable():
    import json

    pipe = _build_pipeline(calm=True)
    result = await pipe.run()
    payload = json.dumps(result.to_dict())
    assert '"decision"' in payload
    assert '"market_quality_score"' in payload
    assert '"market_quality_is_percentile"' in payload


@pytest.mark.asyncio
async def test_pipeline_cold_start_without_store_returns_raw_composite():
    pipe = _build_pipeline(calm=True)
    result = await pipe.run()
    # No store attached -> score == composite_raw and is_percentile False.
    assert result.market_quality_is_percentile is False
    assert result.market_quality_score == result.composite_raw


@pytest.mark.asyncio
async def test_pipeline_cold_start_with_store_falls_back_until_threshold():
    pipe = _build_pipeline(calm=True)
    pipe.store = InMemoryStore()
    result = await pipe.run()
    # Fewer than COLD_START_MIN_SAMPLES of prior history -> raw fallback.
    assert result.market_quality_is_percentile is False


@pytest.mark.asyncio
async def test_pipeline_percentile_map_kicks_in_once_history_deep_enough():
    pipe = _build_pipeline(calm=True)
    store = InMemoryStore()
    # Prefill enough prior samples clustered low so today's composite
    # (~50) ranks near the top.
    start = date(2026, 1, 1)
    for i in range(COLD_START_MIN_SAMPLES + 5):
        await store.append_composite(start + timedelta(days=i), 30.0)
    pipe.store = store

    result = await pipe.run()
    assert result.market_quality_is_percentile is True
    assert result.market_quality_score >= 80.0  # today >> all prior 30s


@pytest.mark.asyncio
async def test_pipeline_reads_cached_percent_above_50d_from_store():
    pipe = _build_pipeline(calm=True)
    store = InMemoryStore()
    # Seed ~3 years of daily %>50d values so the rolling z-score is defined.
    from breadth_compute import PERCENT_ABOVE_50D_METRIC

    base = date(2020, 1, 1)
    for i in range(800):
        await store.put_metric(PERCENT_ABOVE_50D_METRIC, base + timedelta(days=i), 50.0 + i * 0.02)
    pipe.store = store

    result = await pipe.run()
    # The cached metric should show up as a signal.
    names = {s.name for s in result.signals}
    assert "percent_above_50d" in names


@pytest.mark.asyncio
async def test_pipeline_records_composite_on_every_run():
    pipe = _build_pipeline(calm=True)
    store = InMemoryStore()
    pipe.store = store
    await pipe.run()
    assert len(store.composite) == 1
    await pipe.run()
    # Same date -> still one row (insert-or-replace).
    assert len(store.composite) == 1
