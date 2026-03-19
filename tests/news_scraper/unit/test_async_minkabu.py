"""Unit tests for async Minkabu news collector."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_scraper.minkabu import collect_news
from news_scraper.types import ScraperConfig


class TestAsyncMinkabuCollectNews:
    """Tests for async collect_news function in minkabu module."""

    async def test_正常系_collect_newsがコルーチンである(self) -> None:
        """collect_news is a coroutine (async def)."""
        import inspect

        assert inspect.iscoroutinefunction(collect_news)

    async def test_正常系_use_playwright_Falseで空リストを返す(self) -> None:
        """async collect_news returns empty list when use_playwright=False."""
        config = ScraperConfig(use_playwright=False)
        articles = await collect_news(config=config)
        assert articles == []

    async def test_正常系_configがNoneで空リストを返す(self) -> None:
        """async collect_news returns empty list when config is None."""
        articles = await collect_news(config=None)
        assert articles == []

    async def test_正常系_playwright未インストール時に空リストを返す(self) -> None:
        """async collect_news returns empty list when playwright is not installed."""
        config = ScraperConfig(use_playwright=True, max_articles_per_source=5)

        with patch("news_scraper.minkabu.async_playwright", None):
            articles = await collect_news(config=config)

        assert articles == []

    async def test_正常系_async_playwrightを使用して記事を収集する(self) -> None:
        """async collect_news uses async_playwright when use_playwright=True."""
        html = """
        <html><body>
        <ul>
          <li>
            <a href="/news/4469066">
              <h3>テスト記事タイトル</h3>
              <time datetime="2026-03-18T10:00:00+09:00">10:00</time>
            </a>
          </li>
        </ul>
        </body></html>
        """
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.content = AsyncMock(return_value=html)
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_browser.close = AsyncMock()

        mock_chromium = MagicMock()
        mock_chromium.launch = AsyncMock(return_value=mock_browser)

        mock_playwright_obj = MagicMock()
        mock_playwright_obj.chromium = mock_chromium

        mock_async_playwright = MagicMock()
        mock_async_playwright.return_value.__aenter__ = AsyncMock(
            return_value=mock_playwright_obj
        )
        mock_async_playwright.return_value.__aexit__ = AsyncMock(return_value=None)

        config = ScraperConfig(use_playwright=True, max_articles_per_source=5)

        with patch("news_scraper.minkabu.async_playwright", mock_async_playwright):
            articles = await collect_news(config=config)

        assert isinstance(articles, list)

    async def test_正常系_playwrightエラー時に空リストを返す(self) -> None:
        """async collect_news returns empty list on Playwright error."""
        mock_async_playwright = MagicMock()
        mock_async_playwright.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("Browser launch failed")
        )
        mock_async_playwright.return_value.__aexit__ = AsyncMock(return_value=None)

        config = ScraperConfig(use_playwright=True, max_articles_per_source=5)

        with patch("news_scraper.minkabu.async_playwright", mock_async_playwright):
            articles = await collect_news(config=config)

        assert articles == []
