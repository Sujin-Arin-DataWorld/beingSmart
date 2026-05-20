"""기본 지표 sanity check. pytest 권장."""
import numpy as np
import pandas as pd

from src.indicators.technical import sma, ema, rsi, macd, atr, compute_all


def _synthetic_ohlcv(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    high = close + rng.uniform(0, 2, n)
    low = close - rng.uniform(0, 2, n)
    vol = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({
        "Open": close, "High": high, "Low": low, "Close": close, "Volume": vol,
    })


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    assert sma(s, 3).iloc[-1] == 4.0


def test_rsi_range():
    df = _synthetic_ohlcv()
    r = rsi(df["Close"], 14).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_macd_keys():
    df = _synthetic_ohlcv()
    m = macd(df["Close"])
    assert set(m.keys()) == {"macd", "signal", "hist"}


def test_atr_positive():
    df = _synthetic_ohlcv()
    a = atr(df["High"], df["Low"], df["Close"]).dropna()
    assert (a > 0).all()


def test_compute_all_columns():
    df = _synthetic_ohlcv()
    out = compute_all(df)
    for col in ["sma_50", "sma_200", "rsi_14", "macd_hist", "atr_14", "vol_ratio"]:
        assert col in out.columns
