"""news 파싱 — 외부 API 의존 없는 helper 테스트."""
from datetime import datetime, timezone

from src.data.news import _parse_published, _extract_publisher, _extract_url


def test_parse_iso_8601_with_z():
    content = {"pubDate": "2026-05-20T10:00:00Z"}
    result = _parse_published(content, {})
    assert result is not None
    assert result.year == 2026
    assert result.month == 5
    assert result.day == 20


def test_parse_epoch_seconds():
    # 2009-02-13 unix epoch 1234567890
    result = _parse_published({}, {"providerPublishTime": 1234567890})
    assert result is not None
    assert result.year == 2009


def test_parse_returns_none_when_no_date():
    assert _parse_published({}, {}) is None


def test_extract_publisher_from_provider_dict():
    content = {"provider": {"displayName": "Reuters"}}
    assert _extract_publisher(content, {}) == "Reuters"


def test_extract_publisher_fallback_to_item():
    assert _extract_publisher({}, {"publisher": "AP News"}) == "AP News"


def test_extract_publisher_unknown_default():
    assert _extract_publisher({}, {}) == "Unknown"


def test_extract_url_from_canonical():
    content = {"canonicalUrl": {"url": "https://example.com/a"}}
    assert _extract_url(content, {}) == "https://example.com/a"


def test_extract_url_fallback_to_link():
    assert _extract_url({}, {"link": "https://example.com/b"}) == "https://example.com/b"


def test_extract_url_empty_default():
    assert _extract_url({}, {}) == ""
