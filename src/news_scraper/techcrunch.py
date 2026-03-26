"""TechCrunch news collector for the news_scraper package.

Collects technology and startup news from TechCrunch's RSS feed.
Delegates entirely to ``_rss_fetcher.fetch_rss_feeds``.

Examples
--------
>>> import asyncio
>>> from news_scraper.techcrunch import collect_news
>>> from news_scraper.types import ScraperConfig
>>> articles = asyncio.run(collect_news(config=ScraperConfig()))
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

from news_scraper._logging import get_logger
from news_scraper._rss_fetcher import fetch_rss_feeds
from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="techcrunch")

FEEDS: dict[str, str] = {
    "technology": "https://techcrunch.com/feed/",
}


async def collect_news(
    config: ScraperConfig | None = None,
) -> list[Article]:
    """Collect recent news articles from TechCrunch RSS feed.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.

    Returns
    -------
    list[Article]
        List of collected articles, deduplicated by URL.
    """
    if config is None:
        config = ScraperConfig()
    return await fetch_rss_feeds(
        FEEDS,
        config,
        source_name="techcrunch",
        content_field="entry.summary",
        content_is_html=False,
    )
