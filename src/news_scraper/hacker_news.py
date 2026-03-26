"""Hacker News collector for the news_scraper package.

Collects top technology stories from Hacker News RSS feed filtered
by minimum 100 points. Delegates to ``_rss_fetcher.fetch_rss_feeds``.

Examples
--------
>>> import asyncio
>>> from news_scraper.hacker_news import collect_news
>>> from news_scraper.types import ScraperConfig
>>> articles = asyncio.run(collect_news(config=ScraperConfig()))
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

from news_scraper._logging import get_logger
from news_scraper._rss_fetcher import fetch_rss_feeds
from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="hacker_news")

FEEDS: dict[str, str] = {
    "technology": "https://hnrss.org/newest?points=100",
}


async def collect_news(
    config: ScraperConfig | None = None,
) -> list[Article]:
    """Collect recent stories from Hacker News RSS feed.

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
        source_name="hacker_news",
        content_field="entry.summary",
        content_is_html=False,
    )
