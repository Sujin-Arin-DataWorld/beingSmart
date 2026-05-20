"""매수/매도 룰 적용. config.yaml의 파라미터로 동작."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass
class BuySignal:
    ticker: str
    price: float
    rsi: float
    macd_hist: float
    sma_200: float
    sma_50: float
    atr: float
    vol_ratio: float
    suggested_stop: float
    suggested_target: float
    reasons: List[str] = field(default_factory=list)


@dataclass
class SellSignal:
    ticker: str
    price: float
    rsi: float
    reasons: List[str] = field(default_factory=list)


def check_buy(ticker: str, df: pd.DataFrame, strategy_cfg: dict) -> Optional[BuySignal]:
    """매수 후보면 BuySignal, 아니면 None."""
    if len(df) < 200:
        return None
    last = df.iloc[-1]

    screening = strategy_cfg["screening"]
    if last["Close"] < screening["min_price"]:
        return None
    if pd.isna(last["vol_avg_20"]) or last["vol_avg_20"] < screening["min_avg_volume"]:
        return None

    required = ["sma_200", "rsi_14", "macd_hist", "atr_14", "vol_ratio"]
    if any(pd.isna(last[k]) for k in required):
        return None

    rules = strategy_cfg["buy"]
    sell_cfg = strategy_cfg["sell"]
    passed: List[str] = []

    if last["Close"] > last["sma_200"]:
        passed.append("종가 > SMA(200)")
    else:
        return None

    rsi_val = float(last["rsi_14"])
    if rsi_val < rules["rsi_below"]:
        passed.append(f"RSI={rsi_val:.1f} < {rules['rsi_below']}")
    else:
        return None

    # MACD: 히스토그램 양수 또는 직전 3봉 내 음→양 전환
    hist = float(last["macd_hist"])
    macd_ok = False
    if hist > 0:
        prior = df["macd_hist"].iloc[-4:-1] if len(df) >= 4 else pd.Series([], dtype=float)
        if (prior < 0).any():
            macd_ok = True
            passed.append("MACD 골든크로스")
        else:
            macd_ok = True
            passed.append(f"MACD hist={hist:.3f} > 0")
    if not macd_ok:
        return None

    vol_r = float(last["vol_ratio"])
    if vol_r >= rules["min_volume_ratio"]:
        passed.append(f"거래량 {vol_r:.2f}x")
    else:
        return None

    price = float(last["Close"])
    atr_val = float(last["atr_14"])
    stop = price - atr_val * sell_cfg["stop_loss_atr_mult"]
    target = price + atr_val * sell_cfg["take_profit_atr_mult"]

    return BuySignal(
        ticker=ticker,
        price=price,
        rsi=rsi_val,
        macd_hist=hist,
        sma_200=float(last["sma_200"]),
        sma_50=float(last["sma_50"]) if not pd.isna(last["sma_50"]) else 0.0,
        atr=atr_val,
        vol_ratio=vol_r,
        suggested_stop=round(stop, 2),
        suggested_target=round(target, 2),
        reasons=passed,
    )


def check_sell(ticker: str, df: pd.DataFrame, holding: dict, strategy_cfg: dict) -> Optional[SellSignal]:
    """보유 종목의 매도 신호. 신호 없으면 None."""
    if len(df) < 50:
        return None
    last = df.iloc[-1]
    rules = strategy_cfg["sell"]

    price = float(last["Close"])
    reasons: List[str] = []

    rsi_val = float(last["rsi_14"]) if not pd.isna(last["rsi_14"]) else 50.0
    if rsi_val > rules["rsi_above"]:
        reasons.append(f"RSI {rsi_val:.1f} > {rules['rsi_above']} 과매수")

    sma_50 = float(last["sma_50"]) if not pd.isna(last["sma_50"]) else None
    if rules.get("break_below_sma50") and sma_50 and price < sma_50:
        reasons.append(f"SMA(50)=${sma_50:.2f} 이탈")

    atr_val = float(last["atr_14"]) if not pd.isna(last["atr_14"]) else None
    avg_cost = float(holding.get("avg_cost", 0))

    if atr_val and avg_cost > 0:
        atr_stop = avg_cost - atr_val * rules["stop_loss_atr_mult"]
        if price <= atr_stop:
            reasons.append(f"ATR 손절선 ${atr_stop:.2f} 도달")
        atr_target = avg_cost + atr_val * rules["take_profit_atr_mult"]
        if price >= atr_target:
            reasons.append(f"ATR 익절선 ${atr_target:.2f} 도달")

    if avg_cost > 0 and price < avg_cost * rules["break_below_avg_cost_mult"]:
        loss_pct = (price / avg_cost - 1) * 100
        reasons.append(f"평단가 대비 {loss_pct:+.1f}% 안전망")

    if not reasons:
        return None
    return SellSignal(ticker=ticker, price=price, rsi=rsi_val, reasons=reasons)
