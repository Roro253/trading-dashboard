"""Breadth adapter — minimal first pass.

Uses Yahoo-accessible breadth indices. Several of the StockCharts
breadth tickers ($NYMO, $NYSI, $NYHL) mirror to Yahoo under ^-prefixed
symbols, so we can reuse the Yahoo chart endpoint.

What this covers:
    ^NYMO   McClellan Oscillator
    ^NYSI   McClellan Summation Index
    ^NYHL   NYSE net new 52w H minus L
    ^NYAD   NYSE Advance/Decline issues (cumulative)
    ^CPCE   Cboe equity-only put/call (not index P/C)

Intentionally NOT here yet:
    % stocks above 50d MA ($SPXA50R) — no clean free source; defer to
    a constituent-loop via Polygon when we move to server/.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .yahoo import YahooClient


class BreadthSeries:
    MCCLELLAN_OSC = "^NYMO"
    MCCLELLAN_SUM = "^NYSI"
    NET_HL = "^NYHL"
    AD_LINE = "^NYAD"
    EQUITY_PC = "^CPCE"


@dataclass
class BreadthClient:
    """Thin wrapper over YahooClient so caller code reads as
    breadth.fetch_*() rather than yahoo.fetch_close(weird_symbol)."""

    yahoo: YahooClient

    async def fetch(self, symbol: str, range_: str = "3y") -> pd.Series:
        return await self.yahoo.fetch_close(symbol, range_=range_)

    async def fetch_mcclellan_oscillator(self, range_: str = "3y") -> pd.Series:
        return await self.fetch(BreadthSeries.MCCLELLAN_OSC, range_=range_)

    async def fetch_mcclellan_summation(self, range_: str = "3y") -> pd.Series:
        return await self.fetch(BreadthSeries.MCCLELLAN_SUM, range_=range_)

    async def fetch_net_new_highs_lows(self, range_: str = "3y") -> pd.Series:
        return await self.fetch(BreadthSeries.NET_HL, range_=range_)

    async def fetch_ad_line(self, range_: str = "3y") -> pd.Series:
        return await self.fetch(BreadthSeries.AD_LINE, range_=range_)

    async def fetch_equity_put_call(self, range_: str = "3y") -> pd.Series:
        return await self.fetch(BreadthSeries.EQUITY_PC, range_=range_)
