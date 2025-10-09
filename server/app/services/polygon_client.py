from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
import numpy as np
import pandas as pd
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

_POLYGON_BASE_URL = "https://api.polygon.io"
_DEFAULT_TIMEOUT = 10.0
_MAX_RETRIES = 3
_BACKOFF_SECONDS = 1.5


@dataclass(slots=True)
class _RequestConfig:
    method: str
    path: str
    params: Optional[Dict[str, Any]] = None


class PolygonClient:
    """Async Polygon.io client with graceful fallbacks for local development."""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.polygon_api_key
        if not self._api_key:
            logger.warning("polygon.api_key.missing", message="Falling back to synthetic data")

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        self._client = httpx.AsyncClient(
            base_url=_POLYGON_BASE_URL,
            headers=headers,
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "PolygonClient":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def get_agg_bars(
        self,
        symbol: str,
        *,
        timespan: str = "minute",
        multiplier: int = 5,
        lookback: int = 300,
    ) -> pd.DataFrame:
        """Return a DataFrame of recent aggregate bars in UTC."""

        symbol = symbol.upper()
        end_dt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        start_dt = end_dt - _timespan_delta(timespan, multiplier * lookback)

        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": lookback,
        }

        config = _RequestConfig(
            method="GET",
            path=f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_dt.date()}/{end_dt.date()}",
            params=params,
        )

        payload = await self._request(config)
        if payload and payload.get("results"):
            df = _bars_to_frame(payload["results"], symbol)
            if df.empty:
                return _synthetic_bars(symbol, multiplier, lookback, end_dt, timespan)
            return df.tail(lookback)

        logger.info("polygon.agg.fallback", symbol=symbol)
        return _synthetic_bars(symbol, multiplier, lookback, end_dt, timespan)

    async def get_previous_close(self, symbol: str) -> Dict[str, Any]:
        """Return previous close metadata for the symbol."""

        symbol = symbol.upper()
        config = _RequestConfig(
            method="GET",
            path=f"/v2/aggs/ticker/{symbol}/prev",
            params={"adjusted": "true"},
        )

        payload = await self._request(config)
        if payload and payload.get("results"):
            result = payload["results"][0]
            return {
                "symbol": symbol,
                "close": float(result.get("c", math.nan)),
                "volume": float(result.get("v", 0.0)),
                "timestamp": _utc_from_ms(result.get("t")),
            }

        logger.info("polygon.prev_close.fallback", symbol=symbol)
        bars = await self.get_agg_bars(symbol, multiplier=1, lookback=10)
        last_close = float(bars["close"].iloc[-1]) if not bars.empty else math.nan
        return {
            "symbol": symbol,
            "close": last_close,
            "volume": float(bars.get("volume", pd.Series([0.0])).iloc[-1]) if not bars.empty else 0.0,
            "timestamp": bars.index[-1] if not bars.empty else datetime.now(timezone.utc),
        }

    async def get_options_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Return high-level options metrics (stubbed if data unavailable)."""

        symbol = symbol.upper()
        config = _RequestConfig(
            method="GET",
            path=f"/v2/snapshot/options/{symbol}",
        )
        payload = await self._request(config)

        if payload and payload.get("status") == "OK" and payload.get("results"):
            # Polygon returns a collection of expirations; we sample the first entry for simplicity.
            first = payload["results"][0]
            iv = float(first.get("implied_volatility", 0.0))
            oi = float(first.get("open_interest", 0.0))
            volume = float(first.get("day", {}).get("volume", 0.0))
            skew = float(first.get("delta", 0.0))
            return {
                "symbol": symbol,
                "implied_volatility": iv,
                "implied_vol_rank": float(min(1.0, max(0.0, iv / 1.0))),
                "skew_proxy": skew,
                "open_interest_delta": oi,
                "volume_delta": volume,
                "depth_ok": bool(first.get("open_interest", 0) and first.get("day", {}).get("volume", 0)),
            }

        logger.info("polygon.options.fallback", symbol=symbol)
        bars = await self.get_agg_bars(symbol, multiplier=5, lookback=60)
        if bars.empty:
            return _default_options_snapshot(symbol)

        returns = bars["close"].pct_change().dropna()
        vol = float(returns.std() * math.sqrt(252 * (78 / 5))) if not returns.empty else 0.2
        ema_spread = float(abs(bars["close"].ewm(span=21, adjust=False).mean().iloc[-1] - bars["close"].ewm(span=55, adjust=False).mean().iloc[-1]))
        return {
            "symbol": symbol,
            "implied_volatility": max(vol, 0.05),
            "implied_vol_rank": float(min(1.0, vol / 1.0)),
            "skew_proxy": float(np.tanh(ema_spread / max(bars["close"].iloc[-1], 1e-6))),
            "open_interest_delta": float(bars["volume"].diff().fillna(0.0).iloc[-1]),
            "volume_delta": float(bars["volume"].iloc[-1] - bars["volume"].iloc[-2] if len(bars) > 1 else 0.0),
            "depth_ok": False,
        }

    async def _request(self, config: _RequestConfig) -> Optional[Dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._client.request(
                    config.method,
                    config.path,
                    params=config.params,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                if status == 404:
                    logger.warning("polygon.request.404", path=config.path)
                    return None
                logger.warning(
                    "polygon.request.error", attempt=attempt, path=config.path, status=status
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                logger.warning(
                    "polygon.request.transport_error", attempt=attempt, path=config.path, error=str(exc)
                )

            await asyncio.sleep(_BACKOFF_SECONDS * attempt)

        if last_error:
            logger.error("polygon.request.failed", path=config.path, error=str(last_error))
        return None


def _bars_to_frame(results: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    if not results:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "timestamp"]).set_index(
            pd.DatetimeIndex([])
        )

    frame = pd.DataFrame(results)
    rename_map = {
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "t": "timestamp",
    }
    frame = frame.rename(columns=rename_map)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    frame["symbol"] = symbol
    columns = ["timestamp", "open", "high", "low", "close", "volume", "symbol"]
    frame = frame[columns].sort_values("timestamp").reset_index(drop=True)
    frame = frame.set_index("timestamp")
    return frame


def _synthetic_bars(
    symbol: str,
    multiplier: int,
    lookback: int,
    end_dt: datetime,
    timespan: str = "minute",
) -> pd.DataFrame:
    freq = _freq_for_timespan(timespan, multiplier)
    index = pd.date_range(end=end_dt, periods=lookback, freq=freq, tz=timezone.utc)
    seed = abs(hash((symbol, lookback, multiplier))) % (2**32)
    rng = np.random.default_rng(seed)
    base_price = 100 + (seed % 100) / 100
    noise = rng.normal(0, 0.2, size=lookback).cumsum()
    close = base_price + noise
    open_prices = close + rng.normal(0, 0.05, size=lookback)
    high = np.maximum(open_prices, close) + rng.random(lookback) * 0.1
    low = np.minimum(open_prices, close) - rng.random(lookback) * 0.1
    volume = rng.integers(1_000, 5_000, size=lookback)

    frame = pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "symbol": symbol,
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def _freq_for_timespan(timespan: str, multiplier: int) -> str:
    if timespan == "minute":
        return f"{multiplier}T"
    if timespan == "hour":
        return f"{multiplier}H"
    if timespan == "day":
        return f"{multiplier}D"
    # fallback to minutes to keep data dense
    return f"{multiplier}T"


def _timespan_delta(timespan: str, steps: int) -> timedelta:
    if timespan == "minute":
        return timedelta(minutes=steps)
    if timespan == "hour":
        return timedelta(hours=steps)
    if timespan == "day":
        return timedelta(days=steps)
    return timedelta(minutes=steps)


def _utc_from_ms(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _default_options_snapshot(symbol: str) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "implied_volatility": 0.25,
        "implied_vol_rank": 0.5,
        "skew_proxy": 0.0,
        "open_interest_delta": 0.0,
        "volume_delta": 0.0,
    }
