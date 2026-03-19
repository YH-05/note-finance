"""Unit tests for src/news_scraper/jetro.py.

Tests cover the internal helper functions and the main collect_news entry point.
HTTP calls are mocked via unittest.mock to avoid real network access.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from news_scraper._jetro_crawler import CrawledEntry
from news_scraper.jetro import (
    _crawled_entry_to_article,
    _entry_to_article,
    _extract_article_body,
    _extract_tags_from_page,
    _fetch_article_detail,
    _fetch_rss_entries,
    _parse_jetro_date,
    _to_article,
    collect_news,
)
from news_scraper.types import Article, ScraperConfig

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "jetro"
_RSS_FIXTURE = _FIXTURES_DIR / "biznews_rss.xml"
_ARTICLE_FIXTURE = _FIXTURES_DIR / "article_detail.html"


def _make_entry(data: dict) -> MagicMock:
    """Create a feedparser-entry-like mock from a plain dict."""
    entry = MagicMock()
    entry.get = data.get
    return entry


# ---------------------------------------------------------------------------
# TestParseJetroDate
# ---------------------------------------------------------------------------


class TestParseJetroDate:
    """Tests for _parse_jetro_date which handles RFC 2822 and Japanese dates."""

    def test_正常系_RFC2822形式をパースしてUTCに変換(self) -> None:
        """RSS feed の RFC 2822 日付文字列を UTC datetime に変換する。"""
        date_str = "Mon, 18 Mar 2026 09:00:00 +0900"
        result = _parse_jetro_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 18
        # 09:00 JST (+0900) = 00:00 UTC
        assert result.hour == 0
        assert result.tzinfo == timezone.utc

    def test_正常系_日本語日付形式をパース(self) -> None:
        """HTML ページの「YYYY年MM月DD日」形式をパースする。"""
        date_str = "2026年03月18日"
        result = _parse_jetro_date(date_str)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 18
        assert result.tzinfo is not None

    def test_正常系_Noneで現在時刻を返す(self) -> None:
        """None を渡すと現在の UTC 時刻を返す。"""
        before = datetime.now(timezone.utc)
        result = _parse_jetro_date(None)
        after = datetime.now(timezone.utc)
        assert before <= result <= after
        assert result.tzinfo is not None

    def test_正常系_空文字列で現在時刻を返す(self) -> None:
        """空文字列を渡すと現在の UTC 時刻を返す。"""
        before = datetime.now(timezone.utc)
        result = _parse_jetro_date("")
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_異常系_不正な文字列で現在時刻を返す(self) -> None:
        """パース不可能な文字列で現在時刻を返す。"""
        before = datetime.now(timezone.utc)
        result = _parse_jetro_date("invalid-date-string")
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_正常系_日本語日付で月日が1桁の場合(self) -> None:
        """1桁の月日（例: 2026年3月1日）もパースできる。"""
        result = _parse_jetro_date("2026年3月1日")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1

    def test_正常系_UTC以外のタイムゾーンをUTCに変換(self) -> None:
        """+0900 (JST) を UTC に正しく変換する。"""
        date_str = "Fri, 14 Mar 2026 18:00:00 +0900"
        result = _parse_jetro_date(date_str)
        assert result.hour == 9  # 18:00 JST = 09:00 UTC
        assert result.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# TestFetchRssEntries
# ---------------------------------------------------------------------------


class TestFetchRssEntries:
    """Tests for _fetch_rss_entries (JETRO RSS feed fetching)."""

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_RSSフィードからエントリを取得(self, mock_parse: MagicMock) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            {"title": "Article 1", "link": "https://example.com/1"},
            {"title": "Article 2", "link": "https://example.com/2"},
        ]
        mock_parse.return_value = mock_feed

        entries = _fetch_rss_entries()
        assert len(entries) == 2
        mock_parse.assert_called_once()

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_bozoフィードでエントリありの場合は返す(
        self, mock_parse: MagicMock
    ) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = [{"title": "Partial", "link": "https://example.com/p"}]
        mock_parse.return_value = mock_feed

        entries = _fetch_rss_entries()
        assert len(entries) == 1

    @patch("news_scraper.jetro.feedparser.parse")
    def test_異常系_bozoフィードでエントリなしの場合は空リスト(
        self, mock_parse: MagicMock
    ) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_feed.bozo_exception = ValueError("Parse error")
        mock_parse.return_value = mock_feed

        entries = _fetch_rss_entries()
        assert entries == []

    @patch("news_scraper.jetro.feedparser.parse")
    def test_異常系_例外発生時に空リストを返す(self, mock_parse: MagicMock) -> None:
        mock_parse.side_effect = ConnectionError("Network error")
        entries = _fetch_rss_entries()
        assert entries == []

    def test_正常系_フィクスチャファイルが存在する(self) -> None:
        """RSS フィクスチャファイルが存在することを確認。"""
        assert _RSS_FIXTURE.exists(), f"RSS fixture not found: {_RSS_FIXTURE}"


# ---------------------------------------------------------------------------
# TestFetchArticleDetail
# ---------------------------------------------------------------------------


class TestFetchArticleDetail:
    """Tests for _fetch_article_detail (JETRO article page fetching)."""

    def test_正常系_HTMLコンテンツを取得(self) -> None:
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Article content</p></body></html>"
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        result = _fetch_article_detail("https://www.jetro.go.jp/test.html", mock_client)
        assert result is not None
        assert "Article content" in result

    def test_異常系_HTTPエラーでNoneを返す(self) -> None:
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )

        result = _fetch_article_detail("https://www.jetro.go.jp/404.html", mock_client)
        assert result is None

    def test_異常系_リクエストエラーでNoneを返す(self) -> None:
        import httpx

        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")

        result = _fetch_article_detail("https://www.jetro.go.jp/err.html", mock_client)
        assert result is None


# ---------------------------------------------------------------------------
# TestExtractArticleBody
# ---------------------------------------------------------------------------


class TestExtractArticleBody:
    """Tests for _extract_article_body (trafilatura -> lxml fallback)."""

    def test_正常系_trafilaturaで本文を抽出(self) -> None:
        html_content = _ARTICLE_FIXTURE.read_text(encoding="utf-8")
        result = _extract_article_body(html_content)
        assert result is not None
        assert len(result) > 50

    def test_正常系_trafilatura失敗時にlxmlフォールバック(self) -> None:
        """trafilatura が抽出できない場合、lxml CSS セレクタで抽出する。"""
        # Minimal HTML that trafilatura may not extract but lxml can
        html = """
        <html><body>
        <div class="elem_paragraph">
            <p>これはテスト記事の本文です。十分な長さのテキストが含まれています。
            ジェトロの海外ニュースとして公開されたビジネス短信の内容です。</p>
        </div>
        </body></html>
        """
        with patch("news_scraper.jetro.trafilatura.extract", return_value=None):
            result = _extract_article_body(html)
            assert result is not None
            assert "テスト記事" in result

    def test_異常系_抽出できない場合はNoneを返す(self) -> None:
        """空のHTMLからは抽出できない。"""
        with patch("news_scraper.jetro.trafilatura.extract", return_value=None):
            result = _extract_article_body("<html><body></body></html>")
            assert result is None

    def test_正常系_フィクスチャファイルが存在する(self) -> None:
        """記事詳細フィクスチャファイルが存在することを確認。"""
        assert _ARTICLE_FIXTURE.exists(), (
            f"Article fixture not found: {_ARTICLE_FIXTURE}"
        )

    def test_正常系_フィクスチャHTMLから本文を抽出できる(self) -> None:
        """フィクスチャHTMLから記事本文を抽出できることを確認。"""
        html_content = _ARTICLE_FIXTURE.read_text(encoding="utf-8")
        result = _extract_article_body(html_content)
        assert result is not None
        assert len(result) > 0


# ---------------------------------------------------------------------------
# TestExtractTagsFromPage
# ---------------------------------------------------------------------------


class TestExtractTagsFromPage:
    """Tests for _extract_tags_from_page (country/theme/industry tags)."""

    def test_正常系_フィクスチャHTMLからタグを抽出(self) -> None:
        html_content = _ARTICLE_FIXTURE.read_text(encoding="utf-8")
        tags = _extract_tags_from_page(html_content)
        assert isinstance(tags, list)
        assert len(tags) > 0
        # Fixture has tags: 米国, 中国, 関税, 半導体, 貿易
        assert "米国" in tags
        assert "中国" in tags

    def test_正常系_タグなしのHTMLで空リスト(self) -> None:
        html = "<html><body><p>No tags here</p></body></html>"
        tags = _extract_tags_from_page(html)
        assert tags == []

    def test_異常系_不正なHTMLで空リスト(self) -> None:
        tags = _extract_tags_from_page("")
        assert isinstance(tags, list)


# ---------------------------------------------------------------------------
# TestEntryToArticle
# ---------------------------------------------------------------------------


class TestEntryToArticle:
    """Tests for _entry_to_article (JETRO RSS entry -> Article)."""

    def _make_feed_entry(
        self,
        title: str = "テスト記事タイトル",
        link: str = "https://www.jetro.go.jp/biznews/2026/03/test.html",
        published: str = "Mon, 18 Mar 2026 09:00:00 +0900",
        summary: str | None = "テスト記事の概要です。",
        category: str | None = "ビジネス短信",
        tags: list | None = None,
    ) -> MagicMock:
        data: dict = {
            "title": title,
            "link": link,
            "published": published,
            "summary": summary,
            "category": category,
            "tags": tags or [],
        }
        return _make_entry(data)

    def test_正常系_有効なエントリからArticleを生成(self) -> None:
        entry = self._make_feed_entry()
        article = _entry_to_article(entry)
        assert article is not None
        assert article.title == "テスト記事タイトル"
        assert article.url == "https://www.jetro.go.jp/biznews/2026/03/test.html"
        assert article.source == "jetro"
        assert article.summary == "テスト記事の概要です。"

    def test_異常系_title欠落でNoneを返す(self) -> None:
        entry = self._make_feed_entry(title="")
        assert _entry_to_article(entry) is None

    def test_異常系_url欠落でNoneを返す(self) -> None:
        entry = self._make_feed_entry(link="")
        assert _entry_to_article(entry) is None

    def test_正常系_カテゴリがArticleに設定される(self) -> None:
        entry = self._make_feed_entry()
        article = _entry_to_article(entry, category="world")
        assert article is not None
        assert article.category == "world"

    def test_正常系_カテゴリ引数なしでRSSカテゴリを使用(self) -> None:
        entry = self._make_feed_entry(category="ビジネス短信")
        article = _entry_to_article(entry)
        assert article is not None
        assert article.category == "ビジネス短信"

    def test_正常系_summaryなしでArticleを生成(self) -> None:
        entry = self._make_feed_entry(summary=None)
        article = _entry_to_article(entry)
        assert article is not None
        assert article.summary is None

    def test_正常系_sourceがjetroに設定される(self) -> None:
        entry = self._make_feed_entry()
        article = _entry_to_article(entry)
        assert article is not None
        assert article.source == "jetro"

    def test_正常系_metadataにfeed_sourceが含まれる(self) -> None:
        entry = self._make_feed_entry()
        article = _entry_to_article(entry)
        assert article is not None
        assert article.metadata["feed_source"] == "jetro_rss"

    def test_正常系_RSSタグを抽出(self) -> None:
        entry = self._make_feed_entry(tags=[{"term": "米国"}, {"term": "貿易"}])
        article = _entry_to_article(entry)
        assert article is not None
        assert "米国" in article.tags
        assert "貿易" in article.tags

    def test_異常系_titleが非文字列でNoneを返す(self) -> None:
        entry = _make_entry({"title": 123, "link": "https://example.com"})
        assert _entry_to_article(entry) is None


# ---------------------------------------------------------------------------
# TestToArticle
# ---------------------------------------------------------------------------


class TestToArticle:
    """Tests for _to_article (entry + content + tags -> Article)."""

    def _make_feed_entry(self) -> MagicMock:
        data: dict = {
            "title": "テスト記事",
            "link": "https://www.jetro.go.jp/biznews/2026/03/test.html",
            "published": "Mon, 18 Mar 2026 09:00:00 +0900",
            "summary": "概要",
            "category": "ビジネス短信",
            "tags": [{"term": "米国"}],
        }
        return _make_entry(data)

    def test_正常系_コンテンツとタグを結合(self) -> None:
        entry = self._make_feed_entry()
        article = _to_article(entry, None, "Full article text", ["半導体", "貿易"])
        assert article is not None
        assert article.content == "Full article text"
        assert "米国" in article.tags
        assert "半導体" in article.tags
        assert "貿易" in article.tags

    def test_正常系_コンテンツなしでもArticleを生成(self) -> None:
        entry = self._make_feed_entry()
        article = _to_article(entry, None, None, [])
        assert article is not None
        assert article.content is None

    def test_正常系_タグが重複しない(self) -> None:
        entry = self._make_feed_entry()
        article = _to_article(entry, None, None, ["米国", "中国"])
        assert article is not None
        # "米国" comes from RSS tags, should not be duplicated
        assert article.tags.count("米国") == 1
        assert "中国" in article.tags

    def test_異常系_無効なエントリでNoneを返す(self) -> None:
        entry = _make_entry({"title": "", "link": ""})
        assert _to_article(entry, None, "content", ["tag"]) is None


# ---------------------------------------------------------------------------
# TestCollectNews
# ---------------------------------------------------------------------------


class TestCollectNews:
    """Tests for collect_news (main JETRO entry point)."""

    def _make_feed_entry_mock(self, i: int) -> MagicMock:
        data = {
            "title": f"JETRO記事 {i}",
            "link": f"https://www.jetro.go.jp/biznews/2026/03/article{i}.html",
            "published": "Mon, 18 Mar 2026 09:00:00 +0900",
            "summary": f"記事 {i} の概要",
            "category": "ビジネス短信",
            "tags": [],
        }
        return _make_entry(data)

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_RSSフィードから記事を収集(self, mock_parse: MagicMock) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(i) for i in range(3)]
        mock_parse.return_value = mock_feed

        config = ScraperConfig(max_articles_per_source=10)
        articles = collect_news(config=config)

        assert len(articles) == 3
        assert all(a.source == "jetro" for a in articles)
        mock_parse.assert_called_once()

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_max_per_sourceで記事数を制限(self, mock_parse: MagicMock) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(i) for i in range(10)]
        mock_parse.return_value = mock_feed

        config = ScraperConfig(max_articles_per_source=3)
        articles = collect_news(config=config)

        assert len(articles) <= 3

    @patch("news_scraper.jetro.feedparser.parse")
    def test_異常系_フィード取得失敗で空リストを返す(
        self, mock_parse: MagicMock
    ) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        articles = collect_news()
        assert articles == []

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_configがNoneでデフォルト設定を使用(
        self, mock_parse: MagicMock
    ) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(0)]
        mock_parse.return_value = mock_feed

        articles = collect_news(config=None)
        assert isinstance(articles, list)

    @patch("news_scraper.jetro._fetch_article_detail")
    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_include_contentでHTTPクライアントを使用(
        self, mock_parse: MagicMock, mock_fetch_detail: MagicMock
    ) -> None:
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(0)]
        mock_parse.return_value = mock_feed

        mock_fetch_detail.return_value = _ARTICLE_FIXTURE.read_text(encoding="utf-8")

        config = ScraperConfig(include_content=True, max_articles_per_source=1)
        articles = collect_news(config=config)

        assert len(articles) == 1
        # Content should be extracted from the detail page
        assert articles[0].content is not None

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_URLの重複排除が機能する(self, mock_parse: MagicMock) -> None:
        """同一URLのエントリは重複排除される。"""
        entry = self._make_feed_entry_mock(0)
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [entry, entry]  # Same entry twice
        mock_parse.return_value = mock_feed

        articles = collect_news()
        assert len(articles) == 1

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_listArticleを返す(self, mock_parse: MagicMock) -> None:
        """collect_news は list[Article] を返す。"""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [self._make_feed_entry_mock(0)]
        mock_parse.return_value = mock_feed

        articles = collect_news(config=None)
        assert isinstance(articles, list)
        for article in articles:
            assert isinstance(article, Article)


# ---------------------------------------------------------------------------
# TestCrawledEntryToArticle
# ---------------------------------------------------------------------------


class TestCrawledEntryToArticle:
    """Tests for _crawled_entry_to_article (CrawledEntry -> Article)."""

    def _make_crawled_entry(
        self,
        title: str = "テスト記事タイトル",
        url: str = "https://www.jetro.go.jp/biznews/2026/03/test.html",
        category: str = "world",
        subcategory: str = "cn",
        content_type: str | None = "ビジネス短信",
        published: str | None = "2026年03月18日",
    ) -> CrawledEntry:
        return CrawledEntry(
            title=title,
            url=url,
            category=category,
            subcategory=subcategory,
            content_type=content_type,
            published=published,
        )

    def test_正常系_有効なCrawledEntryからArticleを生成(self) -> None:
        """有効な CrawledEntry を Article に変換する。"""
        entry = self._make_crawled_entry()
        article = _crawled_entry_to_article(entry)
        assert article is not None
        assert isinstance(article, Article)
        assert article.title == "テスト記事タイトル"
        assert article.url == "https://www.jetro.go.jp/biznews/2026/03/test.html"
        assert article.source == "jetro"
        assert article.category == "world"

    def test_異常系_title空でNoneを返す(self) -> None:
        """title が空文字の CrawledEntry は None を返す。"""
        entry = self._make_crawled_entry(title="")
        assert _crawled_entry_to_article(entry) is None

    def test_異常系_url空でNoneを返す(self) -> None:
        """url が空文字の CrawledEntry は None を返す。"""
        entry = self._make_crawled_entry(url="")
        assert _crawled_entry_to_article(entry) is None

    def test_正常系_content_typeがtagsに反映(self) -> None:
        """content_type が tags リストに含まれる。"""
        entry = self._make_crawled_entry(content_type="ビジネス短信")
        article = _crawled_entry_to_article(entry)
        assert article is not None
        assert "ビジネス短信" in article.tags

    def test_正常系_content_typeがNoneでtagsは空(self) -> None:
        """content_type が None の場合 tags は空リスト。"""
        entry = self._make_crawled_entry(content_type=None)
        article = _crawled_entry_to_article(entry)
        assert article is not None
        assert article.tags == []

    def test_正常系_metadataにfeed_sourceとsubcategoryが含まれる(self) -> None:
        """metadata に feed_source='jetro_category' と subcategory が含まれる。"""
        entry = self._make_crawled_entry(subcategory="kr")
        article = _crawled_entry_to_article(entry)
        assert article is not None
        assert article.metadata["feed_source"] == "jetro_category"
        assert article.metadata["content_type"] == "ビジネス短信"
        assert article.metadata["subcategory"] == "kr"

    def test_正常系_日本語日付のパース(self) -> None:
        """published の日本語日付文字列が正しくパースされる。"""
        entry = self._make_crawled_entry(published="2026年03月18日")
        article = _crawled_entry_to_article(entry)
        assert article is not None
        assert article.published.year == 2026
        assert article.published.month == 3
        assert article.published.day == 18

    def test_正常系_publishedがNoneで現在時刻(self) -> None:
        """published が None の場合は現在時刻が設定される。"""
        before = datetime.now(timezone.utc)
        entry = self._make_crawled_entry(published=None)
        article = _crawled_entry_to_article(entry)
        after = datetime.now(timezone.utc)
        assert article is not None
        assert before <= article.published <= after


# ---------------------------------------------------------------------------
# TestCollectNewsPhase2
# ---------------------------------------------------------------------------


class TestCollectNewsPhase2:
    """Tests for collect_news Phase 2 (category page crawling)."""

    def _make_feed_entry_mock(self, i: int) -> MagicMock:
        data = {
            "title": f"JETRO記事 {i}",
            "link": f"https://www.jetro.go.jp/biznews/2026/03/article{i}.html",
            "published": "Mon, 18 Mar 2026 09:00:00 +0900",
            "summary": f"記事 {i} の概要",
            "category": "ビジネス短信",
            "tags": [],
        }
        return _make_entry(data)

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_categories指定でPhase2実行(self, mock_parse: MagicMock) -> None:
        """categories を指定すると Phase 2 のカテゴリクロールが実行される。"""
        # Phase 1: RSS returns empty
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        # Phase 2: Mock category crawler returning CrawledEntry
        mock_crawler = MagicMock()
        mock_crawler.crawl_all.return_value = [
            CrawledEntry(
                title="カテゴリ記事1",
                url="https://www.jetro.go.jp/biznews/2026/03/cat1.html",
                category="world",
                subcategory="cn",
                content_type="ビジネス短信",
                published="2026年03月18日",
            ),
        ]
        mock_crawler_cls = MagicMock(return_value=mock_crawler)

        # Patch the class inside the module that gets imported locally
        with patch(
            "news_scraper._jetro_crawler.JetroCategoryCrawler",
            mock_crawler_cls,
        ):
            config = ScraperConfig(max_articles_per_source=50)
            articles = collect_news(
                config=config,
                categories=["world"],
                regions={"asia": ["cn"]},
            )

        assert len(articles) == 1
        assert articles[0].title == "カテゴリ記事1"
        assert articles[0].metadata["feed_source"] == "jetro_category"
        mock_crawler.crawl_all.assert_called_once_with(
            categories=["world"],
            regions={"asia": ["cn"]},
        )

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_ImportErrorでPlaywright未インストール警告(
        self, mock_parse: MagicMock
    ) -> None:
        """Playwright 未インストール時は ImportError を捕捉してスキップする。"""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        # Phase 2: Make the local import raise ImportError using monkeypatch
        import sys

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setitem(sys.modules, "news_scraper._jetro_crawler", None)  # type: ignore[arg-type]
        try:
            # Should not raise, just warn and return empty
            articles = collect_news(
                categories=["world"],
                regions={"asia": ["cn"]},
            )
            assert articles == []
        finally:
            monkeypatch.undo()


# ---------------------------------------------------------------------------
# TestCollectNewsPhase3
# ---------------------------------------------------------------------------


class TestCollectNewsPhase3:
    """Tests for collect_news Phase 3 (archive page crawling)."""

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_archive_pages指定でPhase3実行(self, mock_parse: MagicMock) -> None:
        """archive_pages > 0 かつ regions 指定で Phase 3 が実行される。"""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        mock_crawler = MagicMock()

        async def mock_crawl_archive(**kwargs: object) -> list[CrawledEntry]:
            return [
                CrawledEntry(
                    title="アーカイブ記事",
                    url="https://www.jetro.go.jp/biznews/2025/12/archive1.html",
                    category="world",
                    subcategory="cn",
                    content_type="ビジネス短信",
                    published="2025年12月01日",
                ),
            ]

        mock_crawler.crawl_archive_pages = mock_crawl_archive
        mock_crawler_cls = MagicMock(return_value=mock_crawler)

        with patch(
            "news_scraper._jetro_crawler.JetroCategoryCrawler",
            mock_crawler_cls,
        ):
            config = ScraperConfig(max_articles_per_source=100)
            articles = collect_news(
                config=config,
                archive_pages=1,
                regions={"asia": ["cn"]},
            )

        assert len(articles) > 0
        assert any(a.title == "アーカイブ記事" for a in articles)

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_archive_pages_0でPhase3スキップ(
        self, mock_parse: MagicMock
    ) -> None:
        """archive_pages = 0 の場合 Phase 3 はスキップされる。"""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        articles = collect_news(archive_pages=0, regions={"asia": ["cn"]})
        assert articles == []

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_regionsがNoneでPhase3スキップ(self, mock_parse: MagicMock) -> None:
        """regions が None の場合 Phase 3 はスキップされる。"""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        articles = collect_news(archive_pages=3, regions=None)
        assert articles == []

    @patch("news_scraper.jetro.feedparser.parse")
    def test_正常系_regions空dictでPhase3スキップ(self, mock_parse: MagicMock) -> None:
        """regions が空 dict の場合 Phase 3 はスキップされる。"""
        mock_feed = MagicMock()
        mock_feed.bozo = True
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        # archive_pages > 0 but regions is empty dict {}
        # In Python, empty dict is falsy, so `if archive_pages > 0 and regions:`
        # evaluates to False and Phase 3 is skipped entirely.
        articles = collect_news(archive_pages=3, regions={})
        assert articles == []
