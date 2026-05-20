"""yfinance 데이터 수집. batch download 사용."""
from __future__ import annotations
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf


def fetch_history(tickers: List[str], days: int = 250) -> Dict[str, pd.DataFrame]:
    """여러 티커의 일봉 OHLCV.

    Returns:
        {ticker: DataFrame[Open, High, Low, Close, Volume]}
        데이터가 50봉 미만이거나 다운로드 실패한 티커는 결과에서 제외.
    """
    if not tickers:
        return {}

    df = yf.download(
        tickers=" ".join(tickers),
        period=f"{days}d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    out: Dict[str, pd.DataFrame] = {}
    # 단일 티커일 경우 yfinance는 group_by를 무시함
    if len(tickers) == 1:
        t = tickers[0]
        sub = df.dropna()
        if len(sub) >= 50:
            out[t] = sub
        return out

    for t in tickers:
        try:
            sub = df[t].dropna()
        except (KeyError, AttributeError):
            continue
        if len(sub) >= 50:
            out[t] = sub
    return out


def fetch_current_price(ticker: str) -> Optional[float]:
    try:
        df = yf.Ticker(ticker).history(period="2d", auto_adjust=True)
        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception:
        return None
