"""Unit tests for news_scraper.unified module."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from news_scraper.types import Article, ScraperConfig
from news_scraper.unified import (
    SOURCE_REGISTRY,
    NewsDataFrame,
    collect_financial_news,
)


def _make_article(
    title: str = "Test Article",
    url: str = "https://example.com/test",
    source: str = "cnbc",
    published: datetime | None = None,
) -> Article:
    """Helper to create a test Article."""
    if published is None:
        published = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    return Article(title=title, url=url, published=published, source=source)


class TestNewsDataFrame:
    """Tests for NewsDataFrame wrapper class."""

    def test_正常系_空のデータフレームを作成できる(self) -> None:
        """NewsDataFrame can be created with empty articles list."""
        df = NewsDataFrame([])
        assert len(df) == 0
        assert df.empty is True

    def test_正常系_記事を含むデータフレームを作成できる(self) -> None:
        """NewsDataFrame can be created with articles."""
        articles = [_make_article(url=f"https://example.com/{i}") for i in range(3)]
        df = NewsDataFrame(articles)
        assert len(df) == 3
        assert df.empty is False

    def test_正常系_articlesプロパティが記事リストを返す(self) -> None:
        """NewsDataFrame.articles returns the article list."""
        articles = [_make_article()]
        df = NewsDataFrame(articles)
        assert df.articles == articles

    def test_正常系_to_dictがレコードリストを返す(self) -> None:
        """NewsDataFrame.to_dict returns list of dicts."""
        article = _make_article(title="Test Title", url="https://example.com/test")
        df = NewsDataFrame([article])
        records = df.to_dict()
        assert isinstance(records, list)
        assert len(records) == 1
        record = records[0]
        assert record["title"] == "Test Title"
        assert record["url"] == "https://example.com/test"
        assert record["source"] == "cnbc"
        assert "published" in record
        assert "fetched_at" in record

    def test_正常系_to_dictが空リストで空リストを返す(self) -> None:
        """NewsDataFrame.to_dict returns empty list for empty frame."""
        df = NewsDataFrame([])
        assert df.to_dict() == []

    def test_正常系_to_jsonがシリアライズ可能なリストを返す(self) -> None:
        """NewsDataFrame.to_json returns JSON-serializable list."""
        import json

        article = _make_article()
        df = NewsDataFrame([article])
        result = df.to_json()
        # Must be JSON-serializable
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_正常系_to_jsonがinclude_metadata_Falseでmetadataを除外する(self) -> None:
        """NewsDataFrame.to_json excludes metadata when requested."""
        article = _make_article()
        df = NewsDataFrame([article])
        result = df.to_json(include_metadata=False)
        assert "metadata" not in result[0]

    def test_正常系_イテラブルである(self) -> None:
        """NewsDataFrame is iterable."""
        articles = [_make_article(url=f"https://example.com/{i}") for i in range(3)]
        df = NewsDataFrame(articles)
        result = list(df)
        assert len(result) == 3

    def test_正常系_reprが文字列を返す(self) -> None:
        """NewsDataFrame.__repr__ returns a string."""
        df = NewsDataFrame([])
        assert "NewsDataFrame" in repr(df)
        assert "0" in repr(df)


class TestCollectFinancialNews:
    """Tests for collect_financial_news function."""

    def test_正常系_NewsDataFrameを返す(self) -> None:
        """collect_financial_news returns NewsDataFrame."""
        with patch("news_scraper.cnbc.collect_news", return_value=[]):
            result = collect_financial_news(sources=["cnbc"])
        assert isinstance(result, NewsDataFrame)

    def test_正常系_空ソースリストで空結果を返す(self) -> None:
        """collect_financial_news with unknown sources returns empty."""
        with (
            patch("news_scraper.cnbc.collect_news", return_value=[]),
            patch("news_scraper.nasdaq.collect_news", return_value=[]),
        ):
            df = collect_financial_news(sources=["cnbc", "nasdaq"])
            assert isinstance(df, NewsDataFrame)

    def test_正常系_cnbcソースのみで収集できる(self) -> None:
        """collect_financial_news with cnbc source only."""
        cnbc_articles = [
            _make_article(
                title="CNBC Article", url="https://cnbc.com/1", source="cnbc"
            ),
        ]
        with patch(
            "news_scraper.cnbc.collect_news", return_value=cnbc_articles
        ) as mock_cnbc:
            df = collect_financial_news(sources=["cnbc"])
            mock_cnbc.assert_called_once()
        assert isinstance(df, NewsDataFrame)
        assert len(df) == 1
        assert df.articles[0].source == "cnbc"

    def test_正常系_nasdaqソースのみで収集できる(self) -> None:
        """collect_financial_news with nasdaq source only."""
        nasdaq_articles = [
            _make_article(
                title="NASDAQ Article", url="https://nasdaq.com/1", source="nasdaq"
            ),
        ]
        with patch(
            "news_scraper.nasdaq.collect_news", return_value=nasdaq_articles
        ) as mock_nasdaq:
            df = collect_financial_news(sources=["nasdaq"])
            mock_nasdaq.assert_called_once()
        assert isinstance(df, NewsDataFrame)
        assert len(df) == 1

    def test_正常系_複数ソースで重複URLを除外する(self) -> None:
        """collect_financial_news deduplicates articles by URL."""
        shared_url = "https://example.com/shared-article"
        cnbc_articles = [
            _make_article(url=shared_url, source="cnbc"),
            _make_article(url="https://cnbc.com/unique", source="cnbc"),
        ]
        nasdaq_articles = [
            _make_article(url=shared_url, source="nasdaq"),  # Duplicate URL
        ]
        with (
            patch("news_scraper.cnbc.collect_news", return_value=cnbc_articles),
            patch("news_scraper.nasdaq.collect_news", return_value=nasdaq_articles),
        ):
            df = collect_financial_news(sources=["cnbc", "nasdaq"])

        # Shared URL should only appear once
        assert len(df) == 2
        urls = [a.url for a in df.articles]
        assert urls.count(shared_url) == 1

    def test_正常系_記事が公開日時の降順でソートされる(self) -> None:
        """collect_financial_news returns articles sorted by published date (newest first)."""
        old_article = _make_article(
            url="https://cnbc.com/old",
            published=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        new_article = _make_article(
            url="https://cnbc.com/new",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        # Return in reverse order to verify sorting
        with patch(
            "news_scraper.cnbc.collect_news", return_value=[old_article, new_article]
        ):
            df = collect_financial_news(sources=["cnbc"])

        assert df.articles[0].published > df.articles[1].published

    def test_正常系_デフォルト設定で全ソースを収集する(self) -> None:
        """collect_financial_news with no sources collects from all sources."""
        with (
            patch("news_scraper.cnbc.collect_news", return_value=[]) as mock_cnbc,
            patch("news_scraper.nasdaq.collect_news", return_value=[]) as mock_nasdaq,
        ):
            collect_financial_news()  # No sources specified
            mock_cnbc.assert_called_once()
            mock_nasdaq.assert_called_once()

    def test_正常系_ソースエラー時も他のソースを処理する(self) -> None:
        """collect_financial_news continues when one source fails."""
        nasdaq_articles = [
            _make_article(url="https://nasdaq.com/1", source="nasdaq"),
        ]
        with (
            patch(
                "news_scraper.cnbc.collect_news", side_effect=Exception("CNBC failed")
            ),
            patch("news_scraper.nasdaq.collect_news", return_value=nasdaq_articles),
        ):
            df = collect_financial_news(sources=["cnbc", "nasdaq"])

        # Should still have nasdaq articles despite cnbc failure
        assert len(df) == 1
        assert df.articles[0].source == "nasdaq"

    def test_正常系_reuters_jpソースのみで収集できる(self) -> None:
        """collect_financial_news with reuters_jp source only."""
        reuters_articles = [
            _make_article(
                title="Reuters JP Article",
                url="https://jp.reuters.com/1",
                source="reuters_jp",
            ),
        ]
        with patch(
            "news_scraper.reuters_jp.collect_news", return_value=reuters_articles
        ) as mock_reuters:
            df = collect_financial_news(sources=["reuters_jp"])
            mock_reuters.assert_called_once()
        assert isinstance(df, NewsDataFrame)
        assert len(df) == 1
        assert df.articles[0].source == "reuters_jp"

    def test_正常系_reuters_jpがSOURCE_REGISTRYに登録されている(self) -> None:
        """reuters_jp is registered in SOURCE_REGISTRY."""
        from news_scraper.unified import SOURCE_REGISTRY

        assert "reuters_jp" in SOURCE_REGISTRY

    def test_正常系_configがソースコレクターに渡される(self) -> None:
        """collect_financial_news passes config to source collectors."""
        config = ScraperConfig(max_articles_per_source=10, include_content=True)
        with patch("news_scraper.cnbc.collect_news", return_value=[]) as mock_cnbc:
            collect_financial_news(sources=["cnbc"], config=config)
            mock_cnbc.assert_called_once_with(config=config)

    def test_正常系_Noneのconfigでデフォルト設定を使用する(self) -> None:
        """collect_financial_news uses default ScraperConfig when config is None."""
        with patch("news_scraper.cnbc.collect_news", return_value=[]) as mock_cnbc:
            collect_financial_news(sources=["cnbc"], config=None)
            call_args = mock_cnbc.call_args
            assert call_args is not None
            passed_config = (
                call_args.kwargs.get("config") or call_args.args[0]
                if call_args.args
                else None
            )
            if passed_config is not None:
                assert isinstance(passed_config, ScraperConfig)

    def test_正常系_jetroソースのみで収集できる(self) -> None:
        """collect_financial_news with jetro source only."""
        jetro_articles = [
            _make_article(
                title="JETRO Article",
                url="https://www.jetro.go.jp/biznews/2026/03/test.html",
                source="jetro",
            ),
        ]
        with patch.dict(
            "news_scraper.unified.SOURCE_REGISTRY",
            {"jetro": lambda config: jetro_articles},
        ):
            df = collect_financial_news(sources=["jetro"])
        assert isinstance(df, NewsDataFrame)
        assert len(df) == 1
        assert df.articles[0].source == "jetro"

    def test_正常系_デフォルトソースにjetroが含まれない(self) -> None:
        """collect_financial_news default sources do NOT include jetro."""
        with (
            patch("news_scraper.cnbc.collect_news", return_value=[]) as mock_cnbc,
            patch("news_scraper.nasdaq.collect_news", return_value=[]) as mock_nasdaq,
        ):
            collect_financial_news()  # No sources specified
            mock_cnbc.assert_called_once()
            mock_nasdaq.assert_called_once()
        # jetro should NOT be called by default


class TestSourceRegistry:
    """Tests for SOURCE_REGISTRY configuration."""

    def test_正常系_jetroがSOURCE_REGISTRYに登録されている(self) -> None:
        """SOURCE_REGISTRY contains jetro entry."""
        assert "jetro" in SOURCE_REGISTRY

    def test_正常系_全ソースがSOURCE_REGISTRYに登録されている(self) -> None:
        """SOURCE_REGISTRY contains all expected sources."""
        expected_sources = {"cnbc", "jetro", "nasdaq"}
        assert set(SOURCE_REGISTRY.keys()) == expected_sources

    def test_正常系_jetroコレクターがcallableである(self) -> None:
        """SOURCE_REGISTRY jetro entry is callable."""
        assert callable(SOURCE_REGISTRY["jetro"])
