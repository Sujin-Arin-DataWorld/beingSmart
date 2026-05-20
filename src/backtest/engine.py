"""백테스트 엔진 — historical OHLCV에 룰 시뮬레이션.

설계:
- 매일 종가 기준으로 매도 체크, 매수 후보 추출
- 진입은 다음 거래일 **시가** (look-ahead 방지)
- 슬리피지 적용 (디폴트 0.1% — 매수 +0.1%, 매도 -0.1%)
- position size = equity / max_positions (단순 균등)
- 200일 워밍업 후 시뮬레이션 시작
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd

from src.indicators.technical import compute_all
from src.screener.rules import check_buy


@dataclass
class Trade:
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    entry_reason: str = ""
    exit_date: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    bars_held: Optional[int] = None


@dataclass
class BacktestResult:
    trades: List[Trade]
    equity_curve: pd.Series
    initial_capital: float
    final_capital: float
    config_snapshot: dict
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    n_universe: int = 0


def _normalize_ts(date_str: str, ref_index: pd.DatetimeIndex) -> pd.Timestamp:
    ts = pd.Timestamp(date_str)
    if ref_index.tz is not None and ts.tz is None:
        ts = ts.tz_localize(ref_index.tz)
    return ts


def _exit_check(
    trade: Trade,
    row: pd.Series,
    today: pd.Timestamp,
    strategy_cfg: dict,
    max_hold_days: int,
) -> Optional[str]:
    """매도 사유 결정. None이면 보유 유지."""
    sell = strategy_cfg["sell"]
    price = float(row["Close"])
    atr_val = float(row["atr_14"]) if not pd.isna(row["atr_14"]) else None
    sma_50 = float(row["sma_50"]) if not pd.isna(row["sma_50"]) else None
    rsi_val = float(row["rsi_14"]) if not pd.isna(row["rsi_14"]) else 50.0

    if atr_val:
        stop = trade.entry_price - atr_val * sell["stop_loss_atr_mult"]
        if price <= stop:
            return f"ATR stop ${stop:.2f}"
        target = trade.entry_price + atr_val * sell["take_profit_atr_mult"]
        if price >= target:
            return f"ATR target ${target:.2f}"

    if rsi_val > sell["rsi_above"]:
        return f"RSI {rsi_val:.1f} 과매수"

    if sma_50 and price < sma_50 * 0.98:
        return f"SMA50 ${sma_50:.2f} 이탈"

    if price < trade.entry_price * sell["break_below_avg_cost_mult"]:
        loss_pct = (price / trade.entry_price - 1) * 100
        return f"안전망 {loss_pct:+.1f}%"

    held_days = (today - trade.entry_date).days
    if held_days > max_hold_days:
        return f"max hold {max_hold_days}d"

    return None


def run_backtest(
    history: Dict[str, pd.DataFrame],
    strategy_cfg: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    initial_capital: float = 100_000.0,
    max_positions: int = 10,
    slippage_pct: float = 0.001,
    max_hold_days: int = 60,
) -> BacktestResult:
    if not history:
        raise ValueError("history is empty")

    enriched = {t: compute_all(df) for t, df in history.items()}

    all_dates_set = set()
    for df in enriched.values():
        all_dates_set.update(df.index)
    all_dates = sorted(all_dates_set)
    if not all_dates:
        raise ValueError("no trading days in history")

    ref_idx = enriched[next(iter(enriched))].index

    if start_date:
        ts_start = _normalize_ts(start_date, ref_idx)
        all_dates = [d for d in all_dates if d >= ts_start]
    if end_date:
        ts_end = _normalize_ts(end_date, ref_idx)
        all_dates = [d for d in all_dates if d <= ts_end]

    if len(all_dates) > 200:
        all_dates = all_dates[200:]
    if len(all_dates) < 2:
        raise ValueError("기간이 너무 짧음 (200일 워밍업 후 < 2일)")

    date_to_idx = {d: i for i, d in enumerate(all_dates)}

    cash = float(initial_capital)
    positions: Dict[str, Trade] = {}
    closed: List[Trade] = []
    equity_history: List[Tuple[pd.Timestamp, float]] = []

    for i, today in enumerate(all_dates):
        # 1. 매도 처리 (오늘 종가)
        to_exit: List[Tuple[str, float, str]] = []
        for ticker, trade in positions.items():
            df = enriched.get(ticker)
            if df is None or today not in df.index:
                continue
            row = df.loc[today]
            reason = _exit_check(trade, row, today, strategy_cfg, max_hold_days)
            if reason:
                to_exit.append((ticker, float(row["Close"]), reason))

        for ticker, raw_price, reason in to_exit:
            trade = positions.pop(ticker)
            exit_price = raw_price * (1 - slippage_pct)
            trade.exit_date = today
            trade.exit_price = exit_price
            trade.exit_reason = reason
            trade.pnl = (exit_price - trade.entry_price) * trade.shares
            trade.pnl_pct = (exit_price / trade.entry_price - 1) * 100 if trade.entry_price else 0.0
            entry_idx = date_to_idx.get(trade.entry_date)
            trade.bars_held = (i - entry_idx) if entry_idx is not None else None
            cash += exit_price * trade.shares
            closed.append(trade)

        # 2. 매수 후보 추출 (오늘 종가 기준 신호)
        empty_slots = max_positions - len(positions)
        if empty_slots > 0 and cash > 1000 and i + 1 < len(all_dates):
            candidates = []
            for ticker, df in enriched.items():
                if ticker in positions or today not in df.index:
                    continue
                df_t = df.loc[:today]
                if len(df_t) < 200:
                    continue
                sig = check_buy(ticker, df_t, strategy_cfg)
                if sig:
                    candidates.append(sig)
            candidates.sort(key=lambda s: s.rsi)

            # 3. 다음날 시가로 진입
            next_date = all_dates[i + 1]
            current_equity = cash + sum(
                float(enriched[t].loc[today, "Close"]) * p.shares
                for t, p in positions.items()
                if today in enriched[t].index
            )
            slot_size = current_equity / max_positions

            for sig in candidates[:empty_slots]:
                df = enriched[sig.ticker]
                if next_date not in df.index:
                    continue
                next_open = float(df.loc[next_date, "Open"])
                entry_price = next_open * (1 + slippage_pct)
                target_value = min(slot_size, cash * 0.95)
                if target_value < entry_price:
                    continue
                shares = target_value / entry_price
                cost = shares * entry_price
                if cost > cash:
                    continue
                cash -= cost
                positions[sig.ticker] = Trade(
                    ticker=sig.ticker,
                    entry_date=next_date,
                    entry_price=entry_price,
                    shares=shares,
                    entry_reason="; ".join(sig.reasons),
                )

        # 4. equity 기록
        equity = cash
        for ticker, p in positions.items():
            df = enriched.get(ticker)
            if df is not None and today in df.index:
                equity += float(df.loc[today, "Close"]) * p.shares
        equity_history.append((today, equity))

    # 마지막 날 미청산 청산
    last_day = all_dates[-1]
    for ticker in list(positions.keys()):
        trade = positions.pop(ticker)
        df = enriched.get(ticker)
        if df is None or last_day not in df.index:
            continue
        raw_price = float(df.loc[last_day, "Close"])
        exit_price = raw_price * (1 - slippage_pct)
        trade.exit_date = last_day
        trade.exit_price = exit_price
        trade.exit_reason = "EOT"
        trade.pnl = (exit_price - trade.entry_price) * trade.shares
        trade.pnl_pct = (exit_price / trade.entry_price - 1) * 100 if trade.entry_price else 0.0
        entry_idx = date_to_idx.get(trade.entry_date)
        trade.bars_held = (len(all_dates) - 1 - entry_idx) if entry_idx is not None else None
        cash += exit_price * trade.shares
        closed.append(trade)

    eq = pd.Series(
        data=[v for _, v in equity_history],
        index=pd.DatetimeIndex([d for d, _ in equity_history]),
    )

    return BacktestResult(
        trades=closed,
        equity_curve=eq,
        initial_capital=initial_capital,
        final_capital=cash,
        config_snapshot=strategy_cfg,
        start_date=all_dates[0],
        end_date=all_dates[-1],
        n_universe=len(enriched),
    )
