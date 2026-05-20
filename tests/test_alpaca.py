"""alpaca fallback 단위 테스트 — helper만 (네트워크 의존 안 됨)."""
import os
from unittest.mock import patch

from src.data.alpaca import is_alpaca_available, fetch_history_alpaca, fetch_with_fallback


def test_alpaca_unavailable_without_keys():
    with patch.dict(os.environ, {}, clear=True):
        assert is_alpaca_available() is False


def test_alpaca_available_with_both_keys():
    with patch.dict(os.environ, {"ALPACA_API_KEY": "k", "ALPACA_SECRET": "s"}, clear=True):
        assert is_alpaca_available() is True


def test_alpaca_unavailable_partial_keys():
    with patch.dict(os.environ, {"ALPACA_API_KEY": "k"}, clear=True):
        assert is_alpaca_available() is False
    with patch.dict(os.environ, {"ALPACA_SECRET": "s"}, clear=True):
        assert is_alpaca_available() is False


def test_fetch_alpaca_returns_empty_without_keys():
    with patch.dict(os.environ, {}, clear=True):
        result = fetch_history_alpaca(["AAPL"], days=100)
        assert result == {}


def test_fetch_alpaca_empty_tickers():
    with patch.dict(os.environ, {"ALPACA_API_KEY": "k", "ALPACA_SECRET": "s"}, clear=True):
        result = fetch_history_alpaca([], days=100)
        assert result == {}
