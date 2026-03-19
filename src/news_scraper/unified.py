"""Unified financial news collection for the news_scraper package.

This module provides a single entry point for collecting financial news
from multiple sources (CNBC, NASDAQ, Kabutan, Reuters JP, Minkabu)
and returning a unified DataFrame.

Functions
---------
collect_financial_news
    Collect financial news from multiple sources (async).

Examples
--------
>>> from news_scraper.unified import collect_financial_news
>>> from news_scraper.types import ScraperConfig
>>> import asyncio
>>> config = ScraperConfig(max_articles_per_source=10)
>>> df = asyncio.run(collect_financial_news(sources=["cnbc"], config=config))
>>> hasattr(df, 'to_dict')  # Returns a DataFrame-like object
True
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Iterator

from news_scraper._logging import get_logger
from news_scraper.types import Article, ScraperConfig, SourceName, deduplicate_by_url

logger = get_logger(__name__, module="unified")

# AIDEV-NOTE: Lazy imports to avoid import errors when optional sources are
# not configured or when running in test environments with mocked HTTP calls.
# Each collector function lazily imports its source module at call time.


async def _collect_cnbc(config: ScraperConfig) -> list[Article]:
    # AIDEV-NOTE: cnbc.collect_news is synchronous (uses feedparser + ThreadPoolExecutor).
    # Wrap with asyncio.to_thread to avoid blocking the event loop during asyncio.gather.
    from news_scraper.cnbc import collect_news as _collect

    return await asyncio.to_thread(_collect, config=config)


async def _collect_jetro(config: ScraperConfig) -> list[Article]:
    # AIDEV-NOTE: Lazy import to decouple from optional playwright dependency at load time.
    # jetro.collect_news is synchronous; wrap with to_thread to avoid blocking.
    # Extract JETRO-specific parameters (categories, regions, archive_pages)
    # from config.source_options to pass through without changing the unified signature.
    from news_scraper.jetro import collect_news as _collect

    jetro_opts = config.source_options.get("jetro", {})
    categories = jetro_opts.get("categories")
    regions = jetro_opts.get("regions")
    archive_pages = jetro_opts.get("archive_pages", 0)

    return await asyncio.to_thread(
        _collect,
        config=config,
        categories=categories,
        regions=regions,
        archive_pages=archive_pages,
    )


async def _collect_nasdaq(config: ScraperConfig) -> list[Article]:
    from news_scraper.nasdaq import collect_news as _collect

    return await _collect(config=config)


async def _collect_kabutan(config: ScraperConfig) -> list[Article]:
    from news_scraper.kabutan import collect_news as _collect

    return await _collect(config=config)


async def _collect_reuters_jp(config: ScraperConfig) -> list[Article]:
    from news_scraper.reuters_jp import collect_news as _collect

    return await _collect(config=config)


async def _collect_minkabu(config: ScraperConfig) -> list[Article]:
    if not config.use_playwright:
        logger.info(
            "Minkabu requires Playwright: set use_playwright=True in config "
            "to collect articles. Skipping minkabu source.",
        )
    from news_scraper.minkabu import (  # pyright: ignore[reportMissingImports]
        collect_news as _collect,
    )

    return await _collect(config=config)


def _make_registry_fn(
    func_name: str,
) -> Callable[[ScraperConfig], Coroutine[None, None, list[Article]]]:
    """Return an indirection wrapper that resolves the collector at call-time.

    This allows ``patch("news_scraper.unified._collect_<source>", mock)`` to
    replace the collector seen by ``collect_financial_news`` without needing to
    update ``SOURCE_REGISTRY`` directly.

    Parameters
    ----------
    func_name : str
        The name of the module-level async collector function (e.g.
        ``"_collect_nasdaq"``).

    Returns
    -------
    Callable
        An async wrapper that delegates to the current value of the named
        module attribute at each invocation.
    """

    async def _wrapper(config: ScraperConfig) -> list[Article]:  # type: ignore[misc]
        _mod = sys.modules[__name__]
        _fn = getattr(_mod, func_name)
        return await _fn(config)

    _wrapper.__name__ = func_name + "_wrapper"
    return _wrapper  # type: ignore[return-value]


# Registry maps source names to async collector coroutine functions.
# AIDEV-NOTE: Each entry is an indirection wrapper created by
# ``_make_registry_fn``.  This means that patching the module-level
# ``_collect_*`` attribute (e.g. via ``unittest.mock.patch``) is automatically
# reflected when ``collect_financial_news`` calls the registry entry, because
# the wrapper always reads the current module attribute at invocation time.
# Tests that replace a registry entry directly
# (``SOURCE_REGISTRY["minkabu"] = mock``) are also supported because
# ``_collect_source`` reads from ``SOURCE_REGISTRY`` at call time.
SOURCE_REGISTRY: dict[
    SourceName, Callable[[ScraperConfig], Coroutine[None, None, list[Article]]]
] = {
    "cnbc": _make_registry_fn("_collect_cnbc"),
    "jetro": _make_registry_fn("_collect_jetro"),
    "kabutan": _make_registry_fn("_collect_kabutan"),
    "minkabu": _make_registry_fn("_collect_minkabu"),
    "nasdaq": _make_registry_fn("_collect_nasdaq"),
    "reuters_jp": _make_registry_fn("_collect_reuters_jp"),
}


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

    def __iter__(self) -> Iterator[Article]:
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


async def collect_financial_news(
    sources: list[SourceName] | None = None,
    config: ScraperConfig | None = None,
) -> NewsDataFrame:
    """Collect financial news from multiple sources.

    This is the main entry point for news collection. It orchestrates
    collection from CNBC, NASDAQ, Kabutan, Reuters JP, and Minkabu in
    parallel using ``asyncio.gather``, deduplicates the results, and
    returns them as a unified DataFrame.

    Parameters
    ----------
    sources : list[SourceName] | None, optional
        List of source names to collect from.
        Valid values: "cnbc", "nasdaq", "kabutan", "reuters_jp", "minkabu".
        If None, collects from CNBC and NASDAQ (default).
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
    >>> import asyncio
    >>> config = ScraperConfig(max_articles_per_source=5)
    >>> # In production, this fetches from CNBC and NASDAQ
    >>> df = asyncio.run(collect_financial_news(sources=["cnbc"], config=config))
    >>> isinstance(df, NewsDataFrame)
    True
    """
    if config is None:
        config = ScraperConfig()

    # Default to all sources if not specified
    enabled_sources: list[SourceName] = sources if sources else ["cnbc", "nasdaq"]

    logger.info(
        "Starting financial news collection (async)",
        sources=enabled_sources,
        include_content=config.include_content,
        max_articles_per_source=config.max_articles_per_source,
    )

    started_at = datetime.now(timezone.utc)

    async def _collect_source(
        source_name: SourceName,
    ) -> tuple[SourceName, list[Article]]:
        # AIDEV-NOTE: Resolve the collector at call-time via SOURCE_REGISTRY.
        # Registry entries are indirection callables (see ``_make_registry_fn``)
        # that always delegate to the current module attribute, so both
        # ``patch("news_scraper.unified._collect_*")`` and direct
        # ``SOURCE_REGISTRY[key] = mock`` patches are honoured.
        collector = SOURCE_REGISTRY.get(source_name)
        if collector is None:
            logger.warning("Unknown source, skipping", source=source_name)
            return source_name, []
        try:
            articles = await collector(config)
            logger.info(
                "Source collection complete",
                source=source_name,
                source_articles=len(articles),
            )
            return source_name, articles
        except Exception as e:
            logger.error(
                "Source collection failed",
                source=source_name,
                error=str(e),
                exc_info=True,
            )
            return source_name, []

    # Collect from all sources in parallel
    results = await asyncio.gather(
        *[_collect_source(source) for source in enabled_sources],
        return_exceptions=True,
    )

    all_articles: list[Article] = []
    for result in results:
        if isinstance(result, Exception):
            logger.error(
                "Source collection task raised unexpectedly",
                error=str(result),
                exc_info=True,
            )
        elif isinstance(result, tuple):
            _, source_articles = result
            all_articles.extend(source_articles)

    # Cross-source deduplication by URL
    all_articles = deduplicate_by_url(all_articles)

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
