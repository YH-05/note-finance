"""Sitemap XML parser for backfill URL collection.

Parses sitemap XML files (both single urlset and sitemapindex formats)
to extract article URLs. Supports multiple CMS/SEO platform formats
including Yoast, Rank Math, WP native, Ghost, and custom sitemaps.

Examples
--------
>>> async def example():
...     parser = SitemapParser()
...     entries = await parser.parse("https://example.com/sitemap.xml")
...     posts = parser.filter_post_urls(entries)
...     print(len(posts))
"""

from __future__ import annotations

import contextlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = "rss-feed-collector/0.1.0"
DEFAULT_TIMEOUT = 10

# Sitemap XML namespaces
_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Path segments to exclude when filtering post URLs
_EXCLUDED_PATH_SEGMENTS = frozenset(
    {"/category/", "/tag/", "/author/", "/attachment/", "/page/"}
)

# Security limits
_MAX_XML_BYTES = 10 * 1024 * 1024  # 10 MB: guards against XML bomb / oversized sitemaps
_MAX_SITEMAP_DEPTH = 3  # Guards against circular references in sitemap indexes


def _get_logger() -> Any:
    """Get logger with fallback to standard logging.

    Returns
    -------
    Any
        Logger instance (structlog or standard logging)
    """
    try:
        from rss._logging import get_logger

        return get_logger(__name__, module="sitemap_parser")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SitemapEntry:
    """A single URL entry from a sitemap.

    Attributes
    ----------
    url : str
        The canonical URL of the resource.
    lastmod : str | None
        Last modification date/time string as found in the sitemap,
        or None if not present.
    changefreq : str | None
        Change frequency hint (e.g. "weekly", "monthly"), or None.
    priority : float | None
        Priority hint in range 0.0–1.0, or None.
    """

    url: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class SitemapParser:
    """Async sitemap XML parser supporting index and single-urlset formats.

    Parses sitemap files from various CMS/SEO platforms (Yoast, Rank Math,
    WP native, Ghost, custom) by relying solely on the standard
    ``http://www.sitemaps.org/schemas/sitemap/0.9`` namespace, making it
    platform-agnostic.

    Parameters
    ----------
    http_client : Any | None, optional
        Custom HTTP client.  If None, an internal httpx-based client is
        used.  The client must expose an async ``fetch(url) -> HTTPResponse``
        interface.

    Examples
    --------
    >>> async def example():
    ...     parser = SitemapParser()
    ...     entries = await parser.parse("https://example.com/sitemap.xml")
    ...     posts = parser.filter_post_urls(entries)
    """

    def __init__(self, http_client: Any | None = None) -> None:
        """Initialize SitemapParser.

        Parameters
        ----------
        http_client : Any | None, optional
            Custom HTTP client.  Defaults to None (uses internal httpx client).
        """
        self._http_client = http_client
        logger.debug(
            "Initializing SitemapParser", has_custom_client=http_client is not None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def parse(
        self,
        sitemap_url: str,
        _depth: int = 0,
        _visited: set[str] | None = None,
    ) -> list[SitemapEntry]:
        """Parse a sitemap URL and return all SitemapEntry objects.

        Automatically detects whether the URL points to a sitemap index
        (``<sitemapindex>``) or a single URL set (``<urlset>``) and handles
        each case appropriately.  On fetch or parse errors an empty list is
        returned (no exception propagates).

        Parameters
        ----------
        sitemap_url : str
            URL of the sitemap or sitemap index XML file.
        _depth : int
            Current recursion depth (internal, guards against circular refs).
        _visited : set[str] | None
            Set of already-visited URLs (internal, guards against cycles).

        Returns
        -------
        list[SitemapEntry]
            All URL entries found.  Empty on error.
        """
        # Guard: circular reference / depth limit (INFRA-001 / SEC-004)
        if _visited is None:
            _visited = set()
        if sitemap_url in _visited or _depth > _MAX_SITEMAP_DEPTH:
            logger.warning(
                "sitemap_depth_or_cycle_limit",
                url=sitemap_url,
                depth=_depth,
            )
            return []
        _visited.add(sitemap_url)

        logger.debug("Parsing sitemap", url=sitemap_url, depth=_depth)

        try:
            xml_text = await self._fetch_xml(sitemap_url)
        except Exception as exc:
            logger.warning(
                "Failed to fetch sitemap, returning empty list",
                url=sitemap_url,
                error=str(exc),
            )
            return []

        # Guard: oversized XML (SEC-002 — XML bomb / oversized sitemap)
        if len(xml_text.encode()) > _MAX_XML_BYTES:
            logger.warning(
                "sitemap_xml_too_large",
                url=sitemap_url,
                size_bytes=len(xml_text.encode()),
                limit_bytes=_MAX_XML_BYTES,
            )
            return []

        try:
            root = ET.fromstring(xml_text)  # nosec B314 — Python ET is safe against XXE by default
        except ET.ParseError as exc:
            logger.warning(
                "Failed to parse sitemap XML, returning empty list",
                url=sitemap_url,
                error=str(exc),
            )
            return []

        # Strip namespace for tag comparison
        tag_local = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag_local == "sitemapindex":
            return await self._parse_sitemap_index(
                root, sitemap_url, _depth=_depth, _visited=_visited
            )

        # urlset or unknown → treat as urlset
        return self._parse_urlset(root)

    async def parse_index(self, index_url: str) -> list[str]:
        """Parse a sitemap index and return child sitemap URLs.

        Parameters
        ----------
        index_url : str
            URL of the sitemap index XML file.

        Returns
        -------
        list[str]
            List of child sitemap URLs found in the index.

        Raises
        ------
        Exception
            Re-raises fetch/parse errors for caller to handle.
        """
        logger.debug("Parsing sitemap index", url=index_url)

        xml_text = await self._fetch_xml(index_url)
        root = ET.fromstring(xml_text)  # nosec B314 — Python ET is safe against XXE by default

        ns = {"sm": _NS}
        urls: list[str] = []

        for sitemap_el in root.findall("sm:sitemap", ns):
            loc_el = sitemap_el.find("sm:loc", ns)
            if loc_el is not None and loc_el.text:
                urls.append(loc_el.text.strip())

        logger.debug("Parsed sitemap index", url=index_url, child_count=len(urls))
        return urls

    def filter_post_urls(self, entries: list[SitemapEntry]) -> list[SitemapEntry]:
        """Filter out non-post URLs (category, tag, author, attachment, page).

        Parameters
        ----------
        entries : list[SitemapEntry]
            Sitemap entries to filter.

        Returns
        -------
        list[SitemapEntry]
            Only entries whose URL does not contain any excluded path segment.
        """
        filtered = [
            e
            for e in entries
            if not any(seg in e.url for seg in _EXCLUDED_PATH_SEGMENTS)
        ]

        logger.debug(
            "Filtered post URLs",
            total=len(entries),
            kept=len(filtered),
            removed=len(entries) - len(filtered),
        )
        return filtered

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_xml(self, url: str) -> str:
        """Fetch XML content from URL.

        Parameters
        ----------
        url : str
            URL to fetch.

        Returns
        -------
        str
            Raw XML text.

        Raises
        ------
        Exception
            On network or HTTP errors.
        """
        if self._http_client is not None:
            response = await self._http_client.fetch(url)
            return response.content if hasattr(response, "content") else str(response)

        logger.debug("Fetching sitemap via httpx", url=url)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            headers={"User-Agent": DEFAULT_USER_AGENT},
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _is_safe_sitemap_url(self, child_url: str, parent_url: str) -> bool:
        """Validate that a child sitemap URL is safe to fetch (SSRF guard).

        Only http/https schemes are allowed, and the child URL host must match
        the parent URL host to prevent redirect-based SSRF.

        Parameters
        ----------
        child_url : str
            The child sitemap URL extracted from the index XML.
        parent_url : str
            The URL of the parent sitemap index (trusted origin).

        Returns
        -------
        bool
            True if safe to fetch, False otherwise.
        """
        import urllib.parse

        parsed_child = urllib.parse.urlparse(child_url)
        parsed_parent = urllib.parse.urlparse(parent_url)

        if parsed_child.scheme not in ("http", "https"):
            logger.warning(
                "sitemap_child_url_invalid_scheme",
                url=child_url,
                scheme=parsed_child.scheme,
            )
            return False

        if parsed_child.netloc != parsed_parent.netloc:
            logger.warning(
                "sitemap_child_url_domain_mismatch",
                child_url=child_url,
                child_domain=parsed_child.netloc,
                parent_domain=parsed_parent.netloc,
            )
            return False

        return True

    async def _parse_sitemap_index(
        self,
        root: ET.Element,
        source_url: str,
        _depth: int = 0,
        _visited: set[str] | None = None,
    ) -> list[SitemapEntry]:
        """Expand a sitemapindex element by fetching all child sitemaps.

        Parameters
        ----------
        root : ET.Element
            Root element of the sitemap index document.
        source_url : str
            Original URL (used for SSRF validation and logging).
        _depth : int
            Current recursion depth.
        _visited : set[str] | None
            Set of already-visited URLs.

        Returns
        -------
        list[SitemapEntry]
            All entries collected from child sitemaps.
        """
        import asyncio

        ns = {"sm": _NS}
        child_urls: list[str] = []

        for sitemap_el in root.findall("sm:sitemap", ns):
            loc_el = sitemap_el.find("sm:loc", ns)
            if loc_el is not None and loc_el.text:
                candidate = loc_el.text.strip()
                # SSRF guard: only fetch child URLs from the same domain (INFRA-001)
                if self._is_safe_sitemap_url(candidate, source_url):
                    child_urls.append(candidate)

        logger.debug(
            "Expanding sitemap index",
            source=source_url,
            child_count=len(child_urls),
        )

        # Parallel fetch for performance, pass depth+1 and visited set
        results = await asyncio.gather(
            *[
                self.parse(child_url, _depth=_depth + 1, _visited=_visited)
                for child_url in child_urls
            ],
            return_exceptions=True,
        )
        all_entries: list[SitemapEntry] = []
        for r in results:
            if isinstance(r, list):
                all_entries.extend(r)
            else:
                logger.warning(
                    "sitemap_child_fetch_error",
                    error=str(r),
                )
        return all_entries

    def _parse_urlset(self, root: ET.Element) -> list[SitemapEntry]:
        """Parse a urlset element into SitemapEntry objects.

        Parameters
        ----------
        root : ET.Element
            Root element of the urlset document.

        Returns
        -------
        list[SitemapEntry]
            Parsed entries.
        """
        ns = {"sm": _NS}
        entries: list[SitemapEntry] = []

        for url_el in root.findall("sm:url", ns):
            loc_el = url_el.find("sm:loc", ns)
            if loc_el is None or not loc_el.text:
                continue

            url = loc_el.text.strip()

            lastmod_el = url_el.find("sm:lastmod", ns)
            lastmod = (
                lastmod_el.text.strip()
                if lastmod_el is not None and lastmod_el.text
                else None
            )

            changefreq_el = url_el.find("sm:changefreq", ns)
            changefreq = (
                changefreq_el.text.strip()
                if changefreq_el is not None and changefreq_el.text
                else None
            )

            priority_el = url_el.find("sm:priority", ns)
            priority: float | None = None
            if priority_el is not None and priority_el.text:
                with contextlib.suppress(ValueError):
                    priority = float(priority_el.text.strip())

            entries.append(
                SitemapEntry(
                    url=url,
                    lastmod=lastmod,
                    changefreq=changefreq,
                    priority=priority,
                )
            )

        logger.debug("Parsed urlset", entry_count=len(entries))
        return entries
