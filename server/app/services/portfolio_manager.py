from __future__ import annotations

from typing import Any, Dict

import structlog

from app.services.agents.base import AgentOutput, Decision

logger = structlog.get_logger(__name__)


class PortfolioManager:
    """Combines agent decisions into a portfolio-level stance."""

    def combine(
        self,
        results: Dict[str, AgentOutput],
        weights: Dict[str, float] | None = None,
        *,
        min_conf: float = 0.55,
    ) -> Dict[str, Any]:
        weights = weights or {}
        side_scores: Dict[Decision, float] = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0, "NO_TRADE": 0.0}
        total_weight = 0.0
        contributors: Dict[str, Any] = {}

        for key, output in results.items():
            weight = float(weights.get(key, 1.0))
            confidence = float(output["confidence"])
            decision = output["decision"]

            contributors[key] = {
                "decision": decision,
                "confidence": confidence,
                "weight": weight,
            }

            if confidence < min_conf or decision in ("HOLD", "NO_TRADE"):
                continue

            total_weight += weight
            side_scores[decision] += confidence * weight

        if total_weight == 0:
            logger.info("portfolio.combine.no_signal", reason="min_conf_gate")
            return {
                "decision": "NO_TRADE",
                "confidence": 0.0,
                "method": "min_conf_gate",
                "contributors": contributors,
                "side_scores": side_scores,
            }

        buy_score = side_scores["BUY"]
        sell_score = side_scores["SELL"]

        if buy_score == sell_score:
            decision: Decision = "NO_TRADE"
        else:
            decision = "BUY" if buy_score > sell_score else "SELL"

        winning_score = max(buy_score, sell_score)
        confidence = winning_score / (total_weight or 1.0)
        confidence = float(min(max(confidence, 0.0), 1.0))

        logger.info(
            "portfolio.combine.completed",
            decision=decision,
            confidence=confidence,
            totals=side_scores,
        )

        return {
            "decision": decision,
            "confidence": confidence,
            "method": "weighted",
            "contributors": contributors,
            "side_scores": side_scores,
        }
