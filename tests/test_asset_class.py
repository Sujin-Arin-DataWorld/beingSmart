"""asset_class 매핑 + 노출 단위 테스트."""
from src.portfolio.asset_class import (
    get_asset_class,
    asset_class_exposure,
    diversification_warnings,
)


def test_bond_etf_classified():
    assert get_asset_class("TLT") == "Bond"
    assert get_asset_class("AGG") == "Bond"


def test_commodity_classified():
    assert get_asset_class("GLD") == "Commodity"
    assert get_asset_class("DBC") == "Commodity"


def test_currency_classified():
    assert get_asset_class("UUP") == "Currency"


def test_international_classified():
    assert get_asset_class("EFA") == "International"
    assert get_asset_class("EEM") == "International"


def test_realestate_classified():
    assert get_asset_class("XLRE") == "RealEstate"


def test_unknown_defaults_equity():
    assert get_asset_class("AAPL") == "Equity"
    assert get_asset_class("SOMECRYPTO") == "Equity"


def test_exposure_mixed_classes():
    holdings = [
        {"ticker": "AAPL", "shares": 10},
        {"ticker": "TLT", "shares": 10},
        {"ticker": "GLD", "shares": 10},
    ]
    prices = {"AAPL": 100, "TLT": 100, "GLD": 100}
    exp = asset_class_exposure(holdings, prices)
    assert abs(exp["Equity"] - 1 / 3) < 1e-6
    assert abs(exp["Bond"] - 1 / 3) < 1e-6
    assert abs(exp["Commodity"] - 1 / 3) < 1e-6


def test_warning_when_all_equity():
    exp = {"Equity": 1.0}
    warns = diversification_warnings(exp)
    assert any("주식" in w for w in warns)
    assert any("채권" in w for w in warns)


def test_no_warning_balanced():
    exp = {"Equity": 0.5, "Bond": 0.3, "Commodity": 0.2}
    warns = diversification_warnings(exp)
    assert warns == []


def test_exposure_empty():
    assert asset_class_exposure([], {}) == {}
