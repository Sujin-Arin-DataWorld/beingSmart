"""Paper trading 상태 관리."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import yaml


def _empty_state(initial_capital: float) -> Dict:
    return {
        "initial_capital": float(initial_capital),
        "cash_usd": float(initial_capital),
        "holdings": [],
        "trades": [],
        "started_date": datetime.now().strftime("%Y-%m-%d"),
    }


def load_paper_state(path: Path, initial_capital: float = 100_000.0) -> Dict:
    if not path.exists():
        return _empty_state(initial_capital)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data:
        return _empty_state(initial_capital)
    data.setdefault("initial_capital", float(initial_capital))
    data.setdefault("cash_usd", float(initial_capital))
    data.setdefault("holdings", [])
    data.setdefault("trades", [])
    data.setdefault("started_date", datetime.now().strftime("%Y-%m-%d"))
    return data


def save_paper_state(path: Path, state: Dict) -> None:
    path.write_text(yaml.safe_dump(state, default_flow_style=False), encoding="utf-8")


def add_trade(
    state: Dict,
    ticker: str,
    action: str,
    shares: float,
    price: float,
    date_str: str,
    reason: str = "",
) -> None:
    state["trades"].append({
        "date": date_str,
        "ticker": ticker,
        "action": action,
        "shares": float(shares),
        "price": float(price),
        "value": float(shares * price),
        "reason": reason,
    })


def compute_paper_pnl(state: Dict, current_prices: Dict[str, float]) -> Dict:
    """현재 paper 계좌 P&L."""
    holding_value = 0.0
    unrealized = 0.0
    for h in state.get("holdings", []):
        t = h["ticker"]
        price = current_prices.get(t, h.get("avg_cost", 0.0))
        mv = price * h["shares"]
        holding_value += mv
        unrealized += (price - h["avg_cost"]) * h["shares"]

    cash = state.get("cash_usd", 0.0)
    total_equity = cash + holding_value
    initial = state.get("initial_capital", 1.0)
    total_return_pct = (total_equity / initial - 1) * 100 if initial > 0 else 0.0

    # 실현 손익 (trades에서 매도-매수 매칭은 복잡 — 단순 합계)
    realized = 0.0
    buy_costs: Dict[str, float] = {}
    buy_shares: Dict[str, float] = {}
    for trade in state.get("trades", []):
        t = trade["ticker"]
        if trade["action"] == "BUY":
            buy_costs[t] = buy_costs.get(t, 0.0) + trade["value"]
            buy_shares[t] = buy_shares.get(t, 0.0) + trade["shares"]
        elif trade["action"] == "SELL":
            avg_cost = buy_costs.get(t, 0.0) / buy_shares.get(t, 1.0) if buy_shares.get(t, 0) > 0 else 0
            realized += (trade["price"] - avg_cost) * trade["shares"]

    return {
        "cash": cash,
        "holding_value": holding_value,
        "total_equity": total_equity,
        "unrealized_pnl": unrealized,
        "realized_pnl": realized,
        "total_return_pct": total_return_pct,
        "n_holdings": len(state.get("holdings", [])),
        "n_trades": len(state.get("trades", [])),
    }
