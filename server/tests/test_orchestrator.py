import pandas as pd
import pytest

from app.services.agents.base import AgentOutput
from app.services.auditor import DecisionAuditor
from app.services.orchestrator import run_all_agents
from app.services.portfolio_manager import PortfolioManager
from app.services.risk_manager import RiskManager


class StubAgent:
    key = "stub"
    resolution = "5m"

    def __init__(self, output: AgentOutput) -> None:
        self._output = output

    async def run(self, market):  # noqa: D401
        return self._output


def _market_with_timestamp(timestamp: str) -> dict:
    idx = pd.date_range(timestamp, periods=10, freq="5T", tz="UTC")
    values = {
        "open": [100 + i * 0.1 for i in range(10)],
        "high": [100.5 + i * 0.1 for i in range(10)],
        "low": [99.5 + i * 0.1 for i in range(10)],
        "close": [100 + i * 0.1 for i in range(10)],
        "volume": [100_000 + i * 500 for i in range(10)],
    }
    bars = pd.DataFrame(values, index=idx)
    return {
        "bars_5m": bars,
        "previous_close": {"symbol": "QQQ", "close": 100.0, "timestamp": idx[0].to_pydatetime()},
        "options_snapshot": {"implied_volatility": 0.2, "depth_ok": True},
    }


@pytest.mark.asyncio
async def test_run_all_agents_returns_structured_output():
    agent_output: AgentOutput = {
        "decision": "BUY",
        "confidence": 0.9,
        "inputs": {"example": 1},
        "notes": "stub",
    }
    agents = [StubAgent(agent_output)]
    market = _market_with_timestamp("2024-01-02 14:40:00+00:00")  # 09:40 ET

    overall, results, risk = await run_all_agents(
        market,
        agents,
        RiskManager(),
        PortfolioManager(),
        DecisionAuditor(),
    )

    assert overall["decision"] in {"BUY", "NO_TRADE"}
    assert "stub" in results
    assert "pass" in risk
    assert "risk_reasons" in overall


@pytest.mark.asyncio
async def test_risk_manager_blocks_outside_rth():
    agent_output: AgentOutput = {
        "decision": "BUY",
        "confidence": 0.9,
        "inputs": {"example": 1},
        "notes": "stub",
    }
    agents = [StubAgent(agent_output)]
    market = _market_with_timestamp("2024-01-02 11:00:00+00:00")  # Before RTH

    overall, _, risk = await run_all_agents(
        market,
        agents,
        RiskManager(),
        PortfolioManager(),
        DecisionAuditor(),
    )

    assert risk["pass"] is False
    assert overall["decision"] == "NO_TRADE"
    assert "outside_rth_window" in risk["reasons"]
    assert "reasons" in overall and "outside_rth_window" in overall["reasons"]
    assert "risk_reasons" in overall and "outside_rth_window" in overall["risk_reasons"]
