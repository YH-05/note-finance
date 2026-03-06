"""Tests for Bank of America Research scraper.

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
# BankOfAmericaScraper tests
# ---------------------------------------------------------------------------


class TestBankOfAmericaScraperProperties:
    """Tests for BankOfAmericaScraper properties."""

    def test_正常系_source_keyがbank_of_americaを返す(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        assert scraper.source_key == "bank_of_america"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "bank_of_america"
        assert config.tier == "sell_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        assert "bofa.com" in scraper.listing_url


class TestBankOfAmericaParseListingItem:
    """Tests for BankOfAmericaScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        el = _make_mock_element(
            href="/en-us/content/market-strategies-insights/2026-outlook",
            text="2026 Market Strategy",
        )

        result = scraper.parse_listing_item(
            el,
            "https://business.bofa.com/en-us/content/market-strategies-insights.html",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "bank_of_america"
        assert "2026 Market Strategy" in result.title
        assert result.url.startswith("https://")

    def test_正常系_PDF要素からpdf_urlを検出できる(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()

        pdf_el = MagicMock()
        pdf_el.attrib = {"href": "/reports/strategy.pdf"}

        el = _make_mock_element(
            href="/content/report",
            text="Strategy Report",
        )
        el.css.return_value = [pdf_el]

        result = scraper.parse_listing_item(
            el,
            "https://business.bofa.com",
        )

        assert result is not None
        assert result.pdf_url is not None
        assert result.pdf_url.endswith(".pdf")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://business.bofa.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        el = _make_mock_element(href="/content/report", text="")

        result = scraper.parse_listing_item(
            el,
            "https://business.bofa.com",
        )

        assert result is None


class TestBankOfAmericaExtractReport:
    """Tests for BankOfAmericaScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()
        meta = ReportMetadata(
            url="https://business.bofa.com/en-us/content/strategy",
            title="Market Strategy",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="bank_of_america",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestBankOfAmericaFetchListing:
    """Tests for BankOfAmericaScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper

        scraper = BankOfAmericaScraper()

        el1 = _make_mock_element(
            href="/content/report-1",
            text="Market Commentary 1",
        )
        el2 = _make_mock_element(
            href="/content/report-2",
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
        assert all(r.source_key == "bank_of_america" for r in result)
