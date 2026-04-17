"""API tests using FastAPI TestClient and a mocked Pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api import create_app
from pipeline import PipelineResult
from scoring.decision import EventWindow


@dataclass
class FakePipeline:
    """Canned response so the API layer is tested independently of
    adapter orchestration."""

    canned: PipelineResult
    last_event_window: EventWindow | None = None

    async def run(self, event_window: EventWindow | None = None) -> PipelineResult:
        self.last_event_window = event_window
        return self.canned


def _canned(decision: str = "CAUTION", score: float = 65.0) -> PipelineResult:
    return PipelineResult(
        generated_at="2026-04-17T12:00:00+00:00",
        decision=decision,
        market_quality_score=score,
        composite_raw=score,
        market_quality_is_percentile=False,
        bucket_scores={"credit_liquidity": 70.0, "vol_term_structure": 60.0},
        triggered_kill_switches=[],
        reason_codes=[f"score:{score:.1f}"],
        signals=[],
    )


def _client(pipeline: FakePipeline) -> TestClient:
    app = create_app(pipeline_factory=lambda: pipeline)
    return TestClient(app)


def test_should_i_trade_returns_canned_decision():
    pipe = FakePipeline(canned=_canned("YES", 85.0))
    client = _client(pipe)

    resp = client.get("/should-i-trade")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decision"] == "YES"
    assert body["market_quality_score"] == 85.0
    assert "credit_liquidity" in body["bucket_scores"]


def test_should_i_trade_passes_event_window_flags_to_pipeline():
    pipe = FakePipeline(canned=_canned())
    client = _client(pipe)

    resp = client.get("/should-i-trade", params={"within_24h_macro": "true", "opex_week": "true"})
    assert resp.status_code == 200
    assert pipe.last_event_window is not None
    assert pipe.last_event_window.within_24h_macro is True
    assert pipe.last_event_window.opex_week is True


def test_should_i_trade_defaults_event_window_to_false():
    pipe = FakePipeline(canned=_canned())
    client = _client(pipe)

    resp = client.get("/should-i-trade")
    assert resp.status_code == 200
    assert pipe.last_event_window is not None
    assert pipe.last_event_window.within_24h_macro is False
    assert pipe.last_event_window.opex_week is False


def test_health_endpoint_reports_status():
    pipe = FakePipeline(canned=_canned())
    client = _client(pipe)

    resp = client.get("/should-i-trade/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "should-i-trade"


def test_missing_fred_key_returns_503_in_live_mode(monkeypatch):
    # Using the default live factory (no override) without FRED_API_KEY set.
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    app = create_app()
    client = TestClient(app)

    resp = client.get("/should-i-trade")
    assert resp.status_code == 503
    assert "FRED_API_KEY" in resp.json()["detail"]
