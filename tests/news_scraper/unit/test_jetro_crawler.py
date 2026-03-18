"""Unit tests for src/news_scraper/_jetro_crawler.py.

Tests cover CrawledEntry dataclass and JetroCategoryCrawler class methods.
Playwright calls are mocked to avoid real browser launches.
"""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from news_scraper._jetro_config import JETRO_BASE_URL
from news_scraper._jetro_crawler import (
    CrawledEntry,
    JetroCategoryCrawler,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "jetro"
_CATEGORY_FIXTURE = _FIXTURES_DIR / "category_world_cn.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_browser(html_content: str) -> AsyncMock:
    """Create a mock Playwright browser that serves the given HTML."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=html_content)
    page.close = AsyncMock()

    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()
    return browser


def _make_mock_playwright(browser: AsyncMock) -> AsyncMock:
    """Create a mock Playwright instance that returns the given browser."""
    pw = AsyncMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=browser)
    pw.stop = AsyncMock()
    return pw


def _make_mock_pw_context(html_content: str) -> tuple[MagicMock, AsyncMock]:
    """Build complete mock chain: async_playwright() -> context -> pw -> browser.

    Returns
    -------
    tuple[MagicMock, AsyncMock]
        (mock_async_pw_return_value, page_mock)
        where mock_async_pw_return_value should be set as
        mock_async_pw.return_value.
    """
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=html_content)
    page.close = AsyncMock()

    browser = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)
    browser.close = AsyncMock()

    pw = AsyncMock()
    pw.chromium = MagicMock()
    pw.chromium.launch = AsyncMock(return_value=browser)
    pw.stop = AsyncMock()

    # async context manager: async with async_playwright() as pw
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=pw)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    return mock_ctx, page


# ---------------------------------------------------------------------------
# TestCrawledEntry
# ---------------------------------------------------------------------------


class TestCrawledEntry:
    """Tests for CrawledEntry frozen dataclass."""

    def test_正常系_全フィールドを指定して生成(self) -> None:
        """CrawledEntry を全フィールド指定で生成する。"""
        entry = CrawledEntry(
            title="テスト記事タイトル",
            url="https://www.jetro.go.jp/biznews/2026/03/test.html",
            published="2026年03月18日",
            content_type="ビジネス短信",
            category="world",
            subcategory="cn",
        )
        assert entry.title == "テスト記事タイトル"
        assert entry.url == "https://www.jetro.go.jp/biznews/2026/03/test.html"
        assert entry.published == "2026年03月18日"
        assert entry.content_type == "ビジネス短信"
        assert entry.category == "world"
        assert entry.subcategory == "cn"

    def test_正常系_オプションフィールドのデフォルト値(self) -> None:
        """content_type, published は None がデフォルト。"""
        entry = CrawledEntry(
            title="テスト",
            url="https://example.com",
            category="world",
            subcategory="cn",
        )
        assert entry.content_type is None
        assert entry.published is None

    def test_正常系_frozenで変更不可(self) -> None:
        """frozen=True のため属性を変更するとエラー。"""
        entry = CrawledEntry(
            title="テスト",
            url="https://example.com",
            category="world",
            subcategory="cn",
        )
        with pytest.raises(FrozenInstanceError):
            entry.title = "変更後"  # type: ignore[misc]

    def test_正常系_フィクスチャファイルが存在する(self) -> None:
        """カテゴリページフィクスチャファイルが存在することを確認。"""
        assert _CATEGORY_FIXTURE.exists(), (
            f"Category fixture not found: {_CATEGORY_FIXTURE}"
        )


# ---------------------------------------------------------------------------
# TestJetroCategoryCrawler
# ---------------------------------------------------------------------------


class TestJetroCategoryCrawler:
    """Tests for JetroCategoryCrawler class."""

    def test_正常系_デフォルト設定で初期化(self) -> None:
        """デフォルト設定で JetroCategoryCrawler を初期化する。"""
        crawler = JetroCategoryCrawler()
        assert crawler._timeout_ms == 30000
        assert crawler._headless is True

    def test_正常系_カスタムタイムアウトで初期化(self) -> None:
        """カスタムタイムアウトで初期化する。"""
        crawler = JetroCategoryCrawler(timeout_ms=60000, headless=False)
        assert crawler._timeout_ms == 60000
        assert crawler._headless is False


# ---------------------------------------------------------------------------
# TestExtractSectionEntries
# ---------------------------------------------------------------------------


class TestExtractSectionEntries:
    """Tests for _extract_section_entries_from_html (static HTML parsing)."""

    def test_正常系_ビジネス短信セクションからエントリを抽出(self) -> None:
        """ビジネス短信セクションの記事リストを抽出する。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content=html_content,
            section_id="cty_biznews",
            content_type="ビジネス短信",
            category="world",
            subcategory="cn",
        )
        assert len(entries) == 3
        assert entries[0].title == "米国の対中追加関税、半導体分野に影響拡大"
        assert entries[0].url == f"{JETRO_BASE_URL}/biznews/2026/03/abc123def456.html"
        assert entries[0].published == "2026年03月18日"
        assert entries[0].content_type == "ビジネス短信"
        assert entries[0].category == "world"
        assert entries[0].subcategory == "cn"

    def test_正常系_地域分析レポートセクションからエントリを抽出(self) -> None:
        """地域・分析レポートセクションの記事リストを抽出する。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content=html_content,
            section_id="cty_areareports",
            content_type="地域・分析レポート",
            category="world",
            subcategory="cn",
        )
        assert len(entries) == 2
        assert "半導体産業" in entries[0].title
        assert entries[0].content_type == "地域・分析レポート"

    def test_正常系_空セクションで空リスト(self) -> None:
        """イベント情報セクション（空）では空リストを返す。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content=html_content,
            section_id="cty_events",
            content_type="イベント情報",
            category="world",
            subcategory="cn",
        )
        assert entries == []

    def test_正常系_存在しないセクションIDで空リスト(self) -> None:
        """存在しないセクションIDでは空リストを返す。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content=html_content,
            section_id="cty_nonexistent",
            content_type="不明",
            category="world",
            subcategory="cn",
        )
        assert entries == []

    def test_正常系_相対URLが絶対URLに変換される(self) -> None:
        """相対パスのURLがJETRO_BASE_URLで絶対URLに変換される。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content=html_content,
            section_id="cty_biznews",
            content_type="ビジネス短信",
            category="world",
            subcategory="cn",
        )
        for entry in entries:
            assert entry.url.startswith("https://")

    def test_正常系_調査レポートセクションからエントリを抽出(self) -> None:
        """調査レポートセクションの記事リストを抽出する。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content=html_content,
            section_id="cty_reports",
            content_type="調査レポート",
            category="world",
            subcategory="cn",
        )
        assert len(entries) == 1
        assert "中国進出日系企業" in entries[0].title

    def test_異常系_不正なHTMLで空リスト(self) -> None:
        """パース不可能なHTMLでは空リストを返す。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_html(
            html_content="",
            section_id="cty_biznews",
            content_type="ビジネス短信",
            category="world",
            subcategory="cn",
        )
        assert entries == []


# ---------------------------------------------------------------------------
# TestCrawlCategoryPage
# ---------------------------------------------------------------------------


class TestCrawlCategoryPage:
    """Tests for crawl_category_page (Playwright-based)."""

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_カテゴリページからエントリを取得(
        self, mock_async_pw: MagicMock
    ) -> None:
        """Playwright でカテゴリページを取得しエントリを抽出する。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        mock_ctx, _page = _make_mock_pw_context(html_content)
        mock_async_pw.return_value = mock_ctx

        crawler = JetroCategoryCrawler()
        url = "https://www.jetro.go.jp/biznewstop/asia/cn.html"

        entries = asyncio.run(
            crawler.crawl_category_page(url, category="world", subcategory="cn")
        )

        assert len(entries) > 0
        assert all(isinstance(e, CrawledEntry) for e in entries)
        content_types = {e.content_type for e in entries}
        assert "ビジネス短信" in content_types

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_networkidleタイムアウト時にdomcontentloadedへフォールバック(
        self, mock_async_pw: MagicMock
    ) -> None:
        """networkidle タイムアウト時に domcontentloaded へフォールバックする。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        mock_ctx, page = _make_mock_pw_context(html_content)
        mock_async_pw.return_value = mock_ctx

        # Track calls: first goto raises TimeoutError, second succeeds
        call_count = 0

        async def _goto_side_effect(url: str, **kwargs: Any) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1 and kwargs.get("wait_until") == "networkidle":
                raise TimeoutError("networkidle timeout")

        page.goto = AsyncMock(side_effect=_goto_side_effect)

        crawler = JetroCategoryCrawler()
        url = "https://www.jetro.go.jp/biznewstop/asia/cn.html"

        entries = asyncio.run(
            crawler.crawl_category_page(url, category="world", subcategory="cn")
        )

        # Should still get entries despite initial timeout
        assert len(entries) > 0
        # Verify goto was called twice (networkidle + domcontentloaded)
        assert call_count == 2

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_異常系_両方のwait_untilが失敗時に空リスト(
        self, mock_async_pw: MagicMock
    ) -> None:
        """networkidle と domcontentloaded 両方失敗時は空リストを返す。"""
        mock_ctx, page = _make_mock_pw_context("<html></html>")
        page.goto = AsyncMock(side_effect=TimeoutError("All timeouts"))
        mock_async_pw.return_value = mock_ctx

        crawler = JetroCategoryCrawler()
        url = "https://www.jetro.go.jp/biznewstop/asia/cn.html"

        entries = asyncio.run(
            crawler.crawl_category_page(url, category="world", subcategory="cn")
        )

        assert entries == []


# ---------------------------------------------------------------------------
# TestBuildPageUrls
# ---------------------------------------------------------------------------


class TestBuildPageUrls:
    """Tests for _build_page_urls (URL construction logic)."""

    def test_正常系_worldカテゴリとregionsから国別URLを生成(self) -> None:
        """world + regions で国別のURLリストを生成する。"""
        targets = JetroCategoryCrawler._build_page_urls(
            categories=["world"],
            regions={"asia": ["cn", "kr"]},
        )
        assert len(targets) == 2
        urls = [t[0] for t in targets]
        assert any("cn.html" in u for u in urls)
        assert any("kr.html" in u for u in urls)
        # All should be world category
        assert all(t[1] == "world" for t in targets)

    def test_正常系_themeカテゴリはregions不要で直接URL(self) -> None:
        """theme カテゴリは全サブカテゴリURLをそのまま返す。"""
        targets = JetroCategoryCrawler._build_page_urls(
            categories=["theme"],
            regions=None,
        )
        assert len(targets) > 0
        assert all(t[1] == "theme" for t in targets)

    def test_正常系_空のcategoriesで空リスト(self) -> None:
        """空のcategoriesでは空リストを返す。"""
        targets = JetroCategoryCrawler._build_page_urls(
            categories=[],
            regions=None,
        )
        assert targets == []

    def test_正常系_Noneのcategoriesで空リスト(self) -> None:
        """None のcategoriesでは空リストを返す。"""
        targets = JetroCategoryCrawler._build_page_urls(
            categories=None,
            regions=None,
        )
        assert targets == []

    def test_正常系_存在しないregion_keyはスキップ(self) -> None:
        """JETRO_CATEGORY_URLsに存在しないregion_keyはスキップする。"""
        targets = JetroCategoryCrawler._build_page_urls(
            categories=["world"],
            regions={"nonexistent_region": ["cn"]},
        )
        assert targets == []


# ---------------------------------------------------------------------------
# TestCrawlAll
# ---------------------------------------------------------------------------


class TestCrawlAll:
    """Tests for crawl_all (orchestrates multiple category pages)."""

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_worldカテゴリで国別ページをクロール(
        self, mock_async_pw: MagicMock
    ) -> None:
        """world + regions で国別カテゴリページをクロールする。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        mock_ctx, _page = _make_mock_pw_context(html_content)
        mock_async_pw.return_value = mock_ctx

        crawler = JetroCategoryCrawler()
        entries = crawler.crawl_all(
            categories=["world"],
            regions={"asia": ["cn"]},
        )

        assert len(entries) > 0
        assert all(isinstance(e, CrawledEntry) for e in entries)
        assert all(e.category == "world" for e in entries)
        assert all(e.subcategory == "cn" for e in entries)

    def test_正常系_空のカテゴリで空リスト(self) -> None:
        """空のカテゴリリストで空リストを返す。"""
        crawler = JetroCategoryCrawler()
        entries = crawler.crawl_all(categories=[])
        assert entries == []

    def test_正常系_Noneのカテゴリで空リスト(self) -> None:
        """None のカテゴリで空リストを返す。"""
        crawler = JetroCategoryCrawler()
        entries = crawler.crawl_all(categories=None)
        assert entries == []

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_存在しないregionはスキップ(self, mock_async_pw: MagicMock) -> None:
        """存在しないregionキーはスキップして空リストを返す。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        mock_ctx, _page = _make_mock_pw_context(html_content)
        mock_async_pw.return_value = mock_ctx

        crawler = JetroCategoryCrawler()
        entries = crawler.crawl_all(
            categories=["world"],
            regions={"nonexistent_region": ["cn"]},
        )
        assert entries == []


# ---------------------------------------------------------------------------
# TestSyncWrapper
# ---------------------------------------------------------------------------


class TestSyncWrapper:
    """Tests for the sync wrapper (crawl_all uses asyncio.run internally)."""

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_同期呼び出しで結果を取得(self, mock_async_pw: MagicMock) -> None:
        """crawl_all は同期的に呼び出せる。"""
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        mock_ctx, _page = _make_mock_pw_context(html_content)
        mock_async_pw.return_value = mock_ctx

        crawler = JetroCategoryCrawler()
        entries = crawler.crawl_all(
            categories=["world"],
            regions={"asia": ["cn"]},
        )
        assert isinstance(entries, list)
        assert len(entries) > 0
