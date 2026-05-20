"""매수 신호 강도 점수화 (0~100).

여러 요인을 가중합. config.yaml의 가중치로 조정 가능.
점수 높은 순으로 정렬.
"""
from __future__ import annotations
from typing import Dict, Optional

from src.regime.classifier import Regime, regime_buy_modifier


DEFAULT_WEIGHTS: Dict[str, float] = {
    "rsi": 0.20,        # RSI depth — 깊은 과매도일수록 ↑
    "macd": 0.15,       # MACD 히스토그램 강도
    "volume": 0.10,     # 거래량 ratio
    "trend": 0.15,      # SMA200 거리 (가까울수록 신뢰도 ↑, 너무 가까우면 위험)
    "regime": 0.25,     # 시장 regime 정합성
    "macro": 0.15,      # VIX 등 거시 안정성
}


def _rsi_score(rsi: float) -> float:
    """RSI 낮을수록 점수 높음. 20~40 구간 가중."""
    if rsi <= 20:
        return 100.0
    if rsi <= 30:
        return 90.0 - (rsi - 20) * 1.0   # 20→90, 30→80
    if rsi <= 35:
        return 80.0 - (rsi - 30) * 3.0   # 30→80, 35→65
    if rsi <= 40:
        return 65.0 - (rsi - 35) * 3.0   # 35→65, 40→50
    return max(0.0, 50.0 - (rsi - 40) * 2.5)


def _macd_score(hist: float, price: float) -> float:
    """histogram 크기 / 가격 % → 강도."""
    if price <= 0:
        return 0.0
    pct = abs(hist) / price * 100
    return min(100.0, pct * 50.0)  # 2%면 100


def _volume_score(ratio: float) -> float:
    """1.0 = 50, 2.0 이상 = 100."""
    if ratio < 1.0:
        return ratio * 50.0
    return min(100.0, 50.0 + (ratio - 1.0) * 50.0)


def _trend_score(price: float, sma_200: float) -> float:
    """SMA200 위에서, 0~5% 거리가 sweet spot."""
    if sma_200 <= 0:
        return 0.0
    dist_pct = (price / sma_200 - 1) * 100
    if dist_pct < 0:
        return 0.0
    if dist_pct <= 5:
        return 50.0 + dist_pct * 10.0       # 0→50, 5→100
    if dist_pct <= 15:
        return 100.0 - (dist_pct - 5) * 3.0  # 5→100, 15→70
    return max(0.0, 70.0 - (dist_pct - 15) * 2.0)


def _regime_score(regime: Optional[Regime]) -> float:
    if regime is None:
        return 50.0
    return {
        Regime.BULL: 100.0,
        Regime.CHOPPY: 55.0,
        Regime.BEAR: 20.0,
        Regime.RISK_OFF: 0.0,
    }[regime]


def _macro_score(vix: Optional[float]) -> float:
    """VIX 낮을수록 매수 신뢰 ↑."""
    if vix is None:
        return 50.0
    if vix < 15:
        return 100.0
    if vix < 20:
        return 80.0
    if vix < 25:
        return 55.0
    if vix < 30:
        return 25.0
    return 0.0


def score_buy_signal(
    signal: dict,
    regime: Optional[Regime] = None,
    vix: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """0~100 점수 + 항목별 breakdown.

    Returns:
        {
          "total": 75.3,
          "rsi": 90.0, "macd": ..., "volume": ..., "trend": ..., "regime": ..., "macro": ...,
        }
    """
    w = weights or DEFAULT_WEIGHTS

    rsi_s = _rsi_score(signal["rsi"])
    macd_s = _macd_score(signal["macd_hist"], signal["price"])
    vol_s = _volume_score(signal["vol_ratio"])
    trend_s = _trend_score(signal["price"], signal["sma_200"])
    regime_s = _regime_score(regime)
    macro_s = _macro_score(vix)

    total = (
        rsi_s * w["rsi"]
        + macd_s * w["macd"]
        + vol_s * w["volume"]
        + trend_s * w["trend"]
        + regime_s * w["regime"]
        + macro_s * w["macro"]
    )

    # regime 비활성이면 multiplier 0 적용
    if regime is not None:
        mod = regime_buy_modifier(regime)
        total *= mod["score_multiplier"]

    return {
        "total": round(total, 1),
        "rsi": round(rsi_s, 1),
        "macd": round(macd_s, 1),
        "volume": round(vol_s, 1),
        "trend": round(trend_s, 1),
        "regime": round(regime_s, 1),
        "macro": round(macro_s, 1),
    }
