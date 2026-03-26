"""ZeroHedge news collector for the news_scraper package.

Collects financial commentary from ZeroHedge's RSS feed via FeedBurner.
``entry.summary`` contains HTML full text (~3361 chars, Drupal CMS).
``content_is_html=True`` strips HTML to plain text.
Delegates entirely to ``_rss_fetcher.fetch_rss_feeds``.

Examples
--------
>>> import asyncio
>>> from news_scraper.zero_hedge import collect_news
>>> from news_scraper.types import ScraperConfig
>>> articles = asyncio.run(collect_news(config=ScraperConfig()))
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

from news_scraper._logging import get_logger
from news_scraper._rss_fetcher import fetch_rss_feeds
from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="zero_hedge")

FEEDS: dict[str, str] = {
    "finance": "https://feeds.feedburner.com/zerohedge/feed",
}


async def collect_news(
    config: ScraperConfig | None = None,
) -> list[Article]:
    """Collect recent news articles from ZeroHedge RSS feed.

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
        source_name="zero_hedge",
        content_field="entry.summary",
        content_is_html=True,
    )
