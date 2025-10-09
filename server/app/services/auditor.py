from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

REALIZED_WINDOW_5D = 78 * 5  # 5 trading days of 5-minute bars


class DecisionAuditor:
    """Performs post-portfolio validation and attaches audit metadata."""

    def __init__(self, *, implied_sigma_limit: float = 2.5) -> None:
        self.implied_sigma_limit = implied_sigma_limit

    def verify(
        self,
        market: Dict[str, Any],
        results: Dict[str, Any],
        overall: Dict[str, Any],
    ) -> Dict[str, Any]:
        bars = market.get("bars_5m")
        options_snapshot = market.get("options_snapshot") or {}

        notes: Dict[str, Any] = {}
        failure_modes: List[str] = []

        realized_vol = self._compute_realized_vol(bars)
        implied_vol = self._safe_float(options_snapshot.get("implied_volatility"))
        notes["implied_volatility"] = implied_vol
        notes["realized_vol_5d"] = realized_vol

        if implied_vol is not None and realized_vol is not None and realized_vol > 0:
            diff_ratio = abs(implied_vol - realized_vol) / max(realized_vol, 1e-6)
            notes["implied_realized_diff_ratio"] = diff_ratio
            if diff_ratio > self.implied_sigma_limit:
                failure_modes.append("implied_move_outlier")
        else:
            notes["implied_move_check"] = "insufficient_data"

        if isinstance(bars, pd.DataFrame):
            if not bars.index.is_monotonic_increasing:
                failure_modes.append("non_monotonic_prices")
            if bars.isna().any().any():
                failure_modes.append("nan_in_market_data")
        else:
            failure_modes.append("missing_bars")

        if not self._confidence_within_bounds(overall):
            failure_modes.append("invalid_confidence_range")

        if self._results_have_nan(results):
            failure_modes.append("nan_in_agent_output")

        existing_notes = overall.get("auditor_notes", {})
        combined_notes = {**existing_notes, **notes}

        if failure_modes:
            combined_notes["failure_modes"] = failure_modes[:3]
            updated = overall.copy()
            updated["decision"] = "NO_TRADE"
            updated["method"] = "auditor_override"
            updated["confidence"] = 0.0
            updated["reasons"] = failure_modes[:3]
            updated["auditor_notes"] = combined_notes
            logger.warning("auditor.override", failure_modes=failure_modes)
            return updated

        if combined_notes:
            updated = overall.copy()
            updated["auditor_notes"] = combined_notes
            return updated

        return overall

    def _compute_realized_vol(self, bars: Any) -> float | None:
        if not isinstance(bars, pd.DataFrame) or bars.empty:
            return None

        closes = bars.get("close")
        if closes is None:
            return None
        returns = closes.pct_change().dropna()
        if returns.empty:
            return None
        window = min(len(returns), REALIZED_WINDOW_5D)
        realized = returns.tail(window).std() * math.sqrt(window)
        return float(realized) if not math.isnan(realized) else None

    def _confidence_within_bounds(self, overall: Dict[str, Any]) -> bool:
        try:
            confidence = float(overall.get("confidence", 0.0))
        except (TypeError, ValueError):
            return False
        return 0.0 <= confidence <= 1.0

    def _results_have_nan(self, results: Dict[str, Any]) -> bool:
        visited: set[int] = set()

        def walk(value: Any) -> bool:
            obj_id = id(value)
            if obj_id in visited:
                return False
            visited.add(obj_id)

            if isinstance(value, (float, int, np.floating, np.integer)):
                return math.isnan(float(value))
            if isinstance(value, dict):
                return any(walk(v) for v in value.values())
            if isinstance(value, list):
                return any(walk(item) for item in value)
            return False

        return any(walk(output) for output in results.values())

    def _is_nan(self, value: Any) -> bool:
        if isinstance(value, (float, int)):
            return math.isnan(value)
        if isinstance(value, (np.floating, np.integer)):
            return math.isnan(float(value))
        return False

    def _safe_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            val = float(value)
            return val if not math.isnan(val) else None
        except (TypeError, ValueError):
            return None
