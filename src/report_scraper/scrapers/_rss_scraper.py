"""RSS-based intermediate base class for report scrapers.

Provides ``RssReportScraper``, which implements ``fetch_listing()`` using
feedparser. Concrete subclasses only need to define ``feed_url``,
``source_key``, ``source_config``, and ``extract_report()``.

Classes
-------
RssReportScraper
    Intermediate ABC that fetches and parses RSS/Atom feeds.

Examples
--------
>>> class MyScraper(RssReportScraper):
...     feed_url = "https://example.com/feed.rss"
...     @property
...     def source_key(self) -> str:
...         return "example"
...     @property
...     def source_config(self):
...         ...
...     async def extract_report(self, meta):
...         ...
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, ClassVar

import feedparser

from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.types import ReportMetadata

if TYPE_CHECKING:
    from report_scraper.types import ScrapedReport, SourceConfig


# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from report_scraper._logging import get_logger

        return get_logger(__name__, module="rss_scraper")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()


# ---------------------------------------------------------------------------
# RssReportScraper
# ---------------------------------------------------------------------------


class RssReportScraper(BaseReportScraper):
    """Intermediate base class for RSS/Atom feed-based report scrapers.

    Implements ``fetch_listing()`` by downloading and parsing an RSS/Atom
    feed with feedparser. Subclasses must define the ``feed_url`` class
    variable and implement ``source_key``, ``source_config``, and
    ``extract_report()``.

    Attributes
    ----------
    feed_url : str
        URL of the RSS/Atom feed. Must be set by subclasses.

    Examples
    --------
    >>> class ExampleRssScraper(RssReportScraper):
    ...     feed_url = "https://example.com/rss"
    ...     @property
    ...     def source_key(self) -> str:
    ...         return "example"
    ...     @property
    ...     def source_config(self):
    ...         return SourceConfig(
    ...             key="example", name="Example", tier="buy_side",
    ...             listing_url="https://example.com/rss", rendering="rss",
    ...         )
    ...     async def extract_report(self, meta):
    ...         return None
    """

    feed_url: ClassVar[str]

    # -- Abstract interface (still required from subclasses) -----------------

    @property
    @abstractmethod
    def source_key(self) -> str:
        """Unique identifier for this source."""
        ...

    @property
    @abstractmethod
    def source_config(self) -> SourceConfig:
        """Configuration for this source."""
        ...

    @abstractmethod
    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        """Extract full content from a single report."""
        ...

    # -- RSS feed listing implementation ------------------------------------

    async def fetch_listing(self) -> list[ReportMetadata]:
        """Fetch and parse the RSS/Atom feed to produce report metadata.

        Uses feedparser to parse the feed at ``feed_url``. Handles bozo
        (malformed) feeds gracefully: if the feed is bozo and has no
        entries, returns an empty list. If bozo but has entries, processes
        them with a warning.

        Returns
        -------
        list[ReportMetadata]
            Parsed report metadata from the feed entries.
        """
        logger.info("Fetching RSS feed", source_key=self.source_key, url=self.feed_url)

        try:
            parsed = feedparser.parse(self.feed_url)
        except Exception as exc:
            logger.error(
                "Failed to parse RSS feed",
                source_key=self.source_key,
                url=self.feed_url,
                error=str(exc),
                exc_info=True,
            )
            return []

        # Handle bozo (malformed) feeds
        if parsed.bozo:
            bozo_exc = parsed.get("bozo_exception")
            if not parsed.entries:
                logger.warning(
                    "Malformed RSS feed with no entries, returning empty list",
                    source_key=self.source_key,
                    url=self.feed_url,
                    bozo_exception=str(bozo_exc),
                )
                return []
            logger.warning(
                "Malformed RSS feed but has entries, processing anyway",
                source_key=self.source_key,
                url=self.feed_url,
                bozo_exception=str(bozo_exc),
                entry_count=len(parsed.entries),
            )

        results: list[ReportMetadata] = []
        for entry in parsed.entries:
            try:
                meta = self._entry_to_metadata(entry)
                if meta is not None:
                    results.append(meta)
            except Exception as exc:
                entry_title = entry.get("title", "unknown")
                logger.warning(
                    "Failed to convert feed entry, skipping",
                    source_key=self.source_key,
                    entry_title=entry_title,
                    error=str(exc),
                )
                continue

        logger.info(
            "RSS feed parsed",
            source_key=self.source_key,
            total_entries=len(parsed.entries),
            converted=len(results),
        )
        return results

    # -- Internal helpers ---------------------------------------------------

    def _entry_to_metadata(self, entry: Any) -> ReportMetadata | None:
        """Convert a feedparser entry to ReportMetadata.

        Parameters
        ----------
        entry : Any
            A feedparser entry object.

        Returns
        -------
        ReportMetadata | None
            Converted metadata, or ``None`` if the entry lacks a
            parseable date (published is required).
        """
        title: str = entry.get("title", "")
        link: str = entry.get("link", "")
        author: str | None = entry.get("author") or None
        published = self._parse_date(entry)

        if published is None:
            logger.debug(
                "Skipping entry without parseable date",
                source_key=self.source_key,
                title=title[:80] if title else "(empty)",
            )
            return None

        return ReportMetadata(
            url=link,
            title=title,
            published=published,
            source_key=self.source_key,
            author=author,
        )

    def _parse_date(self, entry: Any) -> datetime | None:
        """Parse a publication date from a feedparser entry.

        Tries multiple strategies in order:
        1. ``published_parsed`` time tuple (feedparser pre-parsed).
        2. ``updated_parsed`` time tuple (Atom fallback).
        3. Raw ``published`` string as RFC 2822.
        4. Raw ``published`` / ``updated`` string as ISO 8601.

        Parameters
        ----------
        entry : Any
            A feedparser entry object.

        Returns
        -------
        datetime | None
            Timezone-aware datetime, or ``None`` if parsing fails.
        """
        # 1. feedparser pre-parsed time tuple
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        # 2. updated_parsed fallback (Atom)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass

        # 3/4. Raw string parsing
        raw = entry.get("published") or entry.get("updated")
        if raw:
            # Try RFC 2822
            try:
                return parsedate_to_datetime(raw)
            except (ValueError, TypeError):
                pass

            # Try ISO 8601
            try:
                return datetime.fromisoformat(raw)
            except (ValueError, TypeError):
                pass

        return None
