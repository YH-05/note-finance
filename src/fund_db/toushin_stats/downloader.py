"""Downloader for Investment Trust Association statistics Excel files.

Scrapes the IMAJ statistics page to discover download links for
B-1, B-2, B-3, and A-2 Excel files, then downloads and stores them
via ``FundDbStore``.

Classes
-------
ToushinStatsDownloader
    Downloads statistics Excel files from IMAJ.

Examples
--------
>>> from pathlib import Path
>>> from fund_db.storage import FundDbStore
>>> store = FundDbStore(Path("/tmp/fund_db"))
>>> downloader = ToushinStatsDownloader(store=store)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import lxml.html

from fund_db._http import download_bytes, validate_url_host
from fund_db._logging import get_logger
from fund_db.config.constants import TOUSHIN_STATS_PAGE
from fund_db.exceptions import DownloadError
from fund_db.types import DownloadResult

if TYPE_CHECKING:
    from fund_db.storage import FundDbStore

logger = get_logger(__name__, module="toushin_stats_downloader")

# File name patterns for each report type
_LINK_PATTERNS: dict[str, list[str]] = {
    "b1": ["shisan_zougen", "B-1", "B1"],
    "b2": ["shohin_bunrui", "B-2", "B2"],
    "b3": ["unyo_kaisha", "B-3", "B3"],
    "a2": ["zentaizou", "A-2", "A2"],
}


class ToushinStatsDownloader:
    """Downloads statistics Excel files from IMAJ.

    Scrapes the IMAJ statistics page to find download links,
    then downloads XLSX files and saves them via ``FundDbStore``.

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
    >>> dl = ToushinStatsDownloader(store=store)
    """

    def __init__(
        self,
        store: FundDbStore,
        *,
        timeout: float = 30.0,
    ) -> None:
        """Initialize ToushinStatsDownloader.

        Parameters
        ----------
        store : FundDbStore
            Storage backend for saving downloaded files.
        timeout : float
            HTTP request timeout in seconds. Default is 30.0.
        """
        self._store = store
        self._timeout = timeout
        self._cached_links: dict[str, str] | None = None

    def _fetch_page(self, url: str) -> str:
        """Fetch HTML content from a URL.

        Parameters
        ----------
        url : str
            URL to fetch.

        Returns
        -------
        str
            HTML content as text.

        Raises
        ------
        DownloadError
            If the HTTP request fails.
        """
        logger.info("Fetching statistics page", url=url)
        content = download_bytes(url, timeout=self._timeout)
        return content.decode()

    def _extract_download_links(self, html: str, base_url: str) -> dict[str, str]:
        """Extract download links for each report type from HTML.

        Parses the HTML to find ``<a>`` tags with ``.xlsx`` hrefs,
        then matches each link against known file name patterns.

        Parameters
        ----------
        html : str
            HTML content of the statistics page.
        base_url : str
            Base URL for resolving relative links.

        Returns
        -------
        dict[str, str]
            Mapping from report key ("b1", "b2", "b3", "a2")
            to absolute download URL.
        """
        doc = lxml.html.fromstring(html)
        doc.make_links_absolute(base_url)

        # Find all .xlsx links
        xlsx_links: list[tuple[str, str]] = []
        for anchor in doc.cssselect("a[href]"):
            href = anchor.get("href", "")
            if href.endswith(".xlsx") or href.endswith(".xls"):
                text = anchor.text_content().strip() if anchor.text_content() else ""
                xlsx_links.append((href, text))

        logger.debug(
            "Found xlsx links on page",
            link_count=len(xlsx_links),
        )

        result: dict[str, str] = {}
        for report_key, patterns in _LINK_PATTERNS.items():
            for href, text in xlsx_links:
                matched = any(
                    pattern.lower() in href.lower() or pattern.lower() in text.lower()
                    for pattern in patterns
                )
                if matched:
                    # Validate URL host before accepting
                    try:
                        validate_url_host(href)
                    except DownloadError:
                        logger.warning(
                            "Skipping link with untrusted host",
                            report=report_key,
                            url=href,
                        )
                        continue
                    result[report_key] = href
                    logger.debug(
                        "Matched download link",
                        report=report_key,
                        url=href,
                    )
                    break

        logger.info(
            "Download links extracted",
            found_reports=list(result.keys()),
            total_xlsx=len(xlsx_links),
        )
        return result

    def _download_file(self, url: str, category: str, filename: str) -> DownloadResult:
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
        logger.info("Downloading statistics Excel", url=url, category=category)
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

    def _get_links(self) -> dict[str, str]:
        """Fetch page and extract download links.

        Results are cached after the first call to avoid
        redundant HTTP requests within the same instance.

        Returns
        -------
        dict[str, str]
            Mapping from report key to download URL.

        Raises
        ------
        DownloadError
            If page fetch or link extraction fails.
        """
        if self._cached_links is not None:
            return self._cached_links
        html = self._fetch_page(TOUSHIN_STATS_PAGE)
        links = self._extract_download_links(html, TOUSHIN_STATS_PAGE)
        self._cached_links = links
        return links

    def download_b1(self) -> DownloadResult:
        """Download B-1 (asset flow) Excel file.

        Returns
        -------
        DownloadResult
            Download result for the B-1 file.

        Raises
        ------
        DownloadError
            If the download fails or B-1 link not found.
        """
        links = self._get_links()
        url = links.get("b1")
        if url is None:
            raise DownloadError(
                "B-1 download link not found on statistics page",
                url=TOUSHIN_STATS_PAGE,
            )
        return self._download_file(
            url=url,
            category="toushin_stats_b1",
            filename="toushin_B1_shisan_zougen.xlsx",
        )

    def download_b2(self) -> DownloadResult:
        """Download B-2 (product class) Excel file.

        Returns
        -------
        DownloadResult
            Download result for the B-2 file.

        Raises
        ------
        DownloadError
            If the download fails or B-2 link not found.
        """
        links = self._get_links()
        url = links.get("b2")
        if url is None:
            raise DownloadError(
                "B-2 download link not found on statistics page",
                url=TOUSHIN_STATS_PAGE,
            )
        return self._download_file(
            url=url,
            category="toushin_stats_b2",
            filename="toushin_B2_shohin_bunrui.xlsx",
        )

    def download_b3(self) -> DownloadResult:
        """Download B-3 (management company) Excel file.

        Returns
        -------
        DownloadResult
            Download result for the B-3 file.

        Raises
        ------
        DownloadError
            If the download fails or B-3 link not found.
        """
        links = self._get_links()
        url = links.get("b3")
        if url is None:
            raise DownloadError(
                "B-3 download link not found on statistics page",
                url=TOUSHIN_STATS_PAGE,
            )
        return self._download_file(
            url=url,
            category="toushin_stats_b3",
            filename="toushin_B3_unyo_kaisha.xlsx",
        )

    def download_a2(self) -> DownloadResult:
        """Download A-2 (overall status) Excel file.

        Returns
        -------
        DownloadResult
            Download result for the A-2 file.

        Raises
        ------
        DownloadError
            If the download fails or A-2 link not found.
        """
        links = self._get_links()
        url = links.get("a2")
        if url is None:
            raise DownloadError(
                "A-2 download link not found on statistics page",
                url=TOUSHIN_STATS_PAGE,
            )
        return self._download_file(
            url=url,
            category="toushin_stats_a2",
            filename="toushin_A2_zentaizou.xlsx",
        )

    def download_all(self) -> list[DownloadResult]:
        """Download all available statistics Excel files.

        Returns
        -------
        list[DownloadResult]
            List of download results for each found file.

        Raises
        ------
        DownloadError
            If any download fails.
        """
        logger.info("Downloading all statistics Excel files")
        links = self._get_links()

        report_configs = {
            "b1": ("toushin_stats_b1", "toushin_B1_shisan_zougen.xlsx"),
            "b2": ("toushin_stats_b2", "toushin_B2_shohin_bunrui.xlsx"),
            "b3": ("toushin_stats_b3", "toushin_B3_unyo_kaisha.xlsx"),
            "a2": ("toushin_stats_a2", "toushin_A2_zentaizou.xlsx"),
        }

        results: list[DownloadResult] = []
        for key, (category, filename) in report_configs.items():
            url = links.get(key)
            if url is not None:
                result = self._download_file(
                    url=url,
                    category=category,
                    filename=filename,
                )
                results.append(result)
            else:
                logger.warning(
                    "Download link not found, skipping",
                    report=key,
                )

        logger.info(
            "All statistics downloads complete",
            total_files=len(results),
            total_bytes=sum(r.size_bytes for r in results),
        )
        return results
