"""시장 regime 분류기 — VIX + SPY 200SMA + breadth 기반.

매수·매도 룰의 활성도와 신호 점수의 multiplier 결정.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Regime(str, Enum):
    BULL = "BULL"           # 강세장 — 매수 룰 풀 적용
    CHOPPY = "CHOPPY"       # 횡보 — 매수 보수적, RSI 임계치 -5
    BEAR = "BEAR"           # 약세장 — 신규 매수 비활성, 매도 우선
    RISK_OFF = "RISK_OFF"   # 패닉 — 모든 진입 disable


@dataclass
class RegimeAssessment:
    regime: Regime
    vix: Optional[float] = None
    sp500_change_5d_pct: Optional[float] = None
    spy_above_sma200: Optional[bool] = None
    breadth_ratio: Optional[float] = None
    reasons: List[str] = field(default_factory=list)


def classify(
    macro: Dict[str, Dict],
    breadth_ratio: Optional[float] = None,
    *,
    risk_off_vix: float = 30.0,
    risk_off_sp_5d: float = -7.0,
    choppy_vix: float = 20.0,
    choppy_breadth: float = 0.40,
) -> RegimeAssessment:
    """매크로 + breadth로 regime 분류. 우선순위: RISK_OFF > BEAR > CHOPPY > BULL."""
    vix_data = macro.get("VIX")
    sp_data = macro.get("SP500")

    vix = vix_data["price"] if vix_data else None
    sp_5d = sp_data["change_5d_pct"] if sp_data else None
    spy_above = sp_data["above_sma_200"] if sp_data else None

    reasons: List[str] = []

    # Tier 1: Risk-Off
    if vix is not None and vix > risk_off_vix:
        reasons.append(f"VIX={vix:.1f} > {risk_off_vix}")
        return RegimeAssessment(Regime.RISK_OFF, vix, sp_5d, spy_above, breadth_ratio, reasons)
    if sp_5d is not None and sp_5d <= risk_off_sp_5d:
        reasons.append(f"S&P 5일 {sp_5d:+.1f}% 급락")
        return RegimeAssessment(Regime.RISK_OFF, vix, sp_5d, spy_above, breadth_ratio, reasons)

    # Tier 2: Bear (장기 추세 이탈)
    if spy_above is False:
        reasons.append("S&P < SMA(200) — 장기 추세 약화")
        return RegimeAssessment(Regime.BEAR, vix, sp_5d, spy_above, breadth_ratio, reasons)

    # Tier 3: Choppy
    choppy = False
    if vix is not None and vix > choppy_vix:
        reasons.append(f"VIX={vix:.1f} > {choppy_vix} (변동성 확대)")
        choppy = True
    if breadth_ratio is not None and breadth_ratio < choppy_breadth:
        reasons.append(f"breadth {breadth_ratio:.2f} < {choppy_breadth} (시장 폭 약함)")
        choppy = True
    if choppy:
        return RegimeAssessment(Regime.CHOPPY, vix, sp_5d, spy_above, breadth_ratio, reasons)

    # Default: Bull
    reasons.append("VIX 안정, S&P 200일선 위")
    return RegimeAssessment(Regime.BULL, vix, sp_5d, spy_above, breadth_ratio, reasons)


def regime_buy_modifier(regime: Regime) -> Dict:
    """regime별 매수 룰 동작 변경."""
    return {
        Regime.BULL: {"active": True, "rsi_adjustment": 0, "score_multiplier": 1.00},
        Regime.CHOPPY: {"active": True, "rsi_adjustment": -5, "score_multiplier": 0.70},
        Regime.BEAR: {"active": False, "rsi_adjustment": -10, "score_multiplier": 0.30},
        Regime.RISK_OFF: {"active": False, "rsi_adjustment": -100, "score_multiplier": 0.00},
    }[regime]


def regime_sell_urgency(regime: Regime) -> float:
    """regime별 매도 긴급도 0~1 (1 = 즉시 매도)."""
    return {
        Regime.BULL: 0.30,
        Regime.CHOPPY: 0.55,
        Regime.BEAR: 0.85,
        Regime.RISK_OFF: 1.00,
    }[regime]
