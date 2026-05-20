"""drawdown 추적 단위 테스트."""
from pathlib import Path
import tempfile

from src.portfolio.drawdown import (
    append_equity_point,
    compute_drawdowns,
    load_equity_history,
    should_disable_new_entries,
    save_equity_history,
)


def test_empty_history_returns_none():
    assert compute_drawdowns([]) is None


def test_single_point_zero_dd():
    history = [{"date": "2026-01-01", "equity": 100_000}]
    m = compute_drawdowns(history)
    assert m["current_dd_pct"] == 0.0
    assert m["max_dd_pct"] == 0.0


def test_max_dd_from_peak():
    history = [
        {"date": "2026-01-01", "equity": 100_000},
        {"date": "2026-01-02", "equity": 120_000},   # peak
        {"date": "2026-01-03", "equity": 90_000},    # -25% from peak
        {"date": "2026-01-04", "equity": 110_000},   # 회복 (still -8.33%)
    ]
    m = compute_drawdowns(history)
    assert abs(m["max_dd_pct"] - (-25.0)) < 0.01
    assert m["current_dd_pct"] < 0  # 110k < peak 120k


def test_full_recovery_zero_current_dd():
    history = [
        {"date": "2026-01-01", "equity": 100_000},
        {"date": "2026-01-02", "equity": 80_000},
        {"date": "2026-01-03", "equity": 120_000},  # new peak
    ]
    m = compute_drawdowns(history)
    assert m["current_dd_pct"] == 0.0


def test_should_disable_below_threshold():
    m = {"current_dd_pct": -20.0}
    assert should_disable_new_entries(m, threshold_pct=-15.0) is True
    assert should_disable_new_entries(m, threshold_pct=-25.0) is False


def test_should_disable_none_history():
    assert should_disable_new_entries(None) is False


def test_should_disable_above_threshold():
    m = {"current_dd_pct": -5.0}
    assert should_disable_new_entries(m, threshold_pct=-15.0) is False


def test_append_overwrites_same_date():
    with tempfile.TemporaryDirectory() as tmpd:
        path = Path(tmpd) / "eq.yaml"
        append_equity_point(path, "2026-01-01", 100_000)
        append_equity_point(path, "2026-01-01", 105_000)  # overwrite
        loaded = load_equity_history(path)
        assert len(loaded) == 1
        assert loaded[0]["equity"] == 105_000


def test_append_sorted():
    with tempfile.TemporaryDirectory() as tmpd:
        path = Path(tmpd) / "eq.yaml"
        append_equity_point(path, "2026-01-03", 110_000)
        append_equity_point(path, "2026-01-01", 100_000)
        append_equity_point(path, "2026-01-02", 105_000)
        loaded = load_equity_history(path)
        dates = [e["date"] for e in loaded]
        assert dates == sorted(dates)


def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpd:
        path = Path(tmpd) / "eq.yaml"
        data = [{"date": "2026-01-01", "equity": 100_000.5}]
        save_equity_history(path, data)
        loaded = load_equity_history(path)
        assert loaded == data
