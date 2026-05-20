"""ATR 기반 자동 position sizing.

리스크 기반: shares = (capital × risk_per_trade) / (entry - stop)
최대 비중 제약: max_position_pct.
둘 중 작은 값 사용.
"""
from __future__ import annotations
from typing import Dict


def compute_position_size(
    entry_price: float,
    stop_price: float,
    capital: float,
    risk_per_trade: float = 0.02,
    max_position_pct: float = 0.15,
    min_shares: int = 1,
) -> Dict:
    """매수 추천 수량.

    Args:
        entry_price: 진입가
        stop_price: 손절가 (반드시 entry_price 미만)
        capital: 가용 자본 (cash + 현재 보유 시장가치)
        risk_per_trade: 자본 대비 트레이드당 최대 손실 비율
        max_position_pct: 단일 종목 최대 비중
        min_shares: 최소 매수 수량

    Returns:
        {
          "shares": int,
          "position_value": float,
          "risk_amount": float,
          "position_pct": float,
          "limited_by": "risk" | "max_position_pct" | "below_min_shares" | "invalid_input",
        }
    """
    if entry_price <= 0 or stop_price <= 0 or stop_price >= entry_price or capital <= 0:
        return {
            "shares": 0, "position_value": 0.0, "risk_amount": 0.0,
            "position_pct": 0.0, "limited_by": "invalid_input",
        }

    risk_per_share = entry_price - stop_price
    max_risk = capital * risk_per_trade
    risk_based_shares = max_risk / risk_per_share

    max_position_value = capital * max_position_pct
    cap_based_shares = max_position_value / entry_price

    if risk_based_shares <= cap_based_shares:
        shares_float = risk_based_shares
        limited_by = "risk"
    else:
        shares_float = cap_based_shares
        limited_by = "max_position_pct"

    shares = int(shares_float)

    if shares < min_shares:
        return {
            "shares": 0, "position_value": 0.0, "risk_amount": 0.0,
            "position_pct": 0.0, "limited_by": "below_min_shares",
        }

    position_value = shares * entry_price
    risk_amount = shares * risk_per_share
    position_pct = position_value / capital

    return {
        "shares": shares,
        "position_value": round(position_value, 2),
        "risk_amount": round(risk_amount, 2),
        "position_pct": round(position_pct, 4),
        "limited_by": limited_by,
    }


def reward_to_risk_ratio(entry_price: float, stop_price: float, target_price: float) -> float:
    """리스크 1당 보상. ATR 기반 stop/target 사용 시 보통 1.5."""
    risk = entry_price - stop_price
    reward = target_price - entry_price
    if risk <= 0:
        return 0.0
    return reward / risk
