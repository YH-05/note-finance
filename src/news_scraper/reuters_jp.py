"""Reuters Japan (jp.reuters.com) news collector for the news_scraper package.

This module collects Japanese financial news from Reuters Japan by scraping HTML.

Functions
---------
collect_news
    Collect recent news articles from jp.reuters.com.

Examples
--------
>>> from news_scraper.reuters_jp import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = collect_news(config=config)
>>> len(articles) >= 0
True
"""

from __future__ import annotations

# AIDEV-NOTE: This is a stub module. Full implementation follows in the next Wave issue.
# See docs/project/project-15/project.md for the implementation plan.
from typing import TYPE_CHECKING

from news_scraper._logging import get_logger

if TYPE_CHECKING:
    from news_scraper.types import Article, ScraperConfig

logger = get_logger(__name__, module="reuters_jp")


def collect_news(config: ScraperConfig | None = None) -> list[Article]:
    """Collect recent news articles from Reuters Japan.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.

    Returns
    -------
    list[Article]
        List of collected articles. Returns empty list until implemented.

    Examples
    --------
    >>> from news_scraper.types import ScraperConfig
    >>> config = ScraperConfig()
    >>> articles = collect_news(config=config)
    >>> isinstance(articles, list)
    True
    """
    # AIDEV-TODO: Implement Reuters Japan scraping
    # See project.md Wave 2 task for implementation details
    logger.warning(
        "reuters_jp.collect_news is not yet implemented, returning empty list"
    )
    return []
