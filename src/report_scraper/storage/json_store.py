"""JSON-based persistent storage for scraped reports.

Manages an ``index.json`` file tracking all known report URLs,
per-run result files in ``runs/``, and extracted text files in
``text/{source_key}/``.

Classes
-------
JsonReportStore
    JSON storage for scraped report data.

Examples
--------
>>> from pathlib import Path
>>> store = JsonReportStore(Path("data/scraped/reports"))
>>> index = store.load_index()
>>> index
{'reports': {}}
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from report_scraper._logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from report_scraper.types import CollectResult, ScrapedReport

logger = get_logger(__name__, module="json_store")

_SOURCE_KEY_RE = re.compile(r"^[a-zA-Z0-9_]+$")
"""Allowed characters for source_key: alphanumeric and underscore."""


class JsonReportStore:
    """JSON-based persistent storage for scraped report data.

    Manages three types of files:

    - ``index.json``: Central index mapping report URLs to metadata.
    - ``runs/{timestamp}.json``: Per-run collection result snapshots.
    - ``text/{source_key}/{hash}.txt``: Extracted text content files.

    Parameters
    ----------
    data_dir : Path
        Root directory for report storage. Subdirectories ``runs/``
        and ``text/`` are created automatically.

    Examples
    --------
    >>> from pathlib import Path
    >>> store = JsonReportStore(Path("/tmp/reports"))
    >>> store.load_index()
    {'reports': {}}
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize JsonReportStore and create directories.

        Parameters
        ----------
        data_dir : Path
            Root directory for report storage.
        """
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "runs").mkdir(exist_ok=True)
        (self.data_dir / "text").mkdir(exist_ok=True)
        self._index_cache: dict[str, Any] | None = None
        logger.debug("JsonReportStore initialized", data_dir=str(data_dir))

    # -- Index operations ---------------------------------------------------

    def load_index(self) -> dict[str, Any]:
        """Load the report index from ``index.json``.

        Returns
        -------
        dict[str, Any]
            Index data with a ``"reports"`` mapping of URL to metadata.
            Returns a default empty index if the file does not exist
            or cannot be parsed.

        Examples
        --------
        >>> store = JsonReportStore(Path("/tmp/reports"))
        >>> store.load_index()
        {'reports': {}}
        """
        if self._index_cache is not None:
            return self._index_cache

        index_path = self.data_dir / "index.json"
        if not index_path.exists():
            logger.debug("Index file not found, returning empty index")
            self._index_cache = {"reports": {}}
            return self._index_cache

        try:
            with index_path.open(encoding="utf-8") as f:
                data: Any = json.load(f)
            if isinstance(data, dict) and "reports" in data:
                logger.debug(
                    "Index loaded",
                    report_count=len(data["reports"]),
                )
                self._index_cache = data
                return self._index_cache  # type: ignore[return-value]
            logger.warning("Index file has unexpected structure, returning empty index")
            self._index_cache = {"reports": {}}
            return self._index_cache
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to load index, returning empty index",
                error=str(exc),
            )
            self._index_cache = {"reports": {}}
            return self._index_cache

    def save_index(self, index: dict[str, Any]) -> None:
        """Save the report index to ``index.json``.

        Parameters
        ----------
        index : dict[str, Any]
            Index data to save. Must contain a ``"reports"`` key.

        Examples
        --------
        >>> store = JsonReportStore(Path("/tmp/reports"))
        >>> store.save_index({"reports": {"https://x.com": {"title": "T"}}})
        """
        index_path = self.data_dir / "index.json"
        try:
            with index_path.open("w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
            self._index_cache = index
            logger.debug(
                "Index saved",
                report_count=len(index.get("reports", {})),
            )
        except OSError as exc:
            logger.error("Failed to save index", error=str(exc))
            raise

    def update_index(self, result: CollectResult) -> None:
        """Update the index with reports from a collection result.

        Adds or updates entries in the index for each report in the
        ``CollectResult``. Uses the report URL as the key.

        Parameters
        ----------
        result : CollectResult
            Collection result containing reports to index.
        """
        index = self.load_index()
        now = datetime.now(timezone.utc).isoformat()

        for report in result.reports:
            meta = report.metadata
            index["reports"][meta.url] = {
                "title": meta.title,
                "source_key": meta.source_key,
                "published": meta.published.isoformat(),
                "collected_at": now,
                "author": meta.author,
                "has_content": report.content is not None,
            }

        self.save_index(index)
        logger.info(
            "Index updated",
            source_key=result.source_key,
            reports_added=len(result.reports),
            total_reports=len(index["reports"]),
        )

    def is_known_url(self, url: str) -> bool:
        """Check if a URL is already in the index.

        Parameters
        ----------
        url : str
            Report URL to check.

        Returns
        -------
        bool
            ``True`` if the URL exists in the index.
        """
        index = self.load_index()
        return url in index["reports"]

    # -- Run snapshots ------------------------------------------------------

    def save_run(
        self,
        result: CollectResult,
        *,
        timestamp: str | None = None,
    ) -> Path:
        """Save a collection run result as a timestamped JSON file.

        Parameters
        ----------
        result : CollectResult
            Collection result to save.
        timestamp : str | None
            Optional timestamp string for the filename. If ``None``,
            a timestamp is generated from the current UTC time.

        Returns
        -------
        Path
            Path to the saved run file.

        Examples
        --------
        >>> store = JsonReportStore(Path("/tmp/reports"))
        >>> # path = store.save_run(result)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")

        run_data: dict[str, Any] = {
            "source_key": result.source_key,
            "timestamp": timestamp,
            "duration": result.duration,
            "reports": [],
            "errors": list(result.errors),
        }

        for report in result.reports:
            meta = report.metadata
            report_entry: dict[str, Any] = {
                "url": meta.url,
                "title": meta.title,
                "published": meta.published.isoformat(),
                "source_key": meta.source_key,
                "author": meta.author,
                "has_content": report.content is not None,
                "content_method": report.content.method if report.content else None,
                "content_length": report.content.length if report.content else 0,
            }
            run_data["reports"].append(report_entry)

        run_path = self.data_dir / "runs" / f"{timestamp}.json"
        try:
            with run_path.open("w", encoding="utf-8") as f:
                json.dump(run_data, f, ensure_ascii=False, indent=2)
            logger.info(
                "Run saved",
                path=str(run_path),
                report_count=len(result.reports),
            )
        except OSError as exc:
            logger.error("Failed to save run", error=str(exc))
            raise

        return run_path

    # -- Text file storage --------------------------------------------------

    def save_text(self, report: ScrapedReport) -> None:
        """Save extracted text content to a file.

        Text files are stored at ``text/{source_key}/{url_hash}.txt``.
        If the report has no content, this method is a no-op.

        Parameters
        ----------
        report : ScrapedReport
            Report whose content to save.
        """
        if report.content is None:
            logger.debug(
                "No content to save",
                url=report.metadata.url,
            )
            return

        source_key = report.metadata.source_key
        if not _SOURCE_KEY_RE.match(source_key):
            raise ValueError(
                f"Invalid source_key (must be alphanumeric/underscore): {source_key}"
            )
        source_dir = self.data_dir / "text" / source_key
        source_dir.mkdir(parents=True, exist_ok=True)

        # Use URL hash as filename to avoid filesystem issues
        url_hash = hashlib.sha256(report.metadata.url.encode("utf-8")).hexdigest()[:32]
        text_path = source_dir / f"{url_hash}.txt"

        try:
            text_path.write_text(report.content.text, encoding="utf-8")
            logger.debug(
                "Text saved",
                path=str(text_path),
                length=report.content.length,
                url=report.metadata.url,
            )
        except OSError as exc:
            logger.error(
                "Failed to save text",
                error=str(exc),
                url=report.metadata.url,
            )
