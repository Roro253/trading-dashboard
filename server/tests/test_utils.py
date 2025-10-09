import pandas as pd
import pytest

from app.services import utils


def _sample_df() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=10, freq="5T")
    data = {
        "open": [100 + i for i in range(10)],
        "high": [100.5 + i for i in range(10)],
        "low": [99.5 + i for i in range(10)],
        "close": [100.2 + i for i in range(10)],
        "volume": [1_000 + (i * 10) for i in range(10)],
    }
    return pd.DataFrame(data, index=idx)


def test_compute_vwap_matches_manual_calc():
    df = _sample_df()
    vwap = utils.compute_vwap(df)
    manual = ((df["high"] + df["low"] + df["close"]) / 3 * df["volume"]).cumsum() / df["volume"].cumsum()
    assert vwap.iloc[-1] == pytest.approx(manual.iloc[-1])


def test_ema_matches_pandas():
    df = _sample_df()
    ema_span = 3
    result = utils.ema(df, span=ema_span)
    expected = df["close"].ewm(span=ema_span, adjust=False).mean()
    assert result.equals(expected)


def test_rsi_reasonable_bounds():
    df = _sample_df()
    rsi_values = utils.rsi(df)
    assert (rsi_values.between(0, 100)).all()
    assert rsi_values.iloc[-1] > 50


def test_atr_positive_values():
    df = _sample_df()
    atr_values = utils.atr(df)
    assert (atr_values > 0).all()
