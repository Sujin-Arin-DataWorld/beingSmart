"""portfolio.yaml 로드 + 보유 종목 현황 계산."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml


def load_portfolio(path: Path) -> dict:
    if not path.exists():
        return {"cash_usd": 0.0, "holdings": []}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("cash_usd", 0.0)
    data.setdefault("holdings", [])
    return data


def compute_holding_status(
    holding: dict,
    current_price: float,
    atr: Optional[float],
    strategy_cfg: dict,
) -> dict:
    """평단·현재가·손절선·익절선·손익률을 한 번에."""
    avg = float(holding["avg_cost"])
    shares = float(holding["shares"])
    sell_cfg = strategy_cfg["sell"]

    market_value = current_price * shares
    cost_basis = avg * shares
    pnl = market_value - cost_basis
    pnl_pct = (current_price / avg - 1) * 100 if avg > 0 else 0.0

    if atr and atr > 0:
        stop_atr = avg - atr * sell_cfg["stop_loss_atr_mult"]
        target_atr = avg + atr * sell_cfg["take_profit_atr_mult"]
    else:
        stop_atr = avg * sell_cfg["break_below_avg_cost_mult"]
        target_atr = avg * (1 + sell_cfg["take_profit_atr_mult"] * 0.05)  # 폴백

    safety_stop = avg * sell_cfg["break_below_avg_cost_mult"]
    effective_stop = max(stop_atr, safety_stop)

    return {
        "ticker": holding["ticker"],
        "shares": shares,
        "avg_cost": avg,
        "current_price": current_price,
        "market_value": market_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "stop_atr": round(stop_atr, 2),
        "safety_stop": round(safety_stop, 2),
        "effective_stop": round(effective_stop, 2),
        "target_atr": round(target_atr, 2),
        "distance_to_stop_pct": (current_price / effective_stop - 1) * 100 if effective_stop > 0 else 0.0,
        "distance_to_target_pct": (target_atr / current_price - 1) * 100 if current_price > 0 else 0.0,
    }
