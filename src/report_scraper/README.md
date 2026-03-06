# report_scraper

Investment report scraper package for note-finance. Collects research reports from buy-side, sell-side, and aggregator sources using RSS feeds, static HTML, and Playwright-rendered (SPA) pages.

## Architecture

### Class Hierarchy

```
BaseReportScraper (ABC)
├── RssReportScraper        # RSS/Atom feed-based sources
│   └── AdvisorPerspectivesScraper
├── HtmlReportScraper       # Static HTML sources (Scrapling StealthyFetcher)
│   ├── BankOfAmericaScraper
│   ├── BlackRockScraper
│   ├── DeutscheBankScraper
│   ├── FidelityScraper
│   ├── InvescoScraper
│   ├── MorganStanleyScraper
│   ├── SchrodersScraper
│   ├── SchwabScraper
│   ├── StateStreetScraper
│   ├── TRowePriceScraper
│   ├── VanguardScraper
│   └── WellsFargoScraper
└── SpaReportScraper        # SPA sources (Scrapling DynamicFetcher / Playwright)
    ├── GoldmanSachsScraper
    ├── JPMorganScraper
    └── PimcoScraper
```

### Package Structure

```
src/report_scraper/
├── __init__.py              # Package exports
├── _logging.py              # structlog configuration
├── exceptions.py            # Exception hierarchy
├── types.py                 # Data models (Pydantic + frozen dataclasses)
├── py.typed                 # PEP 561 marker
├── config/
│   ├── __init__.py
│   └── loader.py            # YAML config loader
├── core/
│   ├── __init__.py
│   ├── base_scraper.py      # BaseReportScraper ABC
│   ├── scraper_engine.py    # Concurrent collection engine
│   └── scraper_registry.py  # Source-to-scraper registry
├── scrapers/
│   ├── __init__.py
│   ├── _rss_scraper.py      # RssReportScraper base
│   ├── _html_scraper.py     # HtmlReportScraper base
│   ├── _spa_scraper.py      # SpaReportScraper base
│   └── *.py                 # Concrete scrapers (16 sources)
├── services/
│   ├── __init__.py
│   ├── content_extractor.py # trafilatura + lxml fallback
│   ├── dedup_tracker.py     # URL-based deduplication
│   ├── pdf_downloader.py    # PDF download via httpx
│   └── summary_exporter.py  # Markdown summary generation
├── storage/
│   ├── __init__.py
│   ├── json_store.py        # JSON report persistence
│   └── pdf_store.py         # PDF file storage
└── cli/
    ├── __init__.py
    └── main.py              # Click CLI (collect, list, test-source)
```

### Data Flow

```
Config (YAML)
    │
    v
ScraperEngine.collect(sources, registry)
    │
    ├── BaseReportScraper.fetch_listing()    # Get ReportMetadata list
    │       │
    │       ├── RssReportScraper   → feedparser
    │       ├── HtmlReportScraper  → Scrapling StealthyFetcher
    │       └── SpaReportScraper   → Scrapling DynamicFetcher
    │
    ├── DedupTracker.is_seen()               # Filter duplicates
    │
    ├── BaseReportScraper.extract_report()   # Get ScrapedReport
    │       │
    │       ├── ContentExtractor.extract()   # HTML → text
    │       └── PdfDownloader.download()     # PDF files
    │
    ├── JsonReportStore.save()               # Persist JSON
    │
    └── RunSummary                           # Aggregated results
            │
            v
        SummaryExporter.export()             # Markdown output
```

### Data Models

| Model | Type | Description |
|-------|------|-------------|
| `SourceConfig` | Pydantic | Source configuration (key, URL, rendering type) |
| `GlobalConfig` | Pydantic | Global settings (output dirs, timeouts) |
| `ReportScraperConfig` | Pydantic | Top-level config (global + sources) |
| `ReportMetadata` | frozen dataclass | Report metadata (URL, title, dates) |
| `ExtractedContent` | frozen dataclass | Extracted text with method info |
| `PdfMetadata` | frozen dataclass | PDF file metadata (URL, path, size) |
| `ScrapedReport` | frozen dataclass | Complete report (metadata + content + PDF) |
| `CollectResult` | frozen dataclass | Per-source results (reports + errors) |
| `RunSummary` | frozen dataclass | Complete run summary |

## Usage

### CLI

```bash
# Collect reports from a specific source
report-scraper collect --source advisor_perspectives

# Collect from all configured sources
report-scraper collect --all

# List available sources
report-scraper list

# Filter by tier
report-scraper list --tier buy_side

# Test a source (dry run)
report-scraper test-source advisor_perspectives

# Custom data directory
report-scraper --data-dir /tmp/reports collect --source blackrock
```

### Python API

```python
from report_scraper.config.loader import load_config
from report_scraper.core.scraper_engine import ScraperEngine
from report_scraper.core.scraper_registry import ScraperRegistry
from report_scraper.services.summary_exporter import SummaryExporter

# Load configuration
config = load_config(Path("data/config/report-scraper-config.yaml"))

# Build engine with services
engine = ScraperEngine(
    content_extractor=extractor,
    pdf_downloader=downloader,
    dedup_tracker=tracker,
    json_store=json_store,
    pdf_store=pdf_store,
    concurrency=5,
)

# Run collection
summary = await engine.collect(sources=["blackrock", "jpmorgan"], registry=registry)

# Export summary
exporter = SummaryExporter()
markdown = exporter.export(summary)
print(markdown)
```

## Configuration

Configuration is defined in YAML format at `data/config/report-scraper-config.yaml`.

```yaml
global:
  output_dir: data/scraped/reports
  pdf_dir: data/scraped/pdfs
  max_reports_per_source: 20
  timeouts:
    connect: 10
    read: 30
  dedup_days: 30

sources:
  - key: advisor_perspectives
    name: Advisor Perspectives
    tier: aggregator
    listing_url: https://www.advisorperspectives.com/articles
    rendering: rss
    tags: [macro, equity]

  - key: blackrock
    name: BlackRock Investment Institute
    tier: buy_side
    listing_url: https://www.blackrock.com/corporate/insights
    rendering: static
    tags: [macro, fixed_income]
    article_selector: "div.article-list a"
```

### Source Tiers

| Tier | Description | Examples |
|------|-------------|---------|
| `buy_side` | Asset managers and institutional investors | BlackRock, Vanguard, PIMCO |
| `sell_side` | Investment banks and brokerages | Goldman Sachs, Morgan Stanley |
| `aggregator` | Content aggregation platforms | Advisor Perspectives |

### Rendering Types

| Type | Engine | Use Case |
|------|--------|----------|
| `rss` | feedparser | RSS/Atom feed sources |
| `static` | Scrapling StealthyFetcher | Server-rendered HTML pages |
| `playwright` | Scrapling DynamicFetcher | JavaScript-rendered SPA pages |

## Adding a New Source

1. **Choose the base class** based on the source's rendering type:
   - RSS feed: extend `RssReportScraper`
   - Static HTML: extend `HtmlReportScraper`
   - JavaScript SPA: extend `SpaReportScraper`

2. **Create the scraper module** in `src/report_scraper/scrapers/`:

```python
"""Example scraper for New Source."""

from __future__ import annotations

from report_scraper.scrapers._html_scraper import HtmlReportScraper
from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig


class NewSourceScraper(HtmlReportScraper):
    listing_url = "https://newsource.com/research"
    article_selector = "div.research-list a"

    @property
    def source_key(self) -> str:
        return "new_source"

    @property
    def source_config(self) -> SourceConfig:
        return SourceConfig(
            key="new_source",
            name="New Source Research",
            tier="sell_side",
            listing_url=self.listing_url,
            rendering="static",
            tags=["macro"],
        )

    def parse_listing_item(self, element, base_url):
        # Extract metadata from each listing element
        ...

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        # Fetch and extract the full report
        ...
```

3. **Register the scraper** in the scraper registry.

4. **Add configuration** to `data/config/report-scraper-config.yaml`:

```yaml
sources:
  - key: new_source
    name: New Source Research
    tier: sell_side
    listing_url: https://newsource.com/research
    rendering: static
    tags: [macro]
    article_selector: "div.research-list a"
```

5. **Write tests** in `tests/report_scraper/unit/`.

## Testing

```bash
# Run all report_scraper tests
uv run pytest tests/report_scraper/ -v

# Run specific test module
uv run pytest tests/report_scraper/unit/test_engine.py -v

# Run with coverage
uv run pytest tests/report_scraper/ --cov=report_scraper -v
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `pydantic` | Configuration validation |
| `structlog` | Structured logging |
| `httpx` | HTTP client (PDF downloads) |
| `feedparser` | RSS/Atom feed parsing |
| `trafilatura` | HTML content extraction |
| `lxml` | Fallback HTML parsing |
| `scrapling` | Web scraping (StealthyFetcher, DynamicFetcher) |
| `click` | CLI framework |
| `rich` | CLI output formatting |
| `pyyaml` | YAML config loading |
