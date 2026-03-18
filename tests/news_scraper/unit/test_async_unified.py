"""Unit tests for async collect_financial_news in news_scraper.unified module.

Tests cover:
- async collect_financial_news returns NewsDataFrame
- deduplication, sorting, error resilience
- asyncio.gather based concurrent collection
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_scraper.types import Article, ScraperConfig
from news_scraper.unified import NewsDataFrame, collect_financial_news


def _make_article(
    title: str = "Test Article",
    url: str = "https://example.com/test",
    source: str = "cnbc",
    published: datetime | None = None,
) -> Article:
    """Helper to create a test Article."""
    if published is None:
        published = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    return Article(title=title, url=url, published=published, source=source)


class TestAsyncCollectFinancialNews:
    """Tests for async collect_financial_news function."""

    async def test_正常系_NewsDataFrameを返す(self) -> None:
        """async collect_financial_news returns NewsDataFrame."""
        with (
            patch("news_scraper.cnbc.collect_news", return_value=[]),
            patch("news_scraper.nasdaq.collect_news", return_value=[]),
        ):
            result = await collect_financial_news(sources=["cnbc", "nasdaq"])
        assert isinstance(result, NewsDataFrame)

    async def test_正常系_cnbcソースのみで収集できる(self) -> None:
        """async collect_financial_news with cnbc source only."""
        cnbc_articles = [
            _make_article(
                title="CNBC Article", url="https://cnbc.com/1", source="cnbc"
            ),
        ]
        with patch("news_scraper.cnbc.collect_news", return_value=cnbc_articles):
            df = await collect_financial_news(sources=["cnbc"])
        assert isinstance(df, NewsDataFrame)
        assert len(df) == 1
        assert df.articles[0].source == "cnbc"

    async def test_正常系_複数ソースで重複URLを除外する(self) -> None:
        """async collect_financial_news deduplicates articles by URL."""
        shared_url = "https://example.com/shared-article"
        cnbc_articles = [
            _make_article(url=shared_url, source="cnbc"),
            _make_article(url="https://cnbc.com/unique", source="cnbc"),
        ]
        nasdaq_articles = [
            _make_article(url=shared_url, source="nasdaq"),
        ]
        with (
            patch("news_scraper.cnbc.collect_news", return_value=cnbc_articles),
            patch("news_scraper.nasdaq.collect_news", return_value=nasdaq_articles),
        ):
            df = await collect_financial_news(sources=["cnbc", "nasdaq"])

        assert len(df) == 2
        urls = [a.url for a in df.articles]
        assert urls.count(shared_url) == 1

    async def test_正常系_記事が公開日時の降順でソートされる(self) -> None:
        """async collect_financial_news returns articles sorted by published date."""
        old_article = _make_article(
            url="https://cnbc.com/old",
            published=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        new_article = _make_article(
            url="https://cnbc.com/new",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        with patch(
            "news_scraper.cnbc.collect_news", return_value=[old_article, new_article]
        ):
            df = await collect_financial_news(sources=["cnbc"])

        assert df.articles[0].published > df.articles[1].published

    async def test_正常系_ソースエラー時も他のソースを処理する(self) -> None:
        """async collect_financial_news continues when one source fails."""
        nasdaq_articles = [
            _make_article(url="https://nasdaq.com/1", source="nasdaq"),
        ]
        with (
            patch(
                "news_scraper.cnbc.collect_news",
                side_effect=Exception("CNBC failed"),
            ),
            patch("news_scraper.nasdaq.collect_news", return_value=nasdaq_articles),
        ):
            df = await collect_financial_news(sources=["cnbc", "nasdaq"])

        assert len(df) == 1
        assert df.articles[0].source == "nasdaq"

    async def test_正常系_configがソースコレクターに渡される(self) -> None:
        """async collect_financial_news passes config to source collectors."""
        config = ScraperConfig(max_articles_per_source=10, include_content=True)
        with patch("news_scraper.cnbc.collect_news", return_value=[]) as mock_cnbc:
            await collect_financial_news(sources=["cnbc"], config=config)
            mock_cnbc.assert_called_once_with(config=config)

    async def test_正常系_reuters_jpソースで収集できる(self) -> None:
        """async collect_financial_news with reuters_jp source."""
        reuters_articles = [
            _make_article(
                title="Reuters JP Article",
                url="https://jp.reuters.com/1",
                source="reuters_jp",
            ),
        ]
        with patch(
            "news_scraper.reuters_jp.collect_news", return_value=reuters_articles
        ):
            df = await collect_financial_news(sources=["reuters_jp"])
        assert len(df) == 1
        assert df.articles[0].source == "reuters_jp"

    async def test_正常系_collect_financial_newsがコルーチンである(self) -> None:
        """collect_financial_news is a coroutine (async def)."""
        import asyncio
        import inspect

        assert inspect.iscoroutinefunction(collect_financial_news)
