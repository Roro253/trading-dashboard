"""Yahoo Finance adapter for volatility term structure and cross-asset.

Uses the public Yahoo chart endpoint. No API key, but fragile — treat
as scaffolding. When we promote this into server/, consider swapping to
Stooq or a paid feed (Polygon already in the stack supports some of
these tickers directly).

Tickers used:
    ^VIX, ^VIX9D, ^VIX3M, ^VIX6M   vol term structure
    ^VVIX                            vol-of-vol
    ^MOVE                            Treasury vol
    ^SKEW                            tail-risk hedging demand
    HYG, LQD                         credit-appetite ratio
    HG=F, GC=F                       copper/gold macro ratio
    JPY=X                            USDJPY carry regime
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import pandas as pd

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"


class YahooSeries:
    VIX = "^VIX"
    VIX9D = "^VIX9D"
    VIX3M = "^VIX3M"
    VIX6M = "^VIX6M"
    VVIX = "^VVIX"
    MOVE = "^MOVE"
    SKEW = "^SKEW"
    HYG = "HYG"
    LQD = "LQD"
    COPPER = "HG=F"
    GOLD = "GC=F"
    USDJPY = "JPY=X"


@dataclass
class YahooClient:
    timeout_s: float = 10.0
    user_agent: str = "Mozilla/5.0 (compatible; trading-dashboard/office-hours)"
    client: httpx.AsyncClient | None = None

    async def fetch_close(
        self,
        symbol: str,
        *,
        range_: str = "3y",
        interval: str = "1d",
    ) -> pd.Series:
        """Return a daily-close pandas Series for ``symbol``.

        ``range_`` options: 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.
        ``interval`` options: 1d, 1wk, 1mo."""
        url = YAHOO_CHART_URL.format(symbol=symbol)
        params: dict[str, Any] = {"range": range_, "interval": interval, "includePrePost": "false"}
        headers = {"User-Agent": self.user_agent}

        client = self.client or httpx.AsyncClient(timeout=self.timeout_s, headers=headers)
        should_close = self.client is None
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if should_close:
                await client.aclose()

        result = (payload.get("chart") or {}).get("result") or []
        if not result:
            return pd.Series(dtype=float, name=symbol)
        r = result[0]
        ts = r.get("timestamp") or []
        quote = ((r.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        if not ts or not closes:
            return pd.Series(dtype=float, name=symbol)
        idx = pd.to_datetime(ts, unit="s").normalize()
        s = pd.Series(closes, index=idx, name=symbol, dtype="float64").dropna()
        return s.sort_index()

    async def fetch_term_structure_ratio(self, range_: str = "3y") -> pd.Series:
        """VIX3M / VIX ratio. Values < 0.95 trigger the backwardation
        kill-switch. Values > 1.0 are normal contango (risk-on regime)."""
        vix = await self.fetch_close(YahooSeries.VIX, range_=range_)
        vix3m = await self.fetch_close(YahooSeries.VIX3M, range_=range_)
        df = pd.concat([vix.rename("vix"), vix3m.rename("vix3m")], axis=1).dropna()
        return (df["vix3m"] / df["vix"]).rename("vix3m_vix_ratio")
