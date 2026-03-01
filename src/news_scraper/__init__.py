"""Financial news scraper package for note-finance.

This package provides tools to collect financial news from CNBC and NASDAQ,
save articles as JSON, and optionally fetch full article content.

The package is designed to work with macOS launchd for automated collection
and produces JSON files compatible with the weekly report pipeline.

Modules
-------
types
    Data models: ``ScraperConfig``, ``Article``, ``ScrapedNewsCollection``.
unified
    Main entry point: ``collect_financial_news()``.
cnbc
    CNBC RSS feed collector.
nasdaq
    NASDAQ API collector.

Quick Start
-----------
>>> from news_scraper import collect_financial_news, ScraperConfig
>>> config = ScraperConfig(include_content=False)
>>> df = collect_financial_news(sources=["cnbc"], config=config)
>>> isinstance(df.articles, list)
True

Notes
-----
This package is intended for local collection on macOS, saving to NAS or
``data/scraped/`` when NAS is unavailable. It is the upstream data source
for the weekly report pipeline.

The ``news_scraper`` package is separate from the ``news`` package:
- ``news``: GitHub Issue publishing pipeline (Claude AI summarization)
- ``news_scraper``: Raw web scraping for local JSON storage
"""

from news_scraper.types import Article, ScrapedNewsCollection, ScraperConfig
from news_scraper.unified import NewsDataFrame, collect_financial_news

__all__ = [
    "Article",
    "NewsDataFrame",
    "ScrapedNewsCollection",
    "ScraperConfig",
    "collect_financial_news",
]
