"""Wealth Finance Blog scraping configuration constants.

This module defines per-domain rate limits, sitemap URLs,
backfill tier assignments, and URL-to-source-key mappings
for the 15 target Wealth Finance Blog sites.

Notes
-----
- WEALTH_DOMAIN_RATE_LIMITS: crawl delay in seconds (0 = no enforced delay)
- BACKFILL_TIER: A (highest priority) → D (lowest priority / Playwright required)
- Tier 3 site (kiplinger.com) is excluded from RSS presets but included
  in sitemap config for backfill via Playwright.
"""

# AIDEV-NOTE: crawl delay values sourced from each site's robots.txt.
# monevator.com: Crawl-delay: 240, marginalrevolution.com: Crawl-delay: 600
WEALTH_DOMAIN_RATE_LIMITS: dict[str, float] = {
    "getrichslowly.org": 2.0,
    "mrmoneymustache.com": 2.0,
    "bogleheads.org": 5.0,
    "thecollegeinvestor.com": 3.0,
    "moneytalksnews.com": 3.0,
    "monevator.com": 240.0,
    "affordanything.com": 2.0,
    "iwillteachyoutoberich.com": 2.0,
    "awealthofcommonsense.com": 2.0,
    "youngandtheinvested.com": 2.0,
    "marginalrevolution.com": 600.0,
    "dividendgrowthstocks.com": 2.0,
    "earlyretirementnow.com": 2.0,
    "financialsamurai.com": 3.0,
    "kiplinger.com": 5.0,
}

# AIDEV-NOTE: sitemap URLs verified against each site's robots.txt Sitemap directive.
# Sites without a declared sitemap use the conventional /sitemap.xml path.
WEALTH_SITEMAP_URLS: dict[str, str] = {
    "getrichslowly.org": "https://www.getrichslowly.org/sitemap.xml",
    "mrmoneymustache.com": "https://www.mrmoneymustache.com/sitemap.xml",
    "bogleheads.org": "https://www.bogleheads.org/wiki/Special:SitemapIndex",
    "thecollegeinvestor.com": "https://thecollegeinvestor.com/sitemap.xml",
    "moneytalksnews.com": "https://www.moneytalksnews.com/sitemap.xml",
    "monevator.com": "https://monevator.com/sitemap.xml",
    "affordanything.com": "https://affordanything.com/sitemap.xml",
    "iwillteachyoutoberich.com": "https://www.iwillteachyoutoberich.com/sitemap.xml",
    "awealthofcommonsense.com": "https://awealthofcommonsense.com/sitemap.xml",
    "youngandtheinvested.com": "https://youngandtheinvested.com/sitemap.xml",
    "marginalrevolution.com": "https://marginalrevolution.com/sitemap.xml",
    "dividendgrowthstocks.com": "https://dividendgrowthstocks.com/sitemap.xml",
    "earlyretirementnow.com": "https://earlyretirementnow.com/sitemap.xml",
    "financialsamurai.com": "https://financialsamurai.com/sitemap.xml",
    "kiplinger.com": "https://www.kiplinger.com/sitemap.xml",
}

# AIDEV-NOTE: Backfill tiers control scraping priority and method:
#   A = high priority, standard HTTP fetch
#   B = medium priority, standard HTTP fetch
#   C = lower priority, standard HTTP fetch with longer delay
#   D = requires Playwright (JavaScript rendering); scraped last
BACKFILL_TIER: dict[str, str] = {
    "getrichslowly.org": "A",
    "mrmoneymustache.com": "A",
    "affordanything.com": "A",
    "awealthofcommonsense.com": "A",
    "monevator.com": "A",
    "moneytalksnews.com": "B",
    "thecollegeinvestor.com": "B",
    "youngandtheinvested.com": "B",
    "dividendgrowthstocks.com": "B",
    "earlyretirementnow.com": "B",
    "iwillteachyoutoberich.com": "C",
    "financialsamurai.com": "C",
    "marginalrevolution.com": "C",
    "bogleheads.org": "C",
    "kiplinger.com": "D",
}

# AIDEV-NOTE: Used by prepare_asset_management_session.py and the main
# scrape_wealth_blogs.py script to map feed URLs to canonical source keys
# for theme matching and session JSON output.
WEALTH_URL_TO_SOURCE_KEY: dict[str, str] = {
    "getrichslowly.org": "getrichslowly",
    "www.getrichslowly.org": "getrichslowly",
    "mrmoneymustache.com": "mrmoneymustache",
    "www.mrmoneymustache.com": "mrmoneymustache",
    "bogleheads.org": "bogleheads",
    "www.bogleheads.org": "bogleheads",
    "thecollegeinvestor.com": "thecollegeinvestor",
    "www.thecollegeinvestor.com": "thecollegeinvestor",
    "moneytalksnews.com": "moneytalksnews",
    "www.moneytalksnews.com": "moneytalksnews",
    "monevator.com": "monevator",
    "www.monevator.com": "monevator",
    "affordanything.com": "affordanything",
    "www.affordanything.com": "affordanything",
    "iwillteachyoutoberich.com": "iwillteachyoutoberich",
    "www.iwillteachyoutoberich.com": "iwillteachyoutoberich",
    "awealthofcommonsense.com": "awealthofcommonsense",
    "www.awealthofcommonsense.com": "awealthofcommonsense",
    "youngandtheinvested.com": "youngandtheinvested",
    "www.youngandtheinvested.com": "youngandtheinvested",
    "marginalrevolution.com": "marginalrevolution",
    "www.marginalrevolution.com": "marginalrevolution",
    "dividendgrowthstocks.com": "dividendgrowthstocks",
    "www.dividendgrowthstocks.com": "dividendgrowthstocks",
    "earlyretirementnow.com": "earlyretirementnow",
    "www.earlyretirementnow.com": "earlyretirementnow",
    "financialsamurai.com": "financialsamurai",
    "www.financialsamurai.com": "financialsamurai",
    "kiplinger.com": "kiplinger",
    "www.kiplinger.com": "kiplinger",
}
