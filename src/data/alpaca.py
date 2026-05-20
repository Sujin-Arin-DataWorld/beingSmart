"""Alpaca historical 데이터 fallback.

yfinance 누락 종목 보완. 무료 가입: https://alpaca.markets/
환경변수 ALPACA_API_KEY, ALPACA_SECRET 필요. 없으면 자동 skip.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import pandas as pd


def is_alpaca_available() -> bool:
    return bool(os.environ.get("ALPACA_API_KEY")) and bool(os.environ.get("ALPACA_SECRET"))


def fetch_history_alpaca(tickers: List[str], days: int = 250) -> Dict[str, pd.DataFrame]:
    """Alpaca REST API로 일봉 다운로드.

    Free tier: IEX 데이터 (지연 15분), 5년 history.

    Returns:
        {ticker: DataFrame[Open, High, Low, Close, Volume]}.
        키 없거나 다운로드 실패 시 빈 dict.
    """
    if not is_alpaca_available() or not tickers:
        return {}

    try:
        import requests
    except ImportError:
        return {}

    api_key = os.environ["ALPACA_API_KEY"]
    secret = os.environ["ALPACA_SECRET"]

    end_dt = datetime.now(timezone.utc) - timedelta(minutes=20)  # 무료 IEX 지연
    start_dt = end_dt - timedelta(days=int(days * 1.5))

    base_url = "https://data.alpaca.markets/v2/stocks/bars"
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret}

    out: Dict[str, pd.DataFrame] = {}
    batch_size = 100

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        params = {
            "symbols": ",".join(batch),
            "timeframe": "1Day",
            "start": start_dt.strftime("%Y-%m-%d"),
            "end": end_dt.strftime("%Y-%m-%d"),
            "limit": 10000,
            "adjustment": "split",
            "feed": "iex",
        }
        try:
            resp = requests.get(base_url, params=params, headers=headers, timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json().get("bars", {})
        except Exception:
            continue

        for ticker, bars in data.items():
            if not bars:
                continue
            df = pd.DataFrame(bars)
            if df.empty or "t" not in df.columns:
                continue
            df["t"] = pd.to_datetime(df["t"])
            df = df.set_index("t").rename(columns={
                "o": "Open", "h": "High", "l": "Low",
                "c": "Close", "v": "Volume",
            })
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            if len(df) >= 50:
                out[ticker] = df

    return out


def fetch_with_fallback(tickers: List[str], days: int = 250) -> Dict[str, pd.DataFrame]:
    """yfinance 우선, 누락 종목은 Alpaca로 보완."""
    from src.data.fetcher import fetch_history as yfinance_fetch

    primary = yfinance_fetch(tickers, days=days)

    if not is_alpaca_available():
        return primary

    missing = [t for t in tickers if t not in primary]
    if not missing:
        return primary

    fallback = fetch_history_alpaca(missing, days=days)
    if fallback:
        primary.update(fallback)
    return primary
