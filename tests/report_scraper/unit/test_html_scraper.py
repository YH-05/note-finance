"""Tests for HtmlReportScraper base class.

Tests cover:
- Static utility methods (resolve_url, is_pdf_url, find_pdf_links)
- fetch_listing() with mocked StealthyFetcher
- Error handling (ImportError, FetchError, non-200 status)
- extract_links_by_css() helper
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
    """Create a concrete test subclass of HtmlReportScraper.

    Returns the class (not an instance) so tests can instantiate
    with or without mocking Scrapling availability.
    """
    from report_scraper.scrapers._html_scraper import HtmlReportScraper

    class TestHtmlScraper(HtmlReportScraper):
        listing_url = "https://example.com/research"
        article_selector = "div.article a"

        @property
        def source_key(self) -> str:
            return "test_html"

        @property
        def source_config(self) -> SourceConfig:
            return SourceConfig(
                key="test_html",
                name="Test HTML Source",
                tier="sell_side",
                listing_url="https://example.com/research",
                rendering="static",
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

    return TestHtmlScraper


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
# resolve_url tests
# ---------------------------------------------------------------------------


class TestResolveUrl:
    """Tests for HtmlReportScraper.resolve_url."""

    def test_正常系_絶対URLはそのまま返す(self, scraper: Any) -> None:
        result = scraper.resolve_url(
            "https://cdn.example.com/report.pdf",
            "https://example.com/page",
        )
        assert result == "https://cdn.example.com/report.pdf"

    def test_正常系_相対URLをベースURLで解決する(self, scraper: Any) -> None:
        result = scraper.resolve_url(
            "/reports/q4.pdf",
            "https://example.com/page",
        )
        assert result == "https://example.com/reports/q4.pdf"

    def test_正常系_相対パスをベースURLで解決する(self, scraper: Any) -> None:
        result = scraper.resolve_url(
            "docs/report.pdf",
            "https://example.com/research/",
        )
        assert result == "https://example.com/research/docs/report.pdf"

    def test_エッジケース_空文字でもベースURLを返す(self, scraper: Any) -> None:
        result = scraper.resolve_url("", "https://example.com/page")
        assert "example.com" in result


# ---------------------------------------------------------------------------
# is_pdf_url tests
# ---------------------------------------------------------------------------


class TestIsPdfUrl:
    """Tests for HtmlReportScraper.is_pdf_url."""

    def test_正常系_pdf拡張子のURLをTrueと判定(self, scraper: Any) -> None:
        assert scraper.is_pdf_url("https://example.com/report.pdf") is True

    def test_正常系_大文字PDF拡張子もTrueと判定(self, scraper: Any) -> None:
        assert scraper.is_pdf_url("https://example.com/report.PDF") is True

    def test_正常系_クエリパラメータ付きpdfURLもTrueと判定(self, scraper: Any) -> None:
        assert scraper.is_pdf_url("https://example.com/report.pdf?token=abc") is True

    def test_正常系_html拡張子のURLをFalseと判定(self, scraper: Any) -> None:
        assert scraper.is_pdf_url("https://example.com/report.html") is False

    def test_正常系_拡張子なしのURLをFalseと判定(self, scraper: Any) -> None:
        assert scraper.is_pdf_url("https://example.com/report") is False


# ---------------------------------------------------------------------------
# find_pdf_links tests
# ---------------------------------------------------------------------------


class TestFindPdfLinks:
    """Tests for HtmlReportScraper.find_pdf_links."""

    def test_正常系_PDFリンクを抽出できる(self, scraper: Any) -> None:
        elements = [
            _make_mock_element(href="/docs/report.pdf"),
            _make_mock_element(href="/docs/page.html"),
            _make_mock_element(href="/docs/analysis.pdf"),
        ]
        result = scraper.find_pdf_links(elements, "https://example.com")
        assert len(result) == 2
        assert "https://example.com/docs/report.pdf" in result
        assert "https://example.com/docs/analysis.pdf" in result

    def test_正常系_href空のエレメントはスキップ(self, scraper: Any) -> None:
        elements = [
            _make_mock_element(href=""),
            _make_mock_element(href="/docs/report.pdf"),
        ]
        result = scraper.find_pdf_links(elements, "https://example.com")
        assert len(result) == 1

    def test_エッジケース_空リストで空結果(self, scraper: Any) -> None:
        result = scraper.find_pdf_links([], "https://example.com")
        assert result == []


# ---------------------------------------------------------------------------
# fetch_listing tests
# ---------------------------------------------------------------------------


class TestFetchListing:
    """Tests for HtmlReportScraper.fetch_listing."""

    @pytest.mark.asyncio
    async def test_正常系_リスティングページからメタデータを取得できる(
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
            patch("report_scraper.scrapers._html_scraper._scrapling_available", True),
            patch(
                "report_scraper.scrapers._html_scraper.StealthyFetcher",
                return_value=mock_fetcher,
            ),
        ):
            result = await scraper.fetch_listing()

        assert len(result) == 2
        assert all(isinstance(r, ReportMetadata) for r in result)
        assert result[0].title == "Q4 Report"
        assert result[1].title == "Q3 Report"
        assert result[0].source_key == "test_html"

    @pytest.mark.asyncio
    async def test_異常系_scrapling未インストールでImportError(
        self, scraper: Any
    ) -> None:
        with (
            patch("report_scraper.scrapers._html_scraper._scrapling_available", False),
            pytest.raises(ImportError, match="scrapling is required"),
        ):
            await scraper.fetch_listing()

    @pytest.mark.asyncio
    async def test_異常系_非200ステータスでFetchError(self, scraper: Any) -> None:
        mock_response = _make_mock_response(status=403)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch.return_value = mock_response

        with (
            patch("report_scraper.scrapers._html_scraper._scrapling_available", True),
            patch(
                "report_scraper.scrapers._html_scraper.StealthyFetcher",
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
            patch("report_scraper.scrapers._html_scraper._scrapling_available", True),
            patch(
                "report_scraper.scrapers._html_scraper.StealthyFetcher",
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
            patch("report_scraper.scrapers._html_scraper._scrapling_available", True),
            patch(
                "report_scraper.scrapers._html_scraper.StealthyFetcher",
                return_value=mock_fetcher,
            ),
        ):
            result = await scraper.fetch_listing()

        assert len(result) == 1
        assert result[0].title == "Q4 Report"


# ---------------------------------------------------------------------------
# extract_links_by_css tests
# ---------------------------------------------------------------------------


class TestExtractLinksByCss:
    """Tests for HtmlReportScraper.extract_links_by_css."""

    def test_正常系_CSSセレクターでリンクを抽出できる(self, scraper: Any) -> None:
        elements = [
            _make_mock_element(href="/page/1"),
            _make_mock_element(href="https://other.com/page/2"),
        ]
        mock_response = MagicMock()
        mock_response.css.return_value = elements

        result = scraper.extract_links_by_css(
            mock_response,
            "a.link",
            "https://example.com",
        )

        assert len(result) == 2
        assert result[0] == "https://example.com/page/1"
        assert result[1] == "https://other.com/page/2"
        mock_response.css.assert_called_once_with("a.link")

    def test_正常系_href空のエレメントはスキップ(self, scraper: Any) -> None:
        elements = [
            _make_mock_element(href=""),
            _make_mock_element(href="/page/1"),
        ]
        mock_response = MagicMock()
        mock_response.css.return_value = elements

        result = scraper.extract_links_by_css(mock_response, "a", "https://example.com")

        assert len(result) == 1
