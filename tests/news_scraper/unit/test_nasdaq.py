"""Unit tests for src/news_scraper/nasdaq.py.

Tests cover helper functions and the main collect_news entry point.
HTTP calls are mocked via pytest-httpserver or unittest.mock to avoid
real network access.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from news_scraper.nasdaq import (
    NASDAQ_API_CATEGORIES_SET,
    _extract_rows_from_response,
    _fetch_category,
    _parse_nasdaq_date,
    _row_to_article,
    collect_news,
)
from news_scraper.types import ScraperConfig


class TestParseNasdaqDate:
    def test_正常系_ISO8601_Z付きをパース(self) -> None:
        result = _parse_nasdaq_date("2026-03-01T12:00:00.000Z")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1
        assert result.hour == 12
        assert result.tzinfo is not None

    def test_正常系_MM_DD_YYYY形式をパース(self) -> None:
        result = _parse_nasdaq_date("03/01/2026")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1

    def test_正常系_日付のみ形式をパース(self) -> None:
        result = _parse_nasdaq_date("2026-03-01")
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 1

    def test_正常系_Noneで現在時刻を返す(self) -> None:
        before = datetime.now(timezone.utc)
        result = _parse_nasdaq_date(None)
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_異常系_全フォーマット不一致で現在時刻を返す(self) -> None:
        before = datetime.now(timezone.utc)
        result = _parse_nasdaq_date("not-a-date-at-all")
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_正常系_タイムゾーンが付与される(self) -> None:
        result = _parse_nasdaq_date("2026-03-01T12:00:00")
        assert result.tzinfo == timezone.utc


class TestRowToArticle:
    def _make_row(
        self,
        title: str = "Test Article",
        url: str = "https://www.nasdaq.com/articles/test",
        date_str: str = "2026-03-01T12:00:00.000Z",
        summary: str | None = "Test summary",
    ) -> dict:
        return {"title": title, "url": url, "date": date_str, "summary": summary}

    def test_正常系_有効な行からArticleを生成(self) -> None:
        row = self._make_row()
        article = _row_to_article(row, "Markets")
        assert article is not None
        assert article.title == "Test Article"
        assert article.url == "https://www.nasdaq.com/articles/test"
        assert article.source == "nasdaq"
        assert article.category == "Markets"

    def test_異常系_title欠落でNoneを返す(self) -> None:
        row = self._make_row(title="")
        assert _row_to_article(row, "Markets") is None

    def test_異常系_url欠落でNoneを返す(self) -> None:
        row = self._make_row(url="")
        assert _row_to_article(row, "Markets") is None

    def test_正常系_相対URLを絶対URLに変換(self) -> None:
        row = self._make_row(url="/articles/test-article")
        article = _row_to_article(row, "Markets")
        assert article is not None
        assert article.url == "https://www.nasdaq.com/articles/test-article"

    def test_正常系_500文字超のsummaryを切り詰め(self) -> None:
        long_summary = "x" * 600
        row = self._make_row(summary=long_summary)
        article = _row_to_article(row, "Markets")
        assert article is not None
        assert article.summary is not None
        assert len(article.summary) <= 500
        assert article.summary.endswith("...")

    def test_正常系_summaryなしでArticleを生成(self) -> None:
        row = self._make_row(summary=None)
        article = _row_to_article(row, "Markets")
        assert article is not None
        assert article.summary is None

    def test_正常系_headlineフィールドをフォールバックとして使用(self) -> None:
        row = {
            "headline": "Headline Article",
            "url": "https://www.nasdaq.com/a",
            "date": "2026-03-01",
        }
        article = _row_to_article(row, "Markets")
        assert article is not None
        assert article.title == "Headline Article"


class TestExtractRowsFromResponse:
    def test_正常系_data_data_rows形式(self) -> None:
        data = {"data": {"rows": [{"title": "T1"}, {"title": "T2"}]}}
        result = _extract_rows_from_response(data)
        assert result == [{"title": "T1"}, {"title": "T2"}]

    def test_正常系_data_data_data形式(self) -> None:
        data = {"data": {"data": [{"title": "T1"}]}}
        result = _extract_rows_from_response(data)
        assert result == [{"title": "T1"}]

    def test_正常系_dataがリスト形式(self) -> None:
        data = {"data": [{"title": "T1"}, {"title": "T2"}]}
        result = _extract_rows_from_response(data)
        assert result == [{"title": "T1"}, {"title": "T2"}]

    def test_正常系_トップレベルrows形式(self) -> None:
        # data key must be non-dict/non-list to reach the top-level fallback
        data = {"data": None, "rows": [{"title": "T1"}]}
        result = _extract_rows_from_response(data)
        assert result == [{"title": "T1"}]

    def test_正常系_トップレベルnews形式(self) -> None:
        # data key must be non-dict/non-list to reach the top-level fallback
        data = {"data": None, "news": [{"title": "T1"}]}
        result = _extract_rows_from_response(data)
        assert result == [{"title": "T1"}]

    def test_エッジケース_空dictで空リストを返す(self) -> None:
        assert _extract_rows_from_response({}) == []

    def test_エッジケース_dataが空dictで空リストを返す(self) -> None:
        assert _extract_rows_from_response({"data": {}}) == []


class TestFetchCategory:
    def test_正常系_HTTPレスポンスから記事を収集(self) -> None:
        payload = {
            "data": {
                "rows": [
                    {"title": "Article 1", "url": "/articles/1", "date": "2026-03-01"},
                    {"title": "Article 2", "url": "/articles/2", "date": "2026-03-01"},
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        articles = _fetch_category(mock_client, "Markets", 10)
        assert len(articles) == 2

    def test_正常系_whitelistに含まれないカテゴリをスキップ(self) -> None:
        mock_client = MagicMock()
        articles = _fetch_category(mock_client, "InvalidCategory", 10)
        assert articles == []
        mock_client.get.assert_not_called()

    def test_異常系_HTTPStatusErrorで空リストを返す(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )
        articles = _fetch_category(mock_client, "Markets", 10)
        assert articles == []

    def test_異常系_RequestErrorで空リストを返す(self) -> None:
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.RequestError("Connection failed")
        articles = _fetch_category(mock_client, "Markets", 10)
        assert articles == []

    def test_正常系_httpxのparamsでURLエンコードされる(self) -> None:
        payload = {"data": {"rows": []}}
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None
        mock_client = MagicMock()
        mock_client.get.return_value = mock_response

        _fetch_category(mock_client, "Markets", 5)

        call_kwargs = mock_client.get.call_args
        assert call_kwargs is not None
        # params should be passed as keyword argument
        _, kwargs = call_kwargs
        assert "params" in kwargs
        assert kwargs["params"]["category"] == "Markets"
        assert kwargs["params"]["limit"] == 5


class TestNasdaqApiCategoriesSet:
    def test_正常系_whitelistセットが正しく構築される(self) -> None:
        assert "Markets" in NASDAQ_API_CATEGORIES_SET
        assert "Earnings" in NASDAQ_API_CATEGORIES_SET
        assert "Economy" in NASDAQ_API_CATEGORIES_SET
        assert "invalid_category" not in NASDAQ_API_CATEGORIES_SET

    def test_正常系_frozensetで変更不可(self) -> None:
        assert isinstance(NASDAQ_API_CATEGORIES_SET, frozenset)


class TestCollectNews:
    @patch("news_scraper.nasdaq.httpx.Client")
    def test_正常系_ThreadPoolExecutorで複数カテゴリを収集(
        self, mock_client_class: MagicMock
    ) -> None:
        payload = {
            "data": {
                "rows": [
                    {"title": "Article", "url": "/articles/1", "date": "2026-03-01"}
                ]
            }
        }
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        config = ScraperConfig(max_articles_per_source=10)
        articles = collect_news(config=config, categories=["Markets", "Earnings"])

        assert isinstance(articles, list)
        # Called once per category
        assert mock_client.get.call_count == 2

    @patch("news_scraper.nasdaq.httpx.Client")
    def test_正常系_デフォルトで全カテゴリを収集(
        self, mock_client_class: MagicMock
    ) -> None:
        payload = {"data": {"rows": []}}
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        articles = collect_news()
        assert isinstance(articles, list)
        # Should attempt all 8 NASDAQ categories
        assert mock_client.get.call_count == 8
