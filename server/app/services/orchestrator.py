from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

import structlog

from app.services.auditor import DecisionAuditor
from app.services.agents.base import Agent
from app.services.polygon_client import PolygonClient
from app.services.portfolio_manager import PortfolioManager
from app.services.risk_manager import RiskManager

logger = structlog.get_logger(__name__)


async def run_all_agents(
    market: Dict[str, Any],
    agents: Iterable[Agent],
    risk_manager: RiskManager,
    portfolio_manager: PortfolioManager,
    auditor: DecisionAuditor,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    results: Dict[str, Any] = {}
    for agent in agents:
        logger.info("orchestrator.agent.run", agent=agent.key)
        results[agent.key] = await agent.run(market)

    risk = await risk_manager.check(market, results)

    if not risk["pass"]:
        logger.warning("orchestrator.risk.blocked", reasons=risk["reasons"])
        overall: Dict[str, Any] = {
            "decision": "NO_TRADE",
            "confidence": 0.0,
            "method": "risk_override",
            "reasons": risk["reasons"],
        }
    else:
        overall = portfolio_manager.combine(results)
        overall = auditor.verify(market, results, overall)

    overall.setdefault("risk_reasons", risk.get("reasons", []))
    return overall, results, risk


class StrategyOrchestrator:
    """Coordinates data collection and agent execution."""

    def __init__(self, polygon_client: PolygonClient | None = None) -> None:
        self.polygon_client = polygon_client or PolygonClient()
        self.risk_manager = RiskManager()
        self.portfolio_manager = PortfolioManager()
        self.auditor = DecisionAuditor()

    async def build_market(self, symbol: str) -> Dict[str, Any]:
        bars_5m = await self.polygon_client.get_agg_bars(symbol, multiplier=5, lookback=300)
        previous_close = await self.polygon_client.get_previous_close(symbol)
        options_snapshot = await self.polygon_client.get_options_snapshot(symbol)
        return {
            "symbol": symbol,
            "bars_5m": bars_5m,
            "previous_close": previous_close,
            "options_snapshot": options_snapshot,
        }

    async def evaluate(self, symbol: str, agents: Iterable[Agent]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        market = await self.build_market(symbol)
        return await run_all_agents(
            market,
            agents,
            self.risk_manager,
            self.portfolio_manager,
            self.auditor,
        )
