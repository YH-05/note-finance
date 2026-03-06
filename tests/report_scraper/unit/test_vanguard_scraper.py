"""Tests for Vanguard scraper.

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
# VanguardScraper tests
# ---------------------------------------------------------------------------


class TestVanguardScraperProperties:
    """Tests for VanguardScraper properties."""

    def test_正常系_source_keyがvanguardを返す(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        assert scraper.source_key == "vanguard"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "vanguard"
        assert config.tier == "buy_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        assert "vanguard.com" in scraper.listing_url


class TestVanguardParseListingItem:
    """Tests for VanguardScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        el = _make_mock_element(
            href="/insights/article/series/market-perspectives-q1-2026",
            text="Market Perspectives Q1 2026",
        )

        result = scraper.parse_listing_item(
            el,
            "https://advisors.vanguard.com/insights/article/series/market-perspectives",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "vanguard"
        assert "Market Perspectives" in result.title
        assert result.url.startswith("https://")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://advisors.vanguard.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        el = _make_mock_element(href="/insights/article", text="")

        result = scraper.parse_listing_item(
            el,
            "https://advisors.vanguard.com",
        )

        assert result is None


class TestVanguardExtractReport:
    """Tests for VanguardScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()
        meta = ReportMetadata(
            url="https://advisors.vanguard.com/insights/article/market-perspectives",
            title="Market Perspectives",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="vanguard",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestVanguardFetchListing:
    """Tests for VanguardScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.vanguard import VanguardScraper

        scraper = VanguardScraper()

        el1 = _make_mock_element(
            href="/insights/article-1",
            text="Market Perspectives 1",
        )
        el2 = _make_mock_element(
            href="/insights/article-2",
            text="Market Perspectives 2",
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
        assert all(r.source_key == "vanguard" for r in result)
