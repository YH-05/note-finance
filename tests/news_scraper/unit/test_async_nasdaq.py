"""Unit tests for async NASDAQ news collector."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from news_scraper.nasdaq import collect_news
from news_scraper.types import ScraperConfig


class TestAsyncNasdaqCollectNews:
    """Tests for async collect_news function."""

    async def test_正常系_collect_newsがコルーチンである(self) -> None:
        """collect_news is a coroutine (async def)."""
        import inspect

        assert inspect.iscoroutinefunction(collect_news)

    async def test_正常系_記事リストを返す(self) -> None:
        """async collect_news returns a list of Article objects."""
        mock_data = {
            "data": {
                "rows": [
                    {
                        "title": "Test Article",
                        "url": "https://www.nasdaq.com/articles/test",
                        "date": "2026-03-01T12:00:00.000Z",
                    }
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            config = ScraperConfig(max_articles_per_source=5)
            articles = await collect_news(config=config, categories=["Markets"])

        assert isinstance(articles, list)

    async def test_正常系_HTTPエラー時に空リストを返す(self) -> None:
        """async collect_news returns empty list on HTTP error."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "403 Forbidden",
                request=MagicMock(),
                response=MagicMock(status_code=403),
            )
        )

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            config = ScraperConfig(max_articles_per_source=5)
            articles = await collect_news(config=config, categories=["Markets"])

        assert articles == []

    async def test_正常系_未知カテゴリはスキップされる(self) -> None:
        """async collect_news skips unknown categories."""
        config = ScraperConfig(max_articles_per_source=5)
        # No HTTP calls should be made for an unknown category
        mock_client = AsyncMock()
        mock_client.get = AsyncMock()

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            articles = await collect_news(config=config, categories=["InvalidCategory"])

        assert articles == []
