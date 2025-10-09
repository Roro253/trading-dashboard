import pandas as pd
import pytest

from app.services.agents.technical import TechnicalAgent


def _market_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=30, freq="5T")
    data = {
        "open": [100 + (i * 0.1) for i in range(30)],
        "high": [100.5 + (i * 0.1) for i in range(30)],
        "low": [99.5 + (i * 0.1) for i in range(30)],
        "close": [100 + (i * 0.2) for i in range(30)],
        "volume": [1_000 + i * 5 for i in range(30)],
    }
    return pd.DataFrame(data, index=idx)


@pytest.mark.asyncio
async def test_technical_agent_generates_buy(monkeypatch):
    df = _market_df()
    agent = TechnicalAgent()

    def series(values):
        return pd.Series(values, index=df.index)

    monkeypatch.setattr(
        "app.services.agents.technical.compute_vwap",
        lambda frame: series([c - 0.2 for c in frame["close"]]),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.ema",
        lambda frame, span: series(
            [c + 0.3 if span == 21 else c - 0.3 for c in frame["close"]]
        ),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.rsi",
        lambda frame, period=14: series([50] * (len(frame) - 1) + [60]),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.atr",
        lambda frame, period=14: series([1.0] * len(frame)),
    )

    result = await agent.run({"bars_5m": df})
    assert result["decision"] == "BUY"
    assert 0.0 < result["confidence"] <= 1.0
    assert result["inputs"]["decision_gates"]["above_vwap"] is True


@pytest.mark.asyncio
async def test_technical_agent_generates_sell(monkeypatch):
    df = _market_df()
    agent = TechnicalAgent()

    def series(values):
        return pd.Series(values, index=df.index)

    monkeypatch.setattr(
        "app.services.agents.technical.compute_vwap",
        lambda frame: series([c + 0.2 for c in frame["close"]]),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.ema",
        lambda frame, span: series(
            [c - 0.3 if span == 21 else c + 0.3 for c in frame["close"]]
        ),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.rsi",
        lambda frame, period=14: series([40] * (len(frame) - 1) + [45]),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.atr",
        lambda frame, period=14: series([1.0] * len(frame)),
    )

    result = await agent.run({"bars_5m": df})
    assert result["decision"] == "SELL"
    assert 0.0 < result["confidence"] <= 1.0
    assert result["inputs"]["decision_gates"]["below_vwap"] is True


@pytest.mark.asyncio
async def test_technical_agent_hold_when_no_conditions(monkeypatch):
    df = _market_df()
    agent = TechnicalAgent()

    def series(values):
        return pd.Series(values, index=df.index)

    monkeypatch.setattr(
        "app.services.agents.technical.compute_vwap",
        lambda frame: series(frame["close"]),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.ema",
        lambda frame, span: series(frame["close"]),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.rsi",
        lambda frame, period=14: series([50] * len(frame)),
    )
    monkeypatch.setattr(
        "app.services.agents.technical.atr",
        lambda frame, period=14: series([1.0] * len(frame)),
    )

    result = await agent.run({"bars_5m": df})
    assert result["decision"] == "HOLD"
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["inputs"]["decision_gates"]["above_vwap"] is False
