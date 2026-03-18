"""Unit tests for src/news_scraper/kabutan.py.

Tests cover:
- KABUTAN_ROW_XPATH constant definition
- _row_to_article: ISO8601+JST datetime parsing and UTC conversion
- _row_to_article: relative URL resolution via urljoin
- _row_to_article: empty title returns None
- collect_news: HTTP error returns empty list
- collect_news: max_articles_per_source is respected
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import lxml.html
import pytest

from news_scraper.kabutan import (
    KABUTAN_BASE_URL,
    KABUTAN_NEWS_URL,
    KABUTAN_ROW_XPATH,
    _row_to_article,
    collect_news,
)
from news_scraper.types import ScraperConfig

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_tr(
    datetime_attr: str = "2026-03-18T18:15:00+09:00",
    title: str = "テスト記事タイトル",
    href: str = "/news/marketnews/?&b=n202603181152",
    category_class: str = "newslist_ctg newsctg4_b",
    category_text: str = "テク",
) -> lxml.html.HtmlElement:
    """Build a minimal kabutan <tr> element for testing."""
    html = f"""<table>
      <tr>
        <td class="news_time">
          <time datetime="{datetime_attr}">03/18 18:15</time>
        </td>
        <td>
          <div class="{category_class}">{category_text}</div>
        </td>
        <td>
          <a href="{href}">{title}</a>
        </td>
      </tr>
    </table>"""
    root = lxml.html.fromstring(html)
    rows = root.xpath("//tr")
    assert rows, "Failed to build test tr element"
    return rows[0]


def _make_tr_empty_title(
    href: str = "/news/marketnews/?&b=n123",
) -> lxml.html.HtmlElement:
    """Build a tr with empty title (no text in anchor)."""
    html = f"""<table>
      <tr>
        <td class="news_time">
          <time datetime="2026-03-18T18:15:00+09:00">03/18 18:15</time>
        </td>
        <td><div class="newslist_ctg newsctg2_b">材料</div></td>
        <td><a href="{href}"></a></td>
      </tr>
    </table>"""
    root = lxml.html.fromstring(html)
    rows = root.xpath("//tr")
    assert rows, "Failed to build test tr element"
    return rows[0]


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────


class TestKabutanConstants:
    """Tests for module-level constants."""

    def test_正常系_KABUTAN_ROW_XPATHが定義されている(self) -> None:
        """KABUTAN_ROW_XPATH constant is defined."""
        assert KABUTAN_ROW_XPATH == "//table[contains(@class, 's_news_list')]//tr"

    def test_正常系_KABUTAN_NEWS_URLが定義されている(self) -> None:
        """KABUTAN_NEWS_URL constant is defined."""
        assert KABUTAN_NEWS_URL == "https://kabutan.jp/news/marketnews/"

    def test_正常系_KABUTAN_BASE_URLが定義されている(self) -> None:
        """KABUTAN_BASE_URL constant is defined."""
        assert KABUTAN_BASE_URL == "https://kabutan.jp"


# ─────────────────────────────────────────────────────────────────────────────
# _row_to_article
# ─────────────────────────────────────────────────────────────────────────────


class TestRowToArticle:
    """Tests for _row_to_article helper function."""

    def test_正常系_有効な行からArticleを生成する(self) -> None:
        """_row_to_article converts a valid tr to an Article."""
        row = _make_tr()
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.title == "テスト記事タイトル"
        assert article.source == "kabutan"

    def test_正常系_datetimeをUTCに変換する(self) -> None:
        """_row_to_article converts ISO8601+JST datetime to UTC."""
        # JST +09:00 → UTC: 18:15 JST == 09:15 UTC
        row = _make_tr(datetime_attr="2026-03-18T18:15:00+09:00")
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.published.tzinfo == timezone.utc
        assert article.published.hour == 9
        assert article.published.minute == 15
        assert article.published.day == 18

    def test_正常系_相対URLをurljoinで絶対URLに変換する(self) -> None:
        """_row_to_article resolves relative URLs using urljoin."""
        href = "/news/marketnews/?&b=n202603181152"
        row = _make_tr(href=href)
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.url == f"https://kabutan.jp{href}"

    def test_正常系_絶対URLはそのまま使用する(self) -> None:
        """_row_to_article keeps absolute URLs unchanged."""
        absolute_url = "https://kabutan.jp/news/marketnews/?&b=n999"
        row = _make_tr(href=absolute_url)
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.url == absolute_url

    def test_異常系_titleが空のtrにNoneを返す(self) -> None:
        """_row_to_article returns None when title is empty."""
        row = _make_tr_empty_title()
        result = _row_to_article(row, KABUTAN_BASE_URL)
        assert result is None

    def test_正常系_カテゴリが設定される(self) -> None:
        """_row_to_article sets category from newslist_ctg element."""
        row = _make_tr(category_text="テク")
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.category == "テク"

    def test_正常系_sourceがkabutanである(self) -> None:
        """_row_to_article sets source to 'kabutan'."""
        row = _make_tr()
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.source == "kabutan"

    def test_正常系_publishedはaware_datetimeである(self) -> None:
        """_row_to_article returns timezone-aware published datetime."""
        row = _make_tr()
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.published.tzinfo is not None

    def test_正常系_異なるJST時刻をUTCに変換する(self) -> None:
        """_row_to_article converts various JST times correctly."""
        # 00:00 JST == 15:00 UTC previous day
        row = _make_tr(datetime_attr="2026-03-19T00:00:00+09:00")
        article = _row_to_article(row, KABUTAN_BASE_URL)

        assert article is not None
        assert article.published.hour == 15
        assert article.published.day == 18  # previous day in UTC


# ─────────────────────────────────────────────────────────────────────────────
# collect_news
# ─────────────────────────────────────────────────────────────────────────────

# Minimal HTML with two kabutan-style news list rows
_KABUTAN_HTML_TWO_ROWS = """<!DOCTYPE html>
<html>
<body>
<table class="s_news_list mgbt0">
  <tr>
    <td class="news_time"><time datetime="2026-03-18T18:00:00+09:00">03/18 18:00</time></td>
    <td><div class="newslist_ctg newsctg4_b">テク</div></td>
    <td><a href="/news/marketnews/?&b=n202603181001">テク記事1</a></td>
  </tr>
  <tr>
    <td class="news_time"><time datetime="2026-03-18T17:00:00+09:00">03/18 17:00</time></td>
    <td><div class="newslist_ctg newsctg1_b">市況</div></td>
    <td><a href="/news/marketnews/?&b=n202603181002">市況記事2</a></td>
  </tr>
</table>
</body>
</html>"""

# HTML replicating the real kabutan.jp two-table layout split by an ad div.
# Top table uses class "s_news_list mgbt0", bottom table uses "s_news_list mgt0".
_KABUTAN_HTML_SPLIT_TABLES = """<!DOCTYPE html>
<html>
<body>
<table class="s_news_list mgbt0">
  <tr>
    <td class="news_time"><time datetime="2026-03-18T18:00:00+09:00">03/18 18:00</time></td>
    <td><div class="newslist_ctg newsctg4_b">テク</div></td>
    <td><a href="/news/marketnews/?&b=n202603181001">上部テーブル記事1</a></td>
  </tr>
  <tr>
    <td class="news_time"><time datetime="2026-03-18T17:00:00+09:00">03/18 17:00</time></td>
    <td><div class="newslist_ctg newsctg1_b">市況</div></td>
    <td><a href="/news/marketnews/?&b=n202603181002">上部テーブル記事2</a></td>
  </tr>
</table>
<div class="advert">広告</div>
<table class="s_news_list mgt0">
  <tr>
    <td class="news_time"><time datetime="2026-03-18T16:00:00+09:00">03/18 16:00</time></td>
    <td><div class="newslist_ctg newsctg2_b">材料</div></td>
    <td><a href="/news/marketnews/?&b=n202603181003">下部テーブル記事3</a></td>
  </tr>
</table>
</body>
</html>"""


def _make_mock_client(html: str = _KABUTAN_HTML_TWO_ROWS) -> MagicMock:
    """Build a mock httpx.Client context-manager that returns the given HTML.

    The returned mock supports ``with httpx.Client(...) as client:`` usage:
    - ``__enter__`` returns a mock with ``get()`` set up
    - ``get()`` returns a mock response whose ``.text`` is the given HTML
    """
    mock_response = MagicMock()
    mock_response.text = html
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    # The instance returned from __enter__
    inner = MagicMock()
    inner.get.return_value = mock_response

    # The object returned by httpx.Client(...)
    outer = MagicMock()
    outer.__enter__ = MagicMock(return_value=inner)
    outer.__exit__ = MagicMock(return_value=False)
    return outer


def _make_error_client(exc: Exception) -> MagicMock:
    """Build a mock httpx.Client whose get() raises the given exception."""
    inner = MagicMock()
    inner.get.side_effect = exc

    outer = MagicMock()
    outer.__enter__ = MagicMock(return_value=inner)
    outer.__exit__ = MagicMock(return_value=False)
    return outer


def _make_http_status_error_client() -> MagicMock:
    """Build a mock httpx.Client whose get() response.raise_for_status() raises."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403 Forbidden",
        request=MagicMock(),
        response=MagicMock(),
    )

    inner = MagicMock()
    inner.get.return_value = mock_response

    outer = MagicMock()
    outer.__enter__ = MagicMock(return_value=inner)
    outer.__exit__ = MagicMock(return_value=False)
    return outer


class TestCollectNews:
    """Tests for the collect_news entry point."""

    def test_正常系_list_Articleを返す(self) -> None:
        """collect_news returns a list of Article objects."""
        with patch(
            "news_scraper.kabutan.httpx.Client", return_value=_make_mock_client()
        ):
            result = collect_news()

        assert isinstance(result, list)

    def test_正常系_記事を収集する(self) -> None:
        """collect_news collects articles from HTML."""
        with patch(
            "news_scraper.kabutan.httpx.Client", return_value=_make_mock_client()
        ):
            result = collect_news()

        assert len(result) == 2
        titles = [a.title for a in result]
        assert "テク記事1" in titles
        assert "市況記事2" in titles

    def test_正常系_max_articles_per_sourceを遵守する(self) -> None:
        """collect_news respects max_articles_per_source limit."""
        config = ScraperConfig(max_articles_per_source=1)

        with patch(
            "news_scraper.kabutan.httpx.Client", return_value=_make_mock_client()
        ):
            result = collect_news(config=config)

        assert len(result) <= 1

    def test_異常系_HTTPエラー時に空リストを返す(self) -> None:
        """collect_news returns empty list on HTTPStatusError."""
        with patch(
            "news_scraper.kabutan.httpx.Client",
            return_value=_make_http_status_error_client(),
        ):
            result = collect_news()

        assert result == []

    def test_異常系_接続エラー時に空リストを返す(self) -> None:
        """collect_news returns empty list on connection error."""
        with patch(
            "news_scraper.kabutan.httpx.Client",
            return_value=_make_error_client(httpx.ConnectError("Connection failed")),
        ):
            result = collect_news()

        assert result == []

    def test_正常系_configがNoneの場合もデフォルトで動作する(self) -> None:
        """collect_news works with config=None (uses defaults)."""
        with patch(
            "news_scraper.kabutan.httpx.Client", return_value=_make_mock_client()
        ):
            result = collect_news(config=None)

        assert isinstance(result, list)

    def test_正常系_URLが絶対URLに変換される(self) -> None:
        """collect_news returns articles with absolute URLs."""
        with patch(
            "news_scraper.kabutan.httpx.Client", return_value=_make_mock_client()
        ):
            result = collect_news()

        for article in result:
            assert article.url.startswith("https://")

    def test_正常系_publishedがUTCである(self) -> None:
        """collect_news returns articles with UTC published datetimes."""
        with patch(
            "news_scraper.kabutan.httpx.Client", return_value=_make_mock_client()
        ):
            result = collect_news()

        for article in result:
            assert article.published.tzinfo == timezone.utc

    def test_正常系_2分割テーブルから全記事を取得する(self) -> None:
        """collect_news parses both s_news_list mgbt0 and s_news_list mgt0 tables.

        Kabutan page structure splits news into two tables separated by an ad div:
        - ``<table class="s_news_list mgbt0">`` (top 10)
        - ``<table class="s_news_list mgt0">``  (bottom 5)
        KABUTAN_ROW_XPATH uses ``contains(@class, 's_news_list')`` to match both.
        """
        with patch(
            "news_scraper.kabutan.httpx.Client",
            return_value=_make_mock_client(_KABUTAN_HTML_SPLIT_TABLES),
        ):
            result = collect_news()

        assert len(result) == 3
        titles = [a.title for a in result]
        assert "上部テーブル記事1" in titles
        assert "上部テーブル記事2" in titles
        assert "下部テーブル記事3" in titles
