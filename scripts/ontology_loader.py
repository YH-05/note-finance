"""ontology_loader -- ``ontology.yaml`` SSoT から旧 knowledge-graph-schema.yaml 互換 API を提供する共通アダプター.

``data/lifecycle-state/research/ontology.yaml`` (v3.0 FIBO 準拠) を Single Source of
Truth として読み込み、以下 6 つの旧互換関数を提供する:

- ``load_consolidation_mapping()`` -- entity_type 統合マッピング
- ``load_source_type_normalization()`` -- source_type 正規化マッピング
- ``load_multilabel_types()`` -- マルチラベル entity_type キー一覧
- ``load_constraints()`` -- Neo4j UNIQUE 制約定義
- ``load_indices()`` -- Neo4j インデックス定義
- ``load_namespaces()`` -- 名前空間定義

``constraints`` / ``indices`` / ``namespaces`` は ontology.yaml に存在しないため、
旧 ``knowledge-graph-schema.yaml`` の値をアダプター内にデフォルト定義として保持する。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from utils_core.logging.config import get_logger
from yaml import safe_load

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_DEFAULT_ONTOLOGY_PATH = (
    _PROJECT_ROOT / "data" / "lifecycle-state" / "research" / "ontology.yaml"
)
"""ontology.yaml のデフォルトパス。"""


# ---------------------------------------------------------------------------
# YAML loader (cached)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _load_yaml(path: Path) -> dict[str, Any]:
    """YAML ファイルを読み込みキャッシュして返す.

    Parameters
    ----------
    path : Path
        YAML ファイルパス。

    Returns
    -------
    dict[str, Any]
        パース済み YAML データ。

    Raises
    ------
    FileNotFoundError
        ファイルが存在しない場合。
    """
    if not path.exists():
        msg = f"Ontology file not found: {path}"
        logger.error(msg)
        raise FileNotFoundError(msg)

    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = safe_load(f)

    logger.debug("Loaded ontology YAML", path=str(path))
    return data


def invalidate_cache() -> None:
    """YAML キャッシュを無効化する（テスト用）."""
    _load_yaml.cache_clear()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_consolidation_mapping(
    ontology_path: Path | None = None,
) -> dict[str, str]:
    """Entity type の統合マッピングを返す.

    Wave10 (Issue #316) で EntityType ノードを ontology.yaml から削除したため、
    ``_ENTITY_TYPE_CONSOLIDATION`` ハードコード定数を返す。
    ``ontology_path`` 引数は後方互換のために保持するが使用しない。

    Parameters
    ----------
    ontology_path : Path | None
        使用しない（後方互換のために保持）。

    Returns
    -------
    dict[str, str]
        ``{raw_entity_type: canonical_entity_type}`` マッピング。
        例: ``{"fintech": "company", "system": "technology", ...}``
    """
    # AIDEV-NOTE: Wave10 — EntityType ノード削除後はハードコード定数から返す
    mapping = dict(_ENTITY_TYPE_CONSOLIDATION)
    logger.info(
        "Loaded consolidation mapping (hardcoded)",
        canonical_count=len(_VALID_ENTITY_TYPES),
        total_mappings=len(mapping),
    )
    return mapping


def load_source_type_normalization(
    ontology_path: Path | None = None,
) -> dict[str, str]:
    """Source type の正規化マッピングを返す.

    ontology.yaml の ``source_classification_nodes`` から ``SourceType`` の
    ``canonical_values`` を読み取り、旧 ``source_type_normalization.mapping`` 互換の
    ``{raw_source_type: canonical_source_type}`` 辞書を生成する。

    ontology.yaml は正規値の一覧のみ保持し、旧形式のような
    異表記→正規値の網羅的マッピングは持たない。そのため、正規値の
    自己マッピング（identity mapping）を返す。

    Parameters
    ----------
    ontology_path : Path | None
        ontology.yaml のパス。None の場合はデフォルトパスを使用。

    Returns
    -------
    dict[str, str]
        正規 source_type の自己マッピング。
        例: ``{"news": "news", "blog": "blog", ...}``

    Raises
    ------
    FileNotFoundError
        ontology.yaml が存在しない場合。
    ValueError
        SourceType の canonical_values が見つからない場合。

    Notes
    -----
    旧 knowledge-graph-schema.yaml は ``web-research -> web`` のような
    異表記マッピングを含んでいたが、ontology.yaml にはその情報がない。
    フル互換が必要な場合は ``_LEGACY_SOURCE_TYPE_NORMALIZATION`` を参照する。
    """
    path = ontology_path or _DEFAULT_ONTOLOGY_PATH
    data = _load_yaml(path)
    source_type_node = _find_classification_node(
        data, "source_classification_nodes", "SourceType"
    )

    canonical_values: list[str] = source_type_node.get("canonical_values", [])
    if not canonical_values:
        msg = "SourceType canonical_values is empty in ontology.yaml"
        raise ValueError(msg)

    # identity mapping for canonical values
    mapping: dict[str, str] = {v: v for v in canonical_values}

    # Merge legacy variant mappings for full backward compatibility
    for raw, canonical in _LEGACY_SOURCE_TYPE_NORMALIZATION.items():
        if raw not in mapping:
            mapping[raw] = canonical

    logger.info(
        "Loaded source_type normalization",
        canonical_count=len(canonical_values),
        total_mappings=len(mapping),
    )
    return mapping


def load_multilabel_types(
    ontology_path: Path | None = None,
) -> list[str]:
    """マルチラベル entity_type キー一覧を返す.

    Wave10 (Issue #316) で EntityType ノードを ontology.yaml から削除したため、
    ``_VALID_ENTITY_TYPES`` ハードコード定数を返す。
    ``ontology_path`` 引数は後方互換のために保持するが使用しない。

    Parameters
    ----------
    ontology_path : Path | None
        使用しない（後方互換のために保持）。

    Returns
    -------
    list[str]
        正規 entity_type キーのリスト（14種）。
        例: ``["company", "technology", "organization", ...]``
    """
    # AIDEV-NOTE: Wave10 — EntityType ノード削除後はハードコード定数から返す
    keys = sorted(_VALID_ENTITY_TYPES)
    logger.info("Loaded multilabel types (hardcoded)", count=len(keys))
    return keys


def load_entity_labels(
    ontology_path: Path | None = None,
) -> list[str]:
    """個別エンティティラベル一覧を返す（13ラベル）.

    ontology.yaml の ``entity_nodes`` セクションから ``label`` を抽出し、
    個別エンティティラベルのリストを返す。

    Parameters
    ----------
    ontology_path : Path | None
        ontology.yaml のパス。None の場合はデフォルトパスを使用。

    Returns
    -------
    list[str]
        個別エンティティラベルのリスト。
        例: ``["Company", "Technology", "Organization", ...]``

    Raises
    ------
    FileNotFoundError
        ontology.yaml が存在しない場合。
    """
    path = ontology_path or _DEFAULT_ONTOLOGY_PATH
    data = _load_yaml(path)
    entity_nodes: list[dict[str, Any]] = data.get("entity_nodes", [])
    if not entity_nodes:
        # フォールバック: デフォルトラベル一覧を返す
        logger.warning("entity_nodes not found in ontology.yaml, using defaults")
        return list(_DEFAULT_ENTITY_LABELS)

    labels = [node["label"] for node in entity_nodes]
    logger.info("Loaded entity labels", count=len(labels))
    return labels


def load_constraints(
    ontology_path: Path | None = None,
) -> list[dict[str, str]]:
    """Neo4j 制約定義を返す.

    ``entity_nodes`` セクションから NODE KEY 制約を生成し、
    その他のノードの UNIQUE 制約と結合して返す。
    旧 ``Entity`` ラベルの UNIQUE 制約は除外する（新スキーマでは廃止）。

    Parameters
    ----------
    ontology_path : Path | None
        ontology.yaml のパス。None の場合はデフォルトパスを使用。

    Returns
    -------
    list[dict[str, str]]
        ``[{"label": "Source", "property": "source_id", "type": "UNIQUE"}, ...]``
        エンティティラベルは ``{"label": "Company", "property": "name", "type": "NODE_KEY"}``
    """
    path = ontology_path or _DEFAULT_ONTOLOGY_PATH
    data = _load_yaml(path)

    constraints: list[dict[str, str]] = []

    # entity_nodes から NODE KEY 制約を生成
    entity_nodes: list[dict[str, Any]] = data.get("entity_nodes", [])
    if entity_nodes:
        for node in entity_nodes:
            label = node.get("label", "")
            key_prop = node.get("key_property", "name")
            constraint_type = node.get("constraint_type", "NODE_KEY")
            if label:
                constraints.append(
                    {"label": label, "property": key_prop, "type": constraint_type}
                )
    else:
        # フォールバック: デフォルトのエンティティ制約
        for label in _DEFAULT_ENTITY_LABELS:
            constraints.append({"label": label, "property": "name", "type": "NODE_KEY"})

    # その他のノードの UNIQUE 制約（Entity ラベルは除外）
    for c in _DEFAULT_CONSTRAINTS:
        if c["label"] != "Entity":
            constraints.append(c)

    logger.debug("Returning constraints", count=len(constraints))
    return constraints


def load_indices() -> list[dict[str, str]]:
    """Neo4j インデックス定義を返す.

    ontology.yaml には索引情報が存在しないため、旧
    ``knowledge-graph-schema.yaml`` の ``indices`` セクションの値を
    アダプター内のデフォルト定義として提供する。

    Returns
    -------
    list[dict[str, str]]
        ``[{"label": "Fact", "property": "fact_type"}, ...]``
    """
    logger.debug("Returning default indices", count=len(_DEFAULT_INDICES))
    return list(_DEFAULT_INDICES)


def load_namespaces() -> dict[str, Any]:
    """名前空間定義を返す.

    ontology.yaml には名前空間情報が存在しないため、旧
    ``knowledge-graph-schema.yaml`` の ``namespaces`` セクションの値を
    アダプター内のデフォルト定義として提供する。

    Returns
    -------
    dict[str, Any]
        旧 ``namespaces`` セクション互換の辞書。
    """
    import copy

    logger.debug(
        "Returning default namespaces", namespace_count=len(_DEFAULT_NAMESPACES)
    )
    return copy.deepcopy(_DEFAULT_NAMESPACES)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _find_classification_node(
    data: dict[str, Any],
    section_key: str,
    target_label: str,
) -> dict[str, Any]:
    """ontology.yaml の分類ノードセクションから指定ラベルのノード定義を検索する.

    Parameters
    ----------
    data : dict[str, Any]
        パース済み ontology.yaml データ。
    section_key : str
        セクションキー（例: ``"entity_classification_nodes"``）。
    target_label : str
        検索対象のラベル名（例: ``"EntityType"``）。

    Returns
    -------
    dict[str, Any]
        該当ノード定義。

    Raises
    ------
    ValueError
        セクションまたはラベルが見つからない場合。
    """
    section: list[dict[str, Any]] = data.get(section_key, [])
    if not section:
        msg = f"Section '{section_key}' not found or empty in ontology.yaml"
        raise ValueError(msg)

    for node in section:
        if node.get("label") == target_label:
            return node

    msg = f"Label '{target_label}' not found in section '{section_key}'"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Legacy source_type variant mappings
# ---------------------------------------------------------------------------
# ontology.yaml は正規値リストのみ保持するが、旧 knowledge-graph-schema.yaml
# には異表記→正規値のマッピングが存在した。完全な後方互換のために保持する。

_LEGACY_SOURCE_TYPE_NORMALIZATION: dict[str, str] = {
    # web cluster
    "web-research": "web",
    "web_research": "web",
    "analysis": "web",
    "data": "web",
    "social": "web",
    "media": "web",
    # news cluster
    "rss": "news",
    "news_article": "news",
    "article": "news",
    "transcript": "news",
    "press_release": "news",
    # pdf cluster
    "report": "pdf",
    "company_filing": "pdf",
    "sec_filing": "pdf",
    "annual_report": "pdf",
    "financial_statement": "pdf",
    "academic_paper": "pdf",
    "paper": "pdf",
    "academic": "pdf",
    "regulatory_filing": "pdf",
    "regulatory_document": "pdf",
    "presentation": "pdf",
    "white_paper": "pdf",
    "research_report": "pdf",
    "legal_guide": "pdf",
    # original cluster
    "original": "original",
}


# ---------------------------------------------------------------------------
# Entity type consolidation mapping (hardcoded fallback)
# AIDEV-NOTE: Wave10 (Issue #316) — EntityType ノード削除に伴い、
# ontology.yaml から読み込む代わりにここで定義する。
# 旧 EntityType.canonical_values と同等の情報を保持。
# ---------------------------------------------------------------------------

_ENTITY_TYPE_CONSOLIDATION: dict[str, str] = {
    # company cluster
    "company": "company",
    "fintech": "company",
    "subsidiary": "company",
    "fintech_holding": "company",
    "digital_bank": "company",
    "it_services": "company",
    # technology cluster
    "technology": "technology",
    "system": "technology",
    # organization cluster
    "organization": "organization",
    "central_bank": "organization",
    "government": "organization",
    "government_agency": "organization",
    "institution": "organization",
    "exchange": "organization",
    # person
    "person": "person",
    # index
    "index": "index",
    # indicator cluster
    "indicator": "indicator",
    "metric": "indicator",
    # instrument cluster
    "instrument": "instrument",
    "etf": "instrument",
    "currency": "instrument",
    "currency_pair": "instrument",
    "fund": "instrument",
    "bond": "instrument",
    "asset": "instrument",
    # commodity
    "commodity": "commodity",
    # country cluster
    "country": "country",
    "region": "country",
    # sector cluster
    "sector": "sector",
    "market": "sector",
    # concept cluster
    "concept": "concept",
    "model": "concept",
    "method": "concept",
    "theme": "concept",
    "article_proposal": "concept",
    "event": "concept",
    "macro": "concept",
    # regulation
    "regulation": "regulation",
    # broker
    "broker": "broker",
    # product cluster
    "product": "product",
    "dataset": "product",
    "data_center": "product",
}

_VALID_ENTITY_TYPES: frozenset[str] = frozenset(
    {
        "company",
        "technology",
        "organization",
        "person",
        "index",
        "indicator",
        "instrument",
        "commodity",
        "country",
        "sector",
        "concept",
        "regulation",
        "broker",
        "product",
    }
)

# ---------------------------------------------------------------------------
# Default entity labels (13 individual labels, replaces the Entity label)
# AIDEV-NOTE: Wave6 (Issue #310) — Entity ラベル廃止、13個別ラベルに分解
# AIDEV-NOTE: Wave10 (Issue #316) — EntityType/InstrumentClass ノード削除完了
# ---------------------------------------------------------------------------

_DEFAULT_ENTITY_LABELS: list[str] = [
    "Company",
    "Technology",
    "Organization",
    "Person",
    "MarketIndex",
    "Indicator",
    "Instrument",
    "Commodity",
    "Country",
    "Concept",
    "Regulation",
    "Broker",
    "Product",
]

# Entity type → individual label mapping (14 canonical types → 13 labels)
# "sector" → Topic (handled separately), all others → individual labels
ENTITY_TYPE_TO_LABEL: dict[str, str] = {
    "company": "Company",
    "technology": "Technology",
    "organization": "Organization",
    "person": "Person",
    "index": "MarketIndex",
    "indicator": "Indicator",
    "instrument": "Instrument",
    "commodity": "Commodity",
    "country": "Country",
    "sector": "Concept",  # sector entities become Concept nodes in new schema
    "concept": "Concept",
    "regulation": "Regulation",
    "broker": "Broker",
    "product": "Product",
}

# ---------------------------------------------------------------------------
# Default constraints (v4.0: Entity ラベル廃止、個別ラベルの NODE KEY 制約に移行)
# AIDEV-NOTE: Entity.entity_id / Entity.entity_key UNIQUE 制約は削除済み
# ---------------------------------------------------------------------------

_DEFAULT_CONSTRAINTS: list[dict[str, str]] = [
    {"label": "Source", "property": "source_id", "type": "UNIQUE"},
    {"label": "Author", "property": "author_id", "type": "UNIQUE"},
    {"label": "Chunk", "property": "chunk_id", "type": "UNIQUE"},
    {"label": "Fact", "property": "fact_id", "type": "UNIQUE"},
    {"label": "Claim", "property": "claim_id", "type": "UNIQUE"},
    {"label": "FinancialDataPoint", "property": "datapoint_id", "type": "UNIQUE"},
    {"label": "FiscalPeriod", "property": "period_id", "type": "UNIQUE"},
    {"label": "Topic", "property": "topic_id", "type": "UNIQUE"},
    {"label": "Topic", "property": "topic_key", "type": "UNIQUE"},
    {"label": "Insight", "property": "insight_id", "type": "UNIQUE"},
    {"label": "Stance", "property": "stance_id", "type": "UNIQUE"},
    {"label": "Question", "property": "question_id", "type": "UNIQUE"},
    {"label": "SkillRun", "property": "skill_run_id", "type": "UNIQUE"},
]

# ---------------------------------------------------------------------------
# Default indices (from knowledge-graph-schema.yaml v3.0)
# ---------------------------------------------------------------------------

_DEFAULT_INDICES: list[dict[str, str]] = [
    {"label": "Fact", "property": "fact_type"},
    {"label": "Fact", "property": "as_of_date"},
    {"label": "Claim", "property": "claim_type"},
    {"label": "Claim", "property": "sentiment"},
    # Wave10: Entity.entity_type / Entity.ticker インデックスは削除済み（Entity ラベル廃止）
    {"label": "FinancialDataPoint", "property": "metric_name"},
    {"label": "FinancialDataPoint", "property": "is_estimate"},
    {"label": "FiscalPeriod", "property": "period_label"},
    {"label": "Insight", "property": "insight_type"},
    {"label": "Insight", "property": "status"},
    {"label": "Source", "property": "source_type"},
    {"label": "Source", "property": "source_hash"},
    {"label": "Stance", "property": "as_of_date"},
    {"label": "Stance", "property": "rating"},
    {"label": "Stance", "property": "sentiment"},
    {"label": "Question", "property": "question_type"},
    {"label": "Question", "property": "priority"},
    {"label": "Question", "property": "status"},
    {"label": "SkillRun", "property": "skill_name"},
    {"label": "SkillRun", "property": "status"},
    {"label": "SkillRun", "property": "start_at"},
    {"label": "SkillRun", "property": "command_source"},
]

# ---------------------------------------------------------------------------
# Default namespaces (from knowledge-graph-schema.yaml v3.0)
# ---------------------------------------------------------------------------

_DEFAULT_NAMESPACES: dict[str, Any] = {
    "kg_v2": {
        "description": "KG v2 schema nodes for knowledge graph",
        "labels": [
            "Source",
            "Author",
            "Chunk",
            "Fact",
            "Claim",
            # Wave10: Entity ラベル廃止 → Company/Technology/Organization 等13個別ラベルに移行
            "Company", "Technology", "Organization", "Person", "MarketIndex",
            "Indicator", "Instrument", "Commodity", "Country", "Concept",
            "Regulation", "Broker", "Product",
            "FinancialDataPoint",
            "FiscalPeriod",
            "Topic",
            "Insight",
            "Stance",
            "Question",
        ],
        "naming": "PascalCase",
    },
    "conversation": {
        "description": "Conversation history tracking nodes",
        "labels": [
            "ConversationSession",
            "ConversationTopic",
            "Project",
        ],
        "naming": "PascalCase",
    },
    "memory": {
        "description": "MCP Memory nodes (root + sub-labels)",
        "root_label": "Memory",
        "sub_labels": [
            "Decision",
            "ContentTheme",
            "Theme",
            "Implementation",
            "Phase",
            "Strategy",
            "CaseStudy",
            "Architecture",
            "Schema",
            "Status",
            "BusinessModel",
            "Workflow",
            "Research",
            "Todo",
            "Discussion",
            "SkillRun",
        ],
        "naming": "PascalCase",
    },
    "archived": {
        "description": "Archived legacy nodes",
        "labels": [
            "Archived",
        ],
        "naming": "PascalCase",
    },
}
