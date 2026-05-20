"""백테스트 성과 지표 — Sharpe, max DD, win rate, profit factor 등."""
from __future__ import annotations
import math
from typing import Dict

from src.backtest.engine import BacktestResult


def compute_metrics(result: BacktestResult) -> Dict[str, float]:
    eq = result.equity_curve
    initial = result.initial_capital
    final = result.final_capital
    trades = result.trades

    if len(eq) < 2:
        return {"error": "insufficient data"}

    n_days = max((eq.index[-1] - eq.index[0]).days, 1)
    n_years = n_days / 365.25

    total_return = (final / initial - 1) if initial > 0 else 0.0
    cagr = ((final / initial) ** (1 / n_years) - 1) if (final > 0 and initial > 0 and n_years > 0) else -1.0

    daily_ret = eq.pct_change().dropna()
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = (daily_ret.mean() / daily_ret.std()) * math.sqrt(252)
    else:
        sharpe = 0.0

    downside = daily_ret[daily_ret < 0]
    if len(downside) > 1 and downside.std() > 0:
        sortino = (daily_ret.mean() / downside.std()) * math.sqrt(252)
    else:
        sortino = 0.0

    cummax = eq.cummax()
    dd = (eq - cummax) / cummax
    max_dd = float(dd.min()) if not dd.empty else 0.0

    n_trades = len(trades)
    if n_trades > 0:
        wins = [t for t in trades if t.pnl is not None and t.pnl > 0]
        losses = [t for t in trades if t.pnl is not None and t.pnl <= 0]
        win_rate = len(wins) / n_trades
        avg_win_pct = (sum(t.pnl_pct for t in wins) / len(wins)) if wins else 0.0
        avg_loss_pct = (sum(t.pnl_pct for t in losses) / len(losses)) if losses else 0.0
        gross_win = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (999.99 if gross_win > 0 else 0.0)
        held_vals = [t.bars_held for t in trades if t.bars_held is not None]
        avg_bars_held = (sum(held_vals) / len(held_vals)) if held_vals else 0.0
    else:
        win_rate = avg_win_pct = avg_loss_pct = profit_factor = avg_bars_held = 0.0

    expectancy = (
        (win_rate * avg_win_pct) + ((1 - win_rate) * avg_loss_pct)
        if n_trades > 0 else 0.0
    )

    return {
        "total_return_pct": round(total_return * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "n_trades": n_trades,
        "win_rate_pct": round(win_rate * 100, 2),
        "avg_win_pct": round(avg_win_pct, 2),
        "avg_loss_pct": round(avg_loss_pct, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy_pct": round(expectancy, 2),
        "avg_bars_held": round(avg_bars_held, 1),
    }


def format_trade_table(result: BacktestResult, top_n: int = 20) -> str:
    trades = result.trades[-top_n:]
    lines = [
        "| 티커 | 진입 | 청산 | 보유 | 수익% | 청산사유 |",
        "|---|---|---|---:|---:|---|",
    ]
    for t in trades:
        lines.append(
            f"| {t.ticker} | "
            f"{t.entry_date.strftime('%Y-%m-%d') if t.entry_date else '-'} | "
            f"{t.exit_date.strftime('%Y-%m-%d') if t.exit_date else '-'} | "
            f"{t.bars_held or 0}d | "
            f"{(t.pnl_pct or 0):+.2f}% | "
            f"{t.exit_reason or '-'} |"
        )
    return "\n".join(lines)


def format_equity_ascii(result: BacktestResult, width: int = 50, rows: int = 30) -> str:
    eq = result.equity_curve
    if len(eq) < 2:
        return "(insufficient data)"
    step = max(1, len(eq) // rows)
    sampled = eq.iloc[::step]
    max_val = float(sampled.max())
    min_val = min(float(result.initial_capital), float(sampled.min()))
    span = max(max_val - min_val, 1.0)
    lines = []
    for d, v in sampled.items():
        bar_len = int((float(v) - min_val) / span * width)
        bar = "█" * max(0, bar_len)
        lines.append(f"{d.strftime('%Y-%m-%d')} ${float(v):>12,.0f}  {bar}")
    return "\n".join(lines)
