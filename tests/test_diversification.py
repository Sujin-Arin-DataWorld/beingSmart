"""diversification 모듈 단위 테스트."""
import numpy as np
import pandas as pd

from src.portfolio.diversification import (
    compute_correlation_matrix,
    sector_exposure,
    beta_weighted_exposure,
    diversification_score,
    correlation_with_existing,
)


def _df(prices):
    n = len(prices)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": prices, "High": prices, "Low": prices, "Close": prices,
         "Volume": [1_000_000] * n},
        index=idx,
    )


def test_correlation_matrix_high_for_identical_series():
    rng = np.random.default_rng(42)
    base = np.cumsum(rng.normal(0, 1, 100)) + 100
    history = {
        "A": _df(base),
        "B": _df(base * 1.001),    # 거의 동일
    }
    corr = compute_correlation_matrix(history, ["A", "B"], window=60)
    assert corr is not None
    assert corr.loc["A", "B"] > 0.99


def test_correlation_none_for_single_ticker():
    h = {"A": _df([100.0] * 100)}
    assert compute_correlation_matrix(h, ["A"], window=60) is None


def test_sector_exposure_single_sector():
    holdings = [{"ticker": "A", "shares": 10}, {"ticker": "B", "shares": 5}]
    fund = {"A": {"sector": "Tech"}, "B": {"sector": "Tech"}}
    prices = {"A": 100, "B": 200}
    exp = sector_exposure(holdings, fund, prices)
    assert exp["Tech"] == 1.0


def test_sector_exposure_mixed_50_50():
    holdings = [{"ticker": "A", "shares": 10}, {"ticker": "B", "shares": 10}]
    fund = {"A": {"sector": "Tech"}, "B": {"sector": "Financial"}}
    prices = {"A": 100, "B": 100}
    exp = sector_exposure(holdings, fund, prices)
    assert abs(exp["Tech"] - 0.5) < 1e-9
    assert abs(exp["Financial"] - 0.5) < 1e-9


def test_beta_weighted_average():
    holdings = [{"ticker": "A", "shares": 10}, {"ticker": "B", "shares": 10}]
    fund = {"A": {"beta": 1.5}, "B": {"beta": 0.5}}
    prices = {"A": 100, "B": 100}
    beta = beta_weighted_exposure(holdings, fund, prices)
    assert abs(beta - 1.0) < 1e-9


def test_diversification_score_in_range():
    corr = pd.DataFrame({"A": [1.0, 0.3], "B": [0.3, 1.0]}, index=["A", "B"])
    sect = {"Tech": 0.5, "Financial": 0.5}
    s = diversification_score(corr, sect)
    assert 0 <= s["total"] <= 100
    assert "avg_correlation" in s


def test_high_correlation_lower_score():
    high = pd.DataFrame({"A": [1.0, 0.95], "B": [0.95, 1.0]}, index=["A", "B"])
    low = pd.DataFrame({"A": [1.0, 0.05], "B": [0.05, 1.0]}, index=["A", "B"])
    sect = {"Tech": 0.5, "Financial": 0.5}
    assert diversification_score(low, sect)["total"] > diversification_score(high, sect)["total"]


def test_concentrated_sector_lower_score():
    corr = pd.DataFrame({"A": [1.0, 0.3], "B": [0.3, 1.0]}, index=["A", "B"])
    balanced = {"Tech": 0.5, "Financial": 0.5}
    concentrated = {"Tech": 0.95, "Financial": 0.05}
    assert (
        diversification_score(corr, balanced)["total"]
        > diversification_score(corr, concentrated)["total"]
    )


def test_correlation_with_existing_average():
    corr = pd.DataFrame(
        {"A": [1.0, 0.5, 0.2], "B": [0.5, 1.0, 0.3], "C": [0.2, 0.3, 1.0]},
        index=["A", "B", "C"],
    )
    # C와 A, B의 평균 상관 = (0.2 + 0.3) / 2 = 0.25
    result = correlation_with_existing("C", ["A", "B"], corr)
    assert abs(result - 0.25) < 1e-9


def test_correlation_with_existing_none_when_no_matrix():
    assert correlation_with_existing("A", ["B"], None) is None
