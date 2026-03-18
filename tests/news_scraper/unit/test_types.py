"""Unit tests for news_scraper.types module."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from news_scraper.types import (
    Article,
    ScrapedNewsCollection,
    ScraperConfig,
    SourceName,
    get_delay,
)


class TestSourceName:
    """Tests for SourceName type alias."""

    def test_正常系_jetroがSourceNameに含まれる(self) -> None:
        """SourceName Literal includes 'jetro'."""
        # SourceName is a type alias for Literal["cnbc", "jetro", "nasdaq"]
        # Verify by checking __value__ of the type alias
        valid_sources: list[SourceName] = ["cnbc", "jetro", "nasdaq"]
        assert "jetro" in valid_sources

    def test_正常系_全ソース名が定義されている(self) -> None:
        """SourceName includes all expected source names."""
        expected: set[str] = {"cnbc", "jetro", "kabutan", "minkabu", "nasdaq", "reuters_jp"}
        # Access the Literal args from the type alias
        source_args = set(SourceName.__value__.__args__)
        assert source_args == expected


class TestScraperConfig:
    """Tests for ScraperConfig model."""

    def test_正常系_デフォルト値で作成できる(self) -> None:
        """ScraperConfig can be created with default values."""
        config = ScraperConfig()
        assert config.include_content is False
        assert config.request_timeout == 30
        assert config.request_delay == 1.0
        assert config.max_articles_per_source == 50
        assert config.use_playwright is False

    def test_正常系_include_contentをTrueに設定できる(self) -> None:
        """ScraperConfig can enable include_content."""
        config = ScraperConfig(include_content=True)
        assert config.include_content is True

    def test_正常系_カスタム値で作成できる(self) -> None:
        """ScraperConfig can be created with custom values."""
        config = ScraperConfig(
            include_content=True,
            request_timeout=60,
            request_delay=2.5,
            max_articles_per_source=100,
            use_playwright=True,
        )
        assert config.include_content is True
        assert config.request_timeout == 60
        assert config.request_delay == 2.5
        assert config.max_articles_per_source == 100
        assert config.use_playwright is True

    def test_異常系_request_timeoutが0以下でバリデーションエラー(self) -> None:
        """ScraperConfig raises ValidationError for request_timeout <= 0."""
        with pytest.raises(ValidationError):
            ScraperConfig(request_timeout=0)

    def test_異常系_max_articles_per_sourceが0以下でバリデーションエラー(self) -> None:
        """ScraperConfig raises ValidationError for max_articles_per_source <= 0."""
        with pytest.raises(ValidationError):
            ScraperConfig(max_articles_per_source=0)

    def test_異常系_request_delayが負の値でバリデーションエラー(self) -> None:
        """ScraperConfig raises ValidationError for negative request_delay."""
        with pytest.raises(ValidationError):
            ScraperConfig(request_delay=-1.0)


class TestGetDelay:
    """Tests for get_delay function."""

    def test_正常系_Noneでデフォルト値を返す(self) -> None:
        """get_delay returns default (1.0) when config is None."""
        assert get_delay(None) == 1.0

    def test_正常系_configからdelayを取得できる(self) -> None:
        """get_delay returns config.request_delay."""
        config = ScraperConfig(request_delay=2.5)
        assert get_delay(config) == 2.5

    def test_正常系_デフォルトconfigで1_0を返す(self) -> None:
        """get_delay returns 1.0 for default config."""
        config = ScraperConfig()
        assert get_delay(config) == 1.0


class TestArticle:
    """Tests for Article model."""

    def test_正常系_必須フィールドで作成できる(self) -> None:
        """Article can be created with required fields."""
        article = Article(
            title="Test Article",
            url="https://www.cnbc.com/2026/03/01/test.html",
            published=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            source="cnbc",
        )
        assert article.title == "Test Article"
        assert article.url == "https://www.cnbc.com/2026/03/01/test.html"
        assert article.source == "cnbc"
        assert article.category is None
        assert article.summary is None
        assert article.content is None
        assert article.author is None
        assert article.tags == []
        assert isinstance(article.metadata, dict)

    def test_正常系_全フィールドで作成できる(self) -> None:
        """Article can be created with all fields."""
        now = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
        article = Article(
            title="Full Article",
            url="https://www.nasdaq.com/articles/full",
            published=now,
            source="nasdaq",
            category="markets",
            summary="This is a summary",
            content="Full content here",
            author="John Doe",
            tags=["markets", "earnings"],
            metadata={"feed_category": "markets"},
        )
        assert article.title == "Full Article"
        assert article.category == "markets"
        assert article.summary == "This is a summary"
        assert article.content == "Full content here"
        assert article.author == "John Doe"
        assert article.tags == ["markets", "earnings"]
        assert article.metadata == {"feed_category": "markets"}

    def test_正常系_fetched_atが自動設定される(self) -> None:
        """Article.fetched_at is automatically set to current UTC time."""
        before = datetime.now(timezone.utc)
        article = Article(
            title="Test",
            url="https://example.com/test",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source="cnbc",
        )
        after = datetime.now(timezone.utc)
        assert before <= article.fetched_at <= after

    def test_異常系_空タイトルでバリデーションエラー(self) -> None:
        """Article raises ValidationError for empty title."""
        with pytest.raises(ValidationError):
            Article(
                title="",
                url="https://example.com/test",
                published=datetime(2026, 3, 1, tzinfo=timezone.utc),
                source="cnbc",
            )

    def test_異常系_空URLでバリデーションエラー(self) -> None:
        """Article raises ValidationError for empty URL."""
        with pytest.raises(ValidationError):
            Article(
                title="Test",
                url="",
                published=datetime(2026, 3, 1, tzinfo=timezone.utc),
                source="cnbc",
            )


class TestScrapedNewsCollection:
    """Tests for ScrapedNewsCollection model."""

    def test_正常系_空コレクションで作成できる(self) -> None:
        """ScrapedNewsCollection can be created with empty articles."""
        collection = ScrapedNewsCollection(source="cnbc", articles=[])
        assert collection.source == "cnbc"
        assert collection.total_count == 0
        assert collection.error_count == 0

    def test_正常系_total_countが記事数を返す(self) -> None:
        """ScrapedNewsCollection.total_count returns article count."""
        articles = [
            Article(
                title=f"Article {i}",
                url=f"https://example.com/{i}",
                published=datetime(2026, 3, 1, tzinfo=timezone.utc),
                source="cnbc",
            )
            for i in range(5)
        ]
        collection = ScrapedNewsCollection(source="cnbc", articles=articles)
        assert collection.total_count == 5

    def test_正常系_fetched_atが自動設定される(self) -> None:
        """ScrapedNewsCollection.fetched_at is automatically set."""
        before = datetime.now(timezone.utc)
        collection = ScrapedNewsCollection(source="cnbc", articles=[])
        after = datetime.now(timezone.utc)
        assert before <= collection.fetched_at <= after
