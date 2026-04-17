"""FastAPI router exposing /should-i-trade.

Mountable either standalone (for office-hours validation) or into the
existing server/ FastAPI app later.

Run standalone:
    FRED_API_KEY=... uvicorn office-hours.api:app --port 8001

Env:
    FRED_API_KEY    required for live mode
    OFFICE_HOURS_DB optional; path to SQLite history file
                    (defaults to ./data/office_hours.db)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query

from adapters import BreadthClient, FredClient, YahooClient
from pipeline import Pipeline, PipelineResult
from scoring.decision import EventWindow
from store import SqliteStore


DEFAULT_DB_PATH = Path(__file__).parent / "data" / "office_hours.db"


def build_default_pipeline() -> Pipeline:
    """Construct a live Pipeline from env. Raises 503 if env not set."""
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="FRED_API_KEY not set; credit/liquidity signals unavailable.",
        )
    fred_http = httpx.AsyncClient(timeout=10.0)
    yahoo_http = httpx.AsyncClient(
        timeout=10.0,
        headers={"User-Agent": "Mozilla/5.0 (compatible; trading-dashboard/office-hours)"},
    )
    fred = FredClient(api_key=api_key, client=fred_http)
    yahoo = YahooClient(client=yahoo_http)
    breadth = BreadthClient(yahoo=yahoo)
    db_path = Path(os.environ.get("OFFICE_HOURS_DB", DEFAULT_DB_PATH))
    store = SqliteStore(path=db_path)
    return Pipeline(fred=fred, yahoo=yahoo, breadth=breadth, store=store)


def _result_to_json(result: PipelineResult) -> dict[str, Any]:
    return result.to_dict()


def create_app(pipeline_factory: Callable[[], Pipeline] | None = None) -> FastAPI:
    app = FastAPI(title="Should I Be Trading? (office-hours)")

    factory: Callable[[], Pipeline] = pipeline_factory or build_default_pipeline

    def get_pipeline() -> Pipeline:
        return factory()

    @app.get("/should-i-trade")
    async def should_i_trade(
        within_24h_macro: bool = Query(
            False,
            description="FOMC/CPI/NFP within 24h -> YES downgrades to CAUTION",
        ),
        opex_week: bool = Query(False, description="Informational; no score impact yet"),
        pipeline: Pipeline = Depends(get_pipeline),
    ) -> dict[str, Any]:
        result = await pipeline.run(
            EventWindow(within_24h_macro=within_24h_macro, opex_week=opex_week)
        )
        return _result_to_json(result)

    @app.get("/should-i-trade/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "should-i-trade",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "fred_configured": bool(os.environ.get("FRED_API_KEY")),
            "db_path": str(os.environ.get("OFFICE_HOURS_DB", DEFAULT_DB_PATH)),
        }

    return app


app = create_app()
