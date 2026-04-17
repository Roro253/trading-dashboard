"""Unit tests for the scoring engine.

Deterministic fixtures only — no network. Adapters are tested separately
with mocked httpx responses.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from scoring import (
    BUCKET_WEIGHTS,
    Bucket,
    Decision,
    KillSwitch,
    compose_market_quality_score,
    compute_bucket_scores,
    decide,
    percentile_rank,
    rolling_zscore,
    zscore_to_bucket_score,
)
from scoring.composite import SignalInput
from scoring.decision import EventWindow, KillSwitchInputs


# ----- normalize ---------------------------------------------------------


def test_rolling_zscore_clamps_to_three_sigma():
    series = pd.Series([1.0] * 10 + [1000.0], index=pd.date_range("2020-01-01", periods=11))
    z = rolling_zscore(series, window=10)
    assert z.iloc[-1] == 3.0


def test_rolling_zscore_returns_nan_before_window_filled():
    series = pd.Series(np.linspace(0, 1, 50), index=pd.date_range("2020-01-01", periods=50))
    z = rolling_zscore(series, window=30)
    assert math.isnan(z.iloc[0])
    assert math.isnan(z.iloc[28])
    assert not math.isnan(z.iloc[29])


def test_zscore_to_bucket_score_endpoints():
    assert zscore_to_bucket_score(0.0) == 50.0
    assert zscore_to_bucket_score(3.0) == pytest.approx(100.0)
    assert zscore_to_bucket_score(-3.0) == pytest.approx(0.0)


def test_zscore_to_bucket_score_inverts_for_risk_off_signals():
    # Rising VIX (z=+2) should hurt bucket score, not help it.
    assert zscore_to_bucket_score(2.0, invert=True) < 50.0
    assert zscore_to_bucket_score(-2.0, invert=True) > 50.0


def test_zscore_nan_maps_to_neutral():
    assert zscore_to_bucket_score(float("nan")) == 50.0


def test_percentile_rank_basic():
    s = pd.Series(range(100))
    assert percentile_rank(s, 50, window=100) == pytest.approx(51.0)
    assert percentile_rank(s, -1, window=100) == pytest.approx(0.0)
    assert percentile_rank(s, 99, window=100) == pytest.approx(100.0)


# ----- composite ---------------------------------------------------------


def test_bucket_weights_sum_to_one():
    assert sum(BUCKET_WEIGHTS.values()) == pytest.approx(1.0)


def test_compute_bucket_scores_weights_by_inv_vol():
    # Two signals in the credit bucket: quiet one (inv_vol=1.0) scores 80,
    # noisy one (inv_vol=0.1) scores 20. Weighted avg ~ 74.5, not 50.
    signals = {
        Bucket.CREDIT_LIQUIDITY: [
            SignalInput(name="hy_oas", bucket_score=80.0, inv_vol_weight=1.0),
            SignalInput(name="noisy", bucket_score=20.0, inv_vol_weight=0.1),
        ],
    }
    out = compute_bucket_scores(signals)
    assert out[Bucket.CREDIT_LIQUIDITY] == pytest.approx((80 * 1.0 + 20 * 0.1) / 1.1)
    # Empty buckets fall back to neutral.
    assert out[Bucket.BREADTH] == 50.0


def test_compose_market_quality_score_respects_bucket_weights():
    # Everything neutral except credit at 100 -> final = 75 + 25*1 = 81.25
    neutral = {b: 50.0 for b in BUCKET_WEIGHTS}
    neutral[Bucket.CREDIT_LIQUIDITY] = 100.0
    score = compose_market_quality_score(neutral)
    expected = sum(50 * w for b, w in BUCKET_WEIGHTS.items() if b != Bucket.CREDIT_LIQUIDITY)
    expected += 100 * BUCKET_WEIGHTS[Bucket.CREDIT_LIQUIDITY]
    assert score == pytest.approx(expected)


# ----- decision ----------------------------------------------------------


def test_decide_yes_when_score_high_and_clean():
    result = decide(85.0, KillSwitchInputs())
    assert result.decision == Decision.YES
    assert result.triggered_kill_switches == []


def test_decide_caution_band():
    result = decide(65.0, KillSwitchInputs())
    assert result.decision == Decision.CAUTION


def test_decide_no_when_score_low():
    result = decide(40.0, KillSwitchInputs())
    assert result.decision == Decision.NO


def test_kill_switch_hy_oas_forces_no_even_if_score_high():
    result = decide(
        95.0,
        KillSwitchInputs(hy_oas_5d_delta_bps=45.0),
    )
    assert result.decision == Decision.NO
    assert KillSwitch.HY_OAS_SPIKE in result.triggered_kill_switches


def test_kill_switch_vix_backwardation_forces_no():
    result = decide(90.0, KillSwitchInputs(vix3m_vix_ratio=0.92))
    assert result.decision == Decision.NO
    assert KillSwitch.VIX_BACKWARDATION in result.triggered_kill_switches


def test_kill_switch_funding_stress_forces_no():
    result = decide(88.0, KillSwitchInputs(sofr_ois_spread_bps=40.0))
    assert result.decision == Decision.NO
    assert KillSwitch.FUNDING_STRESS in result.triggered_kill_switches


def test_missing_kill_switch_inputs_do_not_fire():
    # All None -> composite wins, no false panic.
    result = decide(85.0, KillSwitchInputs())
    assert result.decision == Decision.YES


def test_yes_downgraded_to_caution_into_macro_window():
    result = decide(
        90.0,
        KillSwitchInputs(),
        EventWindow(within_24h_macro=True),
    )
    assert result.decision == Decision.CAUTION
    assert any("within_24h_macro" in r for r in result.reason_codes)


def test_no_not_upgraded_by_event_window():
    result = decide(50.0, KillSwitchInputs(), EventWindow(within_24h_macro=True))
    assert result.decision == Decision.NO
