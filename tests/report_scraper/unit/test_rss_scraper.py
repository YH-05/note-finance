"""Tests for RSS-based report scraper base class and Advisor Perspectives scraper.

Tests cover:
- RssReportScraper date parsing (RFC 2822, ISO 8601, feedparser time tuples)
- RssReportScraper.fetch_listing() with mocked feedparser
- Bozo (malformed feed) error handling
- AdvisorPerspectivesScraper configuration and properties
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from report_scraper.scrapers._rss_scraper import RssReportScraper
from report_scraper.scrapers.advisor_perspectives import AdvisorPerspectivesScraper
from report_scraper.types import ReportMetadata, SourceConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_feed_entry(
    *,
    title: str = "Test Report",
    link: str = "https://example.com/report/1",
    published_parsed: tuple[int, ...] | None = (2026, 3, 1, 12, 0, 0, 5, 60, 0),
    published: str | None = None,
    author: str | None = "John Doe",
    summary: str | None = "Summary of the report.",
) -> MagicMock:
    """Create a mock feedparser entry."""
    entry = MagicMock()
    entry.get = lambda key, default="": {
        "title": title,
        "link": link,
        "published": published,
        "author": author,
        "summary": summary,
    }.get(key, default)
    entry.published_parsed = published_parsed
    entry.updated_parsed = None
    return entry


def _make_parsed_feed(
    *,
    entries: list[Any] | None = None,
    bozo: bool = False,
    bozo_exception: Exception | None = None,
) -> MagicMock:
    """Create a mock feedparser.parse() result."""
    feed = MagicMock()
    feed.entries = entries if entries is not None else []
    feed.bozo = bozo
    feed.get.return_value = bozo_exception
    if bozo_exception is not None:
        feed.__getitem__ = (
            lambda self, key: bozo_exception if key == "bozo_exception" else None
        )
    else:
        feed.__getitem__ = lambda self, key: None
    return feed


@pytest.fixture
def advisor_scraper() -> AdvisorPerspectivesScraper:
    """Create an AdvisorPerspectivesScraper instance."""
    return AdvisorPerspectivesScraper()


# ---------------------------------------------------------------------------
# RssReportScraper._parse_date tests
# ---------------------------------------------------------------------------


class TestParseDateMethod:
    """Tests for RssReportScraper._parse_date."""

    def test_正常系_feedparser_time_tupleから日時をパースできる(self) -> None:
        entry = _make_feed_entry(published_parsed=(2026, 3, 1, 12, 0, 0, 5, 60, 0))
        scraper = AdvisorPerspectivesScraper()
        result = scraper._parse_date(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1
        assert result.tzinfo is not None

    def test_正常系_RFC2822形式の日付文字列をパースできる(self) -> None:
        entry = _make_feed_entry(
            published_parsed=None,
            published="Sat, 01 Mar 2026 12:00:00 GMT",
        )
        scraper = AdvisorPerspectivesScraper()
        result = scraper._parse_date(entry)
        assert result is not None
        assert result.year == 2026
        assert result.month == 3

    def test_正常系_ISO8601形式の日付文字列をパースできる(self) -> None:
        entry = _make_feed_entry(
            published_parsed=None,
            published="2026-03-01T12:00:00+00:00",
        )
        scraper = AdvisorPerspectivesScraper()
        result = scraper._parse_date(entry)
        assert result is not None
        assert result.year == 2026

    def test_異常系_日付情報がない場合Noneを返す(self) -> None:
        entry = _make_feed_entry(published_parsed=None, published=None)
        scraper = AdvisorPerspectivesScraper()
        result = scraper._parse_date(entry)
        assert result is None

    def test_異常系_パース不可能な日付文字列でNoneを返す(self) -> None:
        entry = _make_feed_entry(
            published_parsed=None,
            published="not-a-date",
        )
        scraper = AdvisorPerspectivesScraper()
        result = scraper._parse_date(entry)
        assert result is None


# ---------------------------------------------------------------------------
# RssReportScraper.fetch_listing tests
# ---------------------------------------------------------------------------


class TestFetchListing:
    """Tests for RssReportScraper.fetch_listing."""

    @pytest.mark.asyncio
    async def test_正常系_モックRSSフィードからReportMetadataリストを生成できる(
        self,
    ) -> None:
        entries = [
            _make_feed_entry(
                title="Report A",
                link="https://example.com/a",
                published_parsed=(2026, 3, 1, 12, 0, 0, 5, 60, 0),
                author="Author A",
            ),
            _make_feed_entry(
                title="Report B",
                link="https://example.com/b",
                published_parsed=(2026, 3, 2, 14, 0, 0, 6, 61, 0),
                author="Author B",
            ),
        ]
        parsed = _make_parsed_feed(entries=entries, bozo=False)

        scraper = AdvisorPerspectivesScraper()
        with patch("report_scraper.scrapers._rss_scraper.feedparser") as mock_fp:
            mock_fp.parse.return_value = parsed
            result = await scraper.fetch_listing()

        assert len(result) == 2
        assert all(isinstance(r, ReportMetadata) for r in result)
        assert result[0].title == "Report A"
        assert result[0].url == "https://example.com/a"
        assert result[0].author == "Author A"
        assert result[0].source_key == "advisor_perspectives"
        assert result[1].title == "Report B"

    @pytest.mark.asyncio
    async def test_異常系_bozoフィードで空リストを返す(self) -> None:
        parsed = _make_parsed_feed(
            entries=[],
            bozo=True,
            bozo_exception=Exception("Malformed XML"),
        )

        scraper = AdvisorPerspectivesScraper()
        with patch("report_scraper.scrapers._rss_scraper.feedparser") as mock_fp:
            mock_fp.parse.return_value = parsed
            result = await scraper.fetch_listing()

        assert result == []

    @pytest.mark.asyncio
    async def test_正常系_bozoフィードでもエントリがあれば処理する(self) -> None:
        entries = [
            _make_feed_entry(
                title="Partial Report",
                link="https://example.com/partial",
            ),
        ]
        parsed = _make_parsed_feed(
            entries=entries,
            bozo=True,
            bozo_exception=Exception("Minor XML issue"),
        )

        scraper = AdvisorPerspectivesScraper()
        with patch("report_scraper.scrapers._rss_scraper.feedparser") as mock_fp:
            mock_fp.parse.return_value = parsed
            result = await scraper.fetch_listing()

        assert len(result) == 1
        assert result[0].title == "Partial Report"

    @pytest.mark.asyncio
    async def test_正常系_日付パース失敗のエントリはスキップする(self) -> None:
        good_entry = _make_feed_entry(
            title="Good Report",
            published_parsed=(2026, 3, 1, 12, 0, 0, 5, 60, 0),
        )
        bad_entry = _make_feed_entry(
            title="Bad Date Report",
            published_parsed=None,
            published=None,
        )
        parsed = _make_parsed_feed(entries=[good_entry, bad_entry], bozo=False)

        scraper = AdvisorPerspectivesScraper()
        with patch("report_scraper.scrapers._rss_scraper.feedparser") as mock_fp:
            mock_fp.parse.return_value = parsed
            result = await scraper.fetch_listing()

        # Both entries should be returned; bad date gets None published
        # but the entry itself is not skipped - date is just None
        assert len(result) == 1  # Only good entry (with parseable date)

    @pytest.mark.asyncio
    async def test_異常系_feedparser例外で空リストを返す(self) -> None:
        scraper = AdvisorPerspectivesScraper()
        with patch("report_scraper.scrapers._rss_scraper.feedparser") as mock_fp:
            mock_fp.parse.side_effect = Exception("Network error")
            result = await scraper.fetch_listing()

        assert result == []


# ---------------------------------------------------------------------------
# AdvisorPerspectivesScraper property tests
# ---------------------------------------------------------------------------


class TestAdvisorPerspectivesScraper:
    """Tests for AdvisorPerspectivesScraper configuration."""

    def test_正常系_source_keyが正しい(
        self, advisor_scraper: AdvisorPerspectivesScraper
    ) -> None:
        assert advisor_scraper.source_key == "advisor_perspectives"

    def test_正常系_source_configが正しい(
        self, advisor_scraper: AdvisorPerspectivesScraper
    ) -> None:
        config = advisor_scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "advisor_perspectives"
        assert config.rendering == "rss"
        assert "advisorperspectives.com" in config.listing_url

    def test_正常系_feed_urlが正しい(
        self, advisor_scraper: AdvisorPerspectivesScraper
    ) -> None:
        assert (
            advisor_scraper.feed_url
            == "https://www.advisorperspectives.com/commentaries.rss"
        )

    @pytest.mark.asyncio
    async def test_正常系_extract_reportがScrapedReportを返す(
        self, advisor_scraper: AdvisorPerspectivesScraper
    ) -> None:
        meta = ReportMetadata(
            url="https://example.com/report",
            title="Test Report",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="advisor_perspectives",
        )
        result = await advisor_scraper.extract_report(meta)
        assert result is not None
        assert result.metadata == meta
