"""Assembly layer — adapters -> signals -> score -> decision.

Pure orchestration with injected dependencies. The final Market Quality
Score is the percentile rank of today's composite within its own 3y
trailing distribution (stored in ``store.py``); during cold start
(<60 samples) we fall back to the raw composite so the endpoint still
returns a sensible number.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from adapters import BreadthClient, FredClient, FredSeries, YahooClient, YahooSeries
from breadth_compute import PERCENT_ABOVE_50D_METRIC
from scoring import (
    Bucket,
    DecisionResult,
    compose_market_quality_score,
    compute_bucket_scores,
    decide,
    percentile_rank,
    rolling_zscore,
    zscore_to_bucket_score,
)
from scoring.composite import SignalInput
from scoring.decision import EventWindow, KillSwitchInputs
from store import COLD_START_MIN_SAMPLES, CompositeHistoryStore


BPS_PER_PCT = 100.0  # FRED OAS series are in percent; deltas -> bps
PERCENTILE_WINDOW = 252 * 3  # 3 trading years


@dataclass
class SignalSnapshot:
    name: str
    bucket: str
    value: float | None
    zscore: float | None
    bucket_score: float
    inv_vol_weight: float


@dataclass
class PipelineResult:
    generated_at: str
    decision: str
    market_quality_score: float
    composite_raw: float
    market_quality_is_percentile: bool
    bucket_scores: dict[str, float]
    triggered_kill_switches: list[str]
    reason_codes: list[str]
    signals: list[SignalSnapshot]
    degraded_feeds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _latest_non_nan(series: pd.Series) -> float | None:
    s = series.dropna()
    return float(s.iloc[-1]) if len(s) else None


def _make_signal(
    *,
    name: str,
    bucket: Bucket,
    series: pd.Series,
    invert: bool,
    inv_vol_weight: float,
) -> tuple[SignalInput | None, SignalSnapshot]:
    z_series = rolling_zscore(series.dropna())
    z_latest = z_series.iloc[-1] if len(z_series) and not np.isnan(z_series.iloc[-1]) else None
    bucket_score = zscore_to_bucket_score(z_latest if z_latest is not None else float("nan"), invert=invert)
    snapshot = SignalSnapshot(
        name=name,
        bucket=bucket.value,
        value=_latest_non_nan(series),
        zscore=float(z_latest) if z_latest is not None else None,
        bucket_score=float(bucket_score),
        inv_vol_weight=inv_vol_weight,
    )
    if z_latest is None:
        return None, snapshot
    return (
        SignalInput(name=name, bucket_score=bucket_score, inv_vol_weight=inv_vol_weight),
        snapshot,
    )


@dataclass
class Pipeline:
    fred: FredClient
    yahoo: YahooClient
    breadth: BreadthClient
    store: CompositeHistoryStore | None = None

    # Inverse-volatility weights per signal inside its bucket (placeholders
    # until we compute actual signal volatility on historical data).
    credit_hy_oas_w: float = 1.0
    credit_hy_oas_5d_w: float = 1.0
    credit_net_liq_w: float = 0.6
    vol_vix3m_vix_w: float = 1.0
    vol_vvix_w: float = 0.7
    breadth_nymo_w: float = 1.0
    breadth_nhl_w: float = 0.8
    breadth_pct_50d_w: float = 1.0

    async def run(self, event_window: EventWindow | None = None) -> PipelineResult:
        degraded: list[str] = []
        signals_by_bucket: dict[Bucket, list[SignalInput]] = {}
        snapshots: list[SignalSnapshot] = []

        async def safe(name: str, coro: Any) -> Any:
            try:
                return await coro
            except Exception:  # pragma: no cover - network/transport
                degraded.append(name)
                return pd.Series(dtype=float, name=name)

        # --- Credit / Liquidity ----------------------------------------
        hy_oas = await safe("hy_oas", self.fred.fetch_series(FredSeries.HY_OAS))
        net_liq = await safe("net_liquidity", self.fred.fetch_net_liquidity())

        credit_signals: list[SignalInput] = []
        if len(hy_oas):
            sig, snap = _make_signal(
                name="hy_oas",
                bucket=Bucket.CREDIT_LIQUIDITY,
                series=hy_oas,
                invert=True,
                inv_vol_weight=self.credit_hy_oas_w,
            )
            snapshots.append(snap)
            if sig is not None:
                credit_signals.append(sig)

            hy_5d = hy_oas.diff(5) * BPS_PER_PCT
            sig5, snap5 = _make_signal(
                name="hy_oas_5d_delta_bps",
                bucket=Bucket.CREDIT_LIQUIDITY,
                series=hy_5d,
                invert=True,
                inv_vol_weight=self.credit_hy_oas_5d_w,
            )
            snapshots.append(snap5)
            if sig5 is not None:
                credit_signals.append(sig5)

        if len(net_liq):
            net_liq_4w = net_liq.diff(20)
            sig, snap = _make_signal(
                name="net_liquidity_4w_delta",
                bucket=Bucket.CREDIT_LIQUIDITY,
                series=net_liq_4w,
                invert=False,
                inv_vol_weight=self.credit_net_liq_w,
            )
            snapshots.append(snap)
            if sig is not None:
                credit_signals.append(sig)
        if credit_signals:
            signals_by_bucket[Bucket.CREDIT_LIQUIDITY] = credit_signals

        # --- Vol term structure ---------------------------------------
        vix = await safe("vix", self.yahoo.fetch_close(YahooSeries.VIX))
        vix3m = await safe("vix3m", self.yahoo.fetch_close(YahooSeries.VIX3M))
        vvix = await safe("vvix", self.yahoo.fetch_close(YahooSeries.VVIX))

        vol_signals: list[SignalInput] = []
        ratio: pd.Series = pd.Series(dtype=float)
        if len(vix) and len(vix3m):
            df = pd.concat([vix.rename("vix"), vix3m.rename("vix3m")], axis=1).dropna()
            ratio = (df["vix3m"] / df["vix"]).rename("vix3m_vix_ratio")
            sig, snap = _make_signal(
                name="vix3m_vix_ratio",
                bucket=Bucket.VOL_TERM_STRUCTURE,
                series=ratio,
                invert=False,
                inv_vol_weight=self.vol_vix3m_vix_w,
            )
            snapshots.append(snap)
            if sig is not None:
                vol_signals.append(sig)
        if len(vvix):
            sig, snap = _make_signal(
                name="vvix",
                bucket=Bucket.VOL_TERM_STRUCTURE,
                series=vvix,
                invert=True,
                inv_vol_weight=self.vol_vvix_w,
            )
            snapshots.append(snap)
            if sig is not None:
                vol_signals.append(sig)
        if vol_signals:
            signals_by_bucket[Bucket.VOL_TERM_STRUCTURE] = vol_signals

        # --- Breadth ---------------------------------------------------
        nymo = await safe("nymo", self.breadth.fetch_mcclellan_oscillator())
        nhl = await safe("nhl", self.breadth.fetch_net_new_highs_lows())

        breadth_signals: list[SignalInput] = []
        if len(nymo):
            sig, snap = _make_signal(
                name="mcclellan_oscillator",
                bucket=Bucket.BREADTH,
                series=nymo,
                invert=False,
                inv_vol_weight=self.breadth_nymo_w,
            )
            snapshots.append(snap)
            if sig is not None:
                breadth_signals.append(sig)
        if len(nhl):
            sig, snap = _make_signal(
                name="net_new_highs_lows",
                bucket=Bucket.BREADTH,
                series=nhl,
                invert=False,
                inv_vol_weight=self.breadth_nhl_w,
            )
            snapshots.append(snap)
            if sig is not None:
                breadth_signals.append(sig)

        # Cached %>50d MA — computed out-of-band, read from store.
        if self.store is not None:
            pct_series = await self.store.metric_history(PERCENT_ABOVE_50D_METRIC)  # type: ignore[attr-defined]
            if len(pct_series):
                sig, snap = _make_signal(
                    name="percent_above_50d",
                    bucket=Bucket.BREADTH,
                    series=pct_series,
                    invert=False,
                    inv_vol_weight=self.breadth_pct_50d_w,
                )
                snapshots.append(snap)
                if sig is not None:
                    breadth_signals.append(sig)

        if breadth_signals:
            signals_by_bucket[Bucket.BREADTH] = breadth_signals

        # --- Compose ---------------------------------------------------
        bucket_scores = compute_bucket_scores(signals_by_bucket)
        composite_raw = compose_market_quality_score(bucket_scores)

        # --- Percentile-map today's composite against stored history --
        market_quality_score = composite_raw
        is_percentile = False
        today = date.today()
        if self.store is not None:
            history = await self.store.get_composite_history(exclude=today)
            if len(history) >= COLD_START_MIN_SAMPLES:
                market_quality_score = percentile_rank(
                    history,
                    composite_raw,
                    window=PERCENTILE_WINDOW,
                )
                is_percentile = True
            # Record today's composite for future percentile maps.
            await self.store.append_composite(today, composite_raw)

        # --- Kill-switches --------------------------------------------
        ks_inputs = KillSwitchInputs(
            hy_oas_5d_delta_bps=_latest_non_nan(hy_oas.diff(5) * BPS_PER_PCT) if len(hy_oas) else None,
            vix3m_vix_ratio=_latest_non_nan(ratio) if len(ratio) else None,
            sofr_ois_spread_bps=None,  # needs OIS feed; TODO
        )
        decision: DecisionResult = decide(market_quality_score, ks_inputs, event_window)

        return PipelineResult(
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            decision=decision.decision.value,
            market_quality_score=round(market_quality_score, 2),
            composite_raw=round(composite_raw, 2),
            market_quality_is_percentile=is_percentile,
            bucket_scores={b.value: round(v, 2) for b, v in bucket_scores.items()},
            triggered_kill_switches=[ks.value for ks in decision.triggered_kill_switches],
            reason_codes=decision.reason_codes,
            signals=snapshots,
            degraded_feeds=degraded,
        )
