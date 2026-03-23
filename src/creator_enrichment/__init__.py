"""creator_enrichment - creator-neo4j 自動拡充パッケージ.

ギャップ分析 -> Web検索 -> 分類・Entity抽出 -> パイプライン投入を
サイクルで繰り返し、creator-neo4j のナレッジグラフを自動拡充する。
"""

from .neo4j_writer import CreatorGraphWriter
from .orchestrator import CreatorEnrichmentOrchestrator, FatalError
from .session_log import SessionLogger
from .types import (
    CycleData,
    CycleError,
    CycleReport,
    GapAnalysisResult,
    IngestResult,
    RawItem,
)

__version__ = "0.1.0"

__all__ = [
    "CreatorEnrichmentOrchestrator",
    "CreatorGraphWriter",
    "CycleData",
    "CycleError",
    "CycleReport",
    "FatalError",
    "GapAnalysisResult",
    "IngestResult",
    "RawItem",
    "SessionLogger",
]
