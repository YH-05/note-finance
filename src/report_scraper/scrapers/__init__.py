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
bank_of_america
    Bank of America Research scraper (HTML + PDF).
blackrock
    BlackRock Investment Institute scraper (HTML + PDF).
deutsche_bank
    Deutsche Bank Research scraper (HTML + PDF).
fidelity
    Fidelity Investments scraper (HTML).
invesco
    Invesco scraper (HTML + PDF).
jpmorgan
    JP Morgan Markets & Economy scraper (SPA / dynamic loading).
morgan_stanley
    Morgan Stanley Investment Management scraper (HTML + JSON API).
pimco
    PIMCO Insights scraper (SPA / Coveo JS).
schroders
    Schroders scraper (HTML + PDF).
schwab
    Charles Schwab market commentary scraper (HTML).
state_street
    State Street Global Advisors scraper (HTML + PDF).
t_rowe_price
    T. Rowe Price scraper (HTML + PDF).
vanguard
    Vanguard market perspectives scraper (HTML).
goldman_sachs
    Goldman Sachs Research scraper (SPA / React).
wells_fargo
    Wells Fargo investment strategy scraper (HTML).

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
from report_scraper.scrapers.bank_of_america import BankOfAmericaScraper
from report_scraper.scrapers.blackrock import BlackRockScraper
from report_scraper.scrapers.deutsche_bank import DeutscheBankScraper
from report_scraper.scrapers.fidelity import FidelityScraper
from report_scraper.scrapers.goldman_sachs import GoldmanSachsScraper
from report_scraper.scrapers.invesco import InvescoScraper
from report_scraper.scrapers.jpmorgan import JPMorganScraper
from report_scraper.scrapers.morgan_stanley import MorganStanleyScraper
from report_scraper.scrapers.pimco import PimcoScraper
from report_scraper.scrapers.schroders import SchrodersScraper
from report_scraper.scrapers.schwab import SchwabScraper
from report_scraper.scrapers.state_street import StateStreetScraper
from report_scraper.scrapers.t_rowe_price import TRowePriceScraper
from report_scraper.scrapers.vanguard import VanguardScraper
from report_scraper.scrapers.wells_fargo import WellsFargoScraper

__all__ = [
    "AdvisorPerspectivesScraper",
    "BankOfAmericaScraper",
    "BlackRockScraper",
    "DeutscheBankScraper",
    "FidelityScraper",
    "GoldmanSachsScraper",
    "InvescoScraper",
    "JPMorganScraper",
    "MorganStanleyScraper",
    "PimcoScraper",
    "RssReportScraper",
    "SchrodersScraper",
    "SchwabScraper",
    "StateStreetScraper",
    "TRowePriceScraper",
    "VanguardScraper",
    "WellsFargoScraper",
]
