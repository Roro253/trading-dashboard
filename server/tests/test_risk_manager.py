from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")

from app.core.config import get_settings
from app.services.risk_manager import RiskManager

get_settings.cache_clear()

EASTERN = ZoneInfo("America/New_York")


def _market_at(et_time: datetime, *, volume: float = 250_000) -> dict[str, object]:
    ts_utc = et_time.astimezone(timezone.utc)
    bars = pd.DataFrame(
        {
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [volume],
        },
        index=pd.DatetimeIndex([ts_utc]),
    )
    return {
        "bars_5m": bars,
        "options_snapshot": {"depth_ok": True},
    }


@pytest.mark.asyncio
async def test_risk_manager_blocks_before_min_entry() -> None:
    market = _market_at(datetime(2024, 1, 2, 9, 33, tzinfo=EASTERN))
    manager = RiskManager(liquidity_volume_threshold=1_000)

    result = await manager.check(market, {})

    assert result["pass"] is False
    assert "pre_open_buffer" in result["reasons"]


@pytest.mark.asyncio
async def test_risk_manager_allows_rth_trade() -> None:
    market = _market_at(datetime(2024, 1, 2, 10, 1, tzinfo=EASTERN), volume=500_000)
    manager = RiskManager(liquidity_volume_threshold=1_000)

    result = await manager.check(market, {})

    assert result["pass"] is True
    assert result["reasons"] == []


@pytest.mark.asyncio
async def test_risk_manager_blocks_blackout_window() -> None:
    blackout_et = datetime(2024, 1, 2, 8, 30, tzinfo=EASTERN)
    market = _market_at(datetime(2024, 1, 2, 8, 45, tzinfo=EASTERN), volume=500_000)
    manager = RiskManager(event_blackouts=[blackout_et.astimezone(timezone.utc)], liquidity_volume_threshold=1_000)

    result = await manager.check(market, {})

    assert result["pass"] is False
    assert "event_blackout_window" in result["reasons"]
