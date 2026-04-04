"""HTTP download utilities for the fund_db package.

Provides shared download logic and URL validation used by all
downloader modules (NISA, JPX, toushin_stats).

Functions
---------
download_bytes
    Download bytes from a URL with security checks.
validate_url_host
    Validate that a URL's host is in the allowed list.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from fund_db._logging import get_logger
from fund_db.exceptions import DownloadError

logger = get_logger(__name__, module="http")

ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "www.toushin.or.jp",
        "toushin.or.jp",
        "www.jpx.co.jp",
        "jpx.co.jp",
    }
)

MAX_DOWNLOAD_BYTES: int = 100 * 1024 * 1024  # 100 MB


def download_bytes(url: str, *, timeout: float = 30.0) -> bytes:
    """Download bytes from a URL with security checks.

    Parameters
    ----------
    url : str
        URL to download from.
    timeout : float
        HTTP request timeout in seconds.

    Returns
    -------
    bytes
        Downloaded content.

    Raises
    ------
    DownloadError
        If the HTTP request fails, returns non-2xx, or exceeds size limit.
    """
    logger.info("Downloading", url=url)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise DownloadError(
            f"HTTP {exc.response.status_code} downloading {url}",
            url=url,
            status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise DownloadError(
            f"Failed to download {url}: {exc}",
            url=url,
        ) from exc

    content = response.content
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise DownloadError(
            f"Download exceeds size limit ({len(content)} > {MAX_DOWNLOAD_BYTES})",
            url=url,
        )
    return content


def validate_url_host(url: str, allowed_hosts: frozenset[str] | None = None) -> None:
    """Validate that a URL's host is in the allowed list.

    Parameters
    ----------
    url : str
        URL to validate.
    allowed_hosts : frozenset[str] | None
        Set of allowed hostnames. Uses ``ALLOWED_HOSTS`` if None.

    Raises
    ------
    DownloadError
        If the host is not in the allowed list.
    """
    hosts = allowed_hosts if allowed_hosts is not None else ALLOWED_HOSTS
    parsed = urlparse(url)
    if parsed.netloc not in hosts:
        raise DownloadError(
            f"URL host '{parsed.netloc}' is not in the allowed list",
            url=url,
        )
