"""포트폴리오 상관·집중·다양성 분석."""
from __future__ import annotations
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def compute_correlation_matrix(
    history: Dict[str, pd.DataFrame],
    tickers: List[str],
    window: int = 60,
) -> Optional[pd.DataFrame]:
    """주어진 티커들의 최근 N영업일 일간 수익률 correlation."""
    available = [t for t in tickers if t in history and len(history[t]) >= window + 1]
    if len(available) < 2:
        return None

    returns = pd.DataFrame({
        t: history[t]["Close"].pct_change().iloc[-window:].reset_index(drop=True)
        for t in available
    })
    return returns.corr()


def sector_exposure(
    holdings: List[dict],
    fundamentals: Dict[str, Dict],
    current_prices: Dict[str, float],
) -> Dict[str, float]:
    """섹터별 비중 (시장가치 기준, 합 1.0)."""
    exposure: Dict[str, float] = {}
    for h in holdings:
        t = h["ticker"]
        sector = (fundamentals.get(t) or {}).get("sector") or "Unknown"
        price = current_prices.get(t)
        if price is None:
            continue
        value = price * h["shares"]
        exposure[sector] = exposure.get(sector, 0.0) + value

    total = sum(exposure.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in exposure.items()}


def beta_weighted_exposure(
    holdings: List[dict],
    fundamentals: Dict[str, Dict],
    current_prices: Dict[str, float],
) -> Optional[float]:
    """시장가치 가중 평균 beta. None이면 데이터 부족."""
    weighted_sum = 0.0
    total = 0.0
    for h in holdings:
        t = h["ticker"]
        beta = (fundamentals.get(t) or {}).get("beta")
        price = current_prices.get(t)
        if beta is None or price is None:
            continue
        value = price * h["shares"]
        weighted_sum += beta * value
        total += value
    if total == 0:
        return None
    return weighted_sum / total


def diversification_score(
    corr_matrix: Optional[pd.DataFrame],
    sector_pct: Dict[str, float],
) -> Dict:
    """0~100. 100 = 잘 분산.

    composite = 0.5 × (1 - avg_corr) × 100 + 0.5 × (1 - max_sector) × 100
    """
    if corr_matrix is not None and len(corr_matrix) >= 2:
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        stacked = upper.stack()
        avg_corr = float(stacked.mean()) if len(stacked) > 0 else 0.0
        corr_score = max(0.0, min(100.0, (1 - avg_corr) * 100))
    else:
        avg_corr = None
        corr_score = 50.0

    if sector_pct:
        max_sector = max(sector_pct.values())
        sector_score = max(0.0, min(100.0, (1 - max_sector) * 100))
    else:
        max_sector = 0.0
        sector_score = 50.0

    total = corr_score * 0.5 + sector_score * 0.5
    return {
        "total": round(total, 1),
        "avg_correlation": round(avg_corr, 3) if avg_corr is not None else None,
        "max_sector_pct": round(max_sector * 100, 2),
        "corr_score": round(corr_score, 1),
        "sector_score": round(sector_score, 1),
    }


def correlation_with_existing(
    candidate: str,
    holdings_tickers: List[str],
    corr_matrix: Optional[pd.DataFrame],
) -> Optional[float]:
    """후보 종목이 보유 종목들과의 평균 상관. 높을수록 분산 효과 ↓."""
    if corr_matrix is None or candidate not in corr_matrix.columns:
        return None
    relevant = [t for t in holdings_tickers if t in corr_matrix.columns and t != candidate]
    if not relevant:
        return None
    return float(corr_matrix.loc[candidate, relevant].mean())
