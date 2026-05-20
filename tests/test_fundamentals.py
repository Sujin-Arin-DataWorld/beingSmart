"""fundamentals 모듈 — 외부 API 의존 없는 로직만."""
from src.data.fundamentals import fundamental_health_score


def test_health_score_in_range():
    s = fundamental_health_score({"trailing_pe": 20, "market_cap": 5e10})
    assert 0 <= s <= 100


def test_reasonable_pe_higher_than_extreme():
    reasonable = fundamental_health_score({"trailing_pe": 18, "market_cap": 5e10})
    extreme = fundamental_health_score({"trailing_pe": 200, "market_cap": 5e10})
    assert reasonable > extreme


def test_large_cap_better_than_small_cap():
    large = fundamental_health_score({"trailing_pe": 20, "market_cap": 5e10})
    small = fundamental_health_score({"trailing_pe": 20, "market_cap": 5e8})
    assert large > small


def test_dividend_bonus():
    no_div = fundamental_health_score({"trailing_pe": 20, "market_cap": 5e10})
    with_div = fundamental_health_score({"trailing_pe": 20, "market_cap": 5e10, "dividend_yield": 0.03})
    assert with_div > no_div


def test_empty_fundamentals():
    s = fundamental_health_score({})
    assert 0 <= s <= 100
