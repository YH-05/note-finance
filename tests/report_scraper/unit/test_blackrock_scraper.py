"""Tests for BlackRock BII scraper.

Tests cover:
- parse_listing_item() with mock HTML elements
- PDF link detection via pdf_selector
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
    children: list[MagicMock] | None = None,
    attribs: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock Scrapling element."""
    el = MagicMock()
    el.attrib = {"href": href, **(attribs or {})}
    el.text = text
    # css() returns children or empty list
    el.css.return_value = children or []
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
# BlackRockScraper tests
# ---------------------------------------------------------------------------


class TestBlackRockScraperProperties:
    """Tests for BlackRockScraper properties."""

    def test_正常系_source_keyがblackrock_biiを返す(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        assert scraper.source_key == "blackrock_bii"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "blackrock_bii"
        assert config.tier == "buy_side"
        assert config.rendering == "static"
        assert config.pdf_selector == "a[href$='.pdf']"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        assert "blackrock.com" in scraper.listing_url

    def test_正常系_article_selectorが設定されている(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        assert scraper.article_selector != ""


class TestBlackRockParseListingItem:
    """Tests for BlackRockScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        el = _make_mock_element(
            href="/corporate/insights/weekly-commentary",
            text="Weekly Investment Commentary",
        )
        # Mock nested PDF link elements
        pdf_el = _make_mock_element(href="/corporate/literature/report.pdf")
        el.css.return_value = [pdf_el]

        result = scraper.parse_listing_item(
            el,
            "https://www.blackrock.com/corporate/insights/archives",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "blackrock_bii"
        assert "Weekly Investment Commentary" in result.title
        assert result.url.startswith("https://")

    def test_正常系_PDFリンクが検出される(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        pdf_el = _make_mock_element(href="/literature/report.pdf")
        el = _make_mock_element(
            href="/insights/weekly",
            text="Weekly Report",
        )
        el.css.return_value = [pdf_el]

        result = scraper.parse_listing_item(
            el,
            "https://www.blackrock.com",
        )

        assert result is not None
        assert result.pdf_url is not None
        assert result.pdf_url.endswith(".pdf")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.blackrock.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        el = _make_mock_element(href="/insights/report", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.blackrock.com",
        )

        assert result is None


class TestBlackRockExtractReport:
    """Tests for BlackRockScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()
        meta = ReportMetadata(
            url="https://www.blackrock.com/insights/weekly",
            title="Weekly Commentary",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="blackrock_bii",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestBlackRockFetchListing:
    """Tests for BlackRockScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.blackrock import BlackRockScraper

        scraper = BlackRockScraper()

        el1 = _make_mock_element(
            href="/insights/weekly-1",
            text="Weekly Commentary 1",
        )
        el1.css.return_value = []  # No PDF links

        el2 = _make_mock_element(
            href="/insights/weekly-2",
            text="Weekly Commentary 2",
        )
        pdf_el = _make_mock_element(href="/literature/report.pdf")
        el2.css.return_value = [pdf_el]

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
        assert all(r.source_key == "blackrock_bii" for r in result)
