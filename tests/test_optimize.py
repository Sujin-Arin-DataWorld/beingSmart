"""grid search optimizer 단위 테스트."""
from src.backtest.optimize import _set_nested, rank_results, OptimizeResult


def test_set_nested_simple():
    cfg = {"buy": {"rsi_below": 40}}
    _set_nested(cfg, "buy.rsi_below", 35)
    assert cfg["buy"]["rsi_below"] == 35


def test_set_nested_deep():
    cfg = {"a": {"b": {"c": 1}}}
    _set_nested(cfg, "a.b.c", 99)
    assert cfg["a"]["b"]["c"] == 99


def test_rank_results_filters_low_trades():
    rs = [
        OptimizeResult(params={"x": 1}, metrics={"sharpe": 3.0}, n_trades=5),    # 필터링
        OptimizeResult(params={"x": 2}, metrics={"sharpe": 1.5}, n_trades=30),
        OptimizeResult(params={"x": 3}, metrics={"sharpe": 2.0}, n_trades=20),
    ]
    ranked = rank_results(rs, criterion="sharpe", min_trades=10)
    assert len(ranked) == 2
    assert ranked[0].metrics["sharpe"] == 2.0  # 가장 큰 sharpe + 트레이드 통과
    assert ranked[1].metrics["sharpe"] == 1.5


def test_rank_results_empty_when_all_filtered():
    rs = [
        OptimizeResult(params={}, metrics={"sharpe": 3.0}, n_trades=5),
    ]
    assert rank_results(rs, criterion="sharpe", min_trades=10) == []


def test_rank_different_criterion():
    rs = [
        OptimizeResult(params={"x": 1}, metrics={"sharpe": 1.0, "profit_factor": 2.5}, n_trades=20),
        OptimizeResult(params={"x": 2}, metrics={"sharpe": 2.0, "profit_factor": 1.5}, n_trades=20),
    ]
    by_sharpe = rank_results(rs, criterion="sharpe")
    by_pf = rank_results(rs, criterion="profit_factor")
    assert by_sharpe[0].params["x"] == 2
    assert by_pf[0].params["x"] == 1
