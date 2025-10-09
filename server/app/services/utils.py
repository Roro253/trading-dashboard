from __future__ import annotations

import pandas as pd


def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Volume-weighted average price computed cumulatively without lookahead."""

    required = {"high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        missing = ", ".join(sorted(required - set(df.columns)))
        raise ValueError(f"DataFrame missing required columns: {missing}")

    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_volume = df["volume"].cumsum()
    vwap = (typical_price * df["volume"]).cumsum() / cumulative_volume
    return vwap


def ema(df: pd.DataFrame, span: int, price_col: str = "close") -> pd.Series:
    """Exponential moving average of the specified price column."""

    if price_col not in df.columns:
        raise ValueError(f"DataFrame missing column: {price_col}")
    return df[price_col].ewm(span=span, adjust=False).mean()


def rsi(df: pd.DataFrame, period: int = 14, price_col: str = "close") -> pd.Series:
    """Relative Strength Index computed using Wilder's smoothing."""

    if price_col not in df.columns:
        raise ValueError(f"DataFrame missing column: {price_col}")

    prices = df[price_col]
    delta = prices.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    rsi_series = 100 - (100 / (1 + rs.fillna(0.0)))
    rsi_series = rsi_series.fillna(50.0)
    return rsi_series


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range without forward-looking bias."""

    required = {"high", "low", "close"}
    if not required.issubset(df.columns):
        missing = ", ".join(sorted(required - set(df.columns)))
        raise ValueError(f"DataFrame missing required columns: {missing}")

    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    atr_series = true_range.ewm(alpha=1 / period, adjust=False).mean()
    return atr_series.fillna(true_range)
