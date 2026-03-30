"""scripts/mappers パッケージ。

BaseMapper 抽象クラスと COMMAND_MAPPERS ディスパッチテーブルを提供する。

COMMAND_MAPPERS は emit_research_queue.py の11マッパー関数への
ディスパッチテーブルであり、外部コンシューマーに対してエクスポートされる。

上位4マッパー（web-research / finance-news-workflow / wealth-scrape /
pdf-extraction）は ``BaseMapper`` サブクラスとして実装され、
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

from mappers.base import BaseMapper, ChunkProcessingContext
from mappers.finance_news import FinanceNewsMapper
from mappers.pdf_extraction import PdfExtractionMapper
from mappers.wealth_scrape import WealthScrapeMapper
from mappers.web_research import WebResearchMapper

__all__ = [
    "COMMAND_MAPPERS",
    "BaseMapper",
    "ChunkProcessingContext",
    "FinanceNewsMapper",
    "PdfExtractionMapper",
    "WealthScrapeMapper",
    "WebResearchMapper",
]

# ---------------------------------------------------------------------------
# COMMAND_MAPPERS ディスパッチテーブル
# ---------------------------------------------------------------------------
# 上位4マッパーは BaseMapper サブクラスの map() メソッドを使用する。
# 残り7マッパーは emit_research_queue.py の関数を引き続き使用する。
# ---------------------------------------------------------------------------

type _MapperFn = Callable[[dict[str, Any]], dict[str, Any]]

# 上位4マッパーのインスタンス（シングルトン）
_finance_news_mapper = FinanceNewsMapper()
_wealth_scrape_mapper = WealthScrapeMapper()
_web_research_mapper = WebResearchMapper()
_pdf_extraction_mapper = PdfExtractionMapper()


def _build_command_mappers() -> dict[str, _MapperFn]:
    """COMMAND_MAPPERS ディスパッチテーブルを構築して返す。

    上位4マッパーは BaseMapper サブクラスの map() メソッドを使用し、
    残り7マッパーは emit_research_queue.py の関数を遅延インポートして使用する。

    Returns
    -------
    dict[str, _MapperFn]
        コマンド名 → マッパー関数のディスパッチテーブル。
    """
    from emit_research_queue import COMMAND_MAPPERS as _raw  # type: ignore[import]

    # emit_research_queue.py のテーブルをベースに、上位4マッパーを上書きする
    table = dict(_raw)
    table["finance-news-workflow"] = _finance_news_mapper.map
    table["wealth-scrape"] = _wealth_scrape_mapper.map
    table["web-research"] = _web_research_mapper.map
    table["pdf-extraction"] = _pdf_extraction_mapper.map
    return table


# ディスパッチテーブルの公開エクスポート
# emit_research_queue.py が scripts/ の pythonpath に含まれていることを前提とする。
COMMAND_MAPPERS: dict[str, _MapperFn] = _build_command_mappers()
"""11コマンドのマッパー関数ディスパッチテーブル。

上位4コマンドは BaseMapper サブクラスの map() メソッドを使用:
- ``finance-news-workflow`` → FinanceNewsMapper
- ``wealth-scrape`` → WealthScrapeMapper
- ``web-research`` → WebResearchMapper
- ``pdf-extraction`` → PdfExtractionMapper

残り7コマンドは emit_research_queue.py の関数を使用:
- ``ai-research-collect``
- ``generate-market-report``
- ``asset-management``
- ``reddit-finance-topics``
- ``finance-full``
- ``topic-discovery``
- ``academic-fetch``
"""
