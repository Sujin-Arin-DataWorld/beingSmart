"""FRED 모듈 — helper만 (외부 API 의존 X)."""
import os
from unittest.mock import patch

from src.data.fred import is_fred_available, fetch_series, fetch_fred_snapshot, recession_indicator


def test_fred_unavailable_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert is_fred_available() is False


def test_fred_available_with_key():
    with patch.dict(os.environ, {"FRED_API_KEY": "abc"}, clear=True):
        assert is_fred_available() is True


def test_fetch_series_returns_empty_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert fetch_series("UNRATE") == []


def test_fetch_snapshot_returns_empty_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert fetch_fred_snapshot() == {}


def test_recession_indicator_inverted():
    snap = {"T10Y2Y": {"current": -0.5}}
    result = recession_indicator(snap)
    assert "inversion" in result
    assert "⚠️" in result


def test_recession_indicator_narrow():
    snap = {"T10Y2Y": {"current": 0.1}}
    result = recession_indicator(snap)
    assert "narrow" in result


def test_recession_indicator_healthy():
    snap = {"T10Y2Y": {"current": 1.5}}
    result = recession_indicator(snap)
    assert "healthy" in result


def test_recession_indicator_missing_data():
    assert recession_indicator({}) is None
    assert recession_indicator({"T10Y2Y": {"current": None}}) is None
