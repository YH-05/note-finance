"""Downloader for NISA growth investment target Excel files.

Downloads XLSX files from the Investment Trust Association (IMAJ) website
and stores them via ``FundDbStore``.

Classes
-------
NisaDownloader
    Downloads NISA target fund Excel files.

Examples
--------
>>> from pathlib import Path
>>> from fund_db.storage import FundDbStore
>>> store = FundDbStore(Path("/tmp/fund_db"))
>>> downloader = NisaDownloader(store=store)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fund_db._http import download_bytes
from fund_db._logging import get_logger
from fund_db.config.constants import NISA_LISTED_URL, NISA_UNLISTED_URL
from fund_db.types import DownloadResult

if TYPE_CHECKING:
    from fund_db.storage import FundDbStore

logger = get_logger(__name__, module="nisa_downloader")


class NisaDownloader:
    """Downloads NISA target fund Excel files from IMAJ.

    Uses ``httpx.Client`` for HTTP requests and ``FundDbStore``
    for persisting raw Excel files.

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
    >>> dl = NisaDownloader(store=store)
    """

    def __init__(
        self,
        store: FundDbStore,
        *,
        timeout: float = 30.0,
    ) -> None:
        """Initialize NisaDownloader.

        Parameters
        ----------
        store : FundDbStore
            Storage backend for saving downloaded files.
        timeout : float
            HTTP request timeout in seconds. Default is 30.0.
        """
        self._store = store
        self._timeout = timeout

    def _download(self, url: str, category: str, filename: str) -> DownloadResult:
        """Download a single file and save via FundDbStore.

        Parameters
        ----------
        url : str
            URL to download from.
        category : str
            Storage category for partitioning.
        filename : str
            Filename to save the downloaded content as.

        Returns
        -------
        DownloadResult
            Download result with path, size, and timestamp.

        Raises
        ------
        DownloadError
            If the HTTP request fails or returns a non-2xx status.
        """
        logger.info("Downloading NISA Excel", url=url, category=category)
        content = download_bytes(url, timeout=self._timeout)
        saved_path = self._store.save_raw_excel(
            content=content,
            category=category,
            filename=filename,
        )
        logger.info(
            "Download complete",
            category=category,
            size_bytes=len(content),
            path=str(saved_path),
        )
        return DownloadResult(
            path=saved_path,
            url=url,
            size_bytes=len(content),
            downloaded_at=datetime.now(timezone.utc),
        )

    def download_unlisted(self) -> DownloadResult:
        """Download the non-listed investment trust Excel file.

        Returns
        -------
        DownloadResult
            Download result for the unlisted fund file.

        Raises
        ------
        DownloadError
            If the download fails.
        """
        return self._download(
            url=NISA_UNLISTED_URL,
            category="nisa_unlisted",
            filename="tsumitate_target.xlsx",
        )

    def download_listed(self) -> DownloadResult:
        """Download the listed ETF/REIT Excel file.

        Returns
        -------
        DownloadResult
            Download result for the listed ETF file.

        Raises
        ------
        DownloadError
            If the download fails.
        """
        return self._download(
            url=NISA_LISTED_URL,
            category="nisa_listed",
            filename="tsumitate_target_etf.xlsx",
        )

    def download_all(self) -> list[DownloadResult]:
        """Download both unlisted and listed Excel files.

        Returns
        -------
        list[DownloadResult]
            List of download results for both files.

        Raises
        ------
        DownloadError
            If any download fails.
        """
        logger.info("Downloading all NISA Excel files")
        results = [
            self.download_unlisted(),
            self.download_listed(),
        ]
        logger.info(
            "All NISA downloads complete",
            total_files=len(results),
            total_bytes=sum(r.size_bytes for r in results),
        )
        return results
