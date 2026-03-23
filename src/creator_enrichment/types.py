"""creator_enrichment 共有型定義.

全フェーズ間で共有する TypedDict / Exception を定義する。
Python 3.12+ PEP 695 スタイルの型ヒントを使用。
"""

from typing import Any, Literal, Protocol, TypedDict


# ---------------------------------------------------------------------------
# Phase 2: 検索結果
# ---------------------------------------------------------------------------
class RawItem(TypedDict):
    """Phase 2 検索結果の正規化アイテム.

    Tavily / WebFetch / Reddit から取得した生データを
    統一形式に変換したもの。
    """

    url: str
    title: str
    content: str
    source: str


# ---------------------------------------------------------------------------
# Phase 1: ギャップ分析出力
# ---------------------------------------------------------------------------
class GapAnalysisResult(TypedDict):
    """Phase 1 ギャップ分析の出力.

    Neo4j クエリ結果から算出した、対象ジャンルの
    低カバレッジ概念と既存サンプルを含む。
    """

    genre: str
    low_coverage_concepts: list[str]
    existing_samples: list[str]


# ---------------------------------------------------------------------------
# Phase 3: 抽出結果 (emit_creator_queue_v2 入力形式)
# ---------------------------------------------------------------------------
type SourceDict = dict[str, str]
type FactDict = dict[str, object]
type TipDict = dict[str, object]
type StoryDict = dict[str, object]
type EntityDict = dict[str, str]
type ConceptDict = dict[str, object]
type ServesAsDict = dict[str, str]
type ConceptRelationDict = dict[str, str]


class CycleData(TypedDict):
    """Phase 3 抽出結果 (emit_creator_queue_v2 入力形式).

    分類・Entity/Concept 抽出後のサイクルデータ。
    パイプライン投入スクリプトの入力として使用する。
    """

    genre: str
    cycle_id: str
    sources: list[SourceDict]
    facts: list[FactDict]
    tips: list[TipDict]
    stories: list[StoryDict]
    entities: list[EntityDict]
    concepts: list[ConceptDict]
    serves_as: list[ServesAsDict]
    concept_relations: list[ConceptRelationDict]


# ---------------------------------------------------------------------------
# Phase 4.2: パイプライン投入結果
# ---------------------------------------------------------------------------
class IngestResult(TypedDict):
    """Phase 4.2 パイプライン投入結果.

    /save-to-creator-graph 実行後のノード・リレーション作成件数。
    """

    nodes_created: int
    relations_created: int


# ---------------------------------------------------------------------------
# Phase 5: サイクルサマリー
# ---------------------------------------------------------------------------
type PipelineStatus = Literal["success", "dry-run", "error"]


class CycleReport(TypedDict):
    """Phase 5 サイクルサマリー.

    各サイクル終了時にセッションログへ記録するレポート。
    """

    genre: str
    search_results: int
    contents_created: dict[str, int]
    entities_extracted: int
    relations_detected: int
    pipeline_status: PipelineStatus
    cross_entity_added: int


# ---------------------------------------------------------------------------
# Phase 3: 抽出結果（単一アイテム）
# ---------------------------------------------------------------------------
class ExtractionResult(TypedDict):
    """extract_single() の戻り値型.

    LLM が返す JSON をパースした結果。
    """

    content_type: str
    title: str
    body: str
    source_url: str
    source_type: str
    language: str
    entities: list[dict[str, str]]
    concepts: list[dict[str, Any]]
    serves_as: list[dict[str, str]]
    concept_relations: list[dict[str, str]]


# ---------------------------------------------------------------------------
# フェーズ例外（orchestrator が CycleError にラップする）
# ---------------------------------------------------------------------------
class PhaseError(Exception):
    """フェーズ内で発生したエラー.

    各フェーズは PhaseError を raise し、orchestrator が
    CycleError(cycle_num=N) でラップする。
    """


class CycleError(Exception):
    """サイクル実行中に発生したエラーを隔離する例外.

    orchestrator が PhaseError を catch して cycle_num 付きで再ラップする。

    Attributes
    ----------
    cycle_num : int
        失敗したサイクル番号
    cause : Exception
        元の例外
    """

    def __init__(self, cycle_num: int, cause: Exception) -> None:
        self.cycle_num = cycle_num
        self.cause = cause
        super().__init__(f"Cycle {cycle_num} failed: {cause}")


# ---------------------------------------------------------------------------
# Phase Protocols（orchestrator の依存性逆転用）
# ---------------------------------------------------------------------------
class GapAnalyzerProtocol(Protocol):
    """Phase 1 ギャップ分析のプロトコル."""

    def analyze(
        self,
        prev_genre: str | None,
        genre_filter: str | None,
    ) -> GapAnalysisResult: ...


class SearcherProtocol(Protocol):
    """Phase 2 検索のプロトコル."""

    def search(self, queries: list[str], genre: str) -> list[RawItem]: ...


class ExtractorProtocol(Protocol):
    """Phase 3 抽出のプロトコル."""

    def extract_batch(
        self, *, items: list[RawItem], genre: str
    ) -> CycleData: ...


class CrossEnricherProtocol(Protocol):
    """Phase 4.5 横断リレーション強化のプロトコル."""

    def run(self, cycle_count: int) -> int: ...
