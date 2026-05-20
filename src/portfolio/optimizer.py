"""Inverse-volatility 기반 risk parity (simplest form).

각 자산의 60일 변동성에 반비례하는 가중치 → 변동성 동등화.
mean-variance가 아닌 risk-only → 미래 수익 예측 불필요.
"""
from __future__ import annotations
from typing import Dict, List, Optional

import pandas as pd


def inverse_volatility_weights(
    history: Dict[str, pd.DataFrame],
    tickers: List[str],
    window: int = 60,
    min_weight: float = 0.01,
) -> Optional[Dict[str, float]]:
    """변동성 역수 가중치 (합 1.0).

    Args:
        history: {ticker: OHLCV DataFrame}
        tickers: 가중치 계산 대상
        window: 변동성 측정 영업일
        min_weight: 최소 가중치 (분산 보장)

    Returns:
        {ticker: weight}. 데이터 부족 시 None.
    """
    available = [
        t for t in tickers
        if t in history and len(history[t]) >= window + 1
    ]
    if not available:
        return None

    vols: Dict[str, float] = {}
    for t in available:
        returns = history[t]["Close"].pct_change().iloc[-window:]
        vol = float(returns.std())
        if pd.isna(vol) or vol <= 0:
            continue
        vols[t] = vol

    if not vols:
        return None

    inv = {t: 1.0 / v for t, v in vols.items()}
    total = sum(inv.values())
    weights = {t: v / total for t, v in inv.items()}

    # min_weight floor + 정규화
    weights = {t: max(w, min_weight) for t, w in weights.items()}
    s = sum(weights.values())
    return {t: w / s for t, w in weights.items()}


def compare_actual_vs_target(
    holdings: List[dict],
    current_prices: Dict[str, float],
    target_weights: Dict[str, float],
) -> List[Dict]:
    """현재 비중 vs 권장 비중 + 조정 액션."""
    total_value = sum(
        current_prices.get(h["ticker"], 0) * h["shares"] for h in holdings
    )
    if total_value <= 0:
        return []

    out: List[Dict] = []
    holding_set = {h["ticker"] for h in holdings}

    for h in holdings:
        t = h["ticker"]
        price = current_prices.get(t, 0)
        actual = (price * h["shares"]) / total_value if total_value > 0 else 0
        target = target_weights.get(t, 0)
        diff = actual - target

        if abs(diff) < 0.02:
            action = "유지"
        elif diff > 0:
            action = f"-{diff * 100:.1f}%p 감축"
        else:
            action = f"+{-diff * 100:.1f}%p 증액"

        out.append({
            "ticker": t,
            "actual_pct": round(actual * 100, 2),
            "target_pct": round(target * 100, 2),
            "diff_pct": round(diff * 100, 2),
            "action": action,
        })

    # 보유 안 한 target 종목도 (option)
    for t, w in target_weights.items():
        if t not in holding_set and w >= 0.05:  # 5%+ 추천
            out.append({
                "ticker": t,
                "actual_pct": 0.0,
                "target_pct": round(w * 100, 2),
                "diff_pct": round(-w * 100, 2),
                "action": f"+{w * 100:.1f}%p 신규 (참고)",
            })

    return sorted(out, key=lambda x: -abs(x["diff_pct"]))


def portfolio_risk_score(
    weights: Dict[str, float],
    history: Dict[str, pd.DataFrame],
    window: int = 60,
) -> Optional[Dict]:
    """현재 가중치의 portfolio 변동성 추정 (단순 가중평균, 상관 무시)."""
    contribs = []
    for t, w in weights.items():
        if t not in history or len(history[t]) < window + 1:
            continue
        vol = float(history[t]["Close"].pct_change().iloc[-window:].std())
        if pd.isna(vol):
            continue
        contribs.append({"ticker": t, "weight": w, "vol": vol, "contribution": w * vol})

    if not contribs:
        return None
    total_vol_approx = sum(c["contribution"] for c in contribs)
    return {
        "approx_daily_vol_pct": round(total_vol_approx * 100, 2),
        "approx_annual_vol_pct": round(total_vol_approx * (252 ** 0.5) * 100, 2),
        "top_contributors": sorted(contribs, key=lambda x: -x["contribution"])[:5],
    }
