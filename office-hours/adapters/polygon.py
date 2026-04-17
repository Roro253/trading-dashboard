"""Minimal Polygon aggregates client for office-hours.

Intentionally thin — only the single endpoint we need for the breadth
computation. When office-hours is promoted into ``server/``, callers
switch to the already-async polygon client under
``server/app/services/polygon_client.py`` instead.

Env:
    POLYGON_API_KEY   required
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx
import pandas as pd


POLYGON_BASE = "https://api.polygon.io"


@dataclass
class PolygonClient:
    api_key: str
    timeout_s: float = 15.0
    client: httpx.AsyncClient | None = None

    async def daily_closes(self, ticker: str, lookback_days: int = 80) -> pd.Series:
        """Return daily close prices for ``ticker`` over the last
        ``lookback_days`` calendar days.

        ``lookback_days=80`` gives ~55 trading days, which is enough to
        compute a 50-day SMA plus a little buffer for weekends/holidays.
        """
        end = date.today()
        start = end - timedelta(days=lookback_days)
        url = (
            f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/day/"
            f"{start.isoformat()}/{end.isoformat()}"
        )
        params = {"adjusted": "true", "sort": "asc", "limit": 5000, "apiKey": self.api_key}

        client = self.client or httpx.AsyncClient(timeout=self.timeout_s)
        should_close = self.client is None
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if should_close:
                await client.aclose()

        results = payload.get("results") or []
        if not results:
            return pd.Series(dtype=float, name=ticker)
        idx = pd.to_datetime([r["t"] for r in results], unit="ms").normalize()
        closes = [r["c"] for r in results]
        return pd.Series(closes, index=idx, name=ticker, dtype="float64").sort_index()
