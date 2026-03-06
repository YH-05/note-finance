"""PDF download service using httpx.

Downloads PDF files from URLs with proper error handling and timeout
configuration. Uses httpx as the HTTP client (does not require Scrapling).

Functions
---------
is_pdf_url
    Check if a URL points to a PDF file.
find_pdf_links
    Extract PDF links from HTML anchor elements.

Classes
-------
PdfDownloader
    Async PDF download service.

Examples
--------
>>> from report_scraper.services.pdf_downloader import is_pdf_url
>>> is_pdf_url("https://example.com/report.pdf")
True
>>> is_pdf_url("https://example.com/page.html")
False
"""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

import httpx

from report_scraper._logging import get_logger
from report_scraper.exceptions import FetchError

if TYPE_CHECKING:
    from pathlib import Path

    from report_scraper.types import PdfMetadata

logger = get_logger(__name__, module="pdf_downloader")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PDF_URL_PATTERN = re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE)
"""Regex pattern matching URLs ending with ``.pdf``."""

_FILENAME_SANITIZE_RE = re.compile(r"[^\w\-.]")
"""Regex for characters not allowed in derived filenames."""

ALLOWED_URL_SCHEMES = frozenset({"https", "http"})
"""Allowed URL schemes for download targets (SSRF protection)."""

DEFAULT_TIMEOUT = 60.0
"""Default HTTP timeout in seconds for PDF downloads."""

MAX_PDF_SIZE = 100 * 1024 * 1024  # 100 MB
"""Maximum PDF file size in bytes."""


# ---------------------------------------------------------------------------
# Standalone utility functions
# ---------------------------------------------------------------------------


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private or reserved IP address.

    Parameters
    ----------
    hostname : str
        Hostname or IP address to check.

    Returns
    -------
    bool
        ``True`` if the address is private, loopback, or reserved.
    """
    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_reserved
    except ValueError:
        pass
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
        for _, _, _, _, sockaddr in resolved:
            addr = ipaddress.ip_address(sockaddr[0])
            if addr.is_private or addr.is_loopback or addr.is_reserved:
                return True
    except (socket.gaierror, OSError):
        pass
    return False


def is_pdf_url(url: str) -> bool:
    """Check if a URL points to a PDF file.

    Parameters
    ----------
    url : str
        URL to check.

    Returns
    -------
    bool
        ``True`` if the URL path ends with ``.pdf`` (case-insensitive),
        optionally followed by query parameters.

    Examples
    --------
    >>> is_pdf_url("https://example.com/report.pdf")
    True
    >>> is_pdf_url("https://example.com/report.PDF")
    True
    >>> is_pdf_url("https://example.com/report.pdf?token=abc")
    True
    >>> is_pdf_url("https://example.com/report.html")
    False
    >>> is_pdf_url("")
    False
    """
    if not url:
        return False
    parsed = urlparse(url)
    return bool(PDF_URL_PATTERN.search(parsed.path))


def find_pdf_links(elements: Any, base_url: str) -> list[str]:
    """Extract PDF links from a collection of anchor-like elements.

    Each element must have an ``attrib`` dict containing ``"href"``.

    Parameters
    ----------
    elements : Any
        Iterable of elements with ``attrib`` dict (e.g., lxml or
        Scrapling elements).
    base_url : str
        Base URL for resolving relative links.

    Returns
    -------
    list[str]
        Deduplicated list of absolute PDF URLs found.

    Examples
    --------
    >>> from unittest.mock import MagicMock
    >>> el = MagicMock()
    >>> el.attrib = {"href": "/docs/report.pdf"}
    >>> find_pdf_links([el], "https://example.com")
    ['https://example.com/docs/report.pdf']
    """
    seen: set[str] = set()
    pdf_links: list[str] = []

    for el in elements:
        href = el.attrib.get("href", "")
        if not href:
            continue

        parsed = urlparse(href)
        absolute = href if parsed.scheme else urljoin(base_url, href)

        if is_pdf_url(absolute) and absolute not in seen:
            seen.add(absolute)
            pdf_links.append(absolute)

    return pdf_links


# ---------------------------------------------------------------------------
# PdfDownloader class
# ---------------------------------------------------------------------------


class PdfDownloader:
    """Async PDF download service using httpx.

    Downloads PDF files from URLs with configurable timeouts and size limits.
    Does not depend on Scrapling -- uses httpx for simple HTTP GET requests.

    Parameters
    ----------
    timeout : float
        HTTP request timeout in seconds.
    max_size : int
        Maximum allowed PDF file size in bytes.

    Examples
    --------
    >>> downloader = PdfDownloader()
    >>> # pdf_meta = await downloader.download("https://example.com/r.pdf", Path("/tmp"))
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        max_size: int = MAX_PDF_SIZE,
    ) -> None:
        """Initialize PdfDownloader.

        Parameters
        ----------
        timeout : float
            HTTP request timeout in seconds.
        max_size : int
            Maximum allowed PDF file size in bytes.
        """
        self.timeout = timeout
        self.max_size = max_size
        self._client: httpx.AsyncClient | None = None
        logger.debug(
            "PdfDownloader initialized",
            timeout=timeout,
            max_size_mb=round(max_size / (1024 * 1024), 1),
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def download(
        self,
        url: str,
        output_dir: Path,
        *,
        filename: str | None = None,
    ) -> PdfMetadata:
        """Download a PDF file and save it to the output directory.

        Parameters
        ----------
        url : str
            URL of the PDF to download.
        output_dir : Path
            Directory where the PDF will be saved.
        filename : str | None
            Optional filename override. If ``None``, derived from the URL.

        Returns
        -------
        PdfMetadata
            Metadata about the downloaded PDF file.

        Raises
        ------
        FetchError
            If the download fails (network error, non-200 status,
            or file exceeds ``max_size``).
        """
        from report_scraper.types import PdfMetadata as PdfMeta

        # SSRF protection: validate URL scheme
        parsed_url = urlparse(url)
        if parsed_url.scheme not in ALLOWED_URL_SCHEMES:
            raise FetchError(
                f"Unsupported URL scheme '{parsed_url.scheme}' (allowed: {', '.join(sorted(ALLOWED_URL_SCHEMES))})",
                url=url,
            )

        # SSRF protection: block private/internal IP ranges
        hostname = parsed_url.hostname or ""
        if _is_private_ip(hostname):
            raise FetchError(
                f"Download blocked: private/internal address detected ({hostname})",
                url=url,
            )

        logger.info("Downloading PDF", url=url)

        if filename is None:
            filename = self._derive_filename(url)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename

        client = await self._get_client()

        try:
            # AIDEV-NOTE: Stream download to avoid loading entire PDF into memory
            size = 0
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    logger.warning(
                        "Non-200 status for PDF download",
                        url=url,
                        status=response.status_code,
                    )
                    raise FetchError(
                        f"HTTP {response.status_code} downloading PDF from {url}",
                        url=url,
                        status_code=response.status_code,
                    )

                with output_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=65536):
                        size += len(chunk)
                        if size > self.max_size:
                            logger.warning(
                                "PDF exceeds maximum size",
                                url=url,
                                size_bytes=size,
                                max_bytes=self.max_size,
                            )
                            raise FetchError(
                                f"PDF exceeds maximum size (>{self.max_size} bytes)",
                                url=url,
                            )
                        f.write(chunk)
        except FetchError:
            # Clean up partial file on error
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            raise
        except httpx.TimeoutException as exc:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            logger.error("PDF download timed out", url=url, error=str(exc))
            raise FetchError(
                f"PDF download timed out: {exc}",
                url=url,
            ) from exc
        except httpx.HTTPError as exc:
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            logger.error("PDF download failed", url=url, error=str(exc))
            raise FetchError(
                f"PDF download failed: {exc}",
                url=url,
            ) from exc

        logger.info(
            "PDF downloaded successfully",
            url=url,
            path=str(output_path),
            size_bytes=size,
        )

        return PdfMeta(
            url=url,
            local_path=output_path,
            size_bytes=size,
        )

    @staticmethod
    def _derive_filename(url: str) -> str:
        """Derive a filename from a PDF URL.

        Parameters
        ----------
        url : str
            PDF URL.

        Returns
        -------
        str
            Filename derived from the URL path, or a fallback name.

        Examples
        --------
        >>> PdfDownloader._derive_filename("https://example.com/reports/q4-2025.pdf")
        'q4-2025.pdf'
        >>> PdfDownloader._derive_filename("https://example.com/download?id=123")
        'download.pdf'
        """
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")

        if path:
            name = path.split("/")[-1]
            # Sanitize filename to prevent path traversal
            name = _FILENAME_SANITIZE_RE.sub("_", name)
            if name and name not in (".", ".."):
                if not name.lower().endswith(".pdf"):
                    name += ".pdf"
                return name

        return "download.pdf"
