"""Authority level classifier for Source nodes.

Classifies sources into 6 authority levels based on source_type and URL domain.

Authority levels:
    official  - 企業IR・SEC Filing・中銀・政府機関
    analyst   - セルサイドレポート・格付け機関・自社リサーチ
    media     - 大手報道機関・ニュースメディア
    blog      - 個人メディア・専門ブログ・Seeking Alpha
    social    - SNS・コミュニティ（Reddit, X/Twitter）
    academic  - 学術論文・リサーチペーパー

Usage::

    from scripts.authority_classifier import classify_authority

    level = classify_authority(source_type="news", url="https://www.cnbc.com/...")
    # => "media"
"""

from __future__ import annotations

from urllib.parse import urlparse

OFFICIAL_DOMAINS: frozenset[str] = frozenset({
    "sec.gov", "www.sec.gov", "data.sec.gov", "efts.sec.gov",
    "www.federalreserve.gov", "federalreserve.gov",
    "www.bls.gov", "www.bea.gov", "www.treasury.gov",
    "www.ecb.europa.eu", "www.boj.or.jp",
    "www.imf.org", "www.worldbank.org",
    "investors.ametek.com", "www.asml.com", "engineering.fb.com",
})

MEDIA_DOMAINS: frozenset[str] = frozenset({
    "www.cnbc.com", "cnbc.com",
    "www.reuters.com", "reuters.com",
    "www.ft.com", "ft.com",
    "www.bloomberg.com", "bloomberg.com",
    "www.wsj.com", "wsj.com",
    "www.marketwatch.com", "marketwatch.com",
    "www.nasdaq.com",
    "www.investors.com",
    "www.barrons.com", "barrons.com",
    "techcrunch.com", "www.techcrunch.com",
    "arstechnica.com", "www.arstechnica.com",
    "www.theverge.com", "theverge.com",
    "www.theregister.com",
    "www.macrumors.com",
    "9to5google.com",
    "www.prnewswire.com",
    "www.businesswire.com",
})

SOCIAL_DOMAINS: frozenset[str] = frozenset({
    "www.reddit.com", "reddit.com", "old.reddit.com",
    "twitter.com", "x.com",
    "bsky.app",
})

ACADEMIC_DOMAINS: frozenset[str] = frozenset({
    "www.bmj.com", "bmj.com",
    "www.nber.org", "nber.org",
    "arxiv.org", "www.arxiv.org",
    "ssrn.com", "www.ssrn.com",
    "scholar.google.com",
    "www.jstor.org",
    "www.nature.com",
    "www.science.org",
})

BLOG_DOMAINS: frozenset[str] = frozenset({
    "seekingalpha.com", "www.seekingalpha.com",
})


def _classify_by_url(url: str) -> str | None:
    """Classify by URL domain. Returns level or None."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            domain = url.split("/")[0].lower()
    except Exception:
        return None

    if url.startswith("file://"):
        return "analyst"

    if domain in OFFICIAL_DOMAINS or domain.startswith("ir."):
        return "official"
    if domain in ACADEMIC_DOMAINS:
        return "academic"
    if domain in SOCIAL_DOMAINS:
        return "social"
    if domain in BLOG_DOMAINS:
        return "blog"
    if domain in MEDIA_DOMAINS:
        return "media"

    return None


def classify_authority(source_type: str = "", url: str = "") -> str:
    """Determine authority_level for a Source.

    Parameters
    ----------
    source_type : str
        Source type (news, blog, pdf, web, original).
    url : str
        Source URL.

    Returns
    -------
    str
        One of: official, analyst, media, blog, social, academic.
    """
    if url:
        url_level = _classify_by_url(url)
        if url_level:
            return url_level

    match source_type:
        case "pdf":
            return "analyst"
        case "blog":
            return "blog"
        case "web":
            return "social"
        case "original":
            return "analyst"
        case _:
            return "media"
