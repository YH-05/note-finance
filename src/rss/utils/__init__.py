"""Utility functions for the rss package.

Note: Logging functionality has been migrated to rss._logging.
Import get_logger from rss._logging instead.
"""

from rss.utils.robots_checker import RobotsChecker, RobotsCheckResult
from rss.utils.sitemap_parser import SitemapEntry, SitemapParser
from rss.utils.url_normalizer import (
    calculate_title_similarity,
    is_duplicate,
    normalize_url,
)

__all__: list[str] = [
    "RobotsCheckResult",
    "RobotsChecker",
    "SitemapEntry",
    "SitemapParser",
    "calculate_title_similarity",
    "is_duplicate",
    "normalize_url",
]
