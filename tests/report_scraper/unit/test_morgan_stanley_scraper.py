"""Tests for Morgan Stanley scraper.

Tests cover:
- parse_listing_item() with mock HTML elements
- JSON API parsing via parse_json_response()
- source_key and source_config properties
- Hybrid HTML + JSON API fetch_listing()
"""

from __future__ import annotations

import json
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
    text: str = "",
) -> MagicMock:
    """Create a mock Scrapling response."""
    response = MagicMock()
    response.status = status
    response.css.return_value = elements or []
    response.text = text
    return response


# ---------------------------------------------------------------------------
# MorganStanleyScraper tests
# ---------------------------------------------------------------------------


class TestMorganStanleyScraperProperties:
    """Tests for MorganStanleyScraper properties."""

    def test_正常系_source_keyがmorgan_stanleyを返す(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        assert scraper.source_key == "morgan_stanley"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "morgan_stanley"
        assert config.tier == "sell_side"
        assert config.rendering == "static"

    def test_正常系_listing_urlが設定されている(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        assert "morganstanley.com" in scraper.listing_url


class TestMorganStanleyParseListingItem:
    """Tests for MorganStanleyScraper.parse_listing_item."""

    def test_正常系_記事要素からReportMetadataを生成できる(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        el = _make_mock_element(
            href="/im/en-us/insights/articles/market-outlook",
            text="Market Outlook Q1 2026",
        )

        result = scraper.parse_listing_item(
            el,
            "https://www.morganstanley.com/im/en-us/institutional-investor/insights",
        )

        assert result is not None
        assert isinstance(result, ReportMetadata)
        assert result.source_key == "morgan_stanley"
        assert "Market Outlook" in result.title

    def test_エッジケース_hrefが空の要素はNoneを返す(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        el = _make_mock_element(href="", text="Some Title")

        result = scraper.parse_listing_item(
            el,
            "https://www.morganstanley.com",
        )

        assert result is None


class TestMorganStanleyJsonParsing:
    """Tests for Morgan Stanley JSON API response parsing."""

    def test_正常系_JSON応答からReportMetadataリストを生成できる(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        json_data = [
            {
                "title": "Global Investment Committee Weekly",
                "url": "/im/en-us/insights/articles/gic-weekly",
                "date": "2026-03-01",
                "authors": "Lisa Shalett",
            },
            {
                "title": "On the Markets",
                "url": "/im/en-us/insights/articles/on-the-markets",
                "date": "2026-02-28",
                "authors": "Andrew Slimmon",
            },
        ]

        results = scraper.parse_json_response(json_data)

        assert len(results) == 2
        assert all(isinstance(r, ReportMetadata) for r in results)
        assert results[0].title == "Global Investment Committee Weekly"
        assert results[0].source_key == "morgan_stanley"
        assert results[0].author == "Lisa Shalett"

    def test_正常系_不完全なJSON項目はスキップされる(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        json_data = [
            {
                "title": "Valid Article",
                "url": "/im/en-us/insights/valid",
                "date": "2026-03-01",
            },
            {
                # Missing title
                "url": "/im/en-us/insights/missing-title",
                "date": "2026-03-01",
            },
            {
                "title": "Missing URL",
                # Missing url
                "date": "2026-03-01",
            },
        ]

        results = scraper.parse_json_response(json_data)

        assert len(results) == 1
        assert results[0].title == "Valid Article"

    def test_エッジケース_空のJSONリストで空結果(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        results = scraper.parse_json_response([])
        assert results == []


class TestMorganStanleyExtractReport:
    """Tests for MorganStanleyScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()
        meta = ReportMetadata(
            url="https://www.morganstanley.com/im/en-us/insights/articles/gic-weekly",
            title="GIC Weekly",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="morgan_stanley",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta


class TestMorganStanleyFetchListing:
    """Tests for MorganStanleyScraper.fetch_listing with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_正常系_モックHTMLからReportMetadataリストを生成できる(
        self,
    ) -> None:
        from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper

        scraper = MorganStanleyScraper()

        el1 = _make_mock_element(
            href="/im/en-us/insights/article-1",
            text="Insight Article 1",
        )
        el2 = _make_mock_element(
            href="/im/en-us/insights/article-2",
            text="Insight Article 2",
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
        assert all(r.source_key == "morgan_stanley" for r in result)
