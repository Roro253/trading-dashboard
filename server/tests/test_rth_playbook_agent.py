import pandas as pd
import pytest

from app.services.agents.rth_playbook import RTHPlaybookAgent


@pytest.mark.asyncio
async def test_rth_playbook_generates_ticket_buy():
    agent = RTHPlaybookAgent()
    idx = pd.date_range("2024-01-02 14:50:00+00:00", periods=120, freq="5T", tz="UTC")
    trend = [4000 + (i * 6) + ((-1) ** i) * 5 for i in range(120)]
    bars = pd.DataFrame(
        {
            "open": trend,
            "high": [v + 2 for v in trend],
            "low": [v - 2 for v in trend],
            "close": [v + 1 for v in trend],
            "volume": [200_000] * len(trend),
        },
        index=idx,
    )
    market = {
        "symbol": "SPX",
        "bars_5m": bars,
        "options_snapshot": {"implied_volatility": 0.01, "depth_ok": True},
    }

    result = await agent.run(market)

    assert result["decision"] == "BUY"
    assert "rth_ticket" in result["inputs"]


@pytest.mark.asyncio
async def test_rth_playbook_non_spx_no_trade():
    agent = RTHPlaybookAgent()
    market = {"symbol": "QQQ"}

    result = await agent.run(market)

    assert result["decision"] == "NO_TRADE"
