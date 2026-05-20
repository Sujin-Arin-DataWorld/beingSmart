"""inverse-volatility risk parity 단위 테스트."""
import numpy as np
import pandas as pd

from src.portfolio.optimizer import (
    inverse_volatility_weights,
    compare_actual_vs_target,
    portfolio_risk_score,
)


def _df(returns_seed, n=100, base=100):
    rng = np.random.default_rng(returns_seed)
    rets = rng.normal(0, returns_seed * 0.01, n)
    close = base * (1 + rets).cumprod()
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close,
         "Volume": [1_000_000] * n}, index=idx,
    )


def test_inverse_vol_weights_sum_to_one():
    history = {"A": _df(1), "B": _df(2), "C": _df(3)}
    w = inverse_volatility_weights(history, ["A", "B", "C"], window=60)
    assert w is not None
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_lower_vol_gets_higher_weight():
    history = {"LOWVOL": _df(1), "HIGHVOL": _df(5)}
    w = inverse_volatility_weights(history, ["LOWVOL", "HIGHVOL"], window=60)
    assert w["LOWVOL"] > w["HIGHVOL"]


def test_insufficient_history_returns_none():
    history = {"A": _df(1, n=10)}
    w = inverse_volatility_weights(history, ["A"], window=60)
    assert w is None


def test_min_weight_applied():
    history = {"A": _df(1), "B": _df(2), "C": _df(3)}
    w = inverse_volatility_weights(history, ["A", "B", "C"], window=60, min_weight=0.20)
    for v in w.values():
        assert v >= 0.20 - 1e-6


def test_compare_actual_vs_target_basic():
    holdings = [{"ticker": "A", "shares": 100}, {"ticker": "B", "shares": 50}]
    prices = {"A": 100, "B": 200}  # A: 10000, B: 10000 → 50:50
    target = {"A": 0.7, "B": 0.3}
    result = compare_actual_vs_target(holdings, prices, target)
    a = next(r for r in result if r["ticker"] == "A")
    b = next(r for r in result if r["ticker"] == "B")
    assert abs(a["actual_pct"] - 50.0) < 0.01
    assert abs(b["actual_pct"] - 50.0) < 0.01
    assert "증액" in a["action"]
    assert "감축" in b["action"]


def test_compare_within_threshold_hold():
    holdings = [{"ticker": "A", "shares": 100}]
    prices = {"A": 100}
    target = {"A": 1.0}
    result = compare_actual_vs_target(holdings, prices, target)
    assert result[0]["action"] == "유지"


def test_portfolio_risk_score():
    history = {"A": _df(1), "B": _df(2)}
    weights = {"A": 0.5, "B": 0.5}
    risk = portfolio_risk_score(weights, history, window=60)
    assert risk is not None
    assert risk["approx_daily_vol_pct"] > 0
    assert risk["approx_annual_vol_pct"] > risk["approx_daily_vol_pct"]
