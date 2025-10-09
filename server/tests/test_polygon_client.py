import pytest

from app.services.polygon_client import PolygonClient


@pytest.mark.asyncio
async def test_get_agg_bars_returns_dataframe():
    client = PolygonClient(api_key="")
    try:
        df = await client.get_agg_bars("QQQ", multiplier=5, lookback=20)
        assert not df.empty
        assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)
    finally:
        await client.close()
