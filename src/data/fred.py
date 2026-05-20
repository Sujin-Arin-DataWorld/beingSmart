"""FRED API 거시 경제 지표.

무료 가입: https://fred.stlouisfed.org/docs/api/api_key.html
환경변수 FRED_API_KEY. 없으면 자동 skip.

핵심 시리즈:
- UNRATE: 실업률 (월별)
- CPIAUCSL: CPI all items (월별, 전년대비 yoy로 인플레이션)
- FEDFUNDS: 정책금리 (월별)
- T10Y2Y: 10Y - 2Y Treasury spread (recession indicator)
- T10YIE: 10Y inflation expectation (BEI)
"""
from __future__ import annotations
import os
from typing import Dict, List, Optional


KEY_SERIES = {
    "UNRATE": ("실업률", "%"),
    "CPIAUCSL": ("CPI (raw)", "index"),
    "FEDFUNDS": ("정책금리", "%"),
    "T10Y2Y": ("10Y-2Y spread", "%p"),
    "T10YIE": ("10Y BEI (기대 인플레)", "%"),
}


def is_fred_available() -> bool:
    return bool(os.environ.get("FRED_API_KEY"))


def fetch_series(series_id: str, limit: int = 24) -> List[Dict]:
    """최근 limit개 데이터. 시간 오름차순."""
    if not is_fred_available():
        return []
    try:
        import requests
    except ImportError:
        return []

    api_key = os.environ["FRED_API_KEY"]
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json().get("observations", [])
    except Exception:
        return []

    out = []
    for d in data:
        try:
            v = float(d["value"]) if d.get("value") not in (".", None, "") else None
        except ValueError:
            v = None
        out.append({"date": d.get("date", ""), "value": v})
    return list(reversed(out))


def fetch_fred_snapshot() -> Dict[str, Dict]:
    """주요 시리즈 최신값 + 1년 전 비교.

    Returns:
        {series_id: {label, unit, current, current_date, year_ago, year_ago_date, yoy_change}}
    """
    if not is_fred_available():
        return {}

    snapshot: Dict[str, Dict] = {}
    for series_id, (label, unit) in KEY_SERIES.items():
        data = fetch_series(series_id, limit=24)
        if not data:
            continue
        valid = [d for d in data if d["value"] is not None]
        if not valid:
            continue
        current = valid[-1]

        # 12 데이터포인트 전 (월별이면 1년 전)
        if len(valid) >= 12:
            year_ago = valid[-12]
        else:
            year_ago = valid[0]

        # CPI는 yoy 계산 (raw index 차이가 아닌 % 변화)
        if series_id == "CPIAUCSL" and year_ago["value"] > 0:
            yoy = (current["value"] / year_ago["value"] - 1) * 100
        else:
            yoy = current["value"] - year_ago["value"]

        snapshot[series_id] = {
            "label": label,
            "unit": unit,
            "current": current["value"],
            "current_date": current["date"],
            "year_ago": year_ago["value"],
            "year_ago_date": year_ago["date"],
            "yoy_change": round(yoy, 2),
        }

    return snapshot


def recession_indicator(snapshot: Dict[str, Dict]) -> Optional[str]:
    """10Y-2Y inversion: historical 6~18개월 내 recession 신호 (단 false positive 있음)."""
    t10y2y = snapshot.get("T10Y2Y")
    if not t10y2y:
        return None
    val = t10y2y["current"]
    if val is None:
        return None
    if val < 0:
        return f"⚠️ 10Y-2Y inversion ({val:.2f}%p) — historical recession 신호 (6~18개월 lag)"
    if val < 0.3:
        return f"🟡 10Y-2Y narrow ({val:.2f}%p) — 약세 신호"
    return f"🟢 10Y-2Y healthy ({val:.2f}%p)"
