"""scripts/mappers パッケージ。

BaseMapper 抽象クラスと COMMAND_MAPPERS ディスパッチテーブルを提供する。

COMMAND_MAPPERS は全11マッパーへのディスパッチテーブルであり、
外部コンシューマーに対してエクスポートされる。

全11マッパーは ``BaseMapper`` サブクラスとして実装され、
それぞれのプラグインファイルで定義されている。

Usage
-----
::

    from mappers import COMMAND_MAPPERS, BaseMapper

    mapper_fn = COMMAND_MAPPERS.get("web-research")
    result = mapper_fn(data)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mappers.academic_fetch import AcademicFetchMapper
from mappers.ai_research import AiResearchMapper
from mappers.asset_management import AssetManagementMapper
from mappers.base import BaseMapper, ChunkProcessingContext
from mappers.finance_full import FinanceFullMapper
from mappers.finance_news import FinanceNewsMapper
from mappers.market_report import MarketReportMapper
from mappers.pdf_extraction import PdfExtractionMapper
from mappers.reddit_topics import RedditTopicsMapper
from mappers.topic_discovery import TopicDiscoveryMapper
from mappers.wealth_scrape import WealthScrapeMapper
from mappers.web_research import WebResearchMapper

__all__ = [
    "COMMAND_MAPPERS",
    "AcademicFetchMapper",
    "AiResearchMapper",
    "AssetManagementMapper",
    "BaseMapper",
    "ChunkProcessingContext",
    "FinanceFullMapper",
    "FinanceNewsMapper",
    "MarketReportMapper",
    "PdfExtractionMapper",
    "RedditTopicsMapper",
    "TopicDiscoveryMapper",
    "WealthScrapeMapper",
    "WebResearchMapper",
]

# ---------------------------------------------------------------------------
# COMMAND_MAPPERS ディスパッチテーブル
# ---------------------------------------------------------------------------
# 全11マッパーは BaseMapper サブクラスの map() メソッドを使用する。
# ---------------------------------------------------------------------------

type _MapperFn = Callable[[dict[str, Any]], dict[str, Any]]

# 全11マッパーのインスタンス（シングルトン）
_academic_fetch_mapper = AcademicFetchMapper()
_ai_research_mapper = AiResearchMapper()
_asset_management_mapper = AssetManagementMapper()
_finance_full_mapper = FinanceFullMapper()
_finance_news_mapper = FinanceNewsMapper()
_market_report_mapper = MarketReportMapper()
_pdf_extraction_mapper = PdfExtractionMapper()
_reddit_topics_mapper = RedditTopicsMapper()
_topic_discovery_mapper = TopicDiscoveryMapper()
_wealth_scrape_mapper = WealthScrapeMapper()
_web_research_mapper = WebResearchMapper()

COMMAND_MAPPERS: dict[str, _MapperFn] = {
    "academic-fetch": _academic_fetch_mapper.map,
    "ai-research-collect": _ai_research_mapper.map,
    "asset-management": _asset_management_mapper.map,
    "finance-full": _finance_full_mapper.map,
    "finance-news-workflow": _finance_news_mapper.map,
    "generate-market-report": _market_report_mapper.map,
    "pdf-extraction": _pdf_extraction_mapper.map,
    "reddit-finance-topics": _reddit_topics_mapper.map,
    "topic-discovery": _topic_discovery_mapper.map,
    "wealth-scrape": _wealth_scrape_mapper.map,
    "web-research": _web_research_mapper.map,
}
"""11コマンドのマッパー関数ディスパッチテーブル。

全コマンドは BaseMapper サブクラスの map() メソッドを使用:
- ``academic-fetch``         → AcademicFetchMapper
- ``ai-research-collect``    → AiResearchMapper
- ``asset-management``       → AssetManagementMapper
- ``finance-full``           → FinanceFullMapper
- ``finance-news-workflow``  → FinanceNewsMapper
- ``generate-market-report`` → MarketReportMapper
- ``pdf-extraction``         → PdfExtractionMapper
- ``reddit-finance-topics``  → RedditTopicsMapper
- ``topic-discovery``        → TopicDiscoveryMapper
- ``wealth-scrape``          → WealthScrapeMapper
- ``web-research``           → WebResearchMapper
"""
