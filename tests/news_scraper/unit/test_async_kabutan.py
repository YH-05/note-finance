"""Unit tests for async Kabutan news collector."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from news_scraper.kabutan import collect_news
from news_scraper.types import ScraperConfig


class TestAsyncKabutanCollectNews:
    """Tests for async collect_news function in kabutan module."""

    async def test_正常系_collect_newsがコルーチンである(self) -> None:
        """collect_news is a coroutine (async def)."""
        import inspect

        assert inspect.iscoroutinefunction(collect_news)

    async def test_正常系_記事リストを返す(self) -> None:
        """async collect_news returns a list when HTML is valid."""
        html = """
        <html><body>
        <table class="s_news_list mgbt0">
          <tr>
            <td class="news_time"><time datetime="2026-03-18T18:15:00+09:00">18:15</time></td>
            <td><div class="newslist_ctg">決算</div></td>
            <td><a href="/news/marketnews/?&b=n123">テスト記事</a></td>
          </tr>
        </table>
        </body></html>
        """
        mock_response = MagicMock()
        mock_response.text = html
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
                "403",
                request=MagicMock(),
                response=MagicMock(status_code=403),
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

    async def test_正常系_接続エラー時に空リストを返す(self) -> None:
        """async collect_news returns empty list on network error."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with patch("httpx.AsyncClient") as mock_async_client_cls:
            mock_async_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            config = ScraperConfig(max_articles_per_source=10)
            articles = await collect_news(config=config)

        assert articles == []
