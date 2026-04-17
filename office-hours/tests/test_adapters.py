"""Adapter tests with mocked httpx. No network."""
from __future__ import annotations

import httpx
import pytest

from adapters.fred import FredClient, FredSeries
from adapters.yahoo import YahooClient, YahooSeries


@pytest.mark.asyncio
async def test_fred_fetch_series_parses_observations():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "series_id=BAMLH0A0HYM2" in str(request.url)
        return httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2024-01-02", "value": "3.50"},
                    {"date": "2024-01-03", "value": "."},  # missing
                    {"date": "2024-01-04", "value": "3.75"},
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fred = FredClient(api_key="test", client=client)
        s = await fred.fetch_series(FredSeries.HY_OAS)

    assert len(s) == 2
    assert s.iloc[0] == 3.50
    assert s.iloc[-1] == 3.75


@pytest.mark.asyncio
async def test_fred_net_liquidity_ffills_weekly_walcl_onto_daily():
    def handler(request: httpx.Request) -> httpx.Response:
        series_id = dict(request.url.params)["series_id"]
        if series_id == FredSeries.WALCL:
            obs = [{"date": "2024-01-03", "value": "7500000"}]  # Wed only
        elif series_id == FredSeries.TGA:
            obs = [
                {"date": "2024-01-03", "value": "700000"},
                {"date": "2024-01-04", "value": "710000"},
                {"date": "2024-01-05", "value": "720000"},
            ]
        elif series_id == FredSeries.RRP:
            obs = [
                {"date": "2024-01-03", "value": "500000"},
                {"date": "2024-01-04", "value": "490000"},
                {"date": "2024-01-05", "value": "480000"},
            ]
        else:
            obs = []
        return httpx.Response(200, json={"observations": obs})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fred = FredClient(api_key="test", client=client)
        net = await fred.fetch_net_liquidity()

    # WALCL = 7.5M was only on Wed; it should forward-fill onto Thu/Fri.
    assert len(net) == 3
    assert net.iloc[0] == 7500000 - 700000 - 500000
    assert net.iloc[-1] == 7500000 - 720000 - 480000


@pytest.mark.asyncio
async def test_yahoo_fetch_close_parses_chart_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "timestamp": [1704153600, 1704240000],
                            "indicators": {"quote": [{"close": [18.5, 19.1]}]},
                        }
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        yf = YahooClient(client=client)
        s = await yf.fetch_close(YahooSeries.VIX)

    assert len(s) == 2
    assert s.iloc[-1] == 19.1


@pytest.mark.asyncio
async def test_yahoo_term_structure_ratio_aligns_indexes():
    def handler(request: httpx.Request) -> httpx.Response:
        symbol = str(request.url).split("/chart/")[1].split("?")[0]
        if symbol == YahooSeries.VIX:
            closes = [20.0, 25.0]
        else:
            closes = [22.0, 23.0]
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "timestamp": [1704153600, 1704240000],
                            "indicators": {"quote": [{"close": closes}]},
                        }
                    ]
                }
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        yf = YahooClient(client=client)
        ratio = await yf.fetch_term_structure_ratio()

    # contango first day (22/20=1.1), backwardation second day (23/25=0.92 -> kill-switch)
    assert ratio.iloc[0] == pytest.approx(1.1)
    assert ratio.iloc[-1] == pytest.approx(0.92)
