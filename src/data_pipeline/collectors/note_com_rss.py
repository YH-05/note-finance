"""RSS-based new article monitor for note.com creators.

Periodically checks RSS feeds of configured note.com creators,
detects new free articles, scrapes them via Playwright, and
persists the raw text to :class:`RawStore`.

Flow
----
1. Load ``rss_enabled`` creators from config JSON.
2. For each creator, fetch ``https://note.com/{username}/rss`` via feedparser.
3. Filter out articles already stored in :class:`RawStore`.
4. Launch :class:`NoteComBrowser` only when new articles exist.
5. Scrape each new article; save free ones to RawStore.
6. Update ``last_rss_checked_at`` in the config file.

Examples
--------
>>> from data_pipeline.collectors.note_com_rss import NoteComRssMonitor
>>> monitor = NoteComRssMonitor(config_path=Path("data/config/note-com-creators.json"))
>>> result = monitor.monitor()
>>> print(f"Found {result.new_articles_found}, saved {result.articles_saved}")
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import feedparser

from data_pipeline.collectors.note_com_browser import NoteArticle, NoteComBrowser
from data_pipeline.storage.raw_store import RawStore
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RssEntry:
    """A single RSS feed entry from note.com.

    Attributes
    ----------
    url : str
        Article URL.
    title : str
        Article title from the RSS feed.
    published_at : datetime | None
        Publication datetime parsed from the RSS ``published`` field.
    """

    url: str
    title: str
    published_at: datetime | None


@dataclass
class MonitorResult:
    """Aggregate result of an RSS monitor run.

    Attributes
    ----------
    creators_checked : int
        Number of creators whose RSS feed was checked.
    new_articles_found : int
        Total new (not yet saved) articles discovered.
    articles_saved : int
        Articles successfully saved to RawStore.
    articles_skipped_paid : int
        Articles skipped because they are behind a paywall.
    articles_skipped_duplicate : int
        Articles skipped because they already exist in RawStore.
    errors : list[str]
        Error messages encountered during the run.
    """

    creators_checked: int = 0
    new_articles_found: int = 0
    articles_saved: int = 0
    articles_skipped_paid: int = 0
    articles_skipped_duplicate: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# NoteComRssMonitor
# ---------------------------------------------------------------------------


class NoteComRssMonitor:
    """RSS-based new article monitor for note.com creators.

    Parameters
    ----------
    config_path : Path
        Path to ``note-com-creators.json``.
    raw_store : RawStore | None
        RawStore instance. ``None`` creates a default instance.
    headless : bool
        Run Playwright in headless mode.
    request_delay : float
        Delay in seconds between HTTP requests.
    """

    def __init__(
        self,
        config_path: Path,
        raw_store: RawStore | None = None,
        *,
        headless: bool = True,
        request_delay: float = 2.0,
    ) -> None:
        self._config_path = config_path
        self._raw_store = raw_store or RawStore()
        self._headless = headless
        self._request_delay = request_delay

        logger.debug(
            "rss_monitor_initialized config_path=%s headless=%s request_delay=%s",
            str(config_path),
            headless,
            request_delay,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def monitor(self) -> MonitorResult:
        """Check all ``rss_enabled`` creators for new articles.

        Wraps the async logic in :pymethod:`_monitor_async` with
        ``asyncio.run()``.

        Returns
        -------
        MonitorResult
            Aggregated results of the monitoring run.
        """
        return asyncio.run(self._monitor_async())

    async def _monitor_async(self) -> MonitorResult:
        """Async main logic for the RSS monitoring run.

        Returns
        -------
        MonitorResult
            Aggregated results of the monitoring run.
        """
        result = MonitorResult()

        creators = self._load_rss_creators()
        if not creators:
            logger.info("no_rss_enabled_creators_found")
            return result

        logger.info("rss_monitor_starting creator_count=%d", len(creators))

        # Phase 1: Collect new entries across all creators
        creator_new_entries: list[tuple[dict, list[RssEntry]]] = []

        for creator in creators:
            username: str = creator["username"]
            source_id = f"note-com-{username}"
            result.creators_checked += 1

            try:
                entries = self._fetch_rss(username)
                logger.info(
                    "rss_fetched username=%s entry_count=%d",
                    username,
                    len(entries),
                )
            except Exception as exc:
                msg = f"RSS fetch failed for {username}: {exc}"
                logger.error("rss_fetch_failed username=%s error=%s", username, str(exc))
                result.errors.append(msg)
                continue

            new_entries = self._filter_new(entries, source_id)
            if not new_entries:
                logger.debug("no_new_entries username=%s", username)
                continue

            logger.info(
                "new_entries_found username=%s new_count=%d",
                username,
                len(new_entries),
            )
            result.new_articles_found += len(new_entries)
            creator_new_entries.append((creator, new_entries))

        # Phase 2: Scrape new articles (only if any new entries found)
        if creator_new_entries:
            async with NoteComBrowser(
                headless=self._headless,
                request_delay=self._request_delay,
            ) as browser:
                for creator, new_entries in creator_new_entries:
                    username = creator["username"]
                    source_id = f"note-com-{username}"

                    for entry in new_entries:
                        try:
                            article = await browser.scrape_article(entry.url)
                        except Exception as exc:
                            msg = f"Scrape failed for {entry.url}: {exc}"
                            logger.error(
                                "article_scrape_failed url=%s error=%s",
                                entry.url,
                                str(exc),
                            )
                            result.errors.append(msg)
                            continue

                        if article is None:
                            # scrape_article returns None for paid articles
                            logger.info(
                                "article_paid_skipped url=%s",
                                entry.url,
                            )
                            result.articles_skipped_paid += 1
                            continue

                        # Save free article to RawStore
                        outcome = self._save_article(
                            article=article,
                            source_id=source_id,
                            rss_title=entry.title,
                        )

                        if outcome == "saved":
                            result.articles_saved += 1
                            logger.info(
                                "article_saved url=%s title=%s",
                                article.url,
                                article.title,
                            )
                        elif outcome == "duplicate":
                            result.articles_skipped_duplicate += 1
                            logger.debug(
                                "article_duplicate_skipped url=%s",
                                article.url,
                            )
                        elif outcome == "empty":
                            msg = f"Empty body for {article.url}"
                            logger.warning("article_empty_body url=%s", article.url)
                            result.errors.append(msg)

        # Phase 3: Update config timestamps
        self._update_config(creators)

        logger.info(
            "rss_monitor_completed creators_checked=%d new_articles_found=%d"
            " articles_saved=%d articles_skipped_paid=%d"
            " articles_skipped_duplicate=%d error_count=%d",
            result.creators_checked,
            result.new_articles_found,
            result.articles_saved,
            result.articles_skipped_paid,
            result.articles_skipped_duplicate,
            len(result.errors),
        )

        return result

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_rss_creators(self) -> list[dict]:
        """Load creators with ``rss_enabled=true`` and ``enabled=true``.

        Reads the config JSON and filters creators that have both
        ``enabled`` and ``rss_enabled`` set to ``true``.

        Returns
        -------
        list[dict]
            List of creator configuration dicts.

        Raises
        ------
        FileNotFoundError
            If the config file does not exist.
        """
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self._config_path}"
            )

        config = json.loads(
            self._config_path.read_text(encoding="utf-8"),
        )
        creators: list[dict] = config.get("creators", [])

        rss_creators = [
            c
            for c in creators
            if c.get("enabled", False) and c.get("rss_enabled", False)
        ]

        logger.debug(
            "rss_creators_loaded total_creators=%d rss_enabled_count=%d",
            len(creators),
            len(rss_creators),
        )

        return rss_creators

    # ------------------------------------------------------------------
    # RSS fetching
    # ------------------------------------------------------------------

    def _fetch_rss(self, username: str) -> list[RssEntry]:
        """Fetch and parse a note.com user's RSS feed.

        Uses ``feedparser`` to parse
        ``https://note.com/{username}/rss``.

        Parameters
        ----------
        username : str
            note.com username (without ``@``).

        Returns
        -------
        list[RssEntry]
            Parsed RSS entries with url, title, and published_at.
        """
        feed_url = f"https://note.com/{username}/rss"
        logger.debug("fetching_rss url=%s", feed_url)

        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(
                "rss_parse_warning url=%s bozo_exception=%s",
                feed_url,
                str(feed.get("bozo_exception", "")),
            )

        entries: list[RssEntry] = []
        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url:
                continue

            published_at = self._parse_rss_date(entry.get("published"))

            entries.append(
                RssEntry(
                    url=url,
                    title=title,
                    published_at=published_at,
                ),
            )

        return entries

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _filter_new(
        self,
        entries: list[RssEntry],
        source_id: str,
    ) -> list[RssEntry]:
        """Filter out entries already stored in RawStore.

        Uses :pymethod:`RawStore.exists` to check each entry URL.

        Parameters
        ----------
        entries : list[RssEntry]
            RSS entries to check.
        source_id : str
            Source ID for the RawStore lookup (e.g. ``note-com-username``).

        Returns
        -------
        list[RssEntry]
            Only entries whose URL is not yet in RawStore.
        """
        new_entries: list[RssEntry] = []
        for entry in entries:
            if not self._raw_store.exists(url=entry.url, source_id=source_id):
                new_entries.append(entry)

        return new_entries

    # ------------------------------------------------------------------
    # Saving
    # ------------------------------------------------------------------

    def _save_article(
        self,
        *,
        article: NoteArticle,
        source_id: str,
        rss_title: str,
    ) -> str:
        """Save a scraped article to RawStore.

        Parameters
        ----------
        article : NoteArticle
            Scraped article data from :class:`NoteComBrowser`.
        source_id : str
            Source ID (e.g. ``note-com-username``).
        rss_title : str
            Title from the RSS feed (may differ from scraped title).

        Returns
        -------
        str
            Save outcome: ``"saved"``, ``"duplicate"``, or ``"empty"``.
        """
        metadata: dict = {
            "hashtags": article.hashtags,
            "like_count": article.like_count,
            "rss_title": rss_title,
        }

        return self._raw_store.save_text(
            source_id=source_id,
            url=article.url,
            title=article.title,
            raw_text=article.body_text,
            collection_method="note-com-rss",
            published_at=article.published_at,
            author=article.author,
            language="ja",
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Config update
    # ------------------------------------------------------------------

    def _update_config(self, checked_creators: list[dict]) -> None:
        """Update ``last_rss_checked_at`` for checked creators.

        Reads the config, updates timestamps for each checked creator,
        and writes the file back.

        Parameters
        ----------
        checked_creators : list[dict]
            Creator dicts that were checked in this run.
        """
        try:
            config = json.loads(
                self._config_path.read_text(encoding="utf-8"),
            )
        except Exception as exc:
            logger.error(
                "config_read_failed_for_update error=%s",
                str(exc),
            )
            return

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        checked_usernames = {c["username"] for c in checked_creators}

        for creator in config.get("creators", []):
            if creator.get("username") in checked_usernames:
                creator["last_rss_checked_at"] = now_iso

        try:
            self._config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=4) + "\n",
                encoding="utf-8",
            )
            logger.info(
                "config_updated updated_count=%d timestamp=%s",
                len(checked_usernames),
                now_iso,
            )
        except Exception as exc:
            logger.error(
                "config_write_failed error=%s",
                str(exc),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rss_date(value: str | None) -> datetime | None:
        """Parse an RSS date string (RFC 2822 format).

        Falls back to ISO 8601 parsing if RFC 2822 fails.

        Parameters
        ----------
        value : str | None
            Date string from an RSS ``published`` field.

        Returns
        -------
        datetime | None
            Parsed datetime, or ``None`` if parsing fails.
        """
        if not value:
            return None

        # Try RFC 2822 (standard RSS format)
        try:
            return parsedate_to_datetime(value)
        except (ValueError, TypeError):
            pass

        # Fallback: ISO 8601
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            logger.debug("rss_date_parse_failed value=%s", value)
            return None


__all__ = ["MonitorResult", "NoteComRssMonitor", "RssEntry"]
