"""Developing Telecoms news collector for the news_scraper package.

Collects telecom and emerging market technology news from
Developing Telecoms' RSS feed (Joomla CMS format).

References
----------
- Site: https://developingtelecoms.com/
- RSS: https://developingtelecoms.com/index.php?format=feed&type=rss
- Coverage: 5G, wireless networks, operators, telecom business in emerging markets

Examples
--------
>>> import asyncio
>>> from news_scraper.developing_telecoms import collect_news
>>> from news_scraper.types import ScraperConfig
>>> articles = asyncio.run(collect_news(config=ScraperConfig()))
>>> isinstance(articles, list)
True
"""

from __future__ import annotations

from news_scraper._logging import get_logger
from news_scraper._rss_fetcher import fetch_rss_feeds
from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="developing_telecoms")

# AIDEV-NOTE: Joomla CMS形式のRSSフィード（?format=feed&type=rss）。
# 標準的な /feed や /rss.xml は404のため、このURLのみが有効。
FEEDS: dict[str, str] = {
    "telecom_news": "https://developingtelecoms.com/index.php?format=feed&type=rss",
}


async def collect_news(
    config: ScraperConfig | None = None,
) -> list[Article]:
    """Collect recent articles from Developing Telecoms RSS feed.

    Always fetches full article content via trafilatura regardless of
    the global ``config.include_content`` setting, because the RSS feed
    only provides a short excerpt (1–2 sentences).

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.

    Returns
    -------
    list[Article]
        List of collected articles with full content, deduplicated by URL.
    """
    if config is None:
        config = ScraperConfig()
    # AIDEV-NOTE: RSSフィードが本文の冒頭1〜2文しか含まないため、
    # グローバル設定に関わらず常に全文取得を有効にする。
    config = config.model_copy(update={"include_content": True})
    return await fetch_rss_feeds(
        FEEDS,
        config,
        source_name="developing_telecoms",
        content_field="entry.summary",
        content_is_html=True,
    )
