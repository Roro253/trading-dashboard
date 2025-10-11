from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo

import pandas as pd
import structlog

from app.core.config import get_settings

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
        self.event_blackouts = self._load_blackouts(event_blackouts)
        self.options_depth_bypass = options_depth_bypass

    async def check(self, market: Dict[str, Any], agent_results: Dict[str, Any]) -> Dict[str, Any]:
        reasons: List[str] = []

        bars = market.get("bars_5m")
        event_ts_utc = None
        if isinstance(bars, pd.DataFrame) and not bars.empty:
            latest_ts = bars.index[-1]
            event_ts_utc = self._to_utc(latest_ts)
        else:
            reasons.append("no_market_data")

        if event_ts_utc is None:
            reasons.append("missing_timestamp")
        else:
            timestamp_et = event_ts_utc.astimezone(EASTERN)
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

        if self._is_blackout(event_ts_utc):
            reasons.append("event_blackout_window")

        passed = len(reasons) == 0
        logger.info("risk.check.completed", passed=passed, reasons=reasons)

        return {"pass": passed, "reasons": reasons}

    def _to_utc(self, timestamp: datetime | pd.Timestamp | None) -> datetime | None:
        if timestamp is None:
            return None
        if isinstance(timestamp, pd.Timestamp):
            timestamp = timestamp.to_pydatetime()
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)

    def _is_blackout(self, timestamp_utc: datetime | None) -> bool:
        if timestamp_utc is None or not self.event_blackouts:
            return False
        window = timedelta(minutes=30)
        for event_time in self.event_blackouts:
            if abs((timestamp_utc - event_time)) <= window:
                return True
        return False

    def _load_blackouts(self, explicit: Iterable[datetime] | None) -> List[datetime]:
        if explicit is not None:
            return [dt for dt in (self._to_utc(value) for value in explicit) if dt is not None]

        settings = get_settings()
        blackouts: List[datetime] = []
        for raw in getattr(settings, "event_blackout_iso", []):
            parsed = self._parse_blackout(raw)
            if parsed is not None:
                blackouts.append(parsed)
        return blackouts

    def _parse_blackout(self, value: str) -> datetime | None:
        if not value:
            return None
        try:
            candidate = datetime.fromisoformat(value)
        except ValueError:
            logger.warning("risk.blackout.invalid_iso", value=value)
            return None
        return self._to_utc(candidate)
