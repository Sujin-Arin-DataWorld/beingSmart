"""position sizing 단위 테스트."""
from src.portfolio.sizing import compute_position_size, reward_to_risk_ratio


def test_basic_sizing_returns_positive_shares():
    r = compute_position_size(entry_price=100, stop_price=95, capital=10_000)
    assert r["shares"] > 0
    assert r["position_value"] > 0


def test_max_position_pct_caps_shares():
    # risk: $200 / $5 = 40주
    # cap: $1500 / $100 = 15주 → 15주가 제약
    r = compute_position_size(
        entry_price=100, stop_price=95, capital=10_000,
        risk_per_trade=0.02, max_position_pct=0.15,
    )
    assert r["shares"] <= 15
    assert r["limited_by"] == "max_position_pct"


def test_risk_limits_when_stop_is_tight():
    # 손절폭 1$ → risk: $200/$1 = 200주
    # cap: $1500/$100 = 15주
    # 더 작은 cap이 제약
    r = compute_position_size(
        entry_price=100, stop_price=99, capital=10_000,
        risk_per_trade=0.02, max_position_pct=0.15,
    )
    assert r["limited_by"] == "max_position_pct"


def test_risk_limits_when_stop_is_wide():
    # 손절폭 20$ → risk: $200/$20 = 10주
    # cap: $1500/$100 = 15주
    # 더 작은 risk가 제약
    r = compute_position_size(
        entry_price=100, stop_price=80, capital=10_000,
        risk_per_trade=0.02, max_position_pct=0.15,
    )
    assert r["limited_by"] == "risk"
    assert r["shares"] == 10


def test_invalid_stop_above_entry():
    r = compute_position_size(entry_price=100, stop_price=105, capital=10_000)
    assert r["shares"] == 0
    assert r["limited_by"] == "invalid_input"


def test_zero_capital():
    r = compute_position_size(entry_price=100, stop_price=95, capital=0)
    assert r["shares"] == 0
    assert r["limited_by"] == "invalid_input"


def test_below_min_shares_with_tiny_capital():
    r = compute_position_size(entry_price=1_000, stop_price=995, capital=50, min_shares=1)
    assert r["shares"] == 0
    assert r["limited_by"] == "below_min_shares"


def test_risk_amount_consistent():
    r = compute_position_size(entry_price=100, stop_price=80, capital=10_000,
                              risk_per_trade=0.02, max_position_pct=0.5)
    expected_risk = r["shares"] * 20
    assert abs(r["risk_amount"] - expected_risk) < 0.01


def test_reward_to_risk_3to1():
    rr = reward_to_risk_ratio(entry_price=100, stop_price=95, target_price=115)
    assert rr == 3.0


def test_reward_to_risk_invalid():
    rr = reward_to_risk_ratio(entry_price=100, stop_price=100, target_price=115)
    assert rr == 0.0
