from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from app.services.risk_manager import RiskManager


@pytest.mark.asyncio
async def test_risk_manager_flags_low_volume():
    idx = pd.date_range("2024-01-02 14:40:00+00:00", periods=1, freq="5T", tz="UTC")
    bars = pd.DataFrame(
        {
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100.5],
            "volume": [500],
        },
        index=idx,
    )

    market = {"bars_5m": bars, "options_snapshot": {"implied_volatility": 0.2, "depth_ok": True}}
    risk_manager = RiskManager(liquidity_volume_threshold=10_000)

    result = await risk_manager.check(market, {})

    assert result["pass"] is False
    assert "low_liquidity_volume" in result["reasons"]


@pytest.mark.asyncio
async def test_risk_manager_event_blackout():
    event_time = datetime(2024, 1, 2, 15, 0, tzinfo=timezone.utc)
    idx = pd.DatetimeIndex([event_time])
    bars = pd.DataFrame(
        {
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100.5],
            "volume": [100_000],
        },
        index=idx,
    )
    market = {"bars_5m": bars, "options_snapshot": {"implied_volatility": 0.2, "depth_ok": True}}
    risk_manager = RiskManager(event_blackouts=[event_time + timedelta(minutes=10)], liquidity_volume_threshold=1_000)

    result = await risk_manager.check(market, {})

    assert result["pass"] is False
    assert "event_blackout_window" in result["reasons"]
