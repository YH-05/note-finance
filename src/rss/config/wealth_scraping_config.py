"""Wealth Finance Blog scraping configuration constants.

This module defines per-domain rate limits, sitemap URLs,
backfill tier assignments, and URL-to-source-key mappings
for the target Wealth Finance Blog sites.

Notes
-----
- WEALTH_DOMAIN_RATE_LIMITS: crawl delay in seconds (0 = no enforced delay)
- BACKFILL_TIER: A (highest priority) → D (lowest priority / Playwright required)

Changelog
---------
- v1.1 (2026-03-17): Removed 3 sites (marginalrevolution, bogleheads, kiplinger).
  Added 5 sites (ofdollarsanddata, physicianonfire, whitecoatinvestor,
  rationalwalk, portfoliocharts). Now 17 sites total.
- v1.0: Initial 15 sites.
"""

# AIDEV-NOTE: crawl delay values sourced from each site's robots.txt.
# monevator.com: Crawl-delay: 240
WEALTH_DOMAIN_RATE_LIMITS: dict[str, float] = {
    "getrichslowly.org": 2.0,
    "mrmoneymustache.com": 2.0,
    "thecollegeinvestor.com": 3.0,
    "moneytalksnews.com": 3.0,
    "monevator.com": 240.0,
    "affordanything.com": 2.0,
    "iwillteachyoutoberich.com": 2.0,
    "awealthofcommonsense.com": 2.0,
    "youngandtheinvested.com": 2.0,
    "dividendgrowthstocks.com": 2.0,
    "earlyretirementnow.com": 2.0,
    "financialsamurai.com": 3.0,
    # New sites (v1.1)
    "ofdollarsanddata.com": 2.0,
    "physicianonfire.com": 2.0,
    "whitecoatinvestor.com": 2.0,
    "rationalwalk.com": 2.0,
    "portfoliocharts.com": 2.0,
}

# AIDEV-NOTE: sitemap URLs verified against each site's robots.txt Sitemap directive.
# Sites without a declared sitemap use the conventional /sitemap.xml path.
WEALTH_SITEMAP_URLS: dict[str, str] = {
    "getrichslowly.org": "https://www.getrichslowly.org/sitemap.xml",
    "mrmoneymustache.com": "https://www.mrmoneymustache.com/sitemap.xml",
    "thecollegeinvestor.com": "https://thecollegeinvestor.com/sitemap.xml",
    "moneytalksnews.com": "https://www.moneytalksnews.com/sitemap.xml",
    "monevator.com": "https://monevator.com/sitemap.xml",
    "affordanything.com": "https://affordanything.com/sitemap.xml",
    "iwillteachyoutoberich.com": "https://www.iwillteachyoutoberich.com/sitemap.xml",
    "awealthofcommonsense.com": "https://awealthofcommonsense.com/sitemap.xml",
    "youngandtheinvested.com": "https://youngandtheinvested.com/sitemap.xml",
    "dividendgrowthstocks.com": "https://dividendgrowthstocks.com/sitemap.xml",
    "earlyretirementnow.com": "https://earlyretirementnow.com/sitemap.xml",
    "financialsamurai.com": "https://financialsamurai.com/sitemap.xml",
    # New sites (v1.1)
    "ofdollarsanddata.com": "https://ofdollarsanddata.com/sitemap.xml",
    "physicianonfire.com": "https://www.physicianonfire.com/sitemap.xml",
    "whitecoatinvestor.com": "https://www.whitecoatinvestor.com/sitemap.xml",
    "rationalwalk.com": "https://rationalwalk.com/sitemap.xml",
    "portfoliocharts.com": "https://portfoliocharts.com/sitemap.xml",
}

# AIDEV-NOTE: Backfill tiers control scraping priority and method:
#   A = high priority, standard HTTP fetch
#   B = medium priority, standard HTTP fetch
#   C = lower priority, standard HTTP fetch with longer delay
BACKFILL_TIER: dict[str, str] = {
    "getrichslowly.org": "A",
    "mrmoneymustache.com": "A",
    "affordanything.com": "A",
    "awealthofcommonsense.com": "A",
    "monevator.com": "A",
    "ofdollarsanddata.com": "A",
    "moneytalksnews.com": "B",
    "thecollegeinvestor.com": "B",
    "youngandtheinvested.com": "B",
    "dividendgrowthstocks.com": "B",
    "earlyretirementnow.com": "B",
    "physicianonfire.com": "B",
    "whitecoatinvestor.com": "B",
    "rationalwalk.com": "B",
    "portfoliocharts.com": "B",
    "iwillteachyoutoberich.com": "C",
    "financialsamurai.com": "C",
}

# AIDEV-NOTE: Used by prepare_asset_management_session.py and the main
# scrape_wealth_blogs.py script to map feed URLs to canonical source keys
# for theme matching and session JSON output.
WEALTH_URL_TO_SOURCE_KEY: dict[str, str] = {
    "getrichslowly.org": "getrichslowly",
    "www.getrichslowly.org": "getrichslowly",
    "mrmoneymustache.com": "mrmoneymustache",
    "www.mrmoneymustache.com": "mrmoneymustache",
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
    "dividendgrowthstocks.com": "dividendgrowthstocks",
    "www.dividendgrowthstocks.com": "dividendgrowthstocks",
    "earlyretirementnow.com": "earlyretirementnow",
    "www.earlyretirementnow.com": "earlyretirementnow",
    "financialsamurai.com": "financialsamurai",
    "www.financialsamurai.com": "financialsamurai",
    # New sites (v1.1)
    "ofdollarsanddata.com": "ofdollarsanddata",
    "www.ofdollarsanddata.com": "ofdollarsanddata",
    "physicianonfire.com": "physicianonfire",
    "www.physicianonfire.com": "physicianonfire",
    "whitecoatinvestor.com": "whitecoatinvestor",
    "www.whitecoatinvestor.com": "whitecoatinvestor",
    "rationalwalk.com": "rationalwalk",
    "www.rationalwalk.com": "rationalwalk",
    "portfoliocharts.com": "portfoliocharts",
    "www.portfoliocharts.com": "portfoliocharts",
}
