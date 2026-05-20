"""기술 지표 — pandas로 직접 계산. 외부 ta 라이브러리 미사용."""
from __future__ import annotations
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    return {
        "macd": macd_line,
        "signal": signal_line,
        "hist": macd_line - signal_line,
    }


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """OHLCV에 모든 지표 컬럼 추가."""
    out = df.copy()
    out["sma_50"] = sma(out["Close"], 50)
    out["sma_200"] = sma(out["Close"], 200)
    out["rsi_14"] = rsi(out["Close"], 14)
    m = macd(out["Close"])
    out["macd"] = m["macd"]
    out["macd_signal"] = m["signal"]
    out["macd_hist"] = m["hist"]
    out["atr_14"] = atr(out["High"], out["Low"], out["Close"], 14)
    out["vol_avg_20"] = out["Volume"].rolling(20).mean()
    out["vol_avg_5"] = out["Volume"].rolling(5).mean()
    out["vol_ratio"] = out["vol_avg_5"] / out["vol_avg_20"]
    return out
