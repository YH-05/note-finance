"""Shared utility functions for scraper base classes.

Provides URL resolution, PDF URL detection, PDF link extraction, and
CSS-based link extraction used by both ``HtmlReportScraper`` and
``SpaReportScraper``.

Functions
---------
resolve_url
    Resolve a potentially relative URL against a base URL.
is_pdf_url
    Check if a URL points to a PDF file.
find_pdf_links
    Extract PDF links from anchor-like elements.
extract_links_by_css
    Extract href links matching a CSS selector from a response.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

PDF_URL_PATTERN = re.compile(r"\.pdf(\?.*)?$", re.IGNORECASE)
"""Regex pattern matching URLs that end with ``.pdf``."""


def resolve_url(relative_url: str, base_url: str) -> str:
    """Resolve a potentially relative URL against a base URL.

    Parameters
    ----------
    relative_url : str
        URL that may be relative.
    base_url : str
        Base URL for resolution.

    Returns
    -------
    str
        Absolute URL.

    Examples
    --------
    >>> resolve_url("/reports/q4.pdf", "https://example.com/page")
    'https://example.com/reports/q4.pdf'
    >>> resolve_url("https://cdn.example.com/q4.pdf", "https://example.com")
    'https://cdn.example.com/q4.pdf'
    """
    parsed = urlparse(relative_url)
    if parsed.scheme:
        return relative_url
    return urljoin(base_url, relative_url)


def is_pdf_url(url: str) -> bool:
    """Check if a URL points to a PDF file.

    Parameters
    ----------
    url : str
        URL to check.

    Returns
    -------
    bool
        ``True`` if the URL ends with ``.pdf`` (case-insensitive).

    Examples
    --------
    >>> is_pdf_url("https://example.com/report.pdf")
    True
    >>> is_pdf_url("https://example.com/report.pdf?token=abc")
    True
    >>> is_pdf_url("https://example.com/report.html")
    False
    """
    parsed = urlparse(url)
    return bool(
        PDF_URL_PATTERN.search(
            parsed.path + ("?" + parsed.query if parsed.query else "")
        )
    )


def find_pdf_links(elements: Any, base_url: str) -> list[str]:
    """Extract PDF links from a collection of anchor elements.

    Parameters
    ----------
    elements : Any
        Iterable of Scrapling elements (or any objects with
        ``attrib`` dict containing ``"href"``).
    base_url : str
        Base URL for resolving relative links.

    Returns
    -------
    list[str]
        List of absolute PDF URLs found.
    """
    pdf_links: list[str] = []
    for el in elements:
        href = el.attrib.get("href", "")
        if not href:
            continue
        absolute = resolve_url(href, base_url)
        if is_pdf_url(absolute):
            pdf_links.append(absolute)
    return pdf_links


def default_parse_listing_item(
    element: Any,
    base_url: str,
    *,
    source_key: str,
    tags: tuple[str, ...] = (),
    pdf_selector: str | None = None,
) -> Any | None:
    """Shared parse_listing_item logic for HTML/SPA scrapers.

    Extracts href + title from an element, resolves the URL, optionally
    detects a PDF link, and returns a ``ReportMetadata``.

    Parameters
    ----------
    element : Any
        A Scrapling element matched by ``article_selector``.
    base_url : str
        Base URL for resolving relative links.
    source_key : str
        Source identifier for the metadata.
    tags : tuple[str, ...]
        Tags to attach to the metadata.
    pdf_selector : str | None
        Optional CSS selector for finding PDF links within the element.

    Returns
    -------
    ReportMetadata | None
        Parsed metadata, or ``None`` if the element should be skipped.
    """
    from datetime import datetime, timezone

    from report_scraper.types import ReportMetadata

    href = element.attrib.get("href", "")
    title = element.text or ""

    if not href or not title:
        return None

    url = resolve_url(href, base_url)

    pdf_url: str | None = None
    if pdf_selector is not None:
        try:
            pdf_elements = element.css(pdf_selector)
            pdf_links = find_pdf_links(pdf_elements, base_url)
            if pdf_links:
                pdf_url = pdf_links[0]
        except Exception:
            pass

    if pdf_url is None and is_pdf_url(url):
        pdf_url = url

    return ReportMetadata(
        url=url,
        title=title.strip(),
        published=datetime.now(timezone.utc),
        source_key=source_key,
        pdf_url=pdf_url,
        tags=tags,
    )


def extract_links_by_css(
    response: Any,
    selector: str,
    base_url: str,
) -> list[str]:
    """Extract all href links matching a CSS selector.

    Parameters
    ----------
    response : Any
        Scrapling response object.
    selector : str
        CSS selector to find anchor elements.
    base_url : str
        Base URL for resolving relative links.

    Returns
    -------
    list[str]
        List of absolute URLs.
    """
    elements = response.css(selector)
    links: list[str] = []
    for el in elements:
        href = el.attrib.get("href", "")
        if href:
            links.append(resolve_url(href, base_url))
    return links
