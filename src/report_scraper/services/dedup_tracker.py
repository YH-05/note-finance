"""URL-based deduplication tracker for scraped reports.

Checks ``index.json`` entries by ``(source_key, url, collected_at)``
to determine whether a URL has already been collected within a
configurable look-back window.

Classes
-------
DedupTracker
    URL-based deduplication tracker.

Examples
--------
>>> from pathlib import Path
>>> from report_scraper.storage.json_store import JsonReportStore
>>> store = JsonReportStore(Path("/tmp/dedup-test"))
>>> tracker = DedupTracker(store, dedup_days=30)
>>> tracker.is_seen("source_a", "https://example.com/report/1")
False
>>> tracker.mark_seen("source_a", "https://example.com/report/1")
>>> tracker.is_seen("source_a", "https://example.com/report/1")
True
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from report_scraper._logging import get_logger

if TYPE_CHECKING:
    from report_scraper.storage.json_store import JsonReportStore

logger = get_logger(__name__, module="dedup_tracker")


class DedupTracker:
    """URL-based deduplication tracker using JsonReportStore.

    Examines ``index.json`` entries to decide whether a URL has been
    collected within the last ``dedup_days`` days. URLs whose
    ``collected_at`` timestamp falls outside the window are treated
    as new.

    Parameters
    ----------
    json_store : JsonReportStore
        Store instance that manages ``index.json``.
    dedup_days : int
        Number of days to look back for deduplication. Must be positive.

    Raises
    ------
    ValueError
        If ``dedup_days`` is not positive.

    Examples
    --------
    >>> from pathlib import Path
    >>> from report_scraper.storage.json_store import JsonReportStore
    >>> store = JsonReportStore(Path("/tmp/dedup"))
    >>> tracker = DedupTracker(store, dedup_days=7)
    >>> tracker.dedup_days
    7
    """

    def __init__(self, json_store: JsonReportStore, dedup_days: int = 30) -> None:
        if dedup_days <= 0:
            msg = f"dedup_days must be positive, got {dedup_days}"
            raise ValueError(msg)

        self._store = json_store
        self.dedup_days = dedup_days
        logger.debug(
            "DedupTracker initialized",
            dedup_days=dedup_days,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_seen(self, source_key: str, url: str) -> bool:
        """Check whether a URL has been collected within the dedup window.

        Parameters
        ----------
        source_key : str
            Source identifier (used for logging; the URL itself is the
            dedup key).
        url : str
            Report URL to check.

        Returns
        -------
        bool
            ``True`` if the URL exists in the index **and** its
            ``collected_at`` falls within the last ``dedup_days`` days.
        """
        index = self._store.load_index()
        reports: dict[str, Any] = index.get("reports", {})

        if url not in reports:
            logger.debug("URL not in index", source_key=source_key, url=url)
            return False

        entry = reports[url]
        collected_at_str: str | None = entry.get("collected_at")
        if collected_at_str is None:
            # No timestamp recorded — treat as seen (conservative)
            logger.debug(
                "URL in index but no collected_at, treating as seen",
                source_key=source_key,
                url=url,
            )
            return True

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.dedup_days)
        try:
            collected_at = datetime.fromisoformat(collected_at_str)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Invalid collected_at format, treating as seen",
                source_key=source_key,
                url=url,
                collected_at=collected_at_str,
                error=str(exc),
            )
            return True

        is_within_window = collected_at >= cutoff
        logger.debug(
            "Dedup check",
            source_key=source_key,
            url=url,
            is_seen=is_within_window,
            collected_at=collected_at_str,
            cutoff=cutoff.isoformat(),
        )
        return is_within_window

    def mark_seen(self, source_key: str, url: str) -> None:
        """Record a URL as seen in the index.

        If the URL already exists its ``collected_at`` and
        ``source_key`` are updated. Otherwise a new entry is created.

        Parameters
        ----------
        source_key : str
            Source identifier.
        url : str
            Report URL to record.
        """
        index = self._store.load_index()
        now = datetime.now(timezone.utc).isoformat()

        if url in index["reports"]:
            index["reports"][url]["collected_at"] = now
            index["reports"][url]["source_key"] = source_key
            logger.debug("Updated existing entry", source_key=source_key, url=url)
        else:
            index["reports"][url] = {
                "title": "",
                "source_key": source_key,
                "published": now,
                "collected_at": now,
                "author": None,
                "has_content": False,
            }
            logger.info("Marked new URL as seen", source_key=source_key, url=url)

        self._store.save_index(index)

    def get_history(self, days: int | None = None) -> list[dict[str, Any]]:
        """Return index entries collected within the specified window.

        Parameters
        ----------
        days : int | None
            Number of days to look back. Defaults to ``self.dedup_days``
            when ``None``.

        Returns
        -------
        list[dict[str, Any]]
            List of dicts with ``url``, ``source_key``, ``collected_at``,
            and ``title`` for each matching entry.
        """
        if days is None:
            days = self.dedup_days

        index = self._store.load_index()
        reports: dict[str, Any] = index.get("reports", {})
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result: list[dict[str, Any]] = []
        for url, entry in reports.items():
            collected_at_str: str | None = entry.get("collected_at")
            if collected_at_str is None:
                continue
            try:
                collected_at = datetime.fromisoformat(collected_at_str)
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping entry with invalid collected_at",
                    url=url,
                    collected_at=collected_at_str,
                )
                continue

            if collected_at >= cutoff:
                result.append(
                    {
                        "url": url,
                        "source_key": entry.get("source_key", ""),
                        "collected_at": collected_at_str,
                        "title": entry.get("title", ""),
                    }
                )

        logger.debug(
            "History retrieved",
            days=days,
            total_in_index=len(reports),
            matching=len(result),
        )
        return result
