"""Unit tests for src/news_scraper/cnbc.py.

Tests cover the internal helper functions and the main collect_news entry point.
HTTP calls are mocked via unittest.mock to avoid real network access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from news_scraper.cnbc import (
    _entry_to_article,
    _extract_author,
    _extract_tags,
    _get_entry_field,
    _parse_cnbc_date,
    collect_news,
)
from news_scraper.types import ScraperConfig


def _make_entry(data: dict) -> MagicMock:
    """Create a feedparser-entry-like mock from a plain dict.

    Uses ``*args`` in the lambda so both ``entry.get(k)`` and
    ``entry.get(k, default)`` work correctly.
    """
    entry = MagicMock()
    entry.get = lambda *args: data.get(*args)
    return entry


class TestParseCnbcDate:
    def test_正常系_Noneで現在時刻を返す(self) -> None:
        before = datetime.now(timezone.utc)
        result = _parse_cnbc_date(None)
        after = datetime.now(timezone.utc)
        assert before <= result <= after
        assert result.tzinfo is not None

    def test_正常系_空文字列で現在時刻を返す(self) -> None:
        before = datetime.now(timezone.utc)
        result = _parse_cnbc_date("")
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_正常系_有効なRFC2822文字列をパース(self) -> None:
        date_str = "Mon, 01 Mar 2026 12:00:00 GMT"
        result = _parse_cnbc_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1
        assert result.hour == 12
        assert result.tzinfo is not None

    def test_正常系_UTCに変換される(self) -> None:
        # +0500 offset should be converted to UTC
        date_str = "Mon, 01 Mar 2026 17:00:00 +0500"
        result = _parse_cnbc_date(date_str)
        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # 17:00 +05:00 → 12:00 UTC

    def test_異常系_不正な文字列で現在時刻を返す(self) -> None:
        before = datetime.now(timezone.utc)
        result = _parse_cnbc_date("not-a-date")
        after = datetime.now(timezone.utc)
        assert before <= result <= after


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
        # title is an int (non-string), headline is valid
        entry = _make_entry({"title": 42, "headline": "Valid"})
        result = _get_entry_field(entry, "title", "headline")
        assert result == "Valid"

    def test_エッジケース_空文字列をスキップ(self) -> None:
        entry = _make_entry({"title": "", "headline": "Non-empty"})
        result = _get_entry_field(entry, "title", "headline")
        assert result == "Non-empty"


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


class TestEntryToArticle:
    def _make_feed_entry(
        self,
        title: str = "Test Article",
        link: str = "https://cnbc.com/article",
        published: str = "Mon, 01 Mar 2026 12:00:00 GMT",
        summary: str | None = "Test summary",
    ) -> MagicMock:
        data: dict = {
            "title": title,
            "link": link,
            "published": published,
            "summary": summary,
            "tags": [],
        }
        return _make_entry(data)

    def test_正常系_有効なエントリからArticleを生成(self) -> None:
        entry = self._make_feed_entry()
        article = _entry_to_article(entry, "markets")
        assert article is not None
        assert article.title == "Test Article"
        assert article.url == "https://cnbc.com/article"
        assert article.source == "cnbc"
        assert article.category == "markets"
        assert article.summary == "Test summary"

    def test_異常系_title欠落でNoneを返す(self) -> None:
        entry = self._make_feed_entry(title="")
        assert _entry_to_article(entry, "markets") is None

    def test_異常系_url欠落でNoneを返す(self) -> None:
        entry = self._make_feed_entry(link="")
        assert _entry_to_article(entry, "markets") is None

    def test_正常系_summaryなしでArticleを生成(self) -> None:
        entry = self._make_feed_entry(summary=None)
        article = _entry_to_article(entry, "economy")
        assert article is not None
        assert article.summary is None


class TestCollectNews:
    def _make_feed_entry_mock(self, i: int) -> MagicMock:
        data = {
            "title": f"Article {i}",
            "link": f"https://cnbc.com/{i}",
            "published": "Mon, 01 Mar 2026 12:00:00 GMT",
            "summary": f"Summary {i}",
            "tags": [],
        }
        return _make_entry(data)

    @patch("news_scraper.cnbc.feedparser.parse")
    def test_正常系_feedparserモックで記事を収集(self, mock_parse: MagicMock) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(i) for i in range(3)]
        mock_parse.return_value = mock_feed

        config = ScraperConfig(max_articles_per_source=10)
        articles = collect_news(config=config, categories=["markets"])

        assert len(articles) == 3
        mock_parse.assert_called_once()

    @patch("news_scraper.cnbc.feedparser.parse")
    def test_正常系_未知のカテゴリはスキップ(self, mock_parse: MagicMock) -> None:
        articles = collect_news(categories=["unknown_category_xyz"])
        assert articles == []
        mock_parse.assert_not_called()

    @patch("news_scraper.cnbc.feedparser.parse")
    def test_正常系_bozoフィードでentriesなし(self, mock_parse: MagicMock) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        articles = collect_news(categories=["markets"])
        assert articles == []

    @patch("news_scraper.cnbc.feedparser.parse")
    def test_異常系_例外発生時に空リストを返す(self, mock_parse: MagicMock) -> None:
        mock_parse.side_effect = ConnectionError("Network error")
        articles = collect_news(categories=["markets"])
        assert articles == []

    @patch("news_scraper.cnbc.feedparser.parse")
    def test_正常系_max_per_sourceで記事数を制限(self, mock_parse: MagicMock) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(i) for i in range(10)]
        mock_parse.return_value = mock_feed

        config = ScraperConfig(max_articles_per_source=3)
        articles = collect_news(config=config, categories=["markets"])
        assert len(articles) <= 3
