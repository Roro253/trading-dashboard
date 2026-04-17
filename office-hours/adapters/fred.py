"""FRED (Federal Reserve Economic Data) adapter.

Unlocks the credit/liquidity bucket — the single biggest alpha addition
over the base retail prompt. Requires a free API key from
https://fred.stlouisfed.org/docs/api/api_key.html (env: FRED_API_KEY).

Series used:
    BAMLH0A0HYM2   ICE BofA HY OAS            (kill-switch + weighted input)
    BAMLC0A0CM     ICE BofA IG OAS            (weighted input)
    WALCL          Fed total assets           (net liquidity)
    WTREGEN        Treasury General Account   (net liquidity)
    RRPONTSYD      Overnight Reverse Repo     (net liquidity)
    SOFR           Secured Overnight Rate     (funding-stress proxy)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx
import pandas as pd

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


class FredSeries:
    HY_OAS = "BAMLH0A0HYM2"
    IG_OAS = "BAMLC0A0CM"
    WALCL = "WALCL"
    TGA = "WTREGEN"
    RRP = "RRPONTSYD"
    SOFR = "SOFR"


@dataclass
class FredClient:
    api_key: str
    timeout_s: float = 10.0
    client: httpx.AsyncClient | None = None

    async def fetch_series(
        self,
        series_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.Series:
        """Return a daily-indexed pandas Series of float values.

        FRED returns "." for missing observations — we drop those. The
        index is ``DatetimeIndex`` (UTC-naive, matches how ``server/``
        stores market data)."""
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if start is not None:
            params["observation_start"] = start.isoformat()
        if end is not None:
            params["observation_end"] = end.isoformat()

        client = self.client or httpx.AsyncClient(timeout=self.timeout_s)
        should_close = self.client is None
        try:
            resp = await client.get(FRED_BASE_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
        finally:
            if should_close:
                await client.aclose()

        obs = payload.get("observations", [])
        rows = [(o["date"], o["value"]) for o in obs if o.get("value") not in (None, ".")]
        if not rows:
            return pd.Series(dtype=float, name=series_id)
        df = pd.DataFrame(rows, columns=["date", "value"])
        df["date"] = pd.to_datetime(df["date"])
        df["value"] = df["value"].astype(float)
        return df.set_index("date")["value"].sort_index().rename(series_id)

    async def fetch_net_liquidity(
        self,
        start: date | None = None,
    ) -> pd.Series:
        """Compute Fed Net Liquidity = WALCL - TGA - RRP, daily-forward-filled.

        WALCL is weekly (Wed). TGA and RRP are daily. We forward-fill
        WALCL onto the daily index so the output is a clean daily series
        suitable for rolling z-score and 4w-delta calculations."""
        walcl = await self.fetch_series(FredSeries.WALCL, start=start)
        tga = await self.fetch_series(FredSeries.TGA, start=start)
        rrp = await self.fetch_series(FredSeries.RRP, start=start)

        df = pd.concat([walcl, tga, rrp], axis=1).sort_index()
        df["WALCL"] = df["WALCL"].ffill()
        df = df.dropna(subset=["WTREGEN", "RRPONTSYD"])
        net_liq = df["WALCL"] - df["WTREGEN"] - df["RRPONTSYD"]
        return net_liq.rename("net_liquidity")
