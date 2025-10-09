from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

EASTERN = ZoneInfo("America/New_York")
RTH_START = time(9, 30)
RTH_MIN_ENTRY = time(9, 35)
RTH_END = time(16, 0)


class RiskManager:
    """Applies liquidity, temporal, and event-based trading guards."""

    def __init__(
        self,
        *,
        liquidity_volume_threshold: float = 50_000,
        require_options_depth: bool = False,
        event_blackouts: Iterable[datetime] | None = None,
        options_depth_bypass: bool = True,
    ) -> None:
        self.liquidity_volume_threshold = liquidity_volume_threshold
        self.require_options_depth = require_options_depth
        self.event_blackouts = list(event_blackouts or [])
        self.options_depth_bypass = options_depth_bypass

    async def check(self, market: Dict[str, Any], agent_results: Dict[str, Any]) -> Dict[str, Any]:
        reasons: List[str] = []

        bars = market.get("bars_5m")
        latest_ts: datetime | None = None
        if isinstance(bars, pd.DataFrame) and not bars.empty:
            latest_ts = bars.index[-1]
            if isinstance(latest_ts, pd.Timestamp):
                latest_ts = latest_ts.to_pydatetime()
        else:
            reasons.append("no_market_data")

        timestamp_et = self._to_eastern(latest_ts)
        if timestamp_et is None:
            reasons.append("missing_timestamp")
        else:
            if not (RTH_START <= timestamp_et.time() <= RTH_END):
                reasons.append("outside_rth_window")
            if timestamp_et.time() < RTH_MIN_ENTRY:
                reasons.append("pre_open_buffer")

        if isinstance(bars, pd.DataFrame) and not bars.empty:
            last_volume = float(bars.iloc[-1].get("volume", 0.0))
            if last_volume < self.liquidity_volume_threshold:
                reasons.append("low_liquidity_volume")
        else:
            reasons.append("liquidity_unknown")

        options_snapshot = market.get("options_snapshot") or {}
        depth_flag = bool(options_snapshot.get("depth_ok", False))
        if self.require_options_depth and not (depth_flag or self.options_depth_bypass):
            reasons.append("options_depth_insufficient")

        if self._is_blackout(timestamp_et):
            reasons.append("event_blackout_window")

        passed = len(reasons) == 0
        logger.info("risk.check.completed", passed=passed, reasons=reasons)

        return {"pass": passed, "reasons": reasons}

    def _to_eastern(self, timestamp: datetime | None) -> datetime | None:
        if timestamp is None:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
        return timestamp.astimezone(EASTERN)

    def _is_blackout(self, timestamp_et: datetime | None) -> bool:
        if timestamp_et is None or not self.event_blackouts:
            return False
        window = timedelta(minutes=30)
        for event_time in self.event_blackouts:
            try:
                event_et = event_time.astimezone(EASTERN)
            except ValueError:
                event_et = event_time
            if abs((timestamp_et - event_et)) <= window:
                return True
        return False
