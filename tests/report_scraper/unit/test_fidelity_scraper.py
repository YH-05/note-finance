"""Tests for Fidelity Investments scraper.

Tests cover:
- parse_listing_item() with mock HTML elements
- source_key and source_config properties
- fetch_listing() with mocked StealthyFetcher
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_element(
    *,
    href: str = "",
    text: str = "",
    attribs: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock Scrapling element."""
    el = MagicMock()
    el.attrib = {"href": href, **(attribs or {})}
    el.text = text
    el.css.return_value = []
    return el


def _make_mock_response(
    *,
    status: int = 200,
    elements: list[MagicMock] | None = None,
) -> MagicMock:
    """Create a mock Scrapling response."""
    response = MagicMock()
    response.status = status
    response.css.return_value = elements or []
    return response


# ---------------------------------------------------------------------------
# FidelityScraper tests
# ---------------------------------------------------------------------------


class TestFidelityScraperProperties:
    """Tests for FidelityScraper properties."""

    def test_正常系_source_keyがfidelityを返す(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        assert scraper.source_key == "fidelity"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "fidelity"
        assert config.tier == "buy_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        assert "fidelity.com" in scraper.listing_url


class TestFidelityParseListingItem:
    """Tests for FidelityScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        el = _make_mock_element(
            href="/learning-center/trading-investing/market-outlook",
            text="2026 Market Outlook",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.fidelity.com/learning-center/trading-investing/overview",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "fidelity"
        assert "2026 Market Outlook" in result.title
        assert result.url.startswith("https://")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.fidelity.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        el = _make_mock_element(href="/learning-center/article", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.fidelity.com",
        )

        assert result is None


class TestFidelityExtractReport:
    """Tests for FidelityScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()
        meta = ReportMetadata(
            url="https://www.fidelity.com/learning-center/outlook",
            title="Market Outlook",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="fidelity",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestFidelityFetchListing:
    """Tests for FidelityScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.fidelity import FidelityScraper

        scraper = FidelityScraper()

        el1 = _make_mock_element(
            href="/learning-center/article-1",
            text="Market Commentary 1",
        )
        el2 = _make_mock_element(
            href="/learning-center/article-2",
            text="Market Commentary 2",
        )

        mock_response = _make_mock_response(status=200, elements=[el1, el2])
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = mock_response

        with (
            patch("report_scraper.scrapers._html_scraper._scrapling_available", True),
            patch(
                "report_scraper.scrapers._html_scraper.StealthyFetcher",
                return_value=mock_fetcher,
            ),
        ):
            result = await scraper.fetch_listing()

        assert len(result) == 2
        assert all(isinstance(r, ReportMetadata) for r in result)
        assert all(r.source_key == "fidelity" for r in result)
