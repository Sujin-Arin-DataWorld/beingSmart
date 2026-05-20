"""scoring unit tests — 범위, monotonicity, regime 반영."""
from src.screener.scoring import score_buy_signal
from src.regime.classifier import Regime


def _sig(rsi: float = 30, macd_hist: float = 0.5,
         vol_ratio: float = 1.5, price: float = 100, sma_200: float = 95) -> dict:
    return {
        "rsi": rsi,
        "macd_hist": macd_hist,
        "vol_ratio": vol_ratio,
        "price": price,
        "sma_200": sma_200,
    }


def test_total_score_in_range_0_100():
    s = score_buy_signal(_sig(), regime=Regime.BULL, vix=15)
    assert 0 <= s["total"] <= 100


def test_lower_rsi_yields_higher_score():
    low_rsi = score_buy_signal(_sig(rsi=22), regime=Regime.BULL, vix=15)
    high_rsi = score_buy_signal(_sig(rsi=39), regime=Regime.BULL, vix=15)
    assert low_rsi["total"] > high_rsi["total"]


def test_bull_regime_scores_higher_than_bear():
    bull = score_buy_signal(_sig(), regime=Regime.BULL, vix=15)
    bear = score_buy_signal(_sig(), regime=Regime.BEAR, vix=15)
    assert bull["total"] > bear["total"]


def test_risk_off_zeroes_out_score():
    s = score_buy_signal(_sig(), regime=Regime.RISK_OFF, vix=35)
    assert s["total"] == 0.0


def test_high_vix_reduces_score():
    low_vix = score_buy_signal(_sig(), regime=Regime.BULL, vix=12)
    high_vix = score_buy_signal(_sig(), regime=Regime.BULL, vix=28)
    assert low_vix["total"] > high_vix["total"]


def test_breakdown_contains_all_components():
    s = score_buy_signal(_sig(), regime=Regime.BULL, vix=15)
    for k in ("total", "rsi", "macd", "volume", "trend", "regime", "macro"):
        assert k in s


def test_below_sma200_trend_score_zero():
    s = score_buy_signal(
        _sig(price=90, sma_200=100), regime=Regime.BULL, vix=15
    )
    assert s["trend"] == 0.0
