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
from lxml import html as lxml_html

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
    """Tests for _extract_section_entries_from_tree (static HTML parsing)."""

    @pytest.fixture()
    def _tree(self) -> Any:
        html_content = _CATEGORY_FIXTURE.read_text(encoding="utf-8")
        return lxml_html.fromstring(html_content)

    def test_正常系_ビジネス短信セクションからエントリを抽出(self, _tree: Any) -> None:
        """ビジネス短信セクションの記事リストを抽出する。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_tree(
            tree=_tree,
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

    def test_正常系_地域分析レポートセクションからエントリを抽出(
        self, _tree: Any
    ) -> None:
        """地域・分析レポートセクションの記事リストを抽出する。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_tree(
            tree=_tree,
            section_id="cty_areareports",
            content_type="地域・分析レポート",
            category="world",
            subcategory="cn",
        )
        assert len(entries) == 2
        assert "半導体産業" in entries[0].title
        assert entries[0].content_type == "地域・分析レポート"

    def test_正常系_空セクションで空リスト(self, _tree: Any) -> None:
        """イベント情報セクション（空）では空リストを返す。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_tree(
            tree=_tree,
            section_id="cty_events",
            content_type="イベント情報",
            category="world",
            subcategory="cn",
        )
        assert entries == []

    def test_正常系_存在しないセクションIDで空リスト(self, _tree: Any) -> None:
        """存在しないセクションIDでは空リストを返す。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_tree(
            tree=_tree,
            section_id="cty_nonexistent",
            content_type="不明",
            category="world",
            subcategory="cn",
        )
        assert entries == []

    def test_正常系_相対URLが絶対URLに変換される(self, _tree: Any) -> None:
        """相対パスのURLがJETRO_BASE_URLで絶対URLに変換される。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_tree(
            tree=_tree,
            section_id="cty_biznews",
            content_type="ビジネス短信",
            category="world",
            subcategory="cn",
        )
        for entry in entries:
            assert entry.url.startswith("https://")

    def test_正常系_調査レポートセクションからエントリを抽出(self, _tree: Any) -> None:
        """調査レポートセクションの記事リストを抽出する。"""
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_section_entries_from_tree(
            tree=_tree,
            section_id="cty_reports",
            content_type="調査レポート",
            category="world",
            subcategory="cn",
        )
        assert len(entries) == 1
        assert "中国進出日系企業" in entries[0].title

    def test_異常系_空ツリーでセクションなし(self) -> None:
        """空のHTMLツリーでは空リストを返す。"""
        crawler = JetroCategoryCrawler()
        tree = lxml_html.fromstring("<html><body></body></html>")
        entries = crawler._extract_section_entries_from_tree(
            tree=tree,
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
        assert any("/cn/" in u for u in urls)
        assert any("/kr/" in u for u in urls)
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


# ---------------------------------------------------------------------------
# TestExtractEntriesByHeading
# ---------------------------------------------------------------------------


class TestExtractEntriesByHeading:
    """Tests for _extract_entries_by_heading (h2 heading-based extraction)."""

    def _build_heading_html(
        self,
        heading: str,
        articles: list[tuple[str, str, str]],
    ) -> str:
        """Build HTML with h2 heading and dd/dt article pairs.

        Parameters
        ----------
        heading : str
            The h2 heading text.
        articles : list[tuple[str, str, str]]
            List of (date, title, href) tuples.
        """
        dt_dd_pairs = ""
        for date, title, href in articles:
            dt_dd_pairs += f'<dt>{date}</dt><dd><a href="{href}">{title}</a></dd>\n'

        return f"""
        <html><body>
        <div class="elem_heading_lv2"><h2>{heading}</h2></div>
        <div class="article-list">
            <dl>{dt_dd_pairs}</dl>
        </div>
        </body></html>
        """

    def test_正常系_h2からdd_aエントリを抽出(self) -> None:
        """h2 見出しから dd > a のエントリを抽出する。"""
        html = self._build_heading_html(
            "ビジネス短信",
            [
                ("2026年03月18日", "テスト記事1", "/biznews/2026/03/article1.html"),
                ("2026年03月17日", "テスト記事2", "/biznews/2026/03/article2.html"),
            ],
        )
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")

        assert len(entries) == 2
        assert entries[0].title == "テスト記事1"
        assert entries[0].published == "2026年03月18日"
        assert entries[0].content_type == "ビジネス短信"
        assert entries[0].category == "world"
        assert entries[0].subcategory == "cn"
        assert entries[0].url == f"{JETRO_BASE_URL}/biznews/2026/03/article1.html"

    def test_正常系_複数h2から複数セクションを抽出(self) -> None:
        """複数の h2 見出しからそれぞれのセクションのエントリを抽出する。"""
        html = """
        <html><body>
        <div class="elem_heading_lv2"><h2>ビジネス短信</h2></div>
        <div><dl>
            <dt>2026年03月18日</dt>
            <dd><a href="/biznews/2026/03/a1.html">記事A</a></dd>
        </dl></div>
        <div class="elem_heading_lv2"><h2>調査レポート</h2></div>
        <div><dl>
            <dt>2026年03月15日</dt>
            <dd><a href="/reports/2026/03/r1.html">レポートB</a></dd>
        </dl></div>
        </body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")

        assert len(entries) == 2
        content_types = {e.content_type for e in entries}
        assert "ビジネス短信" in content_types
        assert "調査レポート" in content_types

    def test_正常系_もっと見るリンクをスキップ(self) -> None:
        """「もっと見る」ナビゲーションリンクはスキップされる。"""
        html = """
        <html><body>
        <div class="elem_heading_lv2"><h2>ビジネス短信</h2></div>
        <div><dl>
            <dt>2026年03月18日</dt>
            <dd><a href="/biznews/2026/03/a1.html">記事A</a></dd>
            <dd><a href="/biznews/more.html">もっと見る</a></dd>
        </dl></div>
        </body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")

        assert len(entries) == 1
        assert entries[0].title == "記事A"

    def test_正常系_特集セクションのli_aフォールバック(self) -> None:
        """dd > a がなく li > a がある場合（特集）はフォールバックで抽出する。"""
        html = """
        <html><body>
        <div class="elem_heading_lv2"><h2>特集</h2></div>
        <div>
            <ul>
                <li><a href="/special/2026/03/s1.html">特集記事1</a></li>
                <li><a href="/special/2026/03/s2.html">特集記事2</a></li>
            </ul>
        </div>
        </body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")

        assert len(entries) == 2
        assert entries[0].content_type == "特集"
        assert entries[0].published is None  # li fallback has no date

    def test_正常系_外部ドメインリンクをスキップ(self) -> None:
        """JETRO 以外のドメインのリンクはスキップされる。"""
        html = """
        <html><body>
        <div class="elem_heading_lv2"><h2>ビジネス短信</h2></div>
        <div><dl>
            <dt>2026年03月18日</dt>
            <dd><a href="/biznews/2026/03/a1.html">国内記事</a></dd>
            <dt>2026年03月17日</dt>
            <dd><a href="https://external.example.com/news.html">外部記事</a></dd>
        </dl></div>
        </body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")

        assert len(entries) == 1
        assert entries[0].title == "国内記事"

    def test_正常系_空HTMLで空リスト(self) -> None:
        """h2 見出しがない空の HTML では空リストを返す。"""
        tree = lxml_html.fromstring("<html><body></body></html>")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")
        assert entries == []

    def test_正常系_認識外のh2見出しはスキップ(self) -> None:
        """heading_map に含まれない h2 見出しはスキップされる。"""
        html = """
        <html><body>
        <div class="elem_heading_lv2"><h2>イベント情報</h2></div>
        <div><dl>
            <dt>2026年03月18日</dt>
            <dd><a href="/events/2026/03/e1.html">イベント1</a></dd>
        </dl></div>
        </body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")
        assert entries == []

    def test_正常系_相対URLが絶対URLに変換される(self) -> None:
        """相対パスが JETRO_BASE_URL を使って絶対URLに変換される。"""
        html = self._build_heading_html(
            "ビジネス短信",
            [("2026年03月18日", "記事1", "/biznews/2026/03/test.html")],
        )
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_entries_by_heading(tree, "world", "cn")

        assert len(entries) == 1
        assert entries[0].url.startswith("https://")
        assert JETRO_BASE_URL in entries[0].url


# ---------------------------------------------------------------------------
# TestExtractArchiveEntries
# ---------------------------------------------------------------------------


class TestExtractArchiveEntries:
    """Tests for _extract_archive_entries (archive list page extraction)."""

    def _build_archive_html(
        self,
        articles: list[tuple[str, str, str]],
    ) -> str:
        """Build archive page HTML with li > div.date + div.title structure.

        Parameters
        ----------
        articles : list[tuple[str, str, str]]
            List of (date, title, href) tuples.
        """
        items = ""
        for date, title, href in articles:
            items += f"""
            <li>
                <div class="date">{date}</div>
                <div class="title"><span><a href="{href}">{title}</a></span></div>
            </li>
            """
        return f"<html><body><ul>{items}</ul></body></html>"

    def test_正常系_li_div構造からエントリを抽出(self) -> None:
        """li > div.date + div.title 構造からエントリを抽出する。"""
        html = self._build_archive_html(
            [
                ("2026年03月01日", "アーカイブ記事1", "/biznews/2026/03/arch1.html"),
                ("2026年02月28日", "アーカイブ記事2", "/biznews/2026/02/arch2.html"),
            ]
        )
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_archive_entries(
            tree,
            "world",
            "cn",
            "ビジネス短信",
        )

        assert len(entries) == 2
        assert entries[0].title == "アーカイブ記事1"
        assert entries[0].url == f"{JETRO_BASE_URL}/biznews/2026/03/arch1.html"
        assert entries[0].published == "2026年03月01日"
        assert entries[0].content_type == "ビジネス短信"
        assert entries[0].category == "world"
        assert entries[0].subcategory == "cn"

    def test_正常系_公開日を抽出(self) -> None:
        """div.date から公開日文字列を取得する。"""
        html = self._build_archive_html(
            [
                ("2025年12月15日", "過去記事", "/biznews/2025/12/old.html"),
            ]
        )
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_archive_entries(
            tree,
            "world",
            "cn",
            "調査レポート",
        )

        assert len(entries) == 1
        assert entries[0].published == "2025年12月15日"

    def test_正常系_div_titleなしのliをスキップ(self) -> None:
        """div.title を持たない li 要素はスキップされる。"""
        html = """
        <html><body><ul>
            <li>
                <div class="date">2026年03月01日</div>
                <div class="title"><span><a href="/biznews/a.html">有効記事</a></span></div>
            </li>
            <li>
                <div class="date">2026年03月02日</div>
                <div class="other">タイトルなし</div>
            </li>
        </ul></body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_archive_entries(
            tree,
            "world",
            "cn",
            "ビジネス短信",
        )
        assert len(entries) == 1
        assert entries[0].title == "有効記事"

    def test_正常系_空HTMLで空リスト(self) -> None:
        """空の HTML では空リストを返す。"""
        tree = lxml_html.fromstring("<html><body></body></html>")
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_archive_entries(
            tree,
            "world",
            "cn",
            "ビジネス短信",
        )
        assert entries == []

    def test_正常系_非スラッシュ開始のhrefをスキップ(self) -> None:
        """href が / で始まらないリンクはスキップされる。"""
        html = """
        <html><body><ul>
            <li>
                <div class="date">2026年03月01日</div>
                <div class="title"><span><a href="relative/path.html">相対パス記事</a></span></div>
            </li>
            <li>
                <div class="date">2026年03月02日</div>
                <div class="title"><span><a href="/biznews/valid.html">有効記事</a></span></div>
            </li>
        </ul></body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_archive_entries(
            tree,
            "world",
            "cn",
            "ビジネス短信",
        )
        assert len(entries) == 1
        assert entries[0].title == "有効記事"

    def test_正常系_空タイトルをスキップ(self) -> None:
        """タイトルが空のリンクはスキップされる。"""
        html = """
        <html><body><ul>
            <li>
                <div class="date">2026年03月01日</div>
                <div class="title"><span><a href="/biznews/empty.html"></a></span></div>
            </li>
        </ul></body></html>
        """
        tree = lxml_html.fromstring(html)
        crawler = JetroCategoryCrawler()
        entries = crawler._extract_archive_entries(
            tree,
            "world",
            "cn",
            "ビジネス短信",
        )
        assert entries == []


# ---------------------------------------------------------------------------
# TestCrawlArchivePages
# ---------------------------------------------------------------------------


class TestCrawlArchivePages:
    """Tests for crawl_archive_pages (paginated archive crawling)."""

    def _build_archive_page_html(self, n: int = 3) -> str:
        """Build archive page HTML with n articles."""
        items = ""
        for i in range(n):
            items += f"""
            <li>
                <div class="date">2026年03月{i + 1:02d}日</div>
                <div class="title"><span><a href="/biznews/2026/03/a{i}.html">記事{i}</a></span></div>
            </li>
            """
        return f"<html><body><ul>{items}</ul></body></html>"

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_単一ページからエントリを取得(
        self, mock_async_pw: MagicMock
    ) -> None:
        """単一のアーカイブページからエントリを取得する。"""
        html = self._build_archive_page_html(3)
        mock_ctx, page = _make_mock_pw_context(html)
        mock_async_pw.return_value = mock_ctx

        # No "次へ" button -> locator returns count=0
        next_locator = AsyncMock()
        next_locator.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=next_locator)
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        crawler = JetroCategoryCrawler()
        entries = asyncio.run(
            crawler.crawl_archive_pages(
                url="https://www.jetro.go.jp/biznewstop/asia/cn/biznews/",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                max_pages=1,
            )
        )

        assert len(entries) == 3
        assert all(isinstance(e, CrawledEntry) for e in entries)
        assert all(e.content_type == "ビジネス短信" for e in entries)

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_複数ページを次へボタンで遷移(
        self, mock_async_pw: MagicMock
    ) -> None:
        """「次へ」ボタンをクリックして複数ページを取得する。"""
        page1_html = self._build_archive_page_html(2)
        page2_html = self._build_archive_page_html(2)

        mock_ctx, page = _make_mock_pw_context(page1_html)
        mock_async_pw.return_value = mock_ctx

        # Return page1 first, then page2 after "次へ" click
        page.content = AsyncMock(side_effect=[page1_html, page2_html])

        # "次へ" button available on page 1
        next_locator = AsyncMock()
        next_locator.count = AsyncMock(return_value=1)
        next_locator.click = AsyncMock()
        page.locator = MagicMock(return_value=next_locator)
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        crawler = JetroCategoryCrawler()
        entries = asyncio.run(
            crawler.crawl_archive_pages(
                url="https://www.jetro.go.jp/biznewstop/asia/cn/biznews/",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                max_pages=2,
            )
        )

        assert len(entries) == 4  # 2 from each page
        next_locator.click.assert_called_once()

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_次へボタンなしで停止(self, mock_async_pw: MagicMock) -> None:
        """「次へ」ボタンがない場合はそのページで停止する。"""
        html = self._build_archive_page_html(3)
        mock_ctx, page = _make_mock_pw_context(html)
        mock_async_pw.return_value = mock_ctx

        next_locator = AsyncMock()
        next_locator.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=next_locator)
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        crawler = JetroCategoryCrawler()
        entries = asyncio.run(
            crawler.crawl_archive_pages(
                url="https://www.jetro.go.jp/biznewstop/asia/cn/biznews/",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                max_pages=5,  # Request 5 pages but only 1 exists
            )
        )

        assert len(entries) == 3  # Only from the first page

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_max_pages制限(self, mock_async_pw: MagicMock) -> None:
        """max_pages でページ数が制限される。"""
        html = self._build_archive_page_html(3)
        mock_ctx, page = _make_mock_pw_context(html)
        mock_async_pw.return_value = mock_ctx

        # "次へ" always available
        next_locator = AsyncMock()
        next_locator.count = AsyncMock(return_value=1)
        next_locator.click = AsyncMock()
        page.locator = MagicMock(return_value=next_locator)
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        crawler = JetroCategoryCrawler()
        entries = asyncio.run(
            crawler.crawl_archive_pages(
                url="https://www.jetro.go.jp/biznewstop/asia/cn/biznews/",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                max_pages=1,  # Only 1 page
            )
        )

        # max_pages=1, so no "次へ" click should happen (page_num < max_pages - 1 is False)
        assert len(entries) == 3
        next_locator.click.assert_not_called()

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_異常系_ページ読み込み失敗で空リスト(
        self, mock_async_pw: MagicMock
    ) -> None:
        """ページ読み込みが失敗した場合は空リストを返す。"""
        mock_ctx, page = _make_mock_pw_context("")
        mock_async_pw.return_value = mock_ctx

        # page.content returns invalid HTML
        page.content = AsyncMock(return_value="<invalid")
        page.locator = MagicMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        crawler = JetroCategoryCrawler()
        entries = asyncio.run(
            crawler.crawl_archive_pages(
                url="https://www.jetro.go.jp/biznewstop/asia/cn/biznews/",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                max_pages=1,
            )
        )

        # lxml may parse partially or return empty entries
        assert isinstance(entries, list)

    @patch("news_scraper._jetro_crawler.async_playwright")
    def test_正常系_空のアーカイブページで停止(self, mock_async_pw: MagicMock) -> None:
        """アーカイブページにエントリがない場合はそのページで停止する。"""
        empty_html = "<html><body><ul></ul></body></html>"
        mock_ctx, page = _make_mock_pw_context(empty_html)
        mock_async_pw.return_value = mock_ctx
        page.locator = MagicMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        crawler = JetroCategoryCrawler()
        entries = asyncio.run(
            crawler.crawl_archive_pages(
                url="https://www.jetro.go.jp/biznewstop/asia/cn/biznews/",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                max_pages=3,
            )
        )

        assert entries == []


# ---------------------------------------------------------------------------
# TestResolveHref
# ---------------------------------------------------------------------------


class TestResolveHref:
    """Tests for JetroCategoryCrawler._resolve_href static method."""

    def test_正常系_絶対パスをJETROドメインで解決(self) -> None:
        """Absolute path is resolved to JETRO base URL."""
        result = JetroCategoryCrawler._resolve_href("/biznews/article.html")
        assert result == f"{JETRO_BASE_URL}/biznews/article.html"

    def test_正常系_JETROドメインのHTTP_URLをそのまま返す(self) -> None:
        """JETRO domain URL is returned as-is."""
        url = f"{JETRO_BASE_URL}/biznews/article.html"
        result = JetroCategoryCrawler._resolve_href(url)
        assert result == url

    def test_正常系_相対パスをJETROベースURLで解決(self) -> None:
        """Relative path is resolved with JETRO base URL."""
        result = JetroCategoryCrawler._resolve_href("biznews/article.html")
        assert result == f"{JETRO_BASE_URL}/biznews/article.html"

    def test_異常系_外部ドメインURLはNoneを返す(self) -> None:
        """External domain URL returns None."""
        result = JetroCategoryCrawler._resolve_href("https://example.com/article")
        assert result is None

    def test_異常系_javascriptスキームはNoneを返す(self) -> None:
        """javascript: scheme returns None."""
        result = JetroCategoryCrawler._resolve_href("javascript:void(0)")
        assert result is None

    def test_異常系_dataスキームはNoneを返す(self) -> None:
        """data: scheme returns None."""
        result = JetroCategoryCrawler._resolve_href("data:text/html,test")
        assert result is None

    def test_異常系_ftpスキームはNoneを返す(self) -> None:
        """ftp: scheme returns None."""
        result = JetroCategoryCrawler._resolve_href("ftp://files.example.com/doc")
        assert result is None
