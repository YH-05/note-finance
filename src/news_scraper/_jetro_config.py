"""JETRO-specific constants, CSS selectors, and content metadata.

This module centralises all JETRO (Japan External Trade Organization)
site-specific configuration so that page-structure changes only require
edits in a single place.

Constants
---------
JETRO_BASE_URL
    Root URL of the JETRO website.
JETRO_RSS_BIZNEWS
    URL of the JETRO Business Brief (ビジネス短信) RSS 2.0 feed.
JETRO_CATEGORY_URLS
    Mapping of category group -> sub-category key -> full URL.
ARTICLE_SELECTORS
    CSS selectors for article-page elements, with fallback lists.
SECTION_SELECTORS
    CSS selectors for page section containers, with fallback lists.
CONTENT_TYPES
    Known JETRO content type strings.

Classes
-------
JetroContentMeta
    Immutable metadata for a single JETRO content item.

Examples
--------
>>> from news_scraper._jetro_config import JETRO_BASE_URL, JetroContentMeta
>>> JETRO_BASE_URL
'https://www.jetro.go.jp'
>>> meta = JetroContentMeta(
...     title="Test",
...     url="https://www.jetro.go.jp/biznews/2026/03/test.html",
...     category="world",
...     subcategory="asia",
... )
>>> meta.title
'Test'
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

JETRO_BASE_URL: str = "https://www.jetro.go.jp"
"""Root URL for the JETRO website (no trailing slash)."""

JETRO_RSS_BIZNEWS: str = "https://www.jetro.go.jp/rss/biznews.xml"
"""JETRO Business Brief (ビジネス短信) RSS 2.0 feed URL."""

# ---------------------------------------------------------------------------
# Category URL mappings
# ---------------------------------------------------------------------------

JETRO_CATEGORY_URLS: dict[str, dict[str, str]] = {
    "world": {
        "asia": "https://www.jetro.go.jp/world/asia/",
        "oceania": "https://www.jetro.go.jp/world/oceania/",
        "n_america": "https://www.jetro.go.jp/world/n_america/",
        "cs_america": "https://www.jetro.go.jp/world/cs_america/",
        "europe": "https://www.jetro.go.jp/world/europe/",
        "russia_cis": "https://www.jetro.go.jp/world/russia_cis/",
        "middle_east": "https://www.jetro.go.jp/world/middle_east/",
        "africa": "https://www.jetro.go.jp/world/africa/",
    },
    "theme": {
        "export": "https://www.jetro.go.jp/themetop/export/",
        "wto_fta": "https://www.jetro.go.jp/themetop/wto-fta/",
        "crossborder_ec": "https://www.jetro.go.jp/themetop/crossborder_ec/",
        "import": "https://www.jetro.go.jp/themetop/import/",
        "fdi": "https://www.jetro.go.jp/themetop/fdi/",
        "ip": "https://www.jetro.go.jp/themetop/ip/",
        "innovation": "https://www.jetro.go.jp/themetop/innovation/",
        "standards": "https://www.jetro.go.jp/themetop/standards/",
    },
    "industry": {
        "foods": "https://www.jetro.go.jp/industrytop/foods/",
        "machinery": "https://www.jetro.go.jp/industrytop/machinery/",
        "fashion": "https://www.jetro.go.jp/industrytop/fashion/",
        "life_science": "https://www.jetro.go.jp/industrytop/life_science/",
        "energy": "https://www.jetro.go.jp/industrytop/energy/",
        "design": "https://www.jetro.go.jp/industrytop/design/",
        "contents": "https://www.jetro.go.jp/industrytop/contents/",
        "service": "https://www.jetro.go.jp/industrytop/service/",
        "infrastructure": "https://www.jetro.go.jp/industrytop/infrastructure/",
    },
}
"""Category group -> sub-category key -> full URL.

Groups
------
world
    Geographic regions (Asia, Europe, etc.).
theme
    Purpose-based categories (export, FDI, IP, etc.).
industry
    Industry verticals (foods, machinery, etc.).
"""

# ---------------------------------------------------------------------------
# CSS selectors (fallback lists)
# ---------------------------------------------------------------------------

ARTICLE_SELECTORS: dict[str, list[str]] = {
    "title": [
        "h1",
        ".elem_heading_lv1",
        "#pbBlock h1",
    ],
    "date": [
        "time",
        ".elem_date",
        ".date",
    ],
    "body": [
        ".elem_paragraph",
        "#pbBlock p",
        "article p",
        ".content-body p",
    ],
    "author": [
        ".elem_author",
        ".author",
        ".byline",
    ],
    "tags": [
        ".elem_tag a",
        ".tag-list a",
        "[data-xitagmain]",
    ],
    "pdf_link": [
        "a.pdf-link-gtm",
        "a[href$='.pdf']",
    ],
}
"""CSS selectors for article-page elements.

Each key maps to a list of selectors tried in order (first match wins).
This fallback approach absorbs minor page-structure changes without code edits.
"""

SECTION_SELECTORS: dict[str, list[str]] = {
    "category_title": [
        "#elem_category_title",
        ".category-title",
        ".biznews_top h2",
    ],
    "article_list": [
        ".biznews_top",
        ".article-list",
        "#pbBlock ul",
    ],
    "pagination": [
        ".elem_pagination",
        ".pagination",
        "nav.pager",
    ],
    "related": [
        "[id^='xi_related_']",
        ".xi_recommend_list",
        ".related-articles",
    ],
    "content_block": [
        "[id^='pbBlock']",
        ".content-block",
        "article",
    ],
}
"""CSS selectors for page-level section containers.

Each key maps to a list of selectors tried in order (first match wins).
"""

# ---------------------------------------------------------------------------
# Content types
# ---------------------------------------------------------------------------

CONTENT_TYPES: list[str] = [
    "ビジネス短信",
    "調査レポート",
    "特集",
    "地域・分析レポート",
    "貿易・投資相談Q&A",
]
"""Known JETRO content type strings.

These correspond to the ``category`` field in the RSS feed and web pages.
"""

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JetroContentMeta:
    """Immutable metadata for a single JETRO content item.

    Attributes
    ----------
    title : str
        Content title.
    url : str
        Full URL of the content page.
    category : str
        Top-level category (``"world"``, ``"theme"``, ``"industry"``).
    subcategory : str
        Sub-category key within the top-level category
        (e.g., ``"asia"``, ``"export"``, ``"foods"``).
    content_type : str | None
        Content type string, or ``None`` if unknown.
    published : str | None
        Publication date string (ISO 8601 or display format), or ``None``.
    author : str | None
        Author or department name, or ``None``.

    Examples
    --------
    >>> meta = JetroContentMeta(
    ...     title="ニッチ技術を強みに宇宙産業育成",
    ...     url="https://www.jetro.go.jp/biznews/2026/03/example.html",
    ...     category="world",
    ...     subcategory="europe",
    ... )
    >>> meta.title
    'ニッチ技術を強みに宇宙産業育成'
    >>> meta.category
    'world'
    """

    title: str
    url: str
    category: str
    subcategory: str
    content_type: str | None = None
    published: str | None = None
    author: str | None = None
