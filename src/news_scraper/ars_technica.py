"""Ars Technica news collector for the news_scraper package.

Collects technology and science news from Ars Technica's RSS feed.
Uses ``entry.content[0].value`` (partial HTML, ~1162 chars).
Delegates entirely to ``_rss_fetcher.fetch_rss_feeds``.

Examples
--------
>>> import asyncio
>>> from news_scraper.ars_technica import collect_news
>>> from news_scraper.types import ScraperConfig
>>> articles = asyncio.run(collect_news(config=ScraperConfig()))
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

from news_scraper._logging import get_logger
from news_scraper._rss_fetcher import fetch_rss_feeds
from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="ars_technica")

FEEDS: dict[str, str] = {
    "technology": "https://feeds.arstechnica.com/arstechnica/index",
}


async def collect_news(
    config: ScraperConfig | None = None,
) -> list[Article]:
    """Collect recent news articles from Ars Technica RSS feed.

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
        source_name="ars_technica",
        content_field="entry.content[0].value",
        content_is_html=False,
    )
