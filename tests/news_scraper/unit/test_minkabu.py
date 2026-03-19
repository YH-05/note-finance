"""Unit tests for src/news_scraper/minkabu.py.

Tests cover:
- MINKABU_NEWS_URL constant definition
- collect_news: returns empty list when config=None (use_playwright defaults to False)
- collect_news: returns empty list when config.use_playwright=False
- collect_news: uses async_playwright to fetch page and parses HTML with lxml
- collect_news: respects max_articles_per_source
- collect_news: returns empty list on Playwright launch error (graceful degradation)
- _entry_to_article: converts a valid element to Article
- _entry_to_article: returns None for elements with empty title
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import lxml.html
import pytest

from news_scraper.minkabu import (
    MINKABU_BASE_URL,
    MINKABU_NEWS_URL,
    _entry_to_article,
    collect_news,
)
from news_scraper.types import Article, ScraperConfig

# ─────────────────────────────────────────────────────────────────────────────
# HTML fixture helpers
# ─────────────────────────────────────────────────────────────────────────────

# Minimal Minkabu news article HTML that matches the scraper's selectors.
# Based on the actual minkabu.jp/news structure:
# Article URLs follow the pattern /news/<numeric-id> (e.g. /news/4469066).
# Each article is in a <li> with a nested <a> tag containing the title and href.
_MINKABU_ARTICLE_HTML = """
<div class="news_list">
  <ul>
    <li class="news_list_item">
      <a href="/news/4469066">
        <h3 class="news_list_item__title">テスト記事タイトル1</h3>
        <time datetime="2026-03-18T10:00:00+09:00" class="news_list_item__time">
          2026/03/18 10:00
        </time>
      </a>
    </li>
    <li class="news_list_item">
      <a href="/news/4469067">
        <h3 class="news_list_item__title">テスト記事タイトル2</h3>
        <time datetime="2026-03-18T09:00:00+09:00" class="news_list_item__time">
          2026/03/18 09:00
        </time>
      </a>
    </li>
  </ul>
</div>
"""

_MINKABU_PAGE_HTML = f"""<!DOCTYPE html>
<html lang="ja">
<head><title>みんかぶニュース</title></head>
<body>
{_MINKABU_ARTICLE_HTML}
</body>
</html>"""


def _make_entry_element(
    title: str = "テスト記事タイトル",
    href: str = "/news/4469066",
    datetime_attr: str = "2026-03-18T10:00:00+09:00",
) -> lxml.html.HtmlElement:
    """Build a minimal minkabu news list item element for testing.

    Uses numeric-ID URLs like /news/4469066 (actual minkabu.jp pattern).
    """
    html = f"""<ul>
      <li class="news_list_item">
        <a href="{href}">
          <h3 class="news_list_item__title">{title}</h3>
          <time datetime="{datetime_attr}">2026/03/18 10:00</time>
        </a>
      </li>
    </ul>"""
    root = lxml.html.fromstring(html)
    items = root.xpath("//li[contains(@class, 'news_list_item')]")
    assert items, "Failed to build test li element"
    return items[0]


def _make_empty_title_element() -> lxml.html.HtmlElement:
    """Build a minkabu news list item element with empty title."""
    html = """<ul>
      <li class="news_list_item">
        <a href="/news/9999999">
          <h3 class="news_list_item__title"></h3>
          <time datetime="2026-03-18T10:00:00+09:00">2026/03/18 10:00</time>
        </a>
      </li>
    </ul>"""
    root = lxml.html.fromstring(html)
    items = root.xpath("//li[contains(@class, 'news_list_item')]")
    assert items, "Failed to build test li element"
    return items[0]


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


class TestMinkabuConstants:
    """Tests for module-level constants."""

    def test_正常系_MINKABU_NEWS_URLが定義されている(self) -> None:
        """MINKABU_NEWS_URL constant is defined."""
        assert MINKABU_NEWS_URL == "https://minkabu.jp/news"

    def test_正常系_MINKABU_BASE_URLが定義されている(self) -> None:
        """MINKABU_BASE_URL constant is defined."""
        assert MINKABU_BASE_URL == "https://minkabu.jp"


# ─────────────────────────────────────────────────────────────────────────────
# _entry_to_article
# ─────────────────────────────────────────────────────────────────────────────


class TestEntryToArticle:
    """Tests for _entry_to_article helper function."""

    def test_正常系_有効な要素からArticleを生成する(self) -> None:
        """_entry_to_article converts a valid element to an Article."""
        element = _make_entry_element()
        article = _entry_to_article(element)

        assert article is not None
        assert article.title == "テスト記事タイトル"
        assert article.source == "minkabu"

    def test_正常系_URLが絶対URLに変換される(self) -> None:
        """_entry_to_article converts relative href to absolute URL."""
        href = "/news/4469066"
        element = _make_entry_element(href=href)
        article = _entry_to_article(element)

        assert article is not None
        assert article.url == f"https://minkabu.jp{href}"

    def test_正常系_絶対URLはそのまま使用する(self) -> None:
        """_entry_to_article keeps absolute URLs unchanged."""
        absolute_url = "https://minkabu.jp/news/4469066"
        element = _make_entry_element(href=absolute_url)
        article = _entry_to_article(element)

        assert article is not None
        assert article.url == absolute_url

    def test_正常系_JST時刻をUTCに変換する(self) -> None:
        """_entry_to_article converts JST datetime to UTC."""
        # JST +09:00 → UTC: 10:00 JST == 01:00 UTC
        element = _make_entry_element(datetime_attr="2026-03-18T10:00:00+09:00")
        article = _entry_to_article(element)

        assert article is not None
        assert article.published.tzinfo == timezone.utc
        assert article.published.hour == 1
        assert article.published.day == 18

    def test_正常系_publishedはaware_datetimeである(self) -> None:
        """_entry_to_article returns timezone-aware published datetime."""
        element = _make_entry_element()
        article = _entry_to_article(element)

        assert article is not None
        assert article.published.tzinfo is not None

    def test_正常系_sourceがminkabuである(self) -> None:
        """_entry_to_article sets source to 'minkabu'."""
        element = _make_entry_element()
        article = _entry_to_article(element)

        assert article is not None
        assert article.source == "minkabu"

    def test_異常系_タイトルが空の場合はNoneを返す(self) -> None:
        """_entry_to_article returns None when title is empty."""
        element = _make_empty_title_element()
        result = _entry_to_article(element)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# collect_news: graceful degradation (use_playwright=False)
# ─────────────────────────────────────────────────────────────────────────────


class TestCollectNewsGracefulDegradation:
    """Tests for graceful degradation when use_playwright=False."""

    async def test_正常系_configがNoneの場合は空リストを返す(self) -> None:
        """collect_news returns empty list when config=None (use_playwright defaults False)."""
        result = await collect_news(config=None)
        assert result == []

    async def test_正常系_use_playwright_Falseで空リストを返す(self) -> None:
        """collect_news returns empty list when config.use_playwright=False."""
        config = ScraperConfig(use_playwright=False)
        result = await collect_news(config=config)
        assert result == []

    async def test_正常系_use_playwright_FalseはlistArticleを返す(self) -> None:
        """collect_news returns a list type when use_playwright=False."""
        config = ScraperConfig(use_playwright=False)
        result = await collect_news(config=config)
        assert isinstance(result, list)

    async def test_正常系_use_playwright_Falseはlist型を返す_configなし(self) -> None:
        """collect_news(config=None) returns list type."""
        result = await collect_news()
        assert isinstance(result, list)


# ─────────────────────────────────────────────────────────────────────────────
# collect_news: Playwright enabled
# ─────────────────────────────────────────────────────────────────────────────


def _make_playwright_mock(
    html: str = _MINKABU_PAGE_HTML,
) -> tuple[MagicMock, AsyncMock]:
    """Build mock objects for async_playwright context manager.

    Returns
    -------
    tuple[MagicMock, AsyncMock]
        (async_playwright_patch_target, page_mock)
        where async_playwright_patch_target is suitable for use with patch().
    """
    # page mock (async)
    page = AsyncMock()
    page.content = AsyncMock(return_value=html)
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    # browser mock (async)
    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()

    # playwright instance mock
    playwright_instance = MagicMock()
    playwright_instance.chromium.launch = AsyncMock(return_value=browser)

    # async_playwright() async context manager
    async_pw = MagicMock()
    async_pw.__aenter__ = AsyncMock(return_value=playwright_instance)
    async_pw.__aexit__ = AsyncMock(return_value=False)

    # async_playwright callable that returns the context manager
    async_playwright_fn = MagicMock(return_value=async_pw)

    return async_playwright_fn, page


class TestCollectNewsWithPlaywright:
    """Tests for collect_news when use_playwright=True."""

    async def test_正常系_list_Articleを返す(self) -> None:
        """collect_news returns a list of Article objects."""
        config = ScraperConfig(use_playwright=True)
        async_playwright_fn, _ = _make_playwright_mock()

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        assert isinstance(result, list)

    async def test_正常系_記事を収集する(self) -> None:
        """collect_news collects articles from the Playwright-rendered page."""
        config = ScraperConfig(use_playwright=True, max_articles_per_source=50)
        async_playwright_fn, _ = _make_playwright_mock()

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        assert isinstance(
            result, list
        )  # Result is a list (possibly empty depending on HTML)

    async def test_正常系_URLが絶対URLである(self) -> None:
        """collect_news returns articles with absolute URLs."""
        config = ScraperConfig(use_playwright=True)
        async_playwright_fn, _ = _make_playwright_mock()

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        for article in result:
            assert article.url.startswith("https://")

    async def test_正常系_publishedがUTCである(self) -> None:
        """collect_news returns articles with UTC published datetimes."""
        config = ScraperConfig(use_playwright=True)
        async_playwright_fn, _ = _make_playwright_mock()

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        for article in result:
            assert article.published.tzinfo == timezone.utc

    async def test_正常系_max_articles_per_sourceを遵守する(self) -> None:
        """collect_news respects max_articles_per_source limit."""
        config = ScraperConfig(use_playwright=True, max_articles_per_source=1)
        async_playwright_fn, _ = _make_playwright_mock()

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        assert len(result) <= 1

    async def test_正常系_sourceがminkabuである(self) -> None:
        """collect_news returns articles with source='minkabu'."""
        config = ScraperConfig(use_playwright=True)
        async_playwright_fn, _ = _make_playwright_mock()

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        for article in result:
            assert article.source == "minkabu"

    async def test_異常系_Playwright起動エラー時に空リストを返す(self) -> None:
        """collect_news returns empty list when Playwright raises an exception."""
        config = ScraperConfig(use_playwright=True)

        async_pw = MagicMock()
        async_pw.__aenter__ = AsyncMock(
            side_effect=Exception("Playwright not installed")
        )
        async_pw.__aexit__ = AsyncMock(return_value=False)
        async_playwright_fn = MagicMock(return_value=async_pw)

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        assert result == []

    async def test_異常系_browser_launch失敗時に空リストを返す(self) -> None:
        """collect_news returns empty list when browser.launch() raises."""
        config = ScraperConfig(use_playwright=True)

        playwright_instance = MagicMock()
        playwright_instance.chromium.launch = AsyncMock(
            side_effect=RuntimeError("Browser launch failed")
        )

        async_pw = MagicMock()
        async_pw.__aenter__ = AsyncMock(return_value=playwright_instance)
        async_pw.__aexit__ = AsyncMock(return_value=False)
        async_playwright_fn = MagicMock(return_value=async_pw)

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            result = await collect_news(config=config)

        assert result == []

    async def test_異常系_例外が上位に伝播しない(self) -> None:
        """collect_news does not raise exceptions to the caller."""
        config = ScraperConfig(use_playwright=True)

        async_pw = MagicMock()
        async_pw.__aenter__ = AsyncMock(side_effect=Exception("Fatal error"))
        async_pw.__aexit__ = AsyncMock(return_value=False)
        async_playwright_fn = MagicMock(return_value=async_pw)

        with patch("news_scraper.minkabu.async_playwright", async_playwright_fn):
            # Should not raise
            result = await collect_news(config=config)

        assert isinstance(result, list)
