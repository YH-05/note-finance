"""Common HTML fetch and parse utilities for news_scraper package.

This module provides shared utilities used by all HTML scrapers:
HTTP retrieval via httpx.Client, lxml parsing, URL resolution,
and rate-limit sleep helpers.

Constants
---------
JP_DEFAULT_HEADERS : dict[str, str]
    Default HTTP request headers tuned for Japanese news sites.

Functions
---------
fetch_html
    Fetch HTML content from a URL using an injected httpx.Client.
parse_html
    Parse an HTML string into an lxml HtmlElement.
resolve_relative_url
    Resolve a relative URL against a base URL (urljoin wrapper).
rate_limit_sleep
    Sleep for the configured request delay to respect rate limits.

Examples
--------
>>> import httpx
>>> from news_scraper._html_utils import parse_html, resolve_relative_url
>>> element = parse_html("<html><body><h1>Test</h1></body></html>")
>>> element.xpath("//h1")[0].text_content()
'Test'
>>> resolve_relative_url("/news/1", "https://example.com")
'https://example.com/news/1'
"""

from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx
import lxml.html

from news_scraper._logging import get_logger
from news_scraper.types import ScraperConfig, get_delay

logger = get_logger(__name__, module="html_utils")

# Default HTTP request headers for Japanese news sites
JP_DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,ja-JP;q=0.9,en;q=0.8",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def fetch_html(
    url: str,
    client: httpx.Client,
    headers: dict[str, str] | None = None,
) -> str:
    """Fetch HTML content from a URL using the provided httpx.Client.

    The caller is responsible for creating and managing the client lifetime,
    which allows reuse inside ThreadPoolExecutor workers.

    Parameters
    ----------
    url : str
        URL to fetch.
    client : httpx.Client
        Injected HTTP client to use for the request.
    headers : dict[str, str] | None
        Optional request headers. Defaults to ``JP_DEFAULT_HEADERS`` when None.

    Returns
    -------
    str
        HTML content as a string.

    Raises
    ------
    httpx.HTTPStatusError
        Re-raised when the server returns a 4xx or 5xx response.
    httpx.ConnectError
        Re-raised when the connection cannot be established.

    Examples
    --------
    >>> # Requires a live httpx.Client — see unit tests for mock examples
    """
    effective_headers = headers if headers is not None else JP_DEFAULT_HEADERS
    logger.debug("Fetching HTML", url=url)
    try:
        response = client.get(url, headers=effective_headers)
        response.raise_for_status()
        logger.info("HTML fetched", url=url, status_code=response.status_code)
        return response.text
    except httpx.HTTPStatusError as exc:
        logger.error(
            "HTTP error fetching HTML",
            url=url,
            status_code=exc.response.status_code,
        )
        raise
    except Exception as exc:
        logger.error("Error fetching HTML", url=url, error=str(exc))
        raise


def parse_html(html_content: str) -> lxml.html.HtmlElement:
    """Parse an HTML string into an lxml HtmlElement.

    Parameters
    ----------
    html_content : str
        Raw HTML string to parse.

    Returns
    -------
    lxml.html.HtmlElement
        Root element of the parsed HTML document.

    Examples
    --------
    >>> element = parse_html("<html><body><h1>Hello</h1></body></html>")
    >>> element.xpath("//h1")[0].text_content()
    'Hello'
    """
    logger.debug("Parsing HTML", content_length=len(html_content))
    element = lxml.html.fromstring(html_content)
    logger.debug("HTML parsed", tag=element.tag)
    return element


def resolve_relative_url(relative: str, base: str) -> str:
    """Resolve a relative URL against a base URL.

    A thin wrapper around :func:`urllib.parse.urljoin` with logging.

    Parameters
    ----------
    relative : str
        Relative (or absolute) URL to resolve.
    base : str
        Base URL to resolve against.

    Returns
    -------
    str
        Absolute URL.

    Examples
    --------
    >>> resolve_relative_url("/news/marketnews/?&b=n123", "https://kabutan.jp")
    'https://kabutan.jp/news/marketnews/?&b=n123'
    >>> resolve_relative_url("https://other.com/page", "https://example.com")
    'https://other.com/page'
    """
    resolved = urljoin(base, relative)
    logger.debug("Resolved URL", relative=relative, base=base, resolved=resolved)
    return resolved


def rate_limit_sleep(config: ScraperConfig | None) -> None:
    """Sleep for the configured request delay to respect rate limits.

    Parameters
    ----------
    config : ScraperConfig | None
        Scraper configuration. When None, the default delay (1.0 s) is used.

    Examples
    --------
    >>> from unittest.mock import patch
    >>> config = ScraperConfig(request_delay=0.0)
    >>> with patch("time.sleep") as mock_sleep:
    ...     rate_limit_sleep(config)
    ...     mock_sleep.assert_called_once_with(0.0)
    """
    delay = get_delay(config)
    logger.debug("Rate limit sleep", delay_seconds=delay)
    time.sleep(delay)
