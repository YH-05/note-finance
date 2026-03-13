"""robots.txt checker with ai-directive detection.

Provides RobotsChecker for checking robots.txt allow/deny rules,
crawl-delay extraction, and detection of non-standard AI directives
such as ai-train, GPTBot, and CCBot.

Examples
--------
>>> async def example():
...     checker = RobotsChecker()
...     result = await checker.check("https://example.com/article")
...     print(result.allowed, result.crawl_delay, result.ai_directives)
"""

from __future__ import annotations

import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

AI_DIRECTIVE_KEYS = frozenset({"ai-train", "gptbot", "ccbot"})
DEFAULT_USER_AGENT = "rss-feed-collector/0.1.0"
DEFAULT_TIMEOUT = 10


def _get_logger() -> Any:
    """Get logger with fallback to standard logging.

    Returns
    -------
    Any
        Logger instance (structlog or standard logging)
    """
    try:
        from rss._logging import get_logger

        return get_logger(__name__, module="robots_checker")
    except ImportError:
        import logging

        return logging.getLogger(__name__)


logger: Any = _get_logger()

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RobotsCheckResult:
    """Result of a robots.txt check for a given URL.

    Attributes
    ----------
    url : str
        The URL that was checked.
    allowed : bool
        Whether the user-agent is allowed to fetch the URL.
        Defaults to True (permissive fallback on fetch error).
    crawl_delay : float | None
        Crawl-delay in seconds from robots.txt, or None if not specified.
    ai_directives : dict[str, str]
        Non-standard AI directives found in robots.txt.
        Keys are directive names (e.g. "ai-train", "GPTBot", "CCBot"),
        values are their settings (e.g. "no", "yes").
    error : str | None
        Error message if robots.txt could not be fetched, else None.
    """

    url: str
    allowed: bool = True
    crawl_delay: float | None = None
    ai_directives: dict[str, str] = field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------


class RobotsChecker:
    """Async robots.txt checker with domain-level caching.

    Checks robots.txt allow/deny rules for a given URL, extracts
    Crawl-delay, and detects non-standard AI directives (ai-train,
    GPTBot, CCBot). Results are cached per domain to avoid redundant
    network requests.

    Attributes
    ----------
    user_agent : str
        User-Agent string to check against robots.txt rules.

    Examples
    --------
    >>> async def example():
    ...     checker = RobotsChecker()
    ...     result = await checker.check("https://example.com/article")
    ...     if not result.allowed:
    ...         print("Blocked by robots.txt")
    """

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT) -> None:
        """Initialize RobotsChecker.

        Parameters
        ----------
        user_agent : str, default="rss-feed-collector/0.1.0"
            User-Agent string to check against robots.txt rules.
        """
        self.user_agent = user_agent
        # Domain -> (RobotFileParser, raw_text) cache
        self._cache: dict[str, tuple[urllib.robotparser.RobotFileParser, str]] = {}
        logger.debug("Initializing RobotsChecker", user_agent=user_agent)

    async def check(self, url: str) -> RobotsCheckResult:
        """Check robots.txt rules for the given URL.

        Parameters
        ----------
        url : str
            URL to check against robots.txt.

        Returns
        -------
        RobotsCheckResult
            Check result including allowed status, crawl_delay, and
            ai_directives. On fetch failure, returns allowed=True with
            error message set.
        """
        logger.debug("Checking robots.txt", url=url, user_agent=self.user_agent)

        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        try:
            parser, raw_text = await self._get_or_fetch(domain, robots_url)
        except Exception as exc:
            error_msg = str(exc)
            logger.warning(
                "Failed to fetch robots.txt, defaulting to allow",
                domain=domain,
                error=error_msg,
            )
            return RobotsCheckResult(url=url, allowed=True, error=error_msg)

        allowed = parser.can_fetch(self.user_agent, url)
        crawl_delay_val = parser.crawl_delay(self.user_agent)
        crawl_delay: float | None = (
            float(crawl_delay_val) if crawl_delay_val is not None else None
        )
        ai_directives = self._extract_ai_directives(raw_text)

        logger.debug(
            "robots.txt check completed",
            url=url,
            allowed=allowed,
            crawl_delay=crawl_delay,
            ai_directives=ai_directives,
        )

        return RobotsCheckResult(
            url=url,
            allowed=allowed,
            crawl_delay=crawl_delay,
            ai_directives=ai_directives,
        )

    def get_crawl_delay(self, domain: str) -> float | None:
        """Return the cached crawl-delay for a domain.

        Returns None if the domain has not been fetched yet or if
        no Crawl-delay directive was present in robots.txt.

        Parameters
        ----------
        domain : str
            Domain name (e.g. "example.com").

        Returns
        -------
        float | None
            Crawl-delay in seconds, or None.
        """
        cached = self._cache.get(domain)
        if cached is None:
            return None
        parser, _ = cached
        delay = parser.crawl_delay(self.user_agent)
        return float(delay) if delay is not None else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_or_fetch(
        self, domain: str, robots_url: str
    ) -> tuple[urllib.robotparser.RobotFileParser, str]:
        """Return cached parser or fetch and cache a new one.

        Parameters
        ----------
        domain : str
            Domain key used for caching.
        robots_url : str
            Full URL to robots.txt (e.g. https://example.com/robots.txt).

        Returns
        -------
        tuple[RobotFileParser, str]
            Parsed robots.txt and raw text content.
        """
        if domain in self._cache:
            logger.debug("robots.txt cache hit", domain=domain)
            return self._cache[domain]

        logger.debug("Fetching robots.txt", robots_url=robots_url)
        raw_text = await self._fetch_robots_txt(robots_url)
        parser = self._parse_robots_txt(raw_text)
        self._cache[domain] = (parser, raw_text)
        return parser, raw_text

    async def _fetch_robots_txt(self, robots_url: str) -> str:
        """Fetch robots.txt content via HTTP.

        Parameters
        ----------
        robots_url : str
            URL of robots.txt file.

        Returns
        -------
        str
            Raw robots.txt content. Returns empty string on 404.

        Raises
        ------
        httpx.HTTPError
            On network or HTTP errors (non-404).
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(DEFAULT_TIMEOUT),
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        ) as client:
            response = await client.get(robots_url)
            if response.status_code == 404:
                logger.debug("robots.txt not found (404), treating as allow-all")
                return ""
            response.raise_for_status()
            return response.text

    def _parse_robots_txt(self, raw_text: str) -> urllib.robotparser.RobotFileParser:
        """Parse raw robots.txt text into a RobotFileParser.

        Parameters
        ----------
        raw_text : str
            Raw content of robots.txt.

        Returns
        -------
        urllib.robotparser.RobotFileParser
            Parsed robots.txt object.
        """
        parser = urllib.robotparser.RobotFileParser()
        lines = raw_text.splitlines()
        parser.parse(lines)
        return parser

    def _extract_ai_directives(self, raw_text: str) -> dict[str, str]:
        """Extract non-standard AI directives from raw robots.txt text.

        Detects directives such as:
        - ``ai-train: no``
        - ``GPTBot: no``
        - ``CCBot: no``

        These are non-standard directives not handled by RobotFileParser,
        so they are parsed manually from the raw text.

        Parameters
        ----------
        raw_text : str
            Raw content of robots.txt.

        Returns
        -------
        dict[str, str]
            Dictionary mapping directive name to value (e.g. {"ai-train": "no"}).
        """
        directives: dict[str, str] = {}
        for raw_line in raw_text.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key_stripped = key.strip()
            value_stripped = value.strip()
            if key_stripped.lower() in AI_DIRECTIVE_KEYS:
                directives[key_stripped] = value_stripped
        return directives
