"""walk-forward 백테스트 단위 테스트."""
import numpy as np
import pandas as pd

from src.backtest.walkforward import (
    run_walkforward,
    _summarize,
    WalkForwardWindow,
)


def _make_ohlcv(n: int = 800, seed: int = 42):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    op = close * (1 + rng.uniform(-0.005, 0.005, n))
    vol = rng.integers(1_000_000, 5_000_000, n)
    idx = pd.date_range("2020-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": op, "High": high, "Low": low, "Close": close, "Volume": vol},
        index=idx,
    )


def _strategy_cfg():
    return {
        "buy": {"rsi_below": 40, "price_above_sma200": True,
                "macd_bullish": True, "min_volume_ratio": 1.0},
        "sell": {"rsi_above": 75, "stop_loss_atr_mult": 2.0,
                 "take_profit_atr_mult": 3.0, "break_below_sma50": True,
                 "break_below_avg_cost_mult": 0.92},
        "risk": {"atr_period": 14, "risk_per_trade": 0.02, "max_position_size": 0.15},
        "screening": {"min_avg_volume": 100_000, "min_price": 5, "lookback_days": 800},
    }


def test_walkforward_runs_with_sufficient_data():
    history = {f"T{i}": _make_ohlcv(seed=i) for i in range(3)}
    result = run_walkforward(
        history=history,
        strategy_cfg=_strategy_cfg(),
        test_window_years=1.0,
        step_months=12,
        initial_capital=100_000,
    )
    assert len(result.windows) >= 1


def test_walkforward_raises_on_short_data():
    short = {f"T{i}": _make_ohlcv(n=300, seed=i) for i in range(2)}
    try:
        run_walkforward(short, _strategy_cfg())
        assert False, "should have raised ValueError"
    except ValueError:
        pass


def test_summary_keys():
    windows = [
        WalkForwardWindow(start_date="2020-01-01", end_date="2020-12-31",
                          metrics={"sharpe": 1.2, "max_drawdown_pct": -10, "win_rate_pct": 45,
                                   "profit_factor": 1.5, "total_return_pct": 15, "cagr_pct": 15},
                          n_trades=20, final_capital=115_000),
        WalkForwardWindow(start_date="2021-01-01", end_date="2021-12-31",
                          metrics={"sharpe": 0.8, "max_drawdown_pct": -15, "win_rate_pct": 40,
                                   "profit_factor": 1.3, "total_return_pct": 10, "cagr_pct": 10},
                          n_trades=18, final_capital=110_000),
    ]
    summary = _summarize(windows)
    for k in ("sharpe", "max_drawdown_pct", "win_rate_pct", "profit_factor"):
        assert k in summary
        assert "mean" in summary[k]
        assert "std" in summary[k]


def test_summary_empty_windows():
    assert _summarize([]) == {}


def test_summary_mean_correct():
    windows = [
        WalkForwardWindow("2020", "2021", {"sharpe": 1.0}, 10, 100_000),
        WalkForwardWindow("2021", "2022", {"sharpe": 3.0}, 10, 100_000),
    ]
    summary = _summarize(windows)
    assert summary["sharpe"]["mean"] == 2.0
