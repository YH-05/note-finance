"""Tests for Deutsche Bank Research scraper.

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
# DeutscheBankScraper tests
# ---------------------------------------------------------------------------


class TestDeutscheBankScraperProperties:
    """Tests for DeutscheBankScraper properties."""

    def test_正常系_source_keyがdeutsche_bankを返す(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        assert scraper.source_key == "deutsche_bank"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "deutsche_bank"
        assert config.tier == "sell_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        assert "db.com" in scraper.listing_url


class TestDeutscheBankParseListingItem:
    """Tests for DeutscheBankScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        el = _make_mock_element(
            href="/news/in-the-press/2026-economic-outlook",
            text="2026 Economic Outlook",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.db.com/news/in-the-press",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "deutsche_bank"
        assert "2026 Economic Outlook" in result.title
        assert result.url.startswith("https://")

    def test_正常系_PDF要素からpdf_urlを検出できる(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()

        pdf_el = MagicMock()
        pdf_el.attrib = {"href": "/reports/research.pdf"}

        el = _make_mock_element(
            href="/news/report",
            text="Research Report",
        )
        el.css.return_value = [pdf_el]

        result = scraper.parse_listing_item(
            el,
            "https://www.db.com",
        )

        assert result is not None
        assert result.pdf_url is not None
        assert result.pdf_url.endswith(".pdf")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.db.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        el = _make_mock_element(href="/news/report", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.db.com",
        )

        assert result is None


class TestDeutscheBankExtractReport:
    """Tests for DeutscheBankScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()
        meta = ReportMetadata(
            url="https://www.db.com/news/in-the-press/outlook",
            title="Economic Outlook",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="deutsche_bank",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestDeutscheBankFetchListing:
    """Tests for DeutscheBankScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper

        scraper = DeutscheBankScraper()

        el1 = _make_mock_element(
            href="/news/report-1",
            text="Market Commentary 1",
        )
        el2 = _make_mock_element(
            href="/news/report-2",
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
        assert all(r.source_key == "deutsche_bank" for r in result)
