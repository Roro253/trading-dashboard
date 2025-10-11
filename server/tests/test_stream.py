from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
import pytest
from httpx import ASGITransport, AsyncClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000")

from app.api.routes import ticker_event_stream
from app.core.config import get_settings
from app.db.session import get_session
from app.main import app
from app.services import stream as stream_service

get_settings.cache_clear()


class DummySession:
    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:  # pragma: no cover - simple stub
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.fixture
def override_dependencies(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    async def override_session() -> AsyncIterator[DummySession]:
        session = DummySession()
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_session] = override_session
    broker = stream_service.StreamBroker()
    broker._redis_url = ""
    monkeypatch.setattr(stream_service, "_BROKER", broker)

    yield

    app.dependency_overrides.pop(get_session, None)
    monkeypatch.setattr(stream_service, "_BROKER", None)


@pytest.mark.asyncio
async def test_stream_receives_update(monkeypatch: pytest.MonkeyPatch, override_dependencies: None) -> None:
    async def fake_build_market(self: Any, symbol: str) -> dict[str, Any]:
        idx = pd.date_range("2024-01-02 14:40:00+00:00", periods=1, freq="5min", tz="UTC")
        bars = pd.DataFrame(
            {
                "open": [100.0],
                "high": [101.0],
                "low": [99.0],
                "close": [100.5],
                "volume": [250_000],
            },
            index=idx,
        )
        return {
            "symbol": symbol,
            "bars_5m": bars,
            "previous_close": {"symbol": symbol, "close": 100.0, "volume": 1_000_000, "timestamp": datetime.now(timezone.utc)},
            "options_snapshot": {"symbol": symbol, "depth_ok": True},
        }

    async def fake_run_all_agents(*_: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        overall = {"decision": "BUY", "confidence": 0.75, "method": "weighted"}
        results = {
            "technical": {
                "decision": "BUY",
                "confidence": 0.82,
                "inputs": {"eval_horizon_bars": 3},
                "notes": "stub",
            }
        }
        risk = {"pass": True, "reasons": []}
        return overall, results, risk

    monkeypatch.setattr("app.services.orchestrator.StrategyOrchestrator.build_market", fake_build_market)
    monkeypatch.setattr("app.api.routes.run_all_agents", fake_run_all_agents)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async def consume_stream() -> dict[str, Any]:
            async for event in ticker_event_stream("QQQ"):
                if event.get("event") != "update":
                    continue
                data = event.get("data")
                if isinstance(data, str):
                    return json.loads(data)
                return data

        stream_task = asyncio.create_task(consume_stream())
        await asyncio.sleep(0)
        run_response = await client.post("/api/run/QQQ")
        assert run_response.status_code == 200

        payload = await asyncio.wait_for(stream_task, timeout=3)
        assert payload["ticker"] == "QQQ"
        assert payload["overall"]["decision"] == "BUY"
        assert payload["agents"]["technical"]["decision"] == "BUY"
