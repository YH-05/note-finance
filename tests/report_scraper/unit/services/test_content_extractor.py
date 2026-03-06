"""Tests for report_scraper.services.content_extractor module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from report_scraper.services.content_extractor import (
    MIN_CONTENT_LENGTH,
    PAYWALL_PATTERNS,
    ContentExtractor,
    _detect_paywall,
)
from report_scraper.types import ExtractedContent

# ---------------------------------------------------------------------------
# _detect_paywall tests
# ---------------------------------------------------------------------------


class TestDetectPaywall:
    """Tests for paywall detection helper."""

    def test_正常系_ペイウォールなしでFalse(self) -> None:
        html = "<html><body><p>Normal article content here.</p></body></html>"
        assert _detect_paywall(html) is False

    def test_正常系_空文字でFalse(self) -> None:
        assert _detect_paywall("") is False

    def test_正常系_ペイウォールパターン検出でTrue(self) -> None:
        for pattern in PAYWALL_PATTERNS:
            html = f"<html><body><div class='{pattern}'>Subscribe</div></body></html>"
            assert _detect_paywall(html) is True, f"Failed to detect pattern: {pattern}"

    def test_正常系_subscribe_to_read検出(self) -> None:
        html = "<html><body><p>Subscribe to read the full article</p></body></html>"
        assert _detect_paywall(html) is True


# ---------------------------------------------------------------------------
# ContentExtractor tests
# ---------------------------------------------------------------------------


class TestContentExtractor:
    """Tests for ContentExtractor class."""

    def test_正常系_初期化(self) -> None:
        extractor = ContentExtractor()
        assert extractor.timeout == 30

    def test_正常系_カスタムタイムアウト(self) -> None:
        extractor = ContentExtractor(timeout=60)
        assert extractor.timeout == 60

    def test_正常系_trafilatura抽出成功(self) -> None:
        extractor = ContentExtractor()
        long_text = "A" * (MIN_CONTENT_LENGTH + 50)
        html = f"<html><body><article>{long_text}</article></body></html>"

        with patch(
            "report_scraper.services.content_extractor.trafilatura"
        ) as mock_traf:
            mock_traf.extract.return_value = long_text
            result = extractor.extract_from_html(html, url="https://example.com")

        assert result is not None
        assert result.method == "trafilatura"
        assert result.text == long_text
        assert result.length == len(long_text)

    def test_正常系_trafilatura失敗時にlxmlフォールバック(self) -> None:
        extractor = ContentExtractor()
        long_text = "B" * (MIN_CONTENT_LENGTH + 50)
        html = f"<html><body><article><p>{long_text}</p></article></body></html>"

        with patch(
            "report_scraper.services.content_extractor.trafilatura"
        ) as mock_traf:
            mock_traf.extract.return_value = None
            result = extractor.extract_from_html(html, url="https://example.com")

        assert result is not None
        assert result.method == "lxml"

    def test_異常系_ペイウォール検出でNone(self) -> None:
        extractor = ContentExtractor()
        html = "<html><body><div class='paywall'>Subscribe</div></body></html>"
        result = extractor.extract_from_html(html, url="https://example.com")
        assert result is None

    def test_異常系_コンテンツ不足でNone(self) -> None:
        extractor = ContentExtractor()
        html = "<html><body><p>Short</p></body></html>"

        with patch(
            "report_scraper.services.content_extractor.trafilatura"
        ) as mock_traf:
            mock_traf.extract.return_value = "Short"
            result = extractor.extract_from_html(html, url="https://example.com")

        assert result is None

    def test_異常系_空HTML(self) -> None:
        extractor = ContentExtractor()
        result = extractor.extract_from_html("", url="https://example.com")
        assert result is None

    def test_エッジケース_trafilatura例外でlxmlフォールバック(self) -> None:
        extractor = ContentExtractor()
        long_text = "C" * (MIN_CONTENT_LENGTH + 50)
        html = f"<html><body><article><p>{long_text}</p></article></body></html>"

        with patch(
            "report_scraper.services.content_extractor.trafilatura"
        ) as mock_traf:
            mock_traf.extract.side_effect = Exception("trafilatura error")
            result = extractor.extract_from_html(html, url="https://example.com")

        assert result is not None
        assert result.method == "lxml"

    def test_エッジケース_両方失敗でNone(self) -> None:
        extractor = ContentExtractor()
        html = "<html><body></body></html>"

        with patch(
            "report_scraper.services.content_extractor.trafilatura"
        ) as mock_traf:
            mock_traf.extract.return_value = None
            result = extractor.extract_from_html(html, url="https://example.com")

        assert result is None
