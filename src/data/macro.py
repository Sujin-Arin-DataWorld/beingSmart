"""거시 변수 스냅샷 — VIX, 달러, 금리, 원자재, 지수.

매일 리포트 최상단에 표시. regime 분류기와 scoring 모듈의 입력.
"""
from __future__ import annotations
from typing import Dict, Optional
import pandas as pd
import yfinance as yf


MACRO_TICKERS: Dict[str, str] = {
    "VIX": "^VIX",           # CBOE 변동성 지수
    "DXY": "DX-Y.NYB",       # 달러 인덱스
    "Y10": "^TNX",           # 10년물 (가격 = yield × 10)
    "Y30": "^TYX",           # 30년물
    "GOLD": "GC=F",          # 금 선물
    "OIL": "CL=F",           # WTI 원유 선물
    "SP500": "^GSPC",        # S&P 500
    "DOW": "^DJI",           # 다우
    "NASDAQ": "^IXIC",       # 나스닥
}


def fetch_macro_snapshot(days: int = 250) -> Dict[str, Dict]:
    """각 거시 변수 최신 값 + 변화율 + 200SMA 위치.

    Returns:
        {
          "VIX": {"ticker": "^VIX", "price": 15.2, "change_1d_pct": ..., "above_sma_200": False},
          ...
        }
        다운로드 실패한 항목은 누락.
    """
    symbols = list(MACRO_TICKERS.values())
    df = yf.download(
        tickers=" ".join(symbols),
        period=f"{days}d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    out: Dict[str, Dict] = {}
    for name, sym in MACRO_TICKERS.items():
        try:
            sub = df[sym]["Close"].dropna()
        except (KeyError, AttributeError):
            continue
        if len(sub) < 20:
            continue

        latest = float(sub.iloc[-1])
        prev_1 = float(sub.iloc[-2]) if len(sub) >= 2 else latest
        prev_5 = float(sub.iloc[-6]) if len(sub) >= 6 else latest
        prev_20 = float(sub.iloc[-21]) if len(sub) >= 21 else latest
        sma_200: Optional[float] = (
            float(sub.rolling(200).mean().iloc[-1]) if len(sub) >= 200 else None
        )

        out[name] = {
            "ticker": sym,
            "price": latest,
            "change_1d_pct": (latest / prev_1 - 1) * 100 if prev_1 else 0.0,
            "change_5d_pct": (latest / prev_5 - 1) * 100 if prev_5 else 0.0,
            "change_20d_pct": (latest / prev_20 - 1) * 100 if prev_20 else 0.0,
            "sma_200": sma_200,
            "above_sma_200": sma_200 is not None and latest > sma_200,
        }
    return out


def compute_breadth(history: Dict[str, pd.DataFrame]) -> Optional[float]:
    """universe 종목으로 advance/decline ratio 계산.

    오늘 종가 > 어제 종가 = advance.
    Returns:
        advances / (advances + declines), 또는 None.
    """
    advances = 0
    declines = 0
    for ticker, df in history.items():
        if len(df) < 2:
            continue
        if df["Close"].iloc[-1] > df["Close"].iloc[-2]:
            advances += 1
        elif df["Close"].iloc[-1] < df["Close"].iloc[-2]:
            declines += 1
    total = advances + declines
    if total == 0:
        return None
    return advances / total
