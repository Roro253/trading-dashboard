from __future__ import annotations

import math
from datetime import datetime, time
from typing import Any, Dict
from zoneinfo import ZoneInfo

import pandas as pd
import structlog

from app.services.agents.base import AgentOutput, Decision
from app.services.utils import compute_vwap, ema

logger = structlog.get_logger(__name__)

EASTERN = ZoneInfo("America/New_York")
RTH_MIN_ENTRY = time(9, 35)


class RTHPlaybookAgent:
    key = "rth_playbook"
    resolution = "5m"

    def __init__(self, *, min_confidence: float = 0.4) -> None:
        self.min_confidence = min_confidence

    async def run(self, market: Dict[str, Any]) -> AgentOutput:
        symbol = str(market.get("symbol", "")).upper()
        underlying = "SPX" if symbol in {"SPX", "ES"} else "SPY"

        bars = market.get("bars_5m")
        if not isinstance(bars, pd.DataFrame) or bars.empty:
            logger.warning("rth_playbook.no_bars", symbol=symbol)
            return self._output("NO_TRADE", 0.0, {}, "Missing market bars")

        latest_ts = bars.index[-1]
        latest_local = self._to_eastern(latest_ts)
        if latest_local.time() < RTH_MIN_ENTRY:
            return self._output("NO_TRADE", 0.0, {"latest_ts": latest_local.isoformat()}, "Pre-open buffer")

        options_snapshot = market.get("options_snapshot") or {}
        if not options_snapshot.get("depth_ok", False):
            if options_snapshot:
                logger.info("rth_playbook.depth_placeholder", symbol=symbol)
            return self._output("HOLD", 0.2, {"depth_ok": False}, "Awaiting depth confirmation")

        implied_vol = self._safe_float(options_snapshot.get("implied_volatility"))
        realized_vol = self._realized_vol(bars)
        if implied_vol is None or realized_vol is None:
            return self._output("HOLD", 0.2, {"implied_vol": implied_vol, "realized_vol": realized_vol}, "Volatility inputs incomplete")

        ratio = implied_vol / max(realized_vol, 1e-6)
        trend_fast = ema(bars, span=21).iloc[-1]
        trend_slow = ema(bars, span=55).iloc[-1]
        vwap_value = compute_vwap(bars).iloc[-1]
        price = float(bars["close"].iloc[-1])

        bullish = price > vwap_value and trend_fast > trend_slow and ratio < 0.9
        bearish = price < vwap_value and trend_fast < trend_slow and ratio > 1.1

        decision: Decision
        notes: str
        if bullish:
            decision = "BUY"
            notes = "Implied < realized trend favoring longs"
        elif bearish:
            decision = "SELL"
            notes = "Implied > realized trend favoring shorts"
        else:
            decision = "HOLD"
            notes = "Conditions neutral"

        confidence = self._confidence(ratio, price, vwap_value, trend_fast, trend_slow)
        if decision in {"BUY", "SELL"} and confidence < self.min_confidence:
            decision = "HOLD"
            notes = "Confidence gate"

        ticket = None
        if decision in {"BUY", "SELL"}:
            ticket = self._build_ticket(underlying, decision, price, implied_vol, realized_vol, ratio)

        inputs: Dict[str, Any] = {
            "price": price,
            "vwap": float(vwap_value),
            "ema21": float(trend_fast),
            "ema55": float(trend_slow),
            "implied_vol": implied_vol,
            "realized_vol": realized_vol,
            "vol_ratio": ratio,
            "underlying": underlying,
        }
        if ticket:
            inputs["rth_ticket"] = ticket

        return self._output(decision, confidence, inputs, notes)

    def _confidence(
        self,
        ratio: float,
        price: float,
        vwap_value: float,
        trend_fast: float,
        trend_slow: float,
    ) -> float:
        spread = abs(trend_fast - trend_slow) / max(price, 1e-6)
        vwap_distance = abs(price - vwap_value) / max(price, 1e-6)
        ratio_component = max(0.0, min(1.0, abs(1 - ratio)))
        score = 0.2 * spread + 0.3 * vwap_distance + 0.5 * ratio_component
        return float(max(0.0, min(score, 1.0)))

    def _build_ticket(
        self,
        underlying: str,
        decision: Decision,
        price: float,
        implied_vol: float,
        realized_vol: float,
        ratio: float,
    ) -> Dict[str, Any]:
        structure = "call_vertical" if decision == "BUY" else "put_vertical"
        expiry = "0DTE" if underlying == "SPX" else "1DTE"
        ticket = {
            "underlying": underlying,
            "structure": structure,
            "expiry": expiry,
            "delta": 0.3,
            "entry_rules": [
                "Confirm market breadth supportive",
                f"Maintain vol ratio near {ratio:.2f}",
            ],
            "stop_rules": [
                "Exit on 50% premium decay",
                "Invalidate if vol ratio mean reverts",
            ],
            "targets": [
                "Scale at 30% of expected move",
                "Final exit into close",
            ],
            "sizing_formula": "risk_capital * 0.5%",
            "notes": {
                "implied_vol": implied_vol,
                "realized_vol": realized_vol,
                "vol_ratio": ratio,
                "direction": decision,
                "reference_price": price,
            },
            "alert_only": True,
        }
        return ticket

    def _to_eastern(self, timestamp: datetime) -> datetime:
        ts = timestamp
        if isinstance(ts, pd.Timestamp):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ZoneInfo("UTC"))
        return ts.astimezone(EASTERN)

    def _realized_vol(self, bars: pd.DataFrame) -> float | None:
        returns = bars["close"].pct_change().dropna()
        if returns.empty:
            return None
        realized = returns.tail(390).std() * math.sqrt(390)
        return float(realized) if not math.isnan(realized) else None

    def _safe_float(self, value: Any) -> float | None:
        try:
            if value is None:
                return None
            val = float(value)
            return val if not math.isnan(val) else None
        except (TypeError, ValueError):
            return None

    def _output(self, decision: Decision, confidence: float, inputs: Dict[str, Any], notes: str) -> AgentOutput:
        return AgentOutput(
            decision=decision,
            confidence=float(max(0.0, min(confidence, 1.0))),
            inputs=inputs,
            notes=notes,
        )
