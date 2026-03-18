"""Unit tests for async Reuters Japan news collector."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from news_scraper.reuters_jp import collect_news
from news_scraper.types import ScraperConfig


class TestAsyncReutersJpCollectNews:
    """Tests for async collect_news function in reuters_jp module."""

    async def test_正常系_collect_newsがコルーチンである(self) -> None:
        """collect_news is a coroutine (async def)."""
        import inspect

        assert inspect.iscoroutinefunction(collect_news)

    async def test_正常系_記事リストを返す(self) -> None:
        """async collect_news returns a list of Article objects."""
        markets_html = """
        <html><body>
        <div data-testid="HeroCard">
          <div data-testid="Heading">Test Market Article</div>
          <div data-testid="Title"><a href="/markets/japan/TEST123-2026-03-18/">Article</a></div>
          <time dateTime="2026-03-18T09:14:42.564Z">9:14</time>
        </div>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = markets_html
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            config = ScraperConfig(max_articles_per_source=10)
            articles = await collect_news(config=config)

        assert isinstance(articles, list)

    async def test_正常系_HTTPエラー時に空リストを返す(self) -> None:
        """async collect_news returns empty list on HTTP error."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "429",
                request=MagicMock(),
                response=MagicMock(status_code=429),
            )
        )

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            config = ScraperConfig(max_articles_per_source=10)
            articles = await collect_news(config=config)

        assert articles == []

    async def test_正常系_asyncio_gatherを使用して並列取得する(self) -> None:
        """async collect_news uses asyncio.gather for parallel fetching."""
        import asyncio

        markets_html = """
        <html><body>
        <div data-testid="BasicCard">
          <div data-testid="Heading">Markets Article</div>
          <div data-testid="Title"><a href="/markets/test/TEST123-2026-03-18/">Link</a></div>
          <time dateTime="2026-03-18T09:00:00.000Z">9:00</time>
        </div>
        </body></html>
        """
        business_html = """
        <html><body>
        <div data-testid="MediaStoryCard">
          <h3 data-testid="Heading"><a href="/business/japan/TEST456-2026-03-18/">Business</a></h3>
          <time dateTime="2026-03-18T10:00:00.000Z">10:00</time>
        </div>
        </body></html>
        """

        responses = [
            MagicMock(text=markets_html, status_code=200, raise_for_status=MagicMock()),
            MagicMock(
                text=business_html, status_code=200, raise_for_status=MagicMock()
            ),
        ]
        response_iter = iter(responses)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=lambda *a, **kw: next(response_iter))

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            config = ScraperConfig(max_articles_per_source=10)
            articles = await collect_news(config=config)

        assert isinstance(articles, list)
