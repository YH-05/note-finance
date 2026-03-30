"""Tavily MCP server with API key rotation.

Drop-in replacement for the official ``tavily-mcp`` npm package.
Supports ``TAVILY_API_KEY_1``, ``_2``, ... with automatic rotation
on 429/432 rate-limit errors.

Tools
-----
- tavily_search : Standard web search
- tavily_research : Deep research (advanced depth + answer)
- tavily_extract : URL content extraction
- tavily_crawl : Site crawling
- tavily_map : Sitemap URL extraction

Usage in .mcp.json::

    {
      "tavily": {
        "command": "uv",
        "args": ["run", "--extra", "mcp", "tavily-mcp"],
        "env": {
          "TAVILY_API_KEY_1": "tvly-xxx",
          "TAVILY_API_KEY_2": "tvly-yyy"
        }
      }
    }
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_TAVILY_BASE = "https://api.tavily.com"
_TIMEOUT = 30
_RESEARCH_TIMEOUT = 60
_RATE_LIMIT_CODES = frozenset({429, 432})


# ---------------------------------------------------------------------------
# TavilyKeyPool
# ---------------------------------------------------------------------------
class TavilyKeyPool:
    """Multiple Tavily API keys with round-robin rotation.

    Exhausted keys (432/429) are removed from the pool automatically.

    Parameters
    ----------
    keys : list[str]
        Tavily API keys
    """

    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self._exhausted: set[str] = set()
        self._index = 0

    @classmethod
    def from_env(cls) -> TavilyKeyPool:
        """Build pool from environment variables.

        Reads ``TAVILY_API_KEY_1``, ``_2``, ... (sequential).
        Falls back to ``TAVILY_API_KEY`` (single key).
        """
        keys: list[str] = []
        for i in range(1, 100):
            val = os.environ.get(f"TAVILY_API_KEY_{i}", "")
            if not val:
                break
            keys.append(val)
        if not keys:
            single = os.environ.get("TAVILY_API_KEY", "")
            if single:
                keys.append(single)
        return cls(keys)

    def has_keys(self) -> bool:
        """Return True if at least one key is available."""
        return bool(self._available())

    def get_key(self) -> str | None:
        """Return next available key (round-robin). None if exhausted."""
        available = self._available()
        if not available:
            return None
        self._index = self._index % len(available)
        key = available[self._index]
        self._index = (self._index + 1) % len(available)
        return key

    def mark_exhausted(self, key: str) -> None:
        """Mark a key as rate-limited."""
        self._exhausted.add(key)
        remaining = len(self._available())
        logger.warning(
            "Tavily key exhausted: ...%s  remaining=%d",
            key[-8:],
            remaining,
        )

    def status(self) -> dict[str, int]:
        """Return pool status counts."""
        return {
            "total": len(self._keys),
            "available": len(self._available()),
            "exhausted": len(self._exhausted),
        }

    def _available(self) -> list[str]:
        return [k for k in self._keys if k not in self._exhausted]


# ---------------------------------------------------------------------------
# Module-level pool (lazy init)
# ---------------------------------------------------------------------------
_pool: TavilyKeyPool | None = None


def _get_pool() -> TavilyKeyPool:
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = TavilyKeyPool.from_env()
        s = _pool.status()
        logger.info("TavilyKeyPool initialized: %d keys", s["total"])
    return _pool


# ---------------------------------------------------------------------------
# HTTP helper with key rotation
# ---------------------------------------------------------------------------
def _post_with_rotation(
    endpoint: str,
    payload: dict[str, Any],
    *,
    timeout: int = _TIMEOUT,
) -> dict[str, Any]:
    """POST to Tavily API, rotating keys on rate-limit errors.

    Parameters
    ----------
    endpoint : str
        API path (e.g. ``"search"``).
    payload : dict
        Request body **without** ``api_key`` (injected automatically).
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        Tavily API response, or ``{"error": "..."}`` on failure.
    """
    pool = _get_pool()
    if not pool.has_keys():
        return {
            "error": "No Tavily API keys configured. Set TAVILY_API_KEY_1 or TAVILY_API_KEY."
        }

    last_error: str = "unknown"

    while pool.has_keys():
        key = pool.get_key()
        if key is None:
            break

        body = {**payload, "api_key": key}

        try:
            resp = httpx.post(
                f"{_TAVILY_BASE}/{endpoint}",
                json=body,
                timeout=timeout,
            )
        except httpx.TimeoutException:
            last_error = f"Timeout ({timeout}s)"
            logger.warning("Tavily %s timed out", endpoint)
            break
        except httpx.HTTPError as exc:
            last_error = str(exc)
            logger.error("Tavily %s HTTP error: %s", endpoint, exc)
            break

        if resp.status_code in _RATE_LIMIT_CODES:
            pool.mark_exhausted(key)
            last_error = f"Rate limited (HTTP {resp.status_code})"
            continue

        if resp.status_code >= 400:
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.error("Tavily %s error: %s", endpoint, last_error)
            break

        return resp.json()

    return {"error": f"Tavily API request failed. {last_error}"}


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    name="Tavily Search",
    instructions=(
        "Web search powered by Tavily with automatic API key rotation. "
        "Provides search, research, extract, crawl, and map tools."
    ),
)


@mcp.tool()
def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 3,
    include_answer: bool = False,
    include_raw_content: bool = False,
    include_images: bool = False,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Search the web using Tavily.

    Parameters
    ----------
    query : str
        Search query string
    max_results : int
        Maximum number of results (default: 5, max: 20)
    search_depth : str
        "basic" for fast results, "advanced" for deeper search
    topic : str
        Search topic: "general", "news", or "finance"
    days : int
        Recency filter in days (only for topic="news")
    include_answer : bool
        Include an AI-generated answer summary
    include_raw_content : bool
        Include full raw content of each result
    include_images : bool
        Include related images
    include_domains : list[str] | None
        Only include results from these domains
    exclude_domains : list[str] | None
        Exclude results from these domains

    Returns
    -------
    dict
        Tavily search response with query, results, and optional answer
    """
    payload: dict[str, Any] = {
        "query": query,
        "max_results": min(max_results, 20),
        "search_depth": search_depth,
        "topic": topic,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
        "include_images": include_images,
    }
    if topic == "news":
        payload["days"] = days
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    return _post_with_rotation("search", payload)


@mcp.tool()
def tavily_research(
    query: str,
    max_results: int = 10,
    topic: str = "general",
    days: int = 7,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Deep research on a topic using Tavily advanced search.

    Uses advanced search depth with AI-generated answer for comprehensive research.
    Higher timeout and more results than standard search.

    Parameters
    ----------
    query : str
        Research query string
    max_results : int
        Maximum number of results (default: 10, max: 20)
    topic : str
        Search topic: "general", "news", or "finance"
    days : int
        Recency filter in days (only for topic="news")
    include_domains : list[str] | None
        Only include results from these domains
    exclude_domains : list[str] | None
        Exclude results from these domains

    Returns
    -------
    dict
        Tavily search response with comprehensive results and AI answer
    """
    payload: dict[str, Any] = {
        "query": query,
        "max_results": min(max_results, 20),
        "search_depth": "advanced",
        "topic": topic,
        "include_answer": True,
        "include_raw_content": False,
    }
    if topic == "news":
        payload["days"] = days
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains

    return _post_with_rotation("search", payload, timeout=_RESEARCH_TIMEOUT)


@mcp.tool()
def tavily_extract(
    urls: list[str],
) -> dict[str, Any]:
    """Extract content from one or more URLs.

    Parameters
    ----------
    urls : list[str]
        List of URLs to extract content from

    Returns
    -------
    dict
        Extraction results with raw_content for each URL,
        plus failed_results for URLs that could not be extracted
    """
    return _post_with_rotation("extract", {"urls": urls})


@mcp.tool()
def tavily_crawl(
    url: str,
    max_depth: int = 1,
    limit: int = 50,
) -> dict[str, Any]:
    """Crawl a website starting from a URL.

    Parameters
    ----------
    url : str
        Starting URL to crawl
    max_depth : int
        Maximum crawl depth (default: 1)
    limit : int
        Maximum number of pages to crawl (default: 50)

    Returns
    -------
    dict
        Crawled pages with their content
    """
    return _post_with_rotation(
        "crawl",
        {"url": url, "max_depth": max_depth, "limit": limit},
    )


@mcp.tool()
def tavily_map(
    url: str,
) -> dict[str, Any]:
    """Get a sitemap of URLs from a website.

    Parameters
    ----------
    url : str
        Website URL to map

    Returns
    -------
    dict
        List of discovered URLs from the website
    """
    return _post_with_rotation("map", {"url": url})


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def serve() -> None:
    """Run the MCP server with stdio transport."""
    pool = _get_pool()
    s = pool.status()
    logger.info("Tavily MCP starting: %d keys available", s["available"])
    mcp.run(transport="stdio")


def main() -> None:
    """Entry point for ``tavily-mcp`` command."""
    logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
    serve()


if __name__ == "__main__":
    main()
