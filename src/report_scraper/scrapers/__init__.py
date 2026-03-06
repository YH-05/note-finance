"""Concrete scraper implementations for various report sources.

Modules
-------
_rss_scraper
    RSS-based intermediate base class.
_html_scraper
    HTML-based intermediate base class using Scrapling StealthyFetcher.
_spa_scraper
    SPA-based intermediate base class using Scrapling DynamicFetcher.
advisor_perspectives
    Advisor Perspectives scraper (RSS).
blackrock
    BlackRock Investment Institute scraper (HTML + PDF).
schwab
    Charles Schwab market commentary scraper (HTML).
morgan_stanley
    Morgan Stanley Investment Management scraper (HTML + JSON API).
wells_fargo
    Wells Fargo investment strategy scraper (HTML).
vanguard
    Vanguard market perspectives scraper (HTML).
goldman_sachs
    Goldman Sachs Research scraper (SPA / React).
jpmorgan
    JP Morgan Markets & Economy scraper (SPA / dynamic loading).
pimco
    PIMCO Insights scraper (SPA / Coveo JS).

Examples
--------
>>> from report_scraper.scrapers.advisor_perspectives import AdvisorPerspectivesScraper
>>> scraper = AdvisorPerspectivesScraper()
>>> scraper.source_key
'advisor_perspectives'
"""

from report_scraper.scrapers._rss_scraper import RssReportScraper

# AIDEV-NOTE: HtmlReportScraper uses optional scrapling dependency.
# Import is deferred to avoid ImportWarning when scrapling is not installed.
from report_scraper.scrapers.advisor_perspectives import AdvisorPerspectivesScraper
from report_scraper.scrapers.blackrock import BlackRockScraper
from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper
from report_scraper.scrapers.jpmorgan import JPMorganScraper
from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper
from report_scraper.scrapers.pimco import PimcoScraper
from report_scraper.scrapers.schwab import SchwabScraper
from report_scraper.scrapers.vanguard import VanguardScraper
from report_scraper.scrapers.wells_fargo import WellsFargoScraper

__all__ = [
    "AdvisorPerspectivesScraper",
    "BlackRockScraper",
    "GoldmanSachsScraper",
    "JPMorganScraper",
    "MorganStanleyScraper",
    "PimcoScraper",
    "RssReportScraper",
    "SchwabScraper",
    "VanguardScraper",
    "WellsFargoScraper",
]
