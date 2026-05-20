"""펀더멘털 데이터 + 어닝 캘린더.

yfinance Ticker.info와 get_earnings_dates() 활용. 비공식 API라 누락 가능 — 누락 시 보수적 처리.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional

import yfinance as yf


def fetch_fundamentals(ticker: str) -> Dict:
    """단일 종목 펀더멘털. 실패 시 ticker만 담긴 dict."""
    out: Dict = {"ticker": ticker}
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return out

    out.update({
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "eps": info.get("trailingEps"),
        "beta": info.get("beta"),
        "dividend_yield": info.get("dividendYield"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    })
    return out


def fetch_fundamentals_batch(tickers: List[str]) -> Dict[str, Dict]:
    """다수 종목. yfinance batch info 미지원이라 개별 호출."""
    return {t: fetch_fundamentals(t) for t in tickers}


def fetch_next_earnings(ticker: str, lookahead_days: int = 30) -> Optional[datetime]:
    """다가오는 가장 가까운 어닝 일자. lookahead_days 초과면 None."""
    try:
        df = yf.Ticker(ticker).get_earnings_dates(limit=8)
    except Exception:
        return None
    if df is None or df.empty:
        return None

    tz = df.index.tz
    now = datetime.now(tz) if tz else datetime.now()
    upcoming = df.index[df.index > now]
    if len(upcoming) == 0:
        return None
    nearest = upcoming.min().to_pydatetime()
    delta_days = (nearest - now).days
    if delta_days < 0 or delta_days > lookahead_days:
        return None
    return nearest


def days_to_earnings(ticker: str, lookahead_days: int = 30) -> Optional[int]:
    next_date = fetch_next_earnings(ticker, lookahead_days)
    if next_date is None:
        return None
    now = datetime.now(next_date.tzinfo) if next_date.tzinfo else datetime.now()
    return (next_date - now).days


def is_in_earnings_blackout(ticker: str, blackout_days: int = 7) -> bool:
    """어닝 임박이면 True (신규 매수 차단). 알 수 없으면 False."""
    d = days_to_earnings(ticker, lookahead_days=max(blackout_days * 2, 14))
    if d is None:
        return False
    return 0 <= d <= blackout_days


def fundamental_health_score(fund: Dict) -> Optional[float]:
    """간이 펀더멘털 헬스 0~100.

    - PE 합리적 범위 (5~40)
    - market cap > $1B
    - dividend 또는 양호한 PE
    """
    score = 50.0
    pe = fund.get("trailing_pe") or fund.get("forward_pe")
    mcap = fund.get("market_cap")

    if pe is not None and pe > 0:
        if 8 <= pe <= 25:
            score += 25
        elif 5 <= pe <= 35:
            score += 10
        elif pe > 100:
            score -= 20

    if mcap is not None:
        if mcap >= 10_000_000_000:
            score += 15  # 대형주 안정성
        elif mcap >= 1_000_000_000:
            score += 5
        else:
            score -= 15  # 소형주 리스크

    div = fund.get("dividend_yield")
    if div is not None and 0.01 <= div <= 0.08:
        score += 10  # 합리적 배당

    return max(0.0, min(100.0, score))
