"""Tests for Goldman Sachs Research scraper.

Tests cover:
- parse_listing_item() with mock HTML elements
- PDF link detection
- source_key and source_config properties
- fetch_listing() with mocked DynamicFetcher
- extract_report() wrapping metadata
"""

from __future__ import annotations

from datetime import datetime, timezone
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
) -> MagicMock:
    """Create a mock Scrapling element."""
    el = MagicMock()
    el.attrib = {"href": href}
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
# GoldmanSachsScraper property tests
# ---------------------------------------------------------------------------


class TestGoldmanSachsScraperProperties:
    """Tests for GoldmanSachsScraper properties."""

    def test_正常系_source_keyがgoldman_sachsを返す(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        assert scraper.source_key == "goldman_sachs"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "goldman_sachs"
        assert config.tier == "sell_side"
        assert config.rendering == "playwright"
        assert "macro" in config.tags

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        assert "goldmansachs.com" in scraper.listing_url

    def test_正常系_article_selectorが設定されている(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        assert scraper.article_selector != ""

    def test_正常系_wait_selectorが設定されている(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        assert scraper.wait_selector is not None


# ---------------------------------------------------------------------------
# parse_listing_item tests
# ---------------------------------------------------------------------------


class TestGoldmanSachsParseListingItem:
    """Tests for GoldmanSachsScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        el = _make_mock_element(
            href="/insights/research/markets-outlook",
            text="Global Markets Outlook 2026",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.goldmansachs.com/insights/goldman-sachs-research",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "goldman_sachs"
        assert "Global Markets Outlook" in result.title
        assert result.url.startswith("https://")

    def test_正常系_PDFリンクのURLがpdf_urlに設定される(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        el = _make_mock_element(
            href="/insights/research/report.pdf",
            text="Research Report PDF",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.goldmansachs.com",
        )

        assert result is not None
        assert result.pdf_url is not None
        assert result.pdf_url.endswith(".pdf")

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.goldmansachs.com",
        )

        assert result is None

    def test_エッジケース_titleが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        el = _make_mock_element(href="/insights/report", text="")

        result = scraper.parse_listing_item(
            el,
            "https://www.goldmansachs.com",
        )

        assert result is None

    def test_正常系_タイトルの前後空白がトリムされる(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        el = _make_mock_element(
            href="/insights/report",
            text="  Trimmed Title  ",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.goldmansachs.com",
        )

        assert result is not None
        assert result.title == "Trimmed Title"


# ---------------------------------------------------------------------------
# extract_report tests
# ---------------------------------------------------------------------------


class TestGoldmanSachsExtractReport:
    """Tests for GoldmanSachsScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()
        meta = ReportMetadata(
            url="https://www.goldmansachs.com/insights/research/outlook",
            title="Markets Outlook",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="goldman_sachs",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


# ---------------------------------------------------------------------------
# fetch_listing tests
# ---------------------------------------------------------------------------


class TestGoldmanSachsFetchListing:
    """Tests for GoldmanSachsScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()

        el1 = _make_mock_element(
            href="/insights/research/outlook-1",
            text="Markets Outlook Q1",
        )
        el2 = _make_mock_element(
            href="/insights/research/outlook-2",
            text="Markets Outlook Q2",
        )

        mock_response = _make_mock_response(status=200, elements=[el1, el2])
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = mock_response

        with (
            patch(
                "report_scraper.scrapers._spa_scraper._dynamic_fetcher_available", True
            ),
            patch(
                "report_scraper.scrapers._spa_scraper.DynamicFetcher",
                return_value=mock_fetcher,
            ),
        ):
            result = await scraper.fetch_listing()

        assert len(result) == 2
        assert all(isinstance(r, ReportMetadata) for r in result)
        assert all(r.source_key == "goldman_sachs" for r in result)

    @pytest.mark.asyncio
    async def test_正常系_不完全な要素はスキップされる(self) -> None:
        from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper

        scraper = GoldmanSachsScraper()

        good_el = _make_mock_element(
            href="/insights/valid",
            text="Valid Report",
        )
        bad_el = _make_mock_element(href="", text="")

        mock_response = _make_mock_response(status=200, elements=[good_el, bad_el])
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = mock_response

        with (
            patch(
                "report_scraper.scrapers._spa_scraper._dynamic_fetcher_available", True
            ),
            patch(
                "report_scraper.scrapers._spa_scraper.DynamicFetcher",
                return_value=mock_fetcher,
            ),
        ):
            result = await scraper.fetch_listing()

        assert len(result) == 1
        assert result[0].title == "Valid Report"
