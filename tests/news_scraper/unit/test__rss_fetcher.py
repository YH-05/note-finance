"""Unit tests for src/news_scraper/_rss_fetcher.py.

Tests cover all helper functions and the main fetch_rss_feeds async function.
Network calls are mocked via unittest.mock to avoid real network access.
asyncio.to_thread is patched so feedparser.parse runs synchronously in tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_scraper._rss_fetcher import (
    _extract_author,
    _extract_content,
    _extract_tags,
    _get_entry_field,
    _html_to_text,
    _parse_rss_date,
    fetch_rss_feeds,
)
from news_scraper.types import Article, ScraperConfig

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_entry(data: dict) -> MagicMock:
    """Create a feedparser-entry-like mock from a plain dict.

    Uses dict.get so both ``entry.get(k)`` and ``entry.get(k, default)`` work.
    """
    entry = MagicMock()
    entry.get = data.get
    return entry


# ---------------------------------------------------------------------------
# _parse_rss_date
# ---------------------------------------------------------------------------


class TestParseRssDate:
    def test_正常系_Noneで現在時刻を返す(self) -> None:
        fixed = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        with patch("news_scraper._rss_fetcher.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            mock_dt.fromisoformat = datetime.fromisoformat
            result = _parse_rss_date(None)
        assert result == fixed
        assert result.tzinfo is not None

    def test_正常系_空文字列で現在時刻を返す(self) -> None:
        fixed = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        with patch("news_scraper._rss_fetcher.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            mock_dt.fromisoformat = datetime.fromisoformat
            result = _parse_rss_date("")
        assert result == fixed

    def test_正常系_RFC2822文字列をパース(self) -> None:
        date_str = "Mon, 01 Mar 2026 12:00:00 GMT"
        result = _parse_rss_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1
        assert result.hour == 12
        assert result.tzinfo is not None

    def test_正常系_UTCに変換される(self) -> None:
        date_str = "Mon, 01 Mar 2026 17:00:00 +0500"
        result = _parse_rss_date(date_str)
        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # 17:00 +05:00 → 12:00 UTC

    def test_正常系_ISO8601形式をパース(self) -> None:
        date_str = "2026-03-01T12:00:00+00:00"
        result = _parse_rss_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1
        assert result.tzinfo is not None

    def test_異常系_不正な文字列で現在時刻を返す(self) -> None:
        fixed = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
        with patch("news_scraper._rss_fetcher.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            mock_dt.fromisoformat = datetime.fromisoformat
            result = _parse_rss_date("not-a-date")
        assert result == fixed


# ---------------------------------------------------------------------------
# _get_entry_field
# ---------------------------------------------------------------------------


class TestGetEntryField:
    def test_正常系_最初のキーで値を返す(self) -> None:
        entry = _make_entry({"title": "My Title", "link": "https://example.com"})
        result = _get_entry_field(entry, "title", "headline")
        assert result == "My Title"

    def test_正常系_最初のキーが欠落で次のキーを試みる(self) -> None:
        entry = _make_entry({"headline": "Fallback Title"})
        result = _get_entry_field(entry, "title", "headline")
        assert result == "Fallback Title"

    def test_正常系_全キー欠落でNoneを返す(self) -> None:
        entry = _make_entry({})
        result = _get_entry_field(entry, "title", "headline")
        assert result is None

    def test_異常系_非文字列値をスキップして次のキーを試みる(self) -> None:
        entry = _make_entry({"title": 42, "headline": "Valid"})
        result = _get_entry_field(entry, "title", "headline")
        assert result == "Valid"

    def test_エッジケース_空文字列をスキップ(self) -> None:
        entry = _make_entry({"title": "", "headline": "Non-empty"})
        result = _get_entry_field(entry, "title", "headline")
        assert result == "Non-empty"


# ---------------------------------------------------------------------------
# _extract_tags
# ---------------------------------------------------------------------------


class TestExtractTags:
    def test_正常系_dictタグからtermを抽出(self) -> None:
        entry = _make_entry({"tags": [{"term": "markets"}, {"term": "economy"}]})
        result = _extract_tags(entry)
        assert result == ["markets", "economy"]

    def test_正常系_str形式のタグを抽出(self) -> None:
        entry = _make_entry({"tags": ["markets", "stocks"]})
        result = _extract_tags(entry)
        assert result == ["markets", "stocks"]

    def test_正常系_dictとstrの混在(self) -> None:
        entry = _make_entry({"tags": [{"term": "markets"}, "stocks"]})
        result = _extract_tags(entry)
        assert result == ["markets", "stocks"]

    def test_エッジケース_tagsが非リストで空リストを返す(self) -> None:
        entry = _make_entry({"tags": "not-a-list"})
        result = _extract_tags(entry)
        assert result == []

    def test_エッジケース_tagsが空リストで空リストを返す(self) -> None:
        entry = _make_entry({"tags": []})
        result = _extract_tags(entry)
        assert result == []

    def test_エッジケース_dictにtermがない場合はスキップ(self) -> None:
        entry = _make_entry({"tags": [{"label": "markets"}]})
        result = _extract_tags(entry)
        assert result == []


# ---------------------------------------------------------------------------
# _extract_author
# ---------------------------------------------------------------------------


class TestExtractAuthor:
    def test_正常系_author_detail_nameを返す(self) -> None:
        entry = _make_entry({"author_detail": {"name": "Jane Doe"}})
        result = _extract_author(entry)
        assert result == "Jane Doe"

    def test_正常系_authorフィールドのみ(self) -> None:
        entry = _make_entry({"author_detail": None, "author": "John Smith"})
        result = _extract_author(entry)
        assert result == "John Smith"

    def test_エッジケース_両方なしでNoneを返す(self) -> None:
        entry = _make_entry({})
        result = _extract_author(entry)
        assert result is None

    def test_正常系_余分な空白をstrip(self) -> None:
        entry = _make_entry({"author_detail": {"name": "  Jane Doe  "}})
        result = _extract_author(entry)
        assert result == "Jane Doe"


# ---------------------------------------------------------------------------
# _html_to_text
# ---------------------------------------------------------------------------


class TestHtmlToText:
    def test_正常系_HTMLタグを除去してテキストを返す(self) -> None:
        html = "<p>Hello <b>world</b>!</p>"
        result = _html_to_text(html)
        assert "Hello" in result
        assert "world" in result
        assert "<b>" not in result
        assert "<p>" not in result

    def test_正常系_スクリプトとスタイルを除去(self) -> None:
        html = "<html><body><script>alert(1)</script><p>Content</p></body></html>"
        result = _html_to_text(html)
        assert "Content" in result
        assert "alert" not in result

    def test_エッジケース_空文字列で空文字列を返す(self) -> None:
        result = _html_to_text("")
        assert result == ""

    def test_正常系_プレーンテキストをそのまま返す(self) -> None:
        text = "No HTML here"
        result = _html_to_text(text)
        assert "No HTML here" in result


# ---------------------------------------------------------------------------
# _extract_content
# ---------------------------------------------------------------------------


class TestExtractContent:
    def test_正常系_entry_summary_を返す(self) -> None:
        entry = _make_entry({"summary": "Summary text here"})
        result = _extract_content(entry, "entry.summary", content_is_html=False)
        assert result == "Summary text here"

    def test_正常系_content_field_entry_summary_でsummaryから取得(self) -> None:
        entry = _make_entry({"summary": "My summary"})
        result = _extract_content(entry, "entry.summary", content_is_html=False)
        assert result == "My summary"

    def test_正常系_content_field_content_0_value_でcontentから取得(self) -> None:
        entry = _make_entry({"content": [{"value": "<p>Full content here</p>" * 50}]})
        result = _extract_content(entry, "entry.content[0].value", content_is_html=True)
        assert result is not None
        assert len(result) > 0

    def test_正常系_content_is_html_TrueでHTMLを除去(self) -> None:
        html_text = "<p>Hello <b>world</b>!</p>"
        entry = _make_entry({"summary": html_text})
        result = _extract_content(entry, "entry.summary", content_is_html=True)
        assert result is not None
        assert "<b>" not in result
        assert "Hello" in result

    def test_エッジケース_contentが短すぎる場合はNoneを返す(self) -> None:
        # content[0].value is too short (< 100 chars)
        short_content = "x" * 10
        entry = _make_entry({"content": [{"value": short_content}]})
        result = _extract_content(
            entry, "entry.content[0].value", content_is_html=False
        )
        assert result is None

    def test_エッジケース_contentキーがない場合はNoneを返す(self) -> None:
        entry = _make_entry({})
        result = _extract_content(
            entry, "entry.content[0].value", content_is_html=False
        )
        assert result is None

    def test_エッジケース_summaryがNoneの場合はNoneを返す(self) -> None:
        entry = _make_entry({"summary": None})
        result = _extract_content(entry, "entry.summary", content_is_html=False)
        assert result is None


# ---------------------------------------------------------------------------
# fetch_rss_feeds
# ---------------------------------------------------------------------------


class TestFetchRssFeeds:
    """Tests for the main async fetch_rss_feeds function."""

    def _make_feed_entry(self, i: int) -> MagicMock:
        data = {
            "title": f"Article {i}",
            "link": f"https://example.com/article/{i}",
            "published": "Mon, 01 Mar 2026 12:00:00 GMT",
            "summary": f"Summary {i}",
            "tags": [],
        }
        return _make_entry(data)

    def _make_mock_feed(self, num_entries: int = 3, bozo: bool = False) -> MagicMock:
        mock_feed = MagicMock()
        mock_feed.bozo = bozo
        mock_feed.entries = [self._make_feed_entry(i) for i in range(num_entries)]
        return mock_feed

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_記事を収集できる(self, mock_to_thread: AsyncMock) -> None:
        mock_feed = self._make_mock_feed(3)
        mock_to_thread.return_value = mock_feed

        feeds = {"markets": "https://example.com/rss/markets"}
        config = ScraperConfig(max_articles_per_source=10)

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="test_source",
        )

        assert isinstance(articles, list)
        assert len(articles) == 3
        assert all(isinstance(a, Article) for a in articles)

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_max_articles_per_sourceで記事数を制限(
        self, mock_to_thread: AsyncMock
    ) -> None:
        mock_feed = self._make_mock_feed(10)
        mock_to_thread.return_value = mock_feed

        feeds = {"markets": "https://example.com/rss/markets"}
        config = ScraperConfig(max_articles_per_source=3)

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="test_source",
        )

        assert len(articles) <= 3

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_複数フィードを並列フェッチ(
        self, mock_to_thread: AsyncMock
    ) -> None:
        # Each feed returns entries with DIFFERENT URLs to avoid deduplication
        def _make_feed_for_category(category: str) -> MagicMock:
            mock_feed = MagicMock()
            mock_feed.bozo = False
            mock_feed.entries = [
                _make_entry(
                    {
                        "title": f"Article {category}_{i}",
                        "link": f"https://example.com/{category}/article/{i}",
                        "published": "Mon, 01 Mar 2026 12:00:00 GMT",
                        "summary": f"Summary {i}",
                        "tags": [],
                    }
                )
                for i in range(2)
            ]
            return mock_feed

        call_count = 0

        async def _side_effect(fn: Any, url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            # Alternate between markets and economy feeds
            category = "markets" if call_count == 1 else "economy"
            return _make_feed_for_category(category)

        mock_to_thread.side_effect = _side_effect

        feeds = {
            "markets": "https://example.com/rss/markets",
            "economy": "https://example.com/rss/economy",
        }
        config = ScraperConfig(max_articles_per_source=10)

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="test_source",
        )

        # 2 feeds × 2 entries = 4 total (no duplicates since URLs are unique)
        assert len(articles) == 4

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_bozoフィードでentriesなし(
        self, mock_to_thread: AsyncMock
    ) -> None:
        mock_feed = self._make_mock_feed(0, bozo=True)
        mock_to_thread.return_value = mock_feed

        feeds = {"markets": "https://example.com/rss/markets"}
        config = ScraperConfig()

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="test_source",
        )

        assert articles == []

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_異常系_例外発生時に空リストを返す(
        self, mock_to_thread: AsyncMock
    ) -> None:
        mock_to_thread.side_effect = ConnectionError("Network error")

        feeds = {"markets": "https://example.com/rss/markets"}
        config = ScraperConfig()

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="test_source",
        )

        assert articles == []

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_sourceが正しく設定される(
        self, mock_to_thread: AsyncMock
    ) -> None:
        mock_feed = self._make_mock_feed(2)
        mock_to_thread.return_value = mock_feed

        feeds = {"news": "https://example.com/rss"}
        config = ScraperConfig()

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="ars_technica",
        )

        assert all(a.source == "ars_technica" for a in articles)

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_URLが重複する場合はデデュプ(
        self, mock_to_thread: AsyncMock
    ) -> None:
        # Two feeds returning entries with same URL
        def _make_dupe_entry() -> MagicMock:
            data = {
                "title": "Duplicate Article",
                "link": "https://example.com/same-url",
                "published": "Mon, 01 Mar 2026 12:00:00 GMT",
                "summary": "Summary",
                "tags": [],
            }
            return _make_entry(data)

        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [_make_dupe_entry(), _make_dupe_entry()]
        mock_to_thread.return_value = mock_feed

        feeds = {
            "feed1": "https://example.com/rss1",
            "feed2": "https://example.com/rss2",
        }
        config = ScraperConfig(max_articles_per_source=10)

        articles = await fetch_rss_feeds(
            feeds=feeds,
            config=config,
            source_name="test_source",
        )

        # Duplicates by URL should be removed
        urls = [a.url for a in articles]
        assert len(urls) == len(set(urls))

    @pytest.mark.asyncio
    @patch("news_scraper._rss_fetcher.asyncio.to_thread")
    async def test_正常系_include_content_TrueでArticleExtractorを呼ぶ(
        self,
        mock_to_thread: AsyncMock,
    ) -> None:
        mock_feed = self._make_mock_feed(2)
        mock_to_thread.return_value = mock_feed

        from rss.services.article_extractor import ExtractedArticle, ExtractionStatus

        mock_extracted_0 = ExtractedArticle(
            url="https://example.com/article/0",
            title="Article 0",
            text="Full content here for article 0",
            author=None,
            date=None,
            source=None,
            language=None,
            status=ExtractionStatus.SUCCESS,
            error=None,
            extraction_method="trafilatura",
        )
        mock_extracted_1 = ExtractedArticle(
            url="https://example.com/article/1",
            title="Article 1",
            text="Full content here for article 1",
            author=None,
            date=None,
            source=None,
            language=None,
            status=ExtractionStatus.SUCCESS,
            error=None,
            extraction_method="trafilatura",
        )
        mock_extract_batch = AsyncMock(
            return_value=[mock_extracted_0, mock_extracted_1]
        )

        # Patch ArticleExtractor at the module where it is imported inside the function
        with patch("rss.services.ArticleExtractor") as mock_extractor_cls:
            mock_extractor = MagicMock()
            mock_extractor_cls.return_value = mock_extractor
            mock_extractor.extract_batch = mock_extract_batch

            feeds = {"news": "https://example.com/rss"}
            config = ScraperConfig(include_content=True, max_articles_per_source=10)

            articles = await fetch_rss_feeds(
                feeds=feeds,
                config=config,
                source_name="ars_technica",
            )

        mock_extract_batch.assert_called_once()
        assert isinstance(articles, list)
