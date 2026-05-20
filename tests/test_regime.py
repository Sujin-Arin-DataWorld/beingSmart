"""regime classifier unit tests."""
from src.regime.classifier import classify, Regime, regime_buy_modifier, regime_sell_urgency


def _macro(vix: float = 15.0, sp_5d: float = 0.0, sp_above_sma: bool = True) -> dict:
    return {
        "VIX": {
            "ticker": "^VIX",
            "price": vix,
            "change_1d_pct": 0.0,
            "change_5d_pct": 0.0,
            "change_20d_pct": 0.0,
            "sma_200": None,
            "above_sma_200": False,
        },
        "SP500": {
            "ticker": "^GSPC",
            "price": 5000.0,
            "change_1d_pct": 0.0,
            "change_5d_pct": sp_5d,
            "change_20d_pct": 0.0,
            "sma_200": 4800.0,
            "above_sma_200": sp_above_sma,
        },
    }


def test_bull_default_calm_market():
    r = classify(_macro(vix=12, sp_5d=0.5, sp_above_sma=True))
    assert r.regime == Regime.BULL


def test_choppy_when_vix_above_20():
    r = classify(_macro(vix=22, sp_5d=-1, sp_above_sma=True))
    assert r.regime == Regime.CHOPPY


def test_bear_when_sp_below_sma200():
    r = classify(_macro(vix=18, sp_5d=-2, sp_above_sma=False))
    assert r.regime == Regime.BEAR


def test_risk_off_when_vix_above_30():
    r = classify(_macro(vix=35, sp_5d=-3, sp_above_sma=True))
    assert r.regime == Regime.RISK_OFF


def test_risk_off_when_sp_5d_crash():
    r = classify(_macro(vix=22, sp_5d=-10, sp_above_sma=True))
    assert r.regime == Regime.RISK_OFF


def test_choppy_when_breadth_low():
    r = classify(_macro(vix=15, sp_5d=0, sp_above_sma=True), breadth_ratio=0.3)
    assert r.regime == Regime.CHOPPY


def test_bull_when_breadth_strong():
    r = classify(_macro(vix=14, sp_5d=0.5, sp_above_sma=True), breadth_ratio=0.8)
    assert r.regime == Regime.BULL


def test_buy_modifier_disabled_in_risk_off():
    mod = regime_buy_modifier(Regime.RISK_OFF)
    assert mod["active"] is False
    assert mod["score_multiplier"] == 0.0


def test_sell_urgency_monotonic():
    assert regime_sell_urgency(Regime.BULL) < regime_sell_urgency(Regime.CHOPPY)
    assert regime_sell_urgency(Regime.CHOPPY) < regime_sell_urgency(Regime.BEAR)
    assert regime_sell_urgency(Regime.BEAR) < regime_sell_urgency(Regime.RISK_OFF)
