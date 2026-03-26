"""Unit tests for src/news_scraper/cnbc.py.

Tests cover the CNBC_FEEDS constant and the async collect_news entry point.
Network calls are mocked via unittest.mock to avoid real network access.
asyncio.to_thread is patched so feedparser.parse runs synchronously in tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_scraper.cnbc import CNBC_FEEDS, collect_news
from news_scraper.types import ScraperConfig


def _make_entry(data: dict) -> MagicMock:
    """Create a feedparser-entry-like mock from a plain dict."""
    entry = MagicMock()
    entry.get = data.get
    return entry


def _make_feed_entry_mock(i: int) -> MagicMock:
    data = {
        "title": f"Article {i}",
        "link": f"https://cnbc.com/{i}",
        "published": "Mon, 01 Mar 2026 12:00:00 GMT",
        "summary": f"Summary {i}",
        "tags": [],
    }
    return _make_entry(data)


class TestCnbcFeeds:
    def test_正常系_21フィードが定義されている(self) -> None:
        assert len(CNBC_FEEDS) == 21

    def test_正常系_全URLがCNBCドメイン(self) -> None:
        for name, url in CNBC_FEEDS.items():
            assert "cnbc.com" in url, (
                f"Feed '{name}' URL does not contain cnbc.com: {url}"
            )

    def test_正常系_feeds_jsonの全エントリを含む(self) -> None:
        expected_keys = {
            "top_news",
            "world_news",
            "us_news",
            "markets",
            "investing",
            "economy",
            "finance",
            "technology",
            "asia_news",
            "europe_news",
            "business",
            "earnings",
            "politics",
            "health_care",
            "real_estate",
            "wealth",
            "autos",
            "energy",
            "media",
            "retail",
            "travel",
        }
        assert set(CNBC_FEEDS.keys()) == expected_keys


class TestCollectNews:
    @pytest.mark.asyncio
    async def test_正常系_fetch_rss_feedsに委譲する(self) -> None:
        mock_articles = [MagicMock(), MagicMock()]
        with patch(
            "news_scraper.cnbc.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = mock_articles
            config = ScraperConfig(max_articles_per_source=10)
            result = await collect_news(config=config, categories=["markets"])

        assert result == mock_articles
        mock_fetch.assert_called_once()
        call_args = mock_fetch.call_args
        # feeds is the first positional arg and should contain only "markets"
        assert "markets" in call_args.args[0]
        # source_name is passed as keyword arg
        assert call_args.kwargs.get("source_name") == "cnbc"

    @pytest.mark.asyncio
    async def test_正常系_categoriesなしで全フィードを渡す(self) -> None:
        with patch(
            "news_scraper.cnbc.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await collect_news()

        feeds_arg = mock_fetch.call_args.args[0]
        assert len(feeds_arg) == 21

    @pytest.mark.asyncio
    async def test_正常系_configNoneでデフォルト設定を使用(self) -> None:
        with patch(
            "news_scraper.cnbc.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await collect_news(config=None)

        config_arg = mock_fetch.call_args.args[1]
        assert isinstance(config_arg, ScraperConfig)

    @pytest.mark.asyncio
    async def test_正常系_未知のカテゴリはスキップして空リストを返す(self) -> None:
        with patch(
            "news_scraper.cnbc.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            result = await collect_news(categories=["unknown_category_xyz"])

        assert result == []
        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_正常系_content_fieldがentry_summaryで呼ばれる(self) -> None:
        with patch(
            "news_scraper.cnbc.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await collect_news(categories=["markets"])

        call_kwargs = mock_fetch.call_args
        assert call_kwargs.kwargs.get("content_field") == "entry.summary"
        assert call_kwargs.kwargs.get("content_is_html") is False

    @pytest.mark.asyncio
    async def test_正常系_複数カテゴリを指定できる(self) -> None:
        with patch(
            "news_scraper.cnbc.fetch_rss_feeds", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = []
            await collect_news(categories=["markets", "economy", "earnings"])

        feeds_arg = mock_fetch.call_args.args[0]
        assert set(feeds_arg.keys()) == {"markets", "economy", "earnings"}
