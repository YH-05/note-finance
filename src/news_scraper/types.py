"""Type definitions for the news_scraper package.

This module provides the core data models for the news scraper,
including configuration and article types.

Classes
-------
ScraperConfig
    Configuration for the news scraper.
Article
    Unified news article model returned by scrapers.
ScrapedNewsCollection
    Collection of scraped news articles with metadata.

Examples
--------
>>> config = ScraperConfig(include_content=True)
>>> config.include_content
True
>>> config.request_timeout
30
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

# Valid source names for collect_financial_news()
type SourceName = Literal["cnbc", "nasdaq"]

# Valid NASDAQ categories
NASDAQ_CATEGORIES: list[str] = [
    "Markets",
    "Earnings",
    "Economy",
    "Commodities",
    "Currencies",
    "Technology",
    "Stocks",
    "ETFs",
    "Personal-Finance",
]


def get_delay(config: ScraperConfig | None) -> float:
    """Get the configured delay between requests.

    Parameters
    ----------
    config : ScraperConfig | None
        Configuration object. If None, returns the default delay.

    Returns
    -------
    float
        Delay in seconds between requests.

    Examples
    --------
    >>> config = ScraperConfig(request_delay=2.0)
    >>> get_delay(config)
    2.0
    >>> get_delay(None)
    1.0
    """
    if config is None:
        return 1.0
    return config.request_delay


class ScraperConfig(BaseModel):
    """Configuration for the financial news scraper.

    Attributes
    ----------
    include_content : bool
        Whether to fetch the full article content (default: False).
        When True, an additional HTTP request is made per article.
    request_timeout : int
        HTTP request timeout in seconds (default: 30).
    request_delay : float
        Delay in seconds between requests for rate limiting (default: 1.0).
    max_articles_per_source : int
        Maximum number of articles to fetch per source (default: 50).
    use_playwright : bool
        Whether to use Playwright for JavaScript-rendered pages (default: False).
        Required for NASDAQ archive scraping (Wave 3+).

    Examples
    --------
    >>> config = ScraperConfig()
    >>> config.include_content
    False
    >>> config = ScraperConfig(include_content=True, max_articles_per_source=100)
    >>> config.max_articles_per_source
    100
    """

    include_content: bool = Field(
        default=False,
        description="Whether to fetch full article content",
    )
    request_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="HTTP request timeout in seconds",
    )
    request_delay: float = Field(
        default=1.0,
        ge=0.0,
        le=60.0,
        description="Delay between requests in seconds",
    )
    max_articles_per_source: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum articles to fetch per source",
    )
    use_playwright: bool = Field(
        default=False,
        description=(
            "Whether to use Playwright for JavaScript-rendered pages. "
            "Required for NASDAQ archive scraping."
        ),
    )


class Article(BaseModel):
    """Unified news article model for the news_scraper package.

    This model represents a scraped news article from CNBC, NASDAQ,
    or other financial news sources.

    Attributes
    ----------
    title : str
        Article title.
    url : str
        URL of the original article.
    published : datetime
        Publication date and time (UTC).
    source : str
        Source name (e.g., "cnbc", "nasdaq").
    category : str | None
        Article category (e.g., "markets", "economy").
    summary : str | None
        Article summary or description.
    content : str | None
        Full article content (populated when include_content=True).
    author : str | None
        Article author name.
    tags : list[str]
        Tags or keywords associated with the article.
    fetched_at : datetime
        Timestamp when the article was fetched (UTC).
    metadata : dict[str, Any]
        Source-specific metadata.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> article = Article(
    ...     title="S&P 500 hits record high",
    ...     url="https://www.cnbc.com/2026/03/01/sp500-record.html",
    ...     published=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
    ...     source="cnbc",
    ... )
    >>> article.title
    'S&P 500 hits record high'
    """

    title: str = Field(..., min_length=1, description="Article title")
    url: str = Field(..., min_length=1, description="Article URL")
    published: datetime = Field(..., description="Publication date and time (UTC)")
    source: str = Field(..., min_length=1, description="Source name")
    category: str | None = Field(default=None, description="Article category")
    summary: str | None = Field(default=None, description="Article summary")
    content: str | None = Field(default=None, description="Full article content")
    author: str | None = Field(default=None, description="Article author")
    tags: list[str] = Field(default_factory=list, description="Article tags")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the article was fetched (UTC)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific metadata",
    )


class ScrapedNewsCollection(BaseModel):
    """Collection of scraped news articles with metadata.

    Attributes
    ----------
    articles : list[Article]
        List of scraped articles.
    source : str
        Source name (e.g., "cnbc", "nasdaq").
    fetched_at : datetime
        Timestamp when the collection was fetched.
    total_count : int
        Total number of articles in the collection.
    error_count : int
        Number of articles that failed to be fetched.

    Examples
    --------
    >>> collection = ScrapedNewsCollection(source="cnbc", articles=[])
    >>> collection.total_count
    0
    """

    articles: list[Article] = Field(
        default_factory=list, description="Scraped articles"
    )
    source: str = Field(..., description="Source name")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Collection timestamp (UTC)",
    )
    error_count: int = Field(default=0, ge=0, description="Number of fetch errors")

    @property
    def total_count(self) -> int:
        """Total number of articles in the collection.

        Returns
        -------
        int
            Number of articles.
        """
        return len(self.articles)
