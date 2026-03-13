"""Unit tests for SitemapParser.

Tests cover:
- Single sitemap parsing
- Sitemap index recursive expansion
- URL filtering (category, tag, author, attachment, page)
- lastmod extraction
- Invalid XML error handling
- Multiple platform formats (Yoast, Rank Math, WP native, Ghost, custom)
"""

from __future__ import annotations

import dataclasses
import textwrap
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rss.utils.sitemap_parser import SitemapEntry, SitemapParser

# ---------------------------------------------------------------------------
# XML fixtures
# ---------------------------------------------------------------------------

SINGLE_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/article/post-1</loc>
    <lastmod>2024-01-15</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://example.com/article/post-2</loc>
    <lastmod>2024-02-20</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.6</priority>
  </url>
</urlset>
"""

SITEMAP_INDEX_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-posts.xml</loc>
    <lastmod>2024-03-01</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-pages.xml</loc>
    <lastmod>2024-03-02</lastmod>
  </sitemap>
</sitemapindex>
"""

CHILD_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/article/child-post-1</loc>
    <lastmod>2024-03-10</lastmod>
  </url>
</urlset>
"""

URLS_WITH_EXCLUDED_PATHS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/article/good-post</loc></url>
  <url><loc>https://example.com/category/finance</loc></url>
  <url><loc>https://example.com/tag/stocks</loc></url>
  <url><loc>https://example.com/author/john</loc></url>
  <url><loc>https://example.com/attachment/image-123</loc></url>
  <url><loc>https://example.com/page/2</loc></url>
  <url><loc>https://example.com/article/another-post</loc></url>
</urlset>
"""

# Yoast SEO sitemap format
YOAST_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<?xml-stylesheet type="text/xsl" href="//example.com/wp-content/plugins/wordpress-seo/css/main-sitemap.xsl"?>
<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9
        http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
        xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/yoast-post-1</loc>
    <lastmod>2024-01-10T10:00:00+00:00</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>
"""

# Rank Math sitemap format
RANK_MATH_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
  <url>
    <loc>https://example.com/rank-math-post</loc>
    <lastmod>2024-02-15</lastmod>
    <priority>0.7</priority>
  </url>
</urlset>
"""

# Ghost CMS sitemap format
GHOST_SITEMAP_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/ghost-post-1/</loc>
    <lastmod>2024-03-05T08:00:00.000Z</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>
"""

INVALID_XML = "this is not valid xml at all <<<"

# ---------------------------------------------------------------------------
# SitemapEntry dataclass tests
# ---------------------------------------------------------------------------


class TestSitemapEntry:
    """Test SitemapEntry frozen dataclass."""

    def test_正常系_URLのみで生成できる(self) -> None:
        entry = SitemapEntry(url="https://example.com/post-1")
        assert entry.url == "https://example.com/post-1"
        assert entry.lastmod is None
        assert entry.changefreq is None
        assert entry.priority is None

    def test_正常系_全フィールドを指定して生成できる(self) -> None:
        entry = SitemapEntry(
            url="https://example.com/post-1",
            lastmod="2024-01-15",
            changefreq="monthly",
            priority=0.8,
        )
        assert entry.url == "https://example.com/post-1"
        assert entry.lastmod == "2024-01-15"
        assert entry.changefreq == "monthly"
        assert entry.priority == 0.8

    def test_正常系_frozenなので変更不可(self) -> None:
        entry = SitemapEntry(url="https://example.com/post-1")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            entry.url = "https://other.com"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SitemapParser initialization tests
# ---------------------------------------------------------------------------


class TestSitemapParserInit:
    """Test SitemapParser initialization."""

    def test_正常系_デフォルトでhttp_clientなしで初期化できる(self) -> None:
        parser = SitemapParser()
        assert parser is not None

    def test_正常系_カスタムhttp_clientで初期化できる(self) -> None:
        mock_client = MagicMock()
        parser = SitemapParser(http_client=mock_client)
        assert parser._http_client is mock_client


# ---------------------------------------------------------------------------
# Test 1: 単一サイトマップのパース
# ---------------------------------------------------------------------------


class TestSitemapParserSingleSitemap:
    """Test parsing a single sitemap."""

    @pytest.mark.asyncio
    async def test_正常系_単一サイトマップをパースできる(self) -> None:
        """単一の urlset XML をパースして SitemapEntry リストを返す。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=SINGLE_SITEMAP_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 2
        assert entries[0].url == "https://example.com/article/post-1"
        assert entries[0].lastmod == "2024-01-15"
        assert entries[0].changefreq == "monthly"
        assert entries[0].priority == 0.8

    @pytest.mark.asyncio
    async def test_正常系_lastmodなしのURLもパースできる(self) -> None:
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/no-lastmod</loc>
  </url>
</urlset>
"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=xml)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 1
        assert entries[0].lastmod is None

    @pytest.mark.asyncio
    async def test_正常系_空のurlsetで空リストを返す(self) -> None:
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>
"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=xml)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert entries == []


# ---------------------------------------------------------------------------
# Test 2: サイトマップインデックスの再帰展開
# ---------------------------------------------------------------------------


class TestSitemapParserIndex:
    """Test sitemap index recursive expansion."""

    @pytest.mark.asyncio
    async def test_正常系_インデックスが再帰展開される(self) -> None:
        """sitemapindex を検出して子サイトマップを再帰的にパースする。"""
        parser = SitemapParser()

        async def mock_fetch(url: str) -> str:
            if url == "https://example.com/sitemap-index.xml":
                return SITEMAP_INDEX_XML
            return CHILD_SITEMAP_XML

        parser._fetch_xml = mock_fetch  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap-index.xml")

        # 2 child sitemaps, each with 1 entry
        assert len(entries) == 2
        urls = [e.url for e in entries]
        assert all("child-post" in u for u in urls)

    @pytest.mark.asyncio
    async def test_正常系_インデックスのURLリストを取得できる(self) -> None:
        """parse_index は子サイトマップURLのリストを返す。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=SITEMAP_INDEX_XML)  # type: ignore[method-assign]

        urls = await parser.parse_index("https://example.com/sitemap-index.xml")

        assert len(urls) == 2
        assert "https://example.com/sitemap-posts.xml" in urls
        assert "https://example.com/sitemap-pages.xml" in urls


# ---------------------------------------------------------------------------
# Test 3: URLフィルタリング
# ---------------------------------------------------------------------------


class TestSitemapParserFilter:
    """Test URL filtering of non-post paths."""

    @pytest.mark.asyncio
    async def test_正常系_不要URLが除外される(self) -> None:
        """category, tag, author, attachment, page パスが除外される。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=URLS_WITH_EXCLUDED_PATHS_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")
        filtered = parser.filter_post_urls(entries)

        urls = [e.url for e in filtered]
        assert len(filtered) == 2
        assert "https://example.com/article/good-post" in urls
        assert "https://example.com/article/another-post" in urls
        assert not any("/category/" in u for u in urls)
        assert not any("/tag/" in u for u in urls)
        assert not any("/author/" in u for u in urls)
        assert not any("/attachment/" in u for u in urls)
        assert not any("/page/" in u for u in urls)

    def test_正常系_空リストで空リストを返す(self) -> None:
        parser = SitemapParser()
        result = parser.filter_post_urls([])
        assert result == []

    def test_正常系_全てが記事URLの場合全件返す(self) -> None:
        entries = [
            SitemapEntry(url="https://example.com/post-1"),
            SitemapEntry(url="https://example.com/post-2"),
        ]
        parser = SitemapParser()
        result = parser.filter_post_urls(entries)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Test 4: lastmod の取得
# ---------------------------------------------------------------------------


class TestSitemapParserLastmod:
    """Test lastmod extraction from sitemap entries."""

    @pytest.mark.asyncio
    async def test_正常系_lastmodが正しく取得できる(self) -> None:
        """urlset の各エントリから lastmod を取得できる。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=SINGLE_SITEMAP_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert entries[0].lastmod == "2024-01-15"
        assert entries[1].lastmod == "2024-02-20"

    @pytest.mark.asyncio
    async def test_正常系_ISO8601形式のlastmodも取得できる(self) -> None:
        """ISO 8601 形式のタイムスタンプも lastmod として取得できる。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=YOAST_SITEMAP_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert entries[0].lastmod == "2024-01-10T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Test 5: 不正XMLのエラーハンドリング
# ---------------------------------------------------------------------------


class TestSitemapParserInvalidXML:
    """Test error handling for invalid XML."""

    @pytest.mark.asyncio
    async def test_異常系_不正なXMLでも例外がキャッチされる(self) -> None:
        """不正な XML でも例外が発生せず空リストを返す。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=INVALID_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert entries == []

    @pytest.mark.asyncio
    async def test_異常系_フェッチ失敗でも例外がキャッチされる(self) -> None:
        """HTTP フェッチ失敗でも例外が発生せず空リストを返す。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(side_effect=Exception("connection error"))  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert entries == []


# ---------------------------------------------------------------------------
# Test 6: 各プラットフォーム形式
# ---------------------------------------------------------------------------


class TestSitemapParserPlatformFormats:
    """Test parsing of various platform sitemap formats."""

    @pytest.mark.asyncio
    async def test_正常系_Yoastサイトマップをパースできる(self) -> None:
        """Yoast SEO プラグイン形式のサイトマップをパースできる。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=YOAST_SITEMAP_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 1
        assert entries[0].url == "https://example.com/yoast-post-1"

    @pytest.mark.asyncio
    async def test_正常系_RankMathサイトマップをパースできる(self) -> None:
        """Rank Math SEO プラグイン形式のサイトマップをパースできる。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=RANK_MATH_SITEMAP_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 1
        assert entries[0].url == "https://example.com/rank-math-post"

    @pytest.mark.asyncio
    async def test_正常系_Ghostサイトマップをパースできる(self) -> None:
        """Ghost CMS 形式のサイトマップをパースできる。"""
        parser = SitemapParser()
        parser._fetch_xml = AsyncMock(return_value=GHOST_SITEMAP_XML)  # type: ignore[method-assign]

        entries = await parser.parse("https://example.com/sitemap.xml")

        assert len(entries) == 1
        assert entries[0].url == "https://example.com/ghost-post-1/"


# ---------------------------------------------------------------------------
# TEST-004: _is_safe_sitemap_url のユニットテスト（SSRFガード）
# ---------------------------------------------------------------------------


class TestIsSafeSitemapUrl:
    """TEST-004: _is_safe_sitemap_url の SSRF ガードをテスト。"""

    def test_正常系_同一ドメインのhttpsURLはTrue(self) -> None:
        """同一ドメインのhttps子URLがTrueを返すことを確認する。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "https://example.com/sitemap-posts.xml",
            "https://example.com/sitemap.xml",
        )
        assert result is True

    def test_正常系_同一ドメインのhttpURLはTrue(self) -> None:
        """同一ドメインのhttp子URLがTrueを返すことを確認する。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "http://example.com/sitemap-posts.xml",
            "http://example.com/sitemap.xml",
        )
        assert result is True

    def test_異常系_file_スキームはFalse(self) -> None:
        """file:// スキームの子URLがFalseを返すことを確認する。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "file:///etc/passwd",
            "https://example.com/sitemap.xml",
        )
        assert result is False

    def test_異常系_ftp_スキームはFalse(self) -> None:
        """ftp:// スキームの子URLがFalseを返すことを確認する。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "ftp://example.com/sitemap.xml",
            "https://example.com/sitemap.xml",
        )
        assert result is False

    def test_異常系_異なるドメインはFalse(self) -> None:
        """異なるドメインの子URLがFalseを返すことを確認する（SSRF防止）。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "https://evil.com/malicious-sitemap.xml",
            "https://example.com/sitemap.xml",
        )
        assert result is False

    def test_異常系_サブドメイン偽装はFalse(self) -> None:
        """evil-example.com が example.com と誤マッチしないことを確認する。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "https://evil-example.com/sitemap.xml",
            "https://example.com/sitemap.xml",
        )
        assert result is False

    def test_正常系_同一ドメインの異なるパスはTrue(self) -> None:
        """同一ドメインでパスのみ異なる子URLがTrueを返すことを確認する。"""
        parser = SitemapParser()
        result = parser._is_safe_sitemap_url(
            "https://example.com/blog/sitemap.xml",
            "https://example.com/sitemap-index.xml",
        )
        assert result is True
