"""종목 catalyst 뉴스 — yfinance Ticker.news.

yfinance 응답 형식은 변동성 있음 (구/신 형식). 둘 다 안전 처리.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional

import yfinance as yf


def fetch_recent_news(ticker: str, hours: int = 72, limit: int = 5) -> List[Dict]:
    """최근 N시간 내 뉴스 헤드라인.

    Returns:
        [{"title", "publisher", "url", "published" (datetime), "hours_ago"}]
    """
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []

    now = datetime.now(timezone.utc)
    out: List[Dict] = []

    for item in raw[:20]:
        content = item.get("content") if isinstance(item.get("content"), dict) else item
        title = content.get("title") or item.get("title")
        if not title:
            continue

        published = _parse_published(content, item)
        if published is None:
            continue

        hours_ago = (now - published).total_seconds() / 3600
        if hours_ago > hours or hours_ago < 0:
            continue

        publisher = _extract_publisher(content, item)
        url = _extract_url(content, item)

        out.append({
            "title": title,
            "publisher": publisher,
            "url": url,
            "published": published,
            "hours_ago": round(hours_ago, 1),
        })

        if len(out) >= limit:
            break

    return out


def _parse_published(content: dict, item: dict) -> Optional[datetime]:
    # 신 형식: pubDate / displayTime ISO 문자열
    iso = content.get("pubDate") or content.get("displayTime")
    if isinstance(iso, str):
        try:
            return datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            pass

    # 구 형식: providerPublishTime 에폭
    ts = item.get("providerPublishTime")
    if ts:
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (TypeError, ValueError):
            pass

    return None


def _extract_publisher(content: dict, item: dict) -> str:
    provider = content.get("provider")
    if isinstance(provider, dict):
        name = provider.get("displayName")
        if name:
            return name
    return item.get("publisher") or content.get("publisher") or "Unknown"


def _extract_url(content: dict, item: dict) -> str:
    canonical = content.get("canonicalUrl")
    if isinstance(canonical, dict):
        url = canonical.get("url")
        if url:
            return url
    return item.get("link") or content.get("link") or ""


def fetch_news_batch(
    tickers: List[str], hours: int = 72, per_ticker_limit: int = 3
) -> Dict[str, List[Dict]]:
    return {t: fetch_recent_news(t, hours=hours, limit=per_ticker_limit) for t in tickers}
