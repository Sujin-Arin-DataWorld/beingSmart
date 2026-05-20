"""Ticker → 자산 클래스 매핑 + 자산 클래스별 노출."""
from __future__ import annotations
from typing import Dict, List, Optional


ASSET_CLASS_BY_TICKER = {
    # 채권
    "TLT": "Bond", "IEF": "Bond", "SHY": "Bond", "LQD": "Bond",
    "HYG": "Bond", "AGG": "Bond", "BND": "Bond", "TIP": "Bond",
    "MUB": "Bond", "EMB": "Bond",
    # 원자재
    "GLD": "Commodity", "IAU": "Commodity",
    "SLV": "Commodity", "DBA": "Commodity",
    "USO": "Commodity", "UNG": "Commodity", "DBC": "Commodity",
    "PALL": "Commodity", "PPLT": "Commodity",
    # 통화
    "UUP": "Currency", "FXE": "Currency", "FXY": "Currency",
    "FXB": "Currency", "FXC": "Currency", "FXA": "Currency",
    # 해외 주식
    "EFA": "International", "EEM": "International",
    "VWO": "International", "VXUS": "International",
    "FXI": "International", "MCHI": "International",
    "EWJ": "International", "INDA": "International",
    # 부동산
    "XLRE": "RealEstate", "VNQ": "RealEstate", "IYR": "RealEstate",
}


def get_asset_class(ticker: str, sector: Optional[str] = None) -> str:
    """티커의 자산 클래스. 매핑에 없으면 'Equity'."""
    if ticker in ASSET_CLASS_BY_TICKER:
        return ASSET_CLASS_BY_TICKER[ticker]
    return "Equity"


def asset_class_exposure(
    holdings: List[dict],
    current_prices: Dict[str, float],
    fundamentals: Optional[Dict[str, Dict]] = None,
) -> Dict[str, float]:
    """자산 클래스별 비중 (시장가치 기준, 합 1.0)."""
    exposure: Dict[str, float] = {}
    for h in holdings:
        t = h["ticker"]
        price = current_prices.get(t)
        if price is None:
            continue
        value = price * h["shares"]
        sector = ((fundamentals or {}).get(t) or {}).get("sector")
        cls = get_asset_class(t, sector)
        exposure[cls] = exposure.get(cls, 0.0) + value

    total = sum(exposure.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in exposure.items()}


def diversification_warnings(exposure: Dict[str, float]) -> List[str]:
    """자산 클래스 분산 경고."""
    warnings: List[str] = []
    equity_pct = exposure.get("Equity", 0) + exposure.get("International", 0)
    bond_pct = exposure.get("Bond", 0)

    if equity_pct > 0.90:
        warnings.append(f"⚠️ 주식 노출 {equity_pct * 100:.0f}% — 채권/원자재 분산 검토")
    if bond_pct == 0 and equity_pct > 0.7:
        warnings.append("📌 채권 노출 0% — 위험 분산 부족")
    if exposure.get("Commodity", 0) == 0 and equity_pct > 0.85:
        warnings.append("📌 원자재 0% — 인플레이션 헤지 부족")

    return warnings
