"""Unit tests for src/news_scraper/reuters_jp.py.

Tests cover:
- Module-level constants (XPath expressions, URLs)
- _parse_utc_z_datetime: ISO 8601 UTC (Z suffix) datetime parsing
- _parse_markets_page: HeroCard + BasicCard extraction, relative URL resolution
- _parse_business_page: MediaStoryCard hero/hub variant extraction
- _card_to_article: conversion of card elements to Articles
- collect_news: ThreadPoolExecutor parallel fetch, 429/403 graceful degradation
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import lxml.html
import pytest

from news_scraper.reuters_jp import (
    BUSINESS_CARDS_XPATH,
    BUSINESS_DATE_XPATH,
    BUSINESS_TITLE_XPATH,
    BUSINESS_URL_HERO_XPATH,
    BUSINESS_URL_HUB_XPATH,
    MARKETS_CARDS_XPATH,
    MARKETS_DATE_XPATH,
    MARKETS_TITLE_XPATH,
    MARKETS_URL_XPATH,
    REUTERS_JP_BASE_URL,
    REUTERS_JP_SECTIONS,
    _parse_business_page,
    _parse_markets_page,
    _parse_utc_z_datetime,
    collect_news,
)
from news_scraper.types import Article, ScraperConfig

# ─────────────────────────────────────────────────────────────────────────────
# HTML fixtures
# ─────────────────────────────────────────────────────────────────────────────

# Minimal /markets/ page with one HeroCard and one BasicCard
_MARKETS_HTML = """<!DOCTYPE html>
<html>
<body>
  <div data-testid="HeroCard">
    <div data-testid="Heading">
      <span>日銀が政策金利を据え置き</span>
    </div>
    <div data-testid="Title">
      <a href="/markets/japan/BOJ-DECISION-2026-03-18/">日銀決定</a>
    </div>
    <time dateTime="2026-03-18T09:14:42.564Z">2026/03/18</time>
  </div>
  <div data-testid="BasicCard">
    <div data-testid="Heading">
      <span>東京株式市場・前場 日経平均は小幅高</span>
    </div>
    <div data-testid="Title">
      <a href="/markets/japan/NIKKEI-MORNING-2026-03-18/">日経前場</a>
    </div>
    <time dateTime="2026-03-18T02:30:00.000Z">2026/03/18</time>
  </div>
</body>
</html>"""

# /markets/ page where BasicCard has no Title wrapper (URL on container div)
_MARKETS_HTML_FALLBACK_URL = """<!DOCTYPE html>
<html>
<body>
  <div data-testid="BasicCard" href="/markets/fallback/ARTICLE-2026-03-18/">
    <div data-testid="Heading">
      <span>フォールバック記事タイトル</span>
    </div>
    <time dateTime="2026-03-18T05:00:00.000Z">2026/03/18</time>
  </div>
</body>
</html>"""

# Minimal /business/ page with hero + hub MediaStoryCard variants
_BUSINESS_HTML = """<!DOCTYPE html>
<html>
<body>
  <!-- hero variant: URL is inside h3[data-testid='Heading']//a -->
  <div data-testid="MediaStoryCard">
    <h3 data-testid="Heading">
      <a href="/business/economy/JAPAN-GDP-2026-03-18/">日本GDP発表</a>
    </h3>
    <time dateTime="2026-03-18T08:00:00.000Z">2026/03/18</time>
  </div>
  <!-- hub variant: URL is on a[data-testid='Heading'] -->
  <div data-testid="MediaStoryCard">
    <a data-testid="Heading" href="https://jp.reuters.com/business/autos/TOYOTA-2026-03-18/">
      トヨタ決算発表
    </a>
    <time dateTime="2026-03-18T06:30:00.000Z">2026/03/18</time>
  </div>
</body>
</html>"""

# HTML with no cards (empty page)
_EMPTY_HTML = """<!DOCTYPE html>
<html><body><div>コンテンツなし</div></body></html>"""

# HTML with cards missing datetime
_MARKETS_HTML_NO_DATE = """<!DOCTYPE html>
<html>
<body>
  <div data-testid="BasicCard">
    <div data-testid="Heading">
      <span>日時なし記事</span>
    </div>
    <div data-testid="Title">
      <a href="/markets/japan/NO-DATE-2026-03-18/">日時なし</a>
    </div>
  </div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Mock client helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_mock_response(html: str, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response."""
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.status_code = status_code
    mock_response.raise_for_status = MagicMock()
    return mock_response


def _make_mock_client(
    markets_html: str = _MARKETS_HTML,
    business_html: str = _BUSINESS_HTML,
) -> MagicMock:
    """Build a mock httpx.Client that returns different HTML per URL."""

    def _get(url: str, **kwargs: object) -> MagicMock:
        if "markets" in url:
            return _make_mock_response(markets_html)
        return _make_mock_response(business_html)

    inner = MagicMock()
    inner.get.side_effect = _get

    outer = MagicMock()
    outer.__enter__ = MagicMock(return_value=inner)
    outer.__exit__ = MagicMock(return_value=False)
    return outer


def _make_http_error_client(status_code: int = 403) -> MagicMock:
    """Build a mock httpx.Client whose get() raises HTTPStatusError."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"{status_code} Error",
        request=MagicMock(),
        response=mock_response,
    )

    inner = MagicMock()
    inner.get.return_value = mock_response

    outer = MagicMock()
    outer.__enter__ = MagicMock(return_value=inner)
    outer.__exit__ = MagicMock(return_value=False)
    return outer


def _make_connect_error_client() -> MagicMock:
    """Build a mock httpx.Client whose get() raises ConnectError."""
    inner = MagicMock()
    inner.get.side_effect = httpx.ConnectError("Connection refused")

    outer = MagicMock()
    outer.__enter__ = MagicMock(return_value=inner)
    outer.__exit__ = MagicMock(return_value=False)
    return outer


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


class TestReutersJpConstants:
    """Tests for module-level constants."""

    def test_正常系_REUTERS_JP_BASE_URLが定義されている(self) -> None:
        """REUTERS_JP_BASE_URL constant is defined."""
        assert REUTERS_JP_BASE_URL == "https://jp.reuters.com"

    def test_正常系_REUTERS_JP_SECTIONSにmarketsが含まれる(self) -> None:
        """REUTERS_JP_SECTIONS contains 'markets' key."""
        assert "markets" in REUTERS_JP_SECTIONS
        assert REUTERS_JP_SECTIONS["markets"] == "https://jp.reuters.com/markets/"

    def test_正常系_REUTERS_JP_SECTIONSにbusinessが含まれる(self) -> None:
        """REUTERS_JP_SECTIONS contains 'business' key."""
        assert "business" in REUTERS_JP_SECTIONS
        assert REUTERS_JP_SECTIONS["business"] == "https://jp.reuters.com/business/"

    def test_正常系_MARKETS_CARDS_XPATHがdata_testidベースである(self) -> None:
        """MARKETS_CARDS_XPATH uses data-testid, not CSS class."""
        assert "data-testid" in MARKETS_CARDS_XPATH
        assert "HeroCard" in MARKETS_CARDS_XPATH
        assert "BasicCard" in MARKETS_CARDS_XPATH
        assert "@class" not in MARKETS_CARDS_XPATH

    def test_正常系_BUSINESS_CARDS_XPATHがdata_testidベースである(self) -> None:
        """BUSINESS_CARDS_XPATH uses data-testid, not CSS class."""
        assert "data-testid" in BUSINESS_CARDS_XPATH
        assert "MediaStoryCard" in BUSINESS_CARDS_XPATH
        assert "@class" not in BUSINESS_CARDS_XPATH

    def test_正常系_全XPath定数がdata_testidベースである(self) -> None:
        """All XPath constants use data-testid attribute selectors."""
        xpath_constants = [
            MARKETS_TITLE_XPATH,
            MARKETS_URL_XPATH,
            MARKETS_DATE_XPATH,
            BUSINESS_TITLE_XPATH,
            BUSINESS_URL_HERO_XPATH,
            BUSINESS_URL_HUB_XPATH,
            BUSINESS_DATE_XPATH,
        ]
        for xpath in xpath_constants:
            assert "@class" not in xpath, (
                f"XPath uses @class (unstable hash suffix): {xpath}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# _parse_utc_z_datetime
# ─────────────────────────────────────────────────────────────────────────────


class TestParseUtcZDatetime:
    """Tests for _parse_utc_z_datetime helper function."""

    def test_正常系_Z付きISO8601をUTCとしてパースする(self) -> None:
        """_parse_utc_z_datetime parses ISO 8601 UTC with Z suffix."""
        dt = _parse_utc_z_datetime("2026-03-18T09:14:42.564Z")

        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 18
        assert dt.hour == 9
        assert dt.minute == 14
        assert dt.second == 42

    def test_正常系_返値がUTCであること(self) -> None:
        """_parse_utc_z_datetime returns a UTC timezone-aware datetime."""
        dt = _parse_utc_z_datetime("2026-03-18T09:14:42.564Z")

        assert dt.tzinfo == timezone.utc

    def test_正常系_ミリ秒なしのZ付きをパースする(self) -> None:
        """_parse_utc_z_datetime parses ISO 8601 UTC without milliseconds."""
        dt = _parse_utc_z_datetime("2026-03-18T09:14:42Z")

        assert dt.year == 2026
        assert dt.hour == 9
        assert dt.tzinfo == timezone.utc

    def test_正常系_00時00分のZ付きをパースする(self) -> None:
        """_parse_utc_z_datetime parses midnight UTC."""
        dt = _parse_utc_z_datetime("2026-03-18T00:00:00.000Z")

        assert dt.hour == 0
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.tzinfo == timezone.utc

    def test_異常系_不正な文字列はfallbackを返す(self) -> None:
        """_parse_utc_z_datetime returns a UTC datetime fallback on invalid input."""
        dt = _parse_utc_z_datetime("not-a-datetime")

        assert dt.tzinfo == timezone.utc
        assert isinstance(dt, datetime)


# ─────────────────────────────────────────────────────────────────────────────
# _parse_markets_page
# ─────────────────────────────────────────────────────────────────────────────


class TestParseMarketsPage:
    """Tests for _parse_markets_page helper function."""

    def test_正常系_HeroCardとBasicCardを抽出する(self) -> None:
        """_parse_markets_page extracts both HeroCard and BasicCard articles."""
        articles = _parse_markets_page(_MARKETS_HTML)

        assert len(articles) == 2

    def test_正常系_HeroCardのタイトルを抽出する(self) -> None:
        """_parse_markets_page extracts HeroCard title via data-testid=Heading."""
        articles = _parse_markets_page(_MARKETS_HTML)

        titles = [a.title for a in articles]
        assert "日銀が政策金利を据え置き" in titles

    def test_正常系_BasicCardのタイトルを抽出する(self) -> None:
        """_parse_markets_page extracts BasicCard title."""
        articles = _parse_markets_page(_MARKETS_HTML)

        titles = [a.title for a in articles]
        assert "東京株式市場・前場 日経平均は小幅高" in titles

    def test_正常系_相対URLをurljoinで絶対URLに変換する(self) -> None:
        """_parse_markets_page resolves relative URLs to absolute URLs."""
        articles = _parse_markets_page(_MARKETS_HTML)

        for article in articles:
            assert article.url.startswith("https://jp.reuters.com")

    def test_正常系_datetimeをUTCとしてパースする(self) -> None:
        """_parse_markets_page parses ISO 8601 Z datetime to UTC."""
        articles = _parse_markets_page(_MARKETS_HTML)

        for article in articles:
            assert article.published.tzinfo == timezone.utc

    def test_正常系_sourceがreuters_jpである(self) -> None:
        """_parse_markets_page sets source='reuters_jp'."""
        articles = _parse_markets_page(_MARKETS_HTML)

        for article in articles:
            assert article.source == "reuters_jp"

    def test_正常系_categoryがmarketsである(self) -> None:
        """_parse_markets_page sets category='markets'."""
        articles = _parse_markets_page(_MARKETS_HTML)

        for article in articles:
            assert article.category == "markets"

    def test_正常系_空ページで空リストを返す(self) -> None:
        """_parse_markets_page returns empty list when no cards found."""
        articles = _parse_markets_page(_EMPTY_HTML)

        assert articles == []

    def test_正常系_日時なしカードは現在時刻を使用する(self) -> None:
        """_parse_markets_page uses current UTC time when datetime is missing."""
        articles = _parse_markets_page(_MARKETS_HTML_NO_DATE)

        assert len(articles) == 1
        assert articles[0].published.tzinfo == timezone.utc

    def test_正常系_返値がArticleのリストである(self) -> None:
        """_parse_markets_page returns a list of Article instances."""
        articles = _parse_markets_page(_MARKETS_HTML)

        assert isinstance(articles, list)
        for article in articles:
            assert isinstance(article, Article)


# ─────────────────────────────────────────────────────────────────────────────
# _parse_business_page
# ─────────────────────────────────────────────────────────────────────────────


class TestParseBusinessPage:
    """Tests for _parse_business_page helper function."""

    def test_正常系_heroバリアントとhubバリアントを抽出する(self) -> None:
        """_parse_business_page extracts both hero and hub MediaStoryCard variants."""
        articles = _parse_business_page(_BUSINESS_HTML)

        assert len(articles) == 2

    def test_正常系_heroバリアントのタイトルを抽出する(self) -> None:
        """_parse_business_page extracts hero variant title."""
        articles = _parse_business_page(_BUSINESS_HTML)

        titles = [a.title for a in articles]
        assert "日本GDP発表" in titles

    def test_正常系_hubバリアントのタイトルを抽出する(self) -> None:
        """_parse_business_page extracts hub variant title."""
        articles = _parse_business_page(_BUSINESS_HTML)

        titles = [a.title.strip() for a in articles]
        assert any("トヨタ決算発表" in t for t in titles)

    def test_正常系_heroバリアントのURLがhttpsで始まる(self) -> None:
        """_parse_business_page returns absolute URLs for hero variant."""
        articles = _parse_business_page(_BUSINESS_HTML)

        for article in articles:
            assert article.url.startswith("https://")

    def test_正常系_hubバリアントの絶対URLがそのまま使われる(self) -> None:
        """_parse_business_page keeps absolute URLs from hub variant unchanged."""
        articles = _parse_business_page(_BUSINESS_HTML)

        urls = [a.url for a in articles]
        assert any(
            "jp.reuters.com/business/autos/TOYOTA-2026-03-18/" in u for u in urls
        )

    def test_正常系_datetimeをUTCとしてパースする(self) -> None:
        """_parse_business_page parses datetime attributes to UTC."""
        articles = _parse_business_page(_BUSINESS_HTML)

        for article in articles:
            assert article.published.tzinfo == timezone.utc

    def test_正常系_sourceがreuters_jpである(self) -> None:
        """_parse_business_page sets source='reuters_jp'."""
        articles = _parse_business_page(_BUSINESS_HTML)

        for article in articles:
            assert article.source == "reuters_jp"

    def test_正常系_categoryがbusinessである(self) -> None:
        """_parse_business_page sets category='business'."""
        articles = _parse_business_page(_BUSINESS_HTML)

        for article in articles:
            assert article.category == "business"

    def test_正常系_空ページで空リストを返す(self) -> None:
        """_parse_business_page returns empty list when no cards found."""
        articles = _parse_business_page(_EMPTY_HTML)

        assert articles == []

    def test_正常系_返値がArticleのリストである(self) -> None:
        """_parse_business_page returns a list of Article instances."""
        articles = _parse_business_page(_BUSINESS_HTML)

        assert isinstance(articles, list)
        for article in articles:
            assert isinstance(article, Article)


# ─────────────────────────────────────────────────────────────────────────────
# collect_news
# ─────────────────────────────────────────────────────────────────────────────


class TestCollectNews:
    """Tests for the collect_news entry point."""

    def test_正常系_list_Articleを返す(self) -> None:
        """collect_news returns a list of Article objects."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        assert isinstance(result, list)

    def test_正常系_marketsとbusinessから記事を収集する(self) -> None:
        """collect_news collects articles from both markets and business pages."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        assert len(result) >= 2  # at least one from each page

    def test_正常系_marketsページの記事が含まれる(self) -> None:
        """collect_news includes articles from the markets page."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        titles = [a.title for a in result]
        assert any("日銀" in t for t in titles)

    def test_正常系_businessページの記事が含まれる(self) -> None:
        """collect_news includes articles from the business page."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        titles = [a.title for a in result]
        assert any("GDP" in t or "トヨタ" in t for t in titles)

    def test_正常系_全URLがhttpsで始まる(self) -> None:
        """collect_news returns articles with absolute HTTPS URLs."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        for article in result:
            assert article.url.startswith("https://"), (
                f"Expected https URL, got: {article.url}"
            )

    def test_正常系_publishedがUTCである(self) -> None:
        """collect_news returns articles with UTC published datetimes."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        for article in result:
            assert article.published.tzinfo == timezone.utc

    def test_正常系_configがNoneの場合もデフォルトで動作する(self) -> None:
        """collect_news works with config=None (uses defaults)."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news(config=None)

        assert isinstance(result, list)

    def test_正常系_configを渡しても動作する(self) -> None:
        """collect_news works with an explicit ScraperConfig."""
        config = ScraperConfig(request_delay=0.0, max_articles_per_source=5)

        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news(config=config)

        assert isinstance(result, list)

    def test_異常系_403エラー時に空リストを返す(self) -> None:
        """collect_news returns empty list on HTTP 403 Forbidden."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_http_error_client(status_code=403),
        ):
            result = collect_news()

        assert result == []

    def test_異常系_429エラー時に空リストを返す(self) -> None:
        """collect_news returns empty list on HTTP 429 Too Many Requests."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_http_error_client(status_code=429),
        ):
            result = collect_news()

        assert result == []

    def test_異常系_接続エラー時に空リストを返す(self) -> None:
        """collect_news returns empty list on connection error."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_connect_error_client(),
        ):
            result = collect_news()

        assert result == []

    def test_正常系_重複URLが除外される(self) -> None:
        """collect_news deduplicates articles by URL."""
        # Both pages return same HTML to create duplicates
        duplicate_html = _MARKETS_HTML
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(
                markets_html=duplicate_html, business_html=duplicate_html
            ),
        ):
            result = collect_news()

        urls = [a.url for a in result]
        assert len(urls) == len(set(urls)), "Duplicate URLs found in result"

    def test_正常系_sourceが全てreuters_jpである(self) -> None:
        """collect_news returns articles all with source='reuters_jp'."""
        with patch(
            "news_scraper.reuters_jp.httpx.Client",
            return_value=_make_mock_client(),
        ):
            result = collect_news()

        for article in result:
            assert article.source == "reuters_jp"
