"""Kabutan (kabutan.jp) news collector for the news_scraper package.

This module collects Japanese stock news from kabutan.jp by scraping HTML.

Functions
---------
collect_news
    Collect recent news articles from kabutan.jp.

Examples
--------
>>> from news_scraper.kabutan import collect_news
>>> from news_scraper.types import ScraperConfig
>>> config = ScraperConfig()
>>> articles = collect_news(config=config)
>>> len(articles) >= 0
True
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from news_scraper._logging import get_logger

if TYPE_CHECKING:
    from news_scraper.types import Article, ScraperConfig

# AIDEV-NOTE: This is a stub placeholder for the kabutan scraper.
# Full implementation will be added in Issue #151.
# The stub exists so that unified.py (Issue #150) can register
# the SOURCE_REGISTRY entry without causing pyright errors.

logger = get_logger(__name__, module="kabutan")


def collect_news(config: ScraperConfig | None = None) -> list[Article]:
    """Collect recent news articles from kabutan.jp.

    Parameters
    ----------
    config : ScraperConfig | None, optional
        Scraper configuration. If None, uses default settings.

    Returns
    -------
    list[Article]
        List of scraped articles. Returns empty list until implementation
        is added in Issue #151.

    Notes
    -----
    This function is a stub. Full HTML scraping implementation will be
    provided in Issue #151.
    """
    logger.warning("kabutan scraper is not yet implemented (Issue #151)")
    return []
