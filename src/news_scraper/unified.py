"""Unified financial news collection for the news_scraper package.

This module provides a single entry point for collecting financial news
from multiple sources (CNBC, NASDAQ) and returning a unified DataFrame.

Functions
---------
collect_financial_news
    Collect financial news from multiple sources.

Examples
--------
>>> from news_scraper.unified import collect_financial_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig(max_articles_per_source=10)
>>> df = collect_financial_news(sources=["cnbc"], config=config)
>>> hasattr(df, 'to_dict')  # Returns a DataFrame-like object
True
"""

from __future__ import annotations

from datetime import datetime, timezone

from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig, SourceName

logger = get_logger(__name__, module="unified")

# AIDEV-NOTE: Lazy imports to avoid import errors when optional sources are
# not configured or when running in test environments with mocked HTTP calls.


class NewsDataFrame:
    """DataFrame-like wrapper for news articles.

    Provides a pandas-compatible interface for working with news articles,
    while avoiding a hard dependency on pandas.

    Parameters
    ----------
    articles : list[Article]
        List of articles to wrap.

    Examples
    --------
    >>> articles = []
    >>> df = NewsDataFrame(articles)
    >>> len(df)
    0
    >>> df.empty
    True
    """

    def __init__(self, articles: list[Article]) -> None:
        """Initialize NewsDataFrame with articles.

        Parameters
        ----------
        articles : list[Article]
            List of articles to wrap.
        """
        self._articles = articles

    def __len__(self) -> int:
        """Return number of articles."""
        return len(self._articles)

    def __iter__(self):
        """Iterate over articles."""
        return iter(self._articles)

    @property
    def empty(self) -> bool:
        """Return True if no articles are present.

        Returns
        -------
        bool
            True if the collection is empty.
        """
        return len(self._articles) == 0

    @property
    def articles(self) -> list[Article]:
        """Return the list of articles.

        Returns
        -------
        list[Article]
            All articles in the collection.
        """
        return self._articles

    def to_dict(self, orient: str = "records") -> list[dict] | dict:
        """Convert articles to dictionary format.

        Parameters
        ----------
        orient : str, optional
            Output format. Currently only "records" is supported (default).

        Returns
        -------
        list[dict] | dict
            Articles as a list of dictionaries.

        Examples
        --------
        >>> df = NewsDataFrame([])
        >>> df.to_dict()
        []
        """
        records = []
        for article in self._articles:
            records.append(
                {
                    "title": article.title,
                    "url": article.url,
                    "published": article.published.isoformat(),
                    "source": article.source,
                    "category": article.category,
                    "summary": article.summary,
                    "content": article.content,
                    "author": article.author,
                    "tags": article.tags,
                    "fetched_at": article.fetched_at.isoformat(),
                    "metadata": article.metadata,
                }
            )
        return records

    def to_json(self, include_metadata: bool = True) -> list[dict]:
        """Convert articles to JSON-serializable format.

        Parameters
        ----------
        include_metadata : bool, optional
            Whether to include the metadata field (default: True).

        Returns
        -------
        list[dict]
            Articles as a list of JSON-serializable dictionaries.

        Examples
        --------
        >>> df = NewsDataFrame([])
        >>> df.to_json()
        []
        """
        records = self.to_dict()
        if not include_metadata:
            for record in records:
                record.pop("metadata", None)
        return records  # type: ignore[return-value]

    def __repr__(self) -> str:
        """Return string representation."""
        return f"NewsDataFrame(articles={len(self._articles)})"


def collect_financial_news(
    sources: list[SourceName] | None = None,
    config: ScraperConfig | None = None,
) -> NewsDataFrame:
    """Collect financial news from multiple sources.

    This is the main entry point for news collection. It orchestrates
    collection from CNBC, NASDAQ, and other sources, deduplicates
    the results, and returns them as a unified DataFrame.

    Parameters
    ----------
    sources : list[SourceName] | None, optional
        List of source names to collect from. Valid values: "cnbc", "nasdaq".
        If None, collects from all available sources (default).
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.

    Returns
    -------
    NewsDataFrame
        Collected and deduplicated articles as a DataFrame-like object.
        Use ``df.to_dict()`` or ``df.to_json()`` for serialization.

    Examples
    --------
    >>> from news_scraper.unified import collect_financial_news
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig(max_articles_per_source=5)
    >>> # In production, this fetches from CNBC and NASDAQ
    >>> df = collect_financial_news(sources=["cnbc"], config=config)
    >>> isinstance(df, NewsDataFrame)
    True
    """
    if config is None:
        config = ScraperConfig()

    # Default to all sources if not specified
    enabled_sources: list[SourceName] = sources if sources else ["cnbc", "nasdaq"]

    logger.info(
        "Starting financial news collection",
        sources=enabled_sources,
        include_content=config.include_content,
        max_articles_per_source=config.max_articles_per_source,
    )

    all_articles: list[Article] = []
    seen_urls: set[str] = set()
    started_at = datetime.now(timezone.utc)

    for source_name in enabled_sources:
        source_articles: list[Article] = []

        try:
            if source_name == "cnbc":
                from news_scraper.cnbc import collect_news as collect_cnbc

                source_articles = collect_cnbc(config=config)

            elif source_name == "nasdaq":
                from news_scraper.nasdaq import collect_news as collect_nasdaq

                source_articles = collect_nasdaq(config=config)

            else:
                logger.warning("Unknown source, skipping", source=source_name)
                continue

        except Exception as e:
            logger.error(
                "Source collection failed",
                source=source_name,
                error=str(e),
                exc_info=True,
            )
            continue

        # Deduplicate by URL
        new_count = 0
        for article in source_articles:
            if article.url not in seen_urls:
                seen_urls.add(article.url)
                all_articles.append(article)
                new_count += 1

        logger.info(
            "Source collection complete",
            source=source_name,
            source_articles=len(source_articles),
            new_articles=new_count,
            total_so_far=len(all_articles),
        )

    # Sort by published date (newest first)
    all_articles.sort(key=lambda a: a.published, reverse=True)

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    logger.info(
        "Financial news collection complete",
        total_articles=len(all_articles),
        elapsed_seconds=round(elapsed, 2),
        sources=enabled_sources,
    )

    return NewsDataFrame(all_articles)
