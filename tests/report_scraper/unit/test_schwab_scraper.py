"""Tests for Charles Schwab scraper.

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
# SchwabScraper tests
# ---------------------------------------------------------------------------


class TestSchwabScraperProperties:
    """Tests for SchwabScraper properties."""

    def test_正常系_source_keyがschwabを返す(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        assert scraper.source_key == "schwab"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "schwab"
        assert config.tier == "sell_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        assert "schwab.com" in scraper.listing_url


class TestSchwabParseListingItem:
    """Tests for SchwabScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        el = _make_mock_element(
            href="/learn/market-commentary/2026-outlook",
            text="2026 Market Outlook",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.schwab.com/learn/market-commentary",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "schwab"
        assert "2026 Market Outlook" in result.title
        assert result.url.startswith("https://")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.schwab.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        el = _make_mock_element(href="/learn/commentary", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.schwab.com",
        )

        assert result is None


class TestSchwabExtractReport:
    """Tests for SchwabScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()
        meta = ReportMetadata(
            url="https://www.schwab.com/learn/market-commentary/outlook",
            title="Market Outlook",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="schwab",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestSchwabFetchListing:
    """Tests for SchwabScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.schwab import SchwabScraper

        scraper = SchwabScraper()

        el1 = _make_mock_element(
            href="/learn/commentary-1",
            text="Market Commentary 1",
        )
        el2 = _make_mock_element(
            href="/learn/commentary-2",
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
        assert all(r.source_key == "schwab" for r in result)
