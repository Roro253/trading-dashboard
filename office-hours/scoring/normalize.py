"""Signal normalization primitives.

Fixes the hidden flaw in fixed-weight retail composites: raw-value sums let
the largest-numerical-range indicator dominate. We z-score each input on a
rolling window, clamp to +/-3 sigma, then map to 0-100.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z_CLAMP = 3.0
ZSCORE_WINDOW_DAYS = 252 * 3  # 3y trading days
PERCENTILE_WINDOW_DAYS = 252 * 3


def rolling_zscore(series: pd.Series, window: int = ZSCORE_WINDOW_DAYS) -> pd.Series:
    """Rolling z-score. Requires at least ``window`` observations — earlier
    values return NaN. Std is computed with ddof=0 (population) to stay
    stable on constant sub-windows."""
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    z = (series - mean) / std.replace(0, np.nan)
    return z.clip(-Z_CLAMP, Z_CLAMP)


def zscore_to_bucket_score(z: float, *, invert: bool = False) -> float:
    """Map clamped z-score to 0-100. z=0 -> 50, z=+3 -> 100, z=-3 -> 0.

    Set ``invert=True`` when higher raw value is *risk-off* (e.g., VIX,
    HY OAS, MOVE) so the bucket score still reads "higher = better for
    trading."
    """
    if z is None or (isinstance(z, float) and np.isnan(z)):
        return 50.0
    z = max(-Z_CLAMP, min(Z_CLAMP, float(z)))
    if invert:
        z = -z
    return 50.0 + (100.0 / (2 * Z_CLAMP)) * z


def percentile_rank(series: pd.Series, value: float, window: int = PERCENTILE_WINDOW_DAYS) -> float:
    """Percentile rank of ``value`` within the trailing ``window`` of
    ``series``. Returns 0-100. Used to map the final composite to its
    3y-trailing percentile so that "80" means "top 20% of last 3 years",
    not "summed to 80 on arbitrary scales."
    """
    tail = series.dropna().tail(window)
    if len(tail) == 0:
        return 50.0
    rank = (tail <= value).sum() / len(tail)
    return float(rank * 100.0)
