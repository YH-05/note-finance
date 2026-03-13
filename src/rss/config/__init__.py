"""Configuration package for RSS wealth blog scraping.

This package provides constants and configuration for scraping
Wealth Finance Blog sites.

Constants
---------
WEALTH_DOMAIN_RATE_LIMITS
    Per-domain rate limit settings (crawl delay in seconds).
WEALTH_SITEMAP_URLS
    Sitemap entry points for each of the 15 target sites.
BACKFILL_TIER
    Tier assignment (A/B/C/D) for backfill prioritization.
WEALTH_URL_TO_SOURCE_KEY
    Mapping from domain to canonical source key.

Examples
--------
>>> from rss.config import WEALTH_DOMAIN_RATE_LIMITS, WEALTH_URL_TO_SOURCE_KEY
>>> WEALTH_DOMAIN_RATE_LIMITS["monevator.com"]
240
"""

from rss.config.wealth_scraping_config import (
    BACKFILL_TIER,
    WEALTH_DOMAIN_RATE_LIMITS,
    WEALTH_SITEMAP_URLS,
    WEALTH_URL_TO_SOURCE_KEY,
)

__all__ = [
    "BACKFILL_TIER",
    "WEALTH_DOMAIN_RATE_LIMITS",
    "WEALTH_SITEMAP_URLS",
    "WEALTH_URL_TO_SOURCE_KEY",
]
