"""Paper trading 매일 실행 — 매수 추천을 가상 계좌에 실집행, daily P&L 추적.

실거래에 영향 없음. 룰의 실시간 alpha 측정용.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import yaml

from src.data.fetcher import fetch_history
from src.data.macro import fetch_macro_snapshot, compute_breadth
from src.indicators.technical import compute_all
from src.screener.rules import check_buy, check_sell
from src.screener.scoring import score_buy_signal
from src.regime.classifier import classify as classify_regime
from src.portfolio.sizing import compute_position_size
from src.papertrade.state import (
    load_paper_state, save_paper_state, add_trade, compute_paper_pnl,
)


def run_papertrade(
    root: Path,
    initial_capital: float = 100_000.0,
    top_n_buys: int = 3,
) -> Dict:
    config = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    universe = yaml.safe_load((root / "universe.yaml").read_text(encoding="utf-8"))
    state_path = root / "paper_state.yaml"
    state = load_paper_state(state_path, initial_capital)

    tickers = sorted(set(
        (universe.get("etf") or [])
        + (universe.get("stocks") or [])
        + [h["ticker"] for h in state.get("holdings", [])]
    ))
    history = fetch_history(tickers, days=config["strategy"]["screening"]["lookback_days"])
    enriched = {t: compute_all(df) for t, df in history.items()}

    today_str = datetime.now().strftime("%Y-%m-%d")
    strategy_cfg = config["strategy"]
    current_prices = {t: float(enriched[t].iloc[-1]["Close"]) for t in enriched}

    # 1. 보유 종목 매도 체크
    sells_today = 0
    for holding in list(state["holdings"]):
        t = holding["ticker"]
        if t not in enriched:
            continue
        df = enriched[t]
        sig = check_sell(t, df, holding, strategy_cfg)
        if sig:
            price = current_prices[t]
            proceeds = price * holding["shares"]
            state["cash_usd"] += proceeds
            add_trade(state, t, "SELL", holding["shares"], price, today_str,
                      reason="; ".join(sig.reasons))
            state["holdings"].remove(holding)
            sells_today += 1

    # 2. regime + 매수 후보
    macro = fetch_macro_snapshot(days=250)
    breadth = compute_breadth(history)
    regime_assessment = classify_regime(macro, breadth_ratio=breadth)
    regime = regime_assessment.regime
    vix = (macro.get("VIX") or {}).get("price")

    candidates = []
    min_score = config.get("scoring", {}).get("min_score_threshold", 0)
    weights = config.get("scoring", {}).get("weights")
    for t, df in enriched.items():
        if any(h["ticker"] == t for h in state["holdings"]):
            continue
        sig = check_buy(t, df, strategy_cfg)
        if not sig:
            continue
        score = score_buy_signal(sig.__dict__, regime=regime, vix=vix, weights=weights)
        if score["total"] < min_score:
            continue
        candidates.append((sig, score["total"]))
    candidates.sort(key=lambda x: -x[1])

    # 3. Top N 가상 매수
    holding_mv = sum(current_prices.get(h["ticker"], 0) * h["shares"]
                     for h in state["holdings"])
    total_capital = state["cash_usd"] + holding_mv
    risk_per = config.get("sizing", {}).get("risk_per_trade", 0.02)
    max_pos = config.get("sizing", {}).get("max_position_pct", 0.15)

    buys_today = 0
    for sig, score in candidates[:top_n_buys * 2]:  # 여유 있게
        if buys_today >= top_n_buys:
            break
        sizing = compute_position_size(
            entry_price=sig.price,
            stop_price=sig.suggested_stop,
            capital=total_capital,
            risk_per_trade=risk_per,
            max_position_pct=max_pos,
        )
        if sizing["shares"] <= 0:
            continue
        cost = sizing["shares"] * sig.price
        if cost > state["cash_usd"]:
            continue
        state["cash_usd"] -= cost
        state["holdings"].append({
            "ticker": sig.ticker,
            "shares": int(sizing["shares"]),
            "avg_cost": float(sig.price),
            "purchase_date": today_str,
            "stop_price": float(sig.suggested_stop),
            "target_price": float(sig.suggested_target),
            "entry_score": float(score),
        })
        add_trade(state, sig.ticker, "BUY", sizing["shares"], sig.price, today_str,
                  reason=f"score {score:.1f}")
        buys_today += 1

    save_paper_state(state_path, state)
    pnl = compute_paper_pnl(state, current_prices)
    pnl["sells_today"] = sells_today
    pnl["buys_today"] = buys_today
    pnl["regime"] = regime.value
    pnl["candidates_count"] = len(candidates)
    return {"state": state, "pnl": pnl, "regime_assessment": regime_assessment}
