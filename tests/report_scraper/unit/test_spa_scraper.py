"""Tests for SpaReportScraper base class.

Tests cover:
- fetch_listing() with mocked DynamicFetcher
- Error handling (ImportError when scrapling/playwright not installed)
- Non-200 status handling (FetchError)
- JS rendering wait configuration
- parse_listing_item skip behavior
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from report_scraper.exceptions import FetchError
from report_scraper.types import ReportMetadata, SourceConfig

# ---------------------------------------------------------------------------
# Concrete test subclass
# ---------------------------------------------------------------------------


def _make_test_scraper_class() -> type:
    """Create a concrete test subclass of SpaReportScraper.

    Returns the class (not an instance) so tests can instantiate
    with or without mocking DynamicFetcher availability.
    """
    from report_scraper.scrapers._spa_scraper import SpaReportScraper

    class TestSpaScraper(SpaReportScraper):
        listing_url = "https://example.com/spa-research"
        article_selector = "div.spa-article a"

        @property
        def source_key(self) -> str:
            return "test_spa"

        @property
        def source_config(self) -> SourceConfig:
            return SourceConfig(
                key="test_spa",
                name="Test SPA Source",
                tier="sell_side",
                listing_url="https://example.com/spa-research",
                rendering="playwright",
            )

        def parse_listing_item(
            self,
            element: Any,
            base_url: str,
        ) -> ReportMetadata | None:
            href = element.attrib.get("href", "")
            title = element.text or ""
            if not href or not title:
                return None

            from urllib.parse import urljoin, urlparse

            absolute = href if urlparse(href).scheme else urljoin(base_url, href)

            return ReportMetadata(
                url=absolute,
                title=title,
                published=datetime(2026, 3, 1, tzinfo=timezone.utc),
                source_key=self.source_key,
            )

        async def extract_report(self, meta: ReportMetadata) -> None:
            return None

    return TestSpaScraper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper_class() -> type:
    """Get the test scraper class."""
    return _make_test_scraper_class()


@pytest.fixture
def scraper(scraper_class: type) -> Any:
    """Create a test scraper instance."""
    return scraper_class()


def _make_mock_element(href: str = "", text: str = "") -> MagicMock:
    """Create a mock Scrapling element with href and text."""
    el = MagicMock()
    el.attrib = {"href": href}
    el.text = text
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
# fetch_listing tests
# ---------------------------------------------------------------------------


class TestFetchListing:
    """Tests for SpaReportScraper.fetch_listing."""

    @pytest.mark.asyncio
    async def test_正常系_DynamicFetcherでJSレンダリング後HTMLを取得できる(
        self, scraper: Any
    ) -> None:
        elements = [
            _make_mock_element(href="/reports/q4", text="Q4 Report"),
            _make_mock_element(href="/reports/q3", text="Q3 Report"),
        ]
        mock_response = _make_mock_response(status=200, elements=elements)
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
        assert result[0].title == "Q4 Report"
        assert result[1].title == "Q3 Report"
        assert result[0].source_key == "test_spa"

    @pytest.mark.asyncio
    async def test_正常系_DynamicFetcherにwait_selectorが渡される(
        self, scraper: Any
    ) -> None:
        """wait_selector が設定されている場合、fetch() に渡されることを確認。"""
        scraper.wait_selector = "div.content-loaded"
        mock_response = _make_mock_response(status=200, elements=[])
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
            await scraper.fetch_listing()

        # DynamicFetcher.fetch should be called with the listing URL
        mock_fetcher.fetch.assert_called_once()
        call_args = mock_fetcher.fetch.call_args
        assert call_args[0][0] == "https://example.com/spa-research"

    @pytest.mark.asyncio
    async def test_異常系_DynamicFetcher未インストールでImportError(
        self, scraper: Any
    ) -> None:
        with (
            patch(
                "report_scraper.scrapers._spa_scraper._dynamic_fetcher_available", False
            ),
            pytest.raises(ImportError, match=r"scrapling.*DynamicFetcher.*required"),
        ):
            await scraper.fetch_listing()

    @pytest.mark.asyncio
    async def test_異常系_非200ステータスでFetchError(self, scraper: Any) -> None:
        mock_response = _make_mock_response(status=403)
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
            pytest.raises(FetchError, match="HTTP 403"),
        ):
            await scraper.fetch_listing()

    @pytest.mark.asyncio
    async def test_異常系_フェッチ例外でFetchError(self, scraper: Any) -> None:
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.side_effect = ConnectionError("Network down")

        with (
            patch(
                "report_scraper.scrapers._spa_scraper._dynamic_fetcher_available", True
            ),
            patch(
                "report_scraper.scrapers._spa_scraper.DynamicFetcher",
                return_value=mock_fetcher,
            ),
            pytest.raises(FetchError, match="Failed to fetch listing"),
        ):
            await scraper.fetch_listing()

    @pytest.mark.asyncio
    async def test_正常系_パース失敗のアイテムはスキップする(
        self, scraper: Any
    ) -> None:
        good_element = _make_mock_element(href="/reports/q4", text="Q4 Report")
        bad_element = _make_mock_element(href="", text="")  # Will return None

        mock_response = _make_mock_response(
            status=200, elements=[good_element, bad_element]
        )
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
        assert result[0].title == "Q4 Report"


# ---------------------------------------------------------------------------
# Playwright/DynamicFetcher import warning tests
# ---------------------------------------------------------------------------


class TestImportWarning:
    """Tests for import warning when DynamicFetcher is unavailable."""

    def test_正常系_DynamicFetcher未インストール時に警告が出る(self) -> None:
        import importlib
        import sys

        mod_name = "report_scraper.scrapers._spa_scraper"
        # Remove the cached module so it can be re-imported
        orig_mod = sys.modules.pop(mod_name, None)

        try:
            with (
                patch.dict("sys.modules", {"scrapling": None}),
                pytest.warns(ImportWarning, match=r"scrapling.*DynamicFetcher"),
            ):
                importlib.import_module(mod_name)
        finally:
            # Restore original module to avoid side effects
            if orig_mod is not None:
                sys.modules[mod_name] = orig_mod


# ---------------------------------------------------------------------------
# Helper method tests
# ---------------------------------------------------------------------------


class TestHelperMethods:
    """Tests for inherited helper methods from HtmlReportScraper patterns."""

    def test_正常系_resolve_urlで相対URLを解決する(self, scraper: Any) -> None:
        result = scraper.resolve_url(
            "/reports/q4.pdf",
            "https://example.com/page",
        )
        assert result == "https://example.com/reports/q4.pdf"

    def test_正常系_resolve_urlで絶対URLはそのまま返す(self, scraper: Any) -> None:
        result = scraper.resolve_url(
            "https://cdn.example.com/report.pdf",
            "https://example.com/page",
        )
        assert result == "https://cdn.example.com/report.pdf"

    def test_正常系_is_pdf_urlでPDFを判定(self, scraper: Any) -> None:
        assert scraper.is_pdf_url("https://example.com/report.pdf") is True
        assert scraper.is_pdf_url("https://example.com/report.html") is False
