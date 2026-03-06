"""Content extraction service using trafilatura with lxml fallback.

Extracts article text from HTML using trafilatura as the primary engine.
Falls back to lxml-based extraction if trafilatura fails or returns
insufficient content. Includes paywall detection.

Classes
-------
ContentExtractor
    Service for extracting text content from HTML pages.

Functions
---------
_detect_paywall
    Detect paywall indicators in HTML content.

Examples
--------
>>> extractor = ContentExtractor()
>>> html = "<html><body><article>Full article text...</article></body></html>"
>>> result = extractor.extract_from_html(html, url="https://example.com")
>>> if result is not None:
...     print(result.method)
"""

from __future__ import annotations

import re
from typing import Any

import trafilatura
from lxml import html as lxml_html

from report_scraper._logging import get_logger
from report_scraper.types import ExtractedContent

logger = get_logger(__name__, module="content_extractor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_CONTENT_LENGTH = 100
"""Minimum content length (characters) to consider extraction successful."""

PAYWALL_PATTERNS: list[str] = [
    "paywall",
    "subscriber-only",
    "premium-content",
    "subscription-required",
    "members-only",
    "gated-content",
]
"""CSS class / id patterns indicating a paywall."""

PAYWALL_TEXT_PATTERNS: list[str] = [
    r"subscribe\s+to\s+read",
    r"sign\s+in\s+to\s+continue",
    r"this\s+content\s+is\s+for\s+subscribers",
    r"premium\s+subscribers\s+only",
]
"""Regex patterns in page text indicating a paywall."""

# AIDEV-NOTE: lxml XPath selectors are used as fallback when trafilatura fails.
# Ordered by specificity - more specific selectors are tried first.
ARTICLE_SELECTORS: list[str] = [
    "//article",
    "//main",
    "//*[contains(@class, 'article-body')]",
    "//*[contains(@class, 'article-content')]",
    "//*[contains(@class, 'story-body')]",
    "//*[contains(@class, 'post-content')]",
    "//*[contains(@class, 'entry-content')]",
    "//*[contains(@id, 'article')]",
    "//*[contains(@id, 'content')]",
    "//*[@role='main']",
]
"""XPath selectors for locating article body in HTML."""


# ---------------------------------------------------------------------------
# Paywall detection
# ---------------------------------------------------------------------------


def _detect_paywall(html_content: str) -> bool:
    """Detect paywall indicators in HTML content.

    Checks for paywall-related CSS class/id patterns and text patterns
    in the raw HTML string.

    Parameters
    ----------
    html_content : str
        Raw HTML string to check.

    Returns
    -------
    bool
        ``True`` if paywall indicators are found.

    Examples
    --------
    >>> _detect_paywall("<div class='paywall'>Subscribe</div>")
    True
    >>> _detect_paywall("<div>Free content</div>")
    False
    """
    if not html_content:
        return False

    lower_html = html_content.lower()

    # Check CSS class/id patterns
    for pattern in PAYWALL_PATTERNS:
        if pattern in lower_html:
            logger.debug("Paywall pattern detected", pattern=pattern)
            return True

    # Check text patterns
    for pattern in PAYWALL_TEXT_PATTERNS:
        if re.search(pattern, lower_html):
            logger.debug("Paywall text pattern detected", pattern=pattern)
            return True

    return False


# ---------------------------------------------------------------------------
# lxml fallback extraction
# ---------------------------------------------------------------------------


def _clean_text(text: str) -> str:
    """Clean extracted text by normalizing whitespace.

    Parameters
    ----------
    text : str
        Raw extracted text.

    Returns
    -------
    str
        Cleaned text with normalized whitespace.
    """
    lines = text.splitlines()
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return "\n".join(cleaned_lines)


def _extract_with_lxml(html_content: str) -> str | None:
    """Extract text from HTML using lxml as fallback.

    Tries article-specific XPath selectors first, then falls back
    to extracting from ``<body>``.

    Parameters
    ----------
    html_content : str
        Raw HTML string.

    Returns
    -------
    str | None
        Extracted and cleaned text, or ``None`` if extraction fails.
    """
    if not html_content:
        return None

    try:
        tree = lxml_html.fromstring(html_content)
    except Exception:
        logger.debug("Failed to parse HTML with lxml")
        return None

    # Remove script and style elements
    for element in tree.xpath("//script | //style | //noscript"):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    # Try article-specific selectors
    for selector in ARTICLE_SELECTORS:
        elements = tree.xpath(selector)
        if elements:
            raw_text = elements[0].text_content()
            text = _clean_text(raw_text)
            if text and len(text) >= MIN_CONTENT_LENGTH:
                logger.debug(
                    "Text extracted with lxml selector",
                    selector=selector,
                    length=len(text),
                )
                return text

    # Fallback: extract from <body>
    body_elements = tree.xpath("//body")
    if body_elements:
        raw_text = body_elements[0].text_content()
        text = _clean_text(raw_text)
        if text and len(text) >= MIN_CONTENT_LENGTH:
            logger.debug("Text extracted from body fallback", length=len(text))
            return text

    return None


# ---------------------------------------------------------------------------
# ContentExtractor class
# ---------------------------------------------------------------------------


class ContentExtractor:
    """Content extraction service using trafilatura with lxml fallback.

    Extracts article text from HTML pages. Uses trafilatura as the primary
    extraction engine, which is optimized for news and article extraction.
    Falls back to lxml-based XPath extraction if trafilatura fails.

    Includes paywall detection: if paywall indicators are found in the HTML,
    extraction is skipped and ``None`` is returned.

    Attributes
    ----------
    timeout : int
        HTTP request timeout in seconds (used by callers, not directly).

    Examples
    --------
    >>> extractor = ContentExtractor()
    >>> html = "<html><body><article>Long article text...</article></body></html>"
    >>> result = extractor.extract_from_html(html, url="https://example.com")
    >>> if result is not None:
    ...     print(f"Extracted {result.length} chars via {result.method}")
    """

    def __init__(self, timeout: int = 30) -> None:
        """Initialize ContentExtractor.

        Parameters
        ----------
        timeout : int, default=30
            HTTP request timeout in seconds.
        """
        self.timeout = timeout
        logger.debug("ContentExtractor initialized", timeout=timeout)

    def extract_from_html(
        self,
        html_content: str,
        *,
        url: str,
    ) -> ExtractedContent | None:
        """Extract text content from an HTML string.

        Extraction flow:

        1. Check for empty input.
        2. Detect paywall indicators.
        3. Try trafilatura extraction.
        4. Fall back to lxml extraction.
        5. Validate minimum content length.

        Parameters
        ----------
        html_content : str
            Raw HTML string to extract content from.
        url : str
            URL of the page (for logging purposes).

        Returns
        -------
        ExtractedContent | None
            Extracted content with method and length info, or ``None``
            if extraction fails or a paywall is detected.

        Examples
        --------
        >>> extractor = ContentExtractor()
        >>> result = extractor.extract_from_html(
        ...     "<html><body>Content</body></html>",
        ...     url="https://example.com",
        ... )
        """
        if not html_content:
            logger.debug("Empty HTML content", url=url)
            return None

        # Paywall check
        if _detect_paywall(html_content):
            logger.info("Paywall detected, skipping extraction", url=url)
            return None

        # Try trafilatura first
        text = self._try_trafilatura(html_content, url=url)
        if text and len(text) >= MIN_CONTENT_LENGTH:
            logger.info(
                "Trafilatura extraction successful",
                url=url,
                length=len(text),
            )
            return ExtractedContent(
                text=text,
                method="trafilatura",
                length=len(text),
            )

        # Fall back to lxml
        text = self._try_lxml(html_content, url=url)
        if text and len(text) >= MIN_CONTENT_LENGTH:
            logger.info(
                "lxml fallback extraction successful",
                url=url,
                length=len(text),
            )
            return ExtractedContent(
                text=text,
                method="lxml",
                length=len(text),
            )

        logger.warning(
            "All extraction methods failed or insufficient content",
            url=url,
        )
        return None

    def _try_trafilatura(self, html_content: str, *, url: str) -> str | None:
        """Attempt extraction with trafilatura.

        Parameters
        ----------
        html_content : str
            Raw HTML string.
        url : str
            URL for logging.

        Returns
        -------
        str | None
            Extracted text, or ``None`` if trafilatura fails.
        """
        try:
            result: Any = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                favor_precision=True,
            )
            if result and isinstance(result, str):
                return result
        except Exception as exc:
            logger.warning(
                "Trafilatura extraction error",
                url=url,
                error=str(exc),
            )
        return None

    def _try_lxml(self, html_content: str, *, url: str) -> str | None:
        """Attempt extraction with lxml.

        Parameters
        ----------
        html_content : str
            Raw HTML string.
        url : str
            URL for logging.

        Returns
        -------
        str | None
            Extracted text, or ``None`` if lxml fails.
        """
        try:
            return _extract_with_lxml(html_content)
        except Exception as exc:
            logger.warning(
                "lxml extraction error",
                url=url,
                error=str(exc),
            )
            return None
