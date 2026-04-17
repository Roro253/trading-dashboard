"""Decision layer: YES / CAUTION / NO plus kill-switch overrides.

Kill-switches are hard overrides that force NO regardless of composite
score. These are the three signals that empirically precede the worst
drawdowns and are so asymmetric they don't belong in a weighted sum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    YES = "YES"
    CAUTION = "CAUTION"
    NO = "NO"


class KillSwitch(str, Enum):
    HY_OAS_SPIKE = "hy_oas_spike_5d_gt_30bps"
    VIX_BACKWARDATION = "vix3m_vix_lt_0_95"
    FUNDING_STRESS = "sofr_ois_gt_25bps"


# Thresholds. These are the *starting* values from the literature; they
# should be walk-forward recalibrated on rolling 5y windows before prod.
HY_OAS_5D_SPIKE_BPS = 30.0
VIX_BACKWARDATION_RATIO = 0.95
SOFR_OIS_STRESS_BPS = 25.0

# Decision thresholds on the final (percentile-mapped) score.
YES_THRESHOLD = 80.0
CAUTION_THRESHOLD = 60.0


@dataclass
class KillSwitchInputs:
    """Raw values for kill-switch evaluation. All optional — if the feed
    is down we don't fire the switch (we prefer the weighted composite
    to a false panic)."""

    hy_oas_5d_delta_bps: float | None = None
    vix3m_vix_ratio: float | None = None
    sofr_ois_spread_bps: float | None = None


@dataclass
class EventWindow:
    """Calendar gates. ``within_24h_macro`` covers FOMC / CPI / NFP —
    downgrade YES to CAUTION when true."""

    within_24h_macro: bool = False
    opex_week: bool = False


@dataclass
class DecisionResult:
    decision: Decision
    market_quality_score: float
    triggered_kill_switches: list[KillSwitch] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)


def evaluate_kill_switches(inputs: KillSwitchInputs) -> list[KillSwitch]:
    triggered: list[KillSwitch] = []
    if inputs.hy_oas_5d_delta_bps is not None and inputs.hy_oas_5d_delta_bps > HY_OAS_5D_SPIKE_BPS:
        triggered.append(KillSwitch.HY_OAS_SPIKE)
    if inputs.vix3m_vix_ratio is not None and inputs.vix3m_vix_ratio < VIX_BACKWARDATION_RATIO:
        triggered.append(KillSwitch.VIX_BACKWARDATION)
    if inputs.sofr_ois_spread_bps is not None and inputs.sofr_ois_spread_bps > SOFR_OIS_STRESS_BPS:
        triggered.append(KillSwitch.FUNDING_STRESS)
    return triggered


def decide(
    market_quality_score: float,
    kill_switch_inputs: KillSwitchInputs,
    event_window: EventWindow | None = None,
) -> DecisionResult:
    """Produce a final trading decision.

    Order of operations: kill-switches first (force NO), then score
    thresholds, then calendar half-sizing (YES -> CAUTION into macro prints).
    """
    event_window = event_window or EventWindow()
    triggered = evaluate_kill_switches(kill_switch_inputs)
    reasons: list[str] = []

    if triggered:
        reasons.extend(f"kill_switch:{ks.value}" for ks in triggered)
        return DecisionResult(
            decision=Decision.NO,
            market_quality_score=market_quality_score,
            triggered_kill_switches=triggered,
            reason_codes=reasons,
        )

    if market_quality_score >= YES_THRESHOLD:
        decision = Decision.YES
    elif market_quality_score >= CAUTION_THRESHOLD:
        decision = Decision.CAUTION
    else:
        decision = Decision.NO
    reasons.append(f"score:{market_quality_score:.1f}")

    if decision == Decision.YES and event_window.within_24h_macro:
        decision = Decision.CAUTION
        reasons.append("downgrade:within_24h_macro")

    return DecisionResult(
        decision=decision,
        market_quality_score=market_quality_score,
        triggered_kill_switches=[],
        reason_codes=reasons,
    )
