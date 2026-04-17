"""Composite Market Quality Score.

Professional bucket weighting — differs from the retail 25/25/20/20/10 by
shifting weight from Momentum/Trend into Credit and Vol term structure,
which is where most of the leading-indicator edge lives.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Bucket(str, Enum):
    CREDIT_LIQUIDITY = "credit_liquidity"
    VOL_TERM_STRUCTURE = "vol_term_structure"
    TREND = "trend"
    BREADTH = "breadth"
    DEALER_POSITIONING = "dealer_positioning"
    POSITIONING_SENTIMENT = "positioning_sentiment"
    CROSS_ASSET = "cross_asset"
    CALENDAR = "calendar"


BUCKET_WEIGHTS: dict[Bucket, float] = {
    Bucket.CREDIT_LIQUIDITY: 0.25,
    Bucket.VOL_TERM_STRUCTURE: 0.20,
    Bucket.TREND: 0.15,
    Bucket.BREADTH: 0.15,
    Bucket.DEALER_POSITIONING: 0.10,
    Bucket.POSITIONING_SENTIMENT: 0.08,
    Bucket.CROSS_ASSET: 0.05,
    Bucket.CALENDAR: 0.02,
}


@dataclass(frozen=True)
class SignalInput:
    """A single normalized signal inside a bucket.

    ``bucket_score`` is already 0-100 (use ``zscore_to_bucket_score``).
    ``inv_vol_weight`` is the pre-computed inverse-volatility weight of
    the signal itself; the caller is responsible for normalizing these
    so they sum to 1.0 within a bucket.
    """

    name: str
    bucket_score: float
    inv_vol_weight: float


def compute_bucket_scores(signals_by_bucket: Mapping[Bucket, list[SignalInput]]) -> dict[Bucket, float]:
    """Weighted-average the signals inside each bucket. Empty buckets
    default to 50 (neutral) so a missing feed doesn't force a no-trade."""
    out: dict[Bucket, float] = {}
    for bucket in BUCKET_WEIGHTS:
        signals = signals_by_bucket.get(bucket, [])
        if not signals:
            out[bucket] = 50.0
            continue
        total_w = sum(s.inv_vol_weight for s in signals)
        if total_w <= 0:
            out[bucket] = 50.0
            continue
        out[bucket] = sum(s.bucket_score * s.inv_vol_weight for s in signals) / total_w
    return out


def compose_market_quality_score(bucket_scores: Mapping[Bucket, float]) -> float:
    """Weighted sum of bucket scores -> single 0-100 composite.

    Note: This is the pre-percentile-map composite. Callers should then
    run ``percentile_rank`` against a 3y trailing window of the composite
    to get the final dashboard score.
    """
    total = 0.0
    for bucket, weight in BUCKET_WEIGHTS.items():
        score = bucket_scores.get(bucket, 50.0)
        total += weight * score
    return total
