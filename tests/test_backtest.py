"""backtest engine sanity tests — deterministic synthetic data."""
import numpy as np
import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.metrics import compute_metrics


def _make_ohlcv(n: int = 400, seed: int = 42, drift: float = 0.001, vol: float = 0.02) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    open_ = close * (1 + rng.uniform(-0.005, 0.005, n))
    volume = rng.integers(1_000_000, 5_000_000, n)
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def _strategy_cfg() -> dict:
    return {
        "buy": {
            "rsi_below": 40,
            "price_above_sma200": True,
            "macd_bullish": True,
            "min_volume_ratio": 1.0,
        },
        "sell": {
            "rsi_above": 75,
            "stop_loss_atr_mult": 2.0,
            "take_profit_atr_mult": 3.0,
            "break_below_sma50": True,
            "break_below_avg_cost_mult": 0.92,
        },
        "risk": {"atr_period": 14, "risk_per_trade": 0.02, "max_position_size": 0.15},
        "screening": {
            "min_avg_volume": 100_000,
            "min_price": 5,
            "lookback_days": 400,
        },
    }


def test_backtest_runs_to_completion():
    history = {f"T{i}": _make_ohlcv(seed=i) for i in range(3)}
    result = run_backtest(history, _strategy_cfg(), initial_capital=100_000)
    assert result.final_capital > 0
    assert result.initial_capital == 100_000
    assert result.start_date is not None
    assert result.end_date is not None


def test_metrics_keys_present():
    history = {f"T{i}": _make_ohlcv(seed=i) for i in range(3)}
    result = run_backtest(history, _strategy_cfg(), initial_capital=100_000)
    m = compute_metrics(result)
    for k in (
        "total_return_pct",
        "cagr_pct",
        "sharpe",
        "max_drawdown_pct",
        "n_trades",
        "win_rate_pct",
        "profit_factor",
    ):
        assert k in m, f"missing metric: {k}"


def test_backtest_deterministic():
    history = {f"T{i}": _make_ohlcv(seed=i) for i in range(2)}
    r1 = run_backtest(history, _strategy_cfg(), initial_capital=100_000)
    r2 = run_backtest(history, _strategy_cfg(), initial_capital=100_000)
    assert r1.final_capital == r2.final_capital
    assert len(r1.trades) == len(r2.trades)


def test_max_drawdown_is_non_positive():
    history = {f"T{i}": _make_ohlcv(seed=i) for i in range(3)}
    result = run_backtest(history, _strategy_cfg(), initial_capital=100_000)
    m = compute_metrics(result)
    assert m["max_drawdown_pct"] <= 0.0


def test_equity_curve_has_data():
    history = {f"T{i}": _make_ohlcv(seed=i) for i in range(2)}
    result = run_backtest(history, _strategy_cfg(), initial_capital=100_000)
    assert len(result.equity_curve) > 0
    assert result.equity_curve.iloc[0] > 0
