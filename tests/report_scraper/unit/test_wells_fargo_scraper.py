"""Tests for Wells Fargo scraper.

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
# WellsFargoScraper tests
# ---------------------------------------------------------------------------


class TestWellsFargoScraperProperties:
    """Tests for WellsFargoScraper properties."""

    def test_正常系_source_keyがwells_fargoを返す(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        assert scraper.source_key == "wells_fargo"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "wells_fargo"
        assert config.tier == "sell_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        assert "wellsfargo" in scraper.listing_url


class TestWellsFargoParseListingItem:
    """Tests for WellsFargoScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        el = _make_mock_element(
            href="/research-analysis/strategy/weekly-report",
            text="Investment Strategy Weekly",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.wellsfargoadvisors.com/research-analysis/strategy/weekly.htm",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "wells_fargo"
        assert "Investment Strategy Weekly" in result.title
        assert result.url.startswith("https://")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.wellsfargoadvisors.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        el = _make_mock_element(href="/research/report", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.wellsfargoadvisors.com",
        )

        assert result is None


class TestWellsFargoExtractReport:
    """Tests for WellsFargoScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()
        meta = ReportMetadata(
            url="https://www.wellsfargoadvisors.com/research/strategy/weekly",
            title="Weekly Strategy Report",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="wells_fargo",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestWellsFargoFetchListing:
    """Tests for WellsFargoScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.wells_fargo import WellsFargoScraper

        scraper = WellsFargoScraper()

        el1 = _make_mock_element(
            href="/research/weekly-1",
            text="Weekly Strategy 1",
        )
        el2 = _make_mock_element(
            href="/research/weekly-2",
            text="Weekly Strategy 2",
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
        assert all(r.source_key == "wells_fargo" for r in result)
