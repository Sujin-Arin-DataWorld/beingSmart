"""paper trading state 관리 단위 테스트."""
from pathlib import Path
import tempfile

from src.papertrade.state import (
    load_paper_state,
    save_paper_state,
    add_trade,
    compute_paper_pnl,
)


def test_first_load_creates_initial_state():
    with tempfile.TemporaryDirectory() as tmpd:
        path = Path(tmpd) / "paper.yaml"
        state = load_paper_state(path, initial_capital=50_000)
        assert state["cash_usd"] == 50_000
        assert state["initial_capital"] == 50_000
        assert state["holdings"] == []
        assert state["trades"] == []


def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpd:
        path = Path(tmpd) / "paper.yaml"
        state = load_paper_state(path, 100_000)
        state["cash_usd"] = 90_000
        state["holdings"] = [{"ticker": "AAPL", "shares": 10, "avg_cost": 180.0,
                              "purchase_date": "2026-05-20"}]
        save_paper_state(path, state)
        reloaded = load_paper_state(path)
        assert reloaded["cash_usd"] == 90_000
        assert len(reloaded["holdings"]) == 1
        assert reloaded["holdings"][0]["ticker"] == "AAPL"


def test_add_trade_appends():
    state = {"trades": []}
    add_trade(state, "AAPL", "BUY", 10, 180.0, "2026-05-20", reason="score 75")
    assert len(state["trades"]) == 1
    assert state["trades"][0]["ticker"] == "AAPL"
    assert state["trades"][0]["action"] == "BUY"
    assert state["trades"][0]["value"] == 1800.0


def test_compute_pnl_no_holdings():
    state = {
        "initial_capital": 100_000, "cash_usd": 100_000,
        "holdings": [], "trades": [],
    }
    pnl = compute_paper_pnl(state, {})
    assert pnl["total_equity"] == 100_000
    assert pnl["total_return_pct"] == 0.0
    assert pnl["unrealized_pnl"] == 0.0


def test_compute_pnl_with_unrealized_gain():
    state = {
        "initial_capital": 100_000,
        "cash_usd": 80_000,
        "holdings": [{"ticker": "AAPL", "shares": 100, "avg_cost": 200.0,
                      "purchase_date": "2026-05-01"}],
        "trades": [{"ticker": "AAPL", "action": "BUY", "shares": 100,
                    "price": 200.0, "value": 20_000, "date": "2026-05-01", "reason": ""}],
    }
    pnl = compute_paper_pnl(state, {"AAPL": 220.0})
    assert pnl["holding_value"] == 22_000
    assert pnl["unrealized_pnl"] == 2000
    assert pnl["total_equity"] == 102_000


def test_compute_pnl_realized_after_sell():
    state = {
        "initial_capital": 100_000,
        "cash_usd": 102_000,
        "holdings": [],
        "trades": [
            {"ticker": "AAPL", "action": "BUY", "shares": 100, "price": 200.0,
             "value": 20_000, "date": "2026-05-01", "reason": ""},
            {"ticker": "AAPL", "action": "SELL", "shares": 100, "price": 220.0,
             "value": 22_000, "date": "2026-05-15", "reason": "target"},
        ],
    }
    pnl = compute_paper_pnl(state, {})
    assert pnl["realized_pnl"] == 2000
    assert pnl["total_equity"] == 102_000
