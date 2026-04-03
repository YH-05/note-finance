"""Downloader for JPX listed securities data files.

Downloads the XLS file from the JPX website and stores it
via ``FundDbStore``.

Classes
-------
JpxDownloader
    Downloads the JPX listed securities data file.

Examples
--------
>>> from pathlib import Path
>>> from fund_db.storage import FundDbStore
>>> store = FundDbStore(Path("/tmp/fund_db"))
>>> downloader = JpxDownloader(store=store)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fund_db._http import download_bytes
from fund_db._logging import get_logger
from fund_db.config.constants import JPX_LISTED_URL
from fund_db.types import DownloadResult

if TYPE_CHECKING:
    from fund_db.storage import FundDbStore

logger = get_logger(__name__, module="jpx_downloader")


class JpxDownloader:
    """Downloads the JPX listed securities XLS file.

    Uses ``httpx.Client`` for HTTP requests and ``FundDbStore``
    for persisting the raw XLS file.

    Parameters
    ----------
    store : FundDbStore
        Storage backend for saving downloaded files.
    timeout : float
        HTTP request timeout in seconds.

    Examples
    --------
    >>> from pathlib import Path
    >>> from fund_db.storage import FundDbStore
    >>> store = FundDbStore(Path("/tmp/fund_db"))
    >>> dl = JpxDownloader(store=store)
    """

    def __init__(
        self,
        store: FundDbStore,
        *,
        timeout: float = 30.0,
    ) -> None:
        self._store = store
        self._timeout = timeout

    def download(self) -> DownloadResult:
        """Download the JPX listed securities XLS file.

        Returns
        -------
        DownloadResult
            Download result with path, size, and timestamp.

        Raises
        ------
        DownloadError
            If the HTTP request fails or returns a non-2xx status.
        """
        url = JPX_LISTED_URL
        logger.info("Downloading JPX listed securities", url=url)
        content = download_bytes(url, timeout=self._timeout)
        saved_path = self._store.save_raw_excel(
            content=content,
            category="jpx_listed",
            filename="data_j.xls",
        )
        logger.info(
            "Download complete",
            category="jpx_listed",
            size_bytes=len(content),
            path=str(saved_path),
        )
        return DownloadResult(
            path=saved_path,
            url=url,
            size_bytes=len(content),
            downloaded_at=datetime.now(timezone.utc),
        )
