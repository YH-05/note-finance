"""Tests for Schroders scraper.

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
# SchrodersScraper tests
# ---------------------------------------------------------------------------


class TestSchrodersScraperProperties:
    """Tests for SchrodersScraper properties."""

    def test_正常系_source_keyがschrodersを返す(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        assert scraper.source_key == "schroders"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "schroders"
        assert config.tier == "buy_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        assert "schroders.com" in scraper.listing_url


class TestSchrodersParseListingItem:
    """Tests for SchrodersScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        el = _make_mock_element(
            href="/en-us/us/individual/insights/market-outlook",
            text="2026 Market Outlook",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.schroders.com/en-us/us/individual/insights/",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "schroders"
        assert "2026 Market Outlook" in result.title
        assert result.url.startswith("https://")

    def test_正常系_PDF要素からpdf_urlを検出できる(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()

        pdf_el = MagicMock()
        pdf_el.attrib = {"href": "/reports/outlook.pdf"}

        el = _make_mock_element(
            href="/insights/report",
            text="Research Report",
        )
        el.css.return_value = [pdf_el]

        result = scraper.parse_listing_item(
            el,
            "https://www.schroders.com",
        )

        assert result is not None
        assert result.pdf_url is not None
        assert result.pdf_url.endswith(".pdf")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.schroders.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        el = _make_mock_element(href="/insights/report", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.schroders.com",
        )

        assert result is None


class TestSchrodersExtractReport:
    """Tests for SchrodersScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()
        meta = ReportMetadata(
            url="https://www.schroders.com/en-us/us/individual/insights/outlook",
            title="Market Outlook",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="schroders",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestSchrodersFetchListing:
    """Tests for SchrodersScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.schroders import SchrodersScraper

        scraper = SchrodersScraper()

        el1 = _make_mock_element(
            href="/insights/report-1",
            text="Market Commentary 1",
        )
        el2 = _make_mock_element(
            href="/insights/report-2",
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
        assert all(r.source_key == "schroders" for r in result)
