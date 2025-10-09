from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import structlog

from app.services.agents.base import AgentOutput, Decision
from app.services.utils import atr, compute_vwap, ema, rsi

logger = structlog.get_logger(__name__)


class TechnicalAgent:
    key = "technical"
    resolution = "5m"

    def __init__(self, *, min_history: int = 60) -> None:
        self.min_history = min_history

    async def run(self, market: Dict[str, Any]) -> AgentOutput:
        bars = market.get("bars_5m")
        if bars is None or not isinstance(bars, pd.DataFrame) or bars.empty:
            logger.warning("agent.technical.no_data", resolution=self.resolution)
            return self._output("NO_TRADE", 0.0, {}, "No market data")

        df = bars.sort_index()
        if len(df) < max(self.min_history, 55):
            logger.warning("agent.technical.insufficient_data", rows=len(df))

        vwap_series = compute_vwap(df)
        ema_21 = ema(df, span=21)
        ema_55 = ema(df, span=55)
        rsi_series = rsi(df, period=14)
        atr_series = atr(df, period=14)

        latest = df.iloc[-1]
        price = float(latest["close"])
        vwap_value = float(vwap_series.iloc[-1])
        ema21_value = float(ema_21.iloc[-1])
        ema55_value = float(ema_55.iloc[-1])
        rsi_value = float(rsi_series.iloc[-1])
        atr_value = float(atr_series.iloc[-1])

        bullish = price > vwap_value and ema21_value > ema55_value and 45 <= rsi_value <= 70
        bearish = price < vwap_value and ema21_value < ema55_value and 30 <= rsi_value <= 55

        decision: Decision
        notes: str
        if bullish:
            decision = "BUY"
            notes = "bullish structure"
        elif bearish:
            decision = "SELL"
            notes = "bearish structure"
        else:
            decision = "HOLD"
            notes = "neutral posture"

        confidence = self._confidence(decision, price, vwap_value, ema21_value, ema55_value)

        inputs: Dict[str, Any] = {
            "close": price,
            "vwap": vwap_value,
            "ema21": ema21_value,
            "ema55": ema55_value,
            "rsi": rsi_value,
            "atr": atr_value,
            "decision_gates": {
                "above_vwap": price > vwap_value,
                "ema_trend": ema21_value > ema55_value,
                "rsi_window_ok": 45 <= rsi_value <= 70,
                "below_vwap": price < vwap_value,
                "ema_down": ema21_value < ema55_value,
                "rsi_bearish_window": 30 <= rsi_value <= 55,
            },
        }

        return self._output(decision, confidence, inputs, notes)

    def _confidence(
        self,
        decision: Decision,
        price: float,
        vwap_value: float,
        ema21_value: float,
        ema55_value: float,
    ) -> float:
        if decision == "HOLD":
            spread = abs(ema21_value - ema55_value) / max(price, 1e-6)
            return float(min(1.0, spread * 0.5))

        vwap_distance = abs(price - vwap_value) / max(vwap_value, 1e-6)
        ema_spread = abs(ema21_value - ema55_value) / max(price, 1e-6)
        return float(min(1.0, (vwap_distance + ema_spread) * 1.5))

    @staticmethod
    def _output(decision: Decision, confidence: float, inputs: Dict[str, Any], notes: str) -> AgentOutput:
        return AgentOutput(
            decision=decision,
            confidence=float(min(max(confidence, 0.0), 1.0)),
            inputs=inputs,
            notes=notes,
        )
