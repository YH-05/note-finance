"""CNBC news collector for the news_scraper package.

This module collects financial news from CNBC's RSS feeds.
CNBC provides RSS feeds for various financial categories including
markets, investing, economy, and more.

Functions
---------
collect_news
    Collect recent news articles from CNBC RSS feeds (async).

Examples
--------
>>> import asyncio
>>> from news_scraper.cnbc import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = asyncio.run(collect_news(config=config))
>>> len(articles) >= 0
True
"""

from __future__ import annotations

from news_scraper._logging import get_logger
from news_scraper._rss_fetcher import fetch_rss_feeds
from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="cnbc")

# CNBC RSS feed URLs — full 21-feed set from feeds.json
CNBC_FEEDS: dict[str, str] = {
    "top_news": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "world_news": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362",
    "us_news": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15837362",
    "markets": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20907743",
    "investing": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069",
    "economy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
    "finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "technology": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "asia_news": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19832390",
    "europe_news": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19794221",
    "business": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",
    "earnings": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839135",
    "politics": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000113",
    "health_care": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000108",
    "real_estate": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000115",
    "wealth": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001054",
    "autos": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000101",
    "energy": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19836768",
    "media": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000110",
    "retail": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000116",
    "travel": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000739",
}


async def collect_news(
    config: ScraperConfig | None = None,
    categories: list[str] | None = None,
) -> list[Article]:
    """Collect recent news articles from CNBC RSS feeds.

    Fetches articles from CNBC's RSS feeds for the specified categories.
    If no categories are specified, fetches from all available feeds.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.
    categories : list[str] | None, optional
        List of CNBC category keys to fetch. If None, fetches all 21 feeds.

    Returns
    -------
    list[Article]
        List of collected articles, deduplicated by URL.

    Examples
    --------
    >>> import asyncio
    >>> from news_scraper.cnbc import collect_news
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig(max_articles_per_source=10)
    >>> articles = asyncio.run(collect_news(config=config, categories=["markets"]))
    >>> isinstance(articles, list)
    True
    """
    if config is None:
        config = ScraperConfig()

    feeds = (
        {cat: CNBC_FEEDS[cat] for cat in categories if cat in CNBC_FEEDS}
        if categories is not None
        else CNBC_FEEDS
    )

    if not feeds:
        logger.warning("No valid CNBC categories found", requested=categories)
        return []

    logger.info(
        "Starting CNBC news collection",
        feeds=list(feeds.keys()),
        max_articles_per_source=config.max_articles_per_source,
    )

    return await fetch_rss_feeds(
        feeds,
        config,
        source_name="cnbc",
        content_field="entry.summary",
        content_is_html=False,
    )
