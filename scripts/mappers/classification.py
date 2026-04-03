"""mappers/classification.py — v3.0 分類レイヤー処理。

YAML SSoT の定数、分類ノードビルダー、_apply_classification_layer を提供する。
emit_research_queue.py の分類レイヤー処理を抽出し、再利用可能なモジュールとして提供する。

Usage
-----
::

    from mappers.classification import apply_classification_layer

    apply_classification_layer(mapped, command)
"""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlparse

from mappers.base import BaseMapper
from ontology_loader import load_consolidation_mapping

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (from emit_research_queue.py classification constants)
# ---------------------------------------------------------------------------

SOURCE_TYPE_NORMALIZATION: dict[str, str] = {
    "academic_paper": "academic",
    "academic-paper": "academic",
    "research_paper": "academic",
    "tower_company_analysis": "analysis",
    "company_analysis": "analysis",
    "digital_services_analysis": "analysis",
    "regulatory_analysis": "analysis",
    "political_analysis": "analysis",
    "macro_data": "data",
    "spectrum_data": "data",
    "web-research": "web",
    "annual_report": "company_filing",
    "regulatory_filing": "company_filing",
    "research": "report",
    "official": "report",
    "original": "report",
}
"""Maps source_type values to 12 canonical types for SourceType nodes."""

ENTITY_TYPE_CONSOLIDATION: dict[str, str] = load_consolidation_mapping()
"""Maps raw entity_types to 14 canonical types. SSoT: ontology_loader._ENTITY_TYPE_CONSOLIDATION."""

ENTITY_TYPE_META: dict[str, str] = {
    "company": "企業",
    "technology": "テクノロジー",
    "organization": "機関",
    "person": "人物",
    "index": "株価指数",
    "indicator": "経済指標",
    "instrument": "金融商品",
    "commodity": "コモディティ",
    "country": "国・地域",
    "sector": "セクター",
    "concept": "概念",
    "regulation": "規制・政策",
    "broker": "ブローカー",
    "product": "プロダクト",
}
"""EntityType name_ja metadata for 14 canonical types."""

DATAPOINT_TYPE_MAP: dict[bool, str] = {
    True: "estimate",
    False: "actual",
}
"""Maps is_estimate boolean to DataPointType name."""

CONCEPT_CATEGORY_MAP: dict[str, str] = {
    # MacroEconomics
    "macro": "MacroEconomics",
    "political": "MacroEconomics",
    "geopolitical": "MacroEconomics",
    "geopolitics": "MacroEconomics",
    # EquityResearch
    "stock": "EquityResearch",
    "earnings": "EquityResearch",
    "valuation": "EquityResearch",
    "equity_research": "EquityResearch",
    "competition": "EquityResearch",
    "competitive_analysis": "EquityResearch",
    "kpi": "EquityResearch",
    # SectorAnalysis
    "sector": "SectorAnalysis",
    "sector_analysis": "SectorAnalysis",
    "cross_sector": "SectorAnalysis",
    "industry-trend": "SectorAnalysis",
    "cost_competition": "SectorAnalysis",
    # InvestmentStrategy
    "investment_strategy": "InvestmentStrategy",
    "investment_framework": "InvestmentStrategy",
    "investment": "InvestmentStrategy",
    "institutional_investing": "InvestmentStrategy",
    "capital-allocation": "InvestmentStrategy",
    "fund_comparison": "InvestmentStrategy",
    "strategy": "InvestmentStrategy",
    # Technology
    "technology": "Technology",
    "ai": "Technology",
    "quantitative_finance": "Technology",
    "data_analysis": "Technology",
    # WealthManagement
    "wealth": "WealthManagement",
    "assets": "WealthManagement",
    "wealth-management": "WealthManagement",
    "asset-management": "WealthManagement",
    # Regulation
    "regulatory": "Regulation",
    "regulation": "Regulation",
    "governance": "Regulation",
    "corporate-action": "Regulation",
    # ContentPlanning
    "content_planning": "ContentPlanning",
    "reddit": "ContentPlanning",
    "theme": "ContentPlanning",
    # Fallback mappings from THEME_TO_CATEGORY output
    "finance": "InvestmentStrategy",
    "other": "MacroEconomics",
}
"""Maps 46+ topic.category values to 8 ConceptCategory names."""

CONCEPT_CATEGORY_META: dict[str, dict[str, str]] = {
    "MacroEconomics": {"name_ja": "マクロ経済", "layer": "What"},
    "EquityResearch": {"name_ja": "株式リサーチ", "layer": "What"},
    "SectorAnalysis": {"name_ja": "セクター分析", "layer": "What"},
    "InvestmentStrategy": {"name_ja": "投資戦略", "layer": "What"},
    "Technology": {"name_ja": "テクノロジー", "layer": "What"},
    "WealthManagement": {"name_ja": "資産形成", "layer": "What"},
    "Regulation": {"name_ja": "規制", "layer": "What"},
    "ContentPlanning": {"name_ja": "コンテンツ企画", "layer": "Meta"},
}
"""ConceptCategory node metadata (name_ja, layer)."""

TRUST_LEVEL_NORMALIZATION: dict[str, str] = {
    "official": "official",
    "academic": "academic",
    "company": "company",
    "institutional": "institutional",
    "analyst": "analyst",
    "industry": "industry",
    "media": "media",
    "primary": "primary",
    "blog": "blog",
    "social": "social",
    "government": "official",
    "regulatory": "official",
    "research": "academic",
    "peer_reviewed": "academic",
    "corporate": "company",
    "sell_side": "analyst",
    "buy_side": "institutional",
    "news": "media",
    "press": "media",
    "user_generated": "social",
}
"""Maps 20 authority level strings to 10 canonical TrustLevel names."""

TRUST_LEVEL_META: dict[str, dict[str, Any]] = {
    "official": {"name_ja": "公的機関", "rank": 1},
    "academic": {"name_ja": "学術", "rank": 2},
    "company": {"name_ja": "企業", "rank": 3},
    "institutional": {"name_ja": "機関投資家", "rank": 4},
    "analyst": {"name_ja": "アナリスト", "rank": 5},
    "industry": {"name_ja": "業界専門家", "rank": 6},
    "primary": {"name_ja": "一次情報", "rank": 7},
    "media": {"name_ja": "メディア", "rank": 8},
    "blog": {"name_ja": "ブログ", "rank": 9},
    "social": {"name_ja": "SNS", "rank": 10},
}
"""TrustLevel metadata."""

LANGUAGE_META: dict[str, str] = {
    "ja": "日本語",
    "en": "英語",
    "zh": "中国語",
    "ko": "韓国語",
}
"""Language code to name_ja mapping."""

PIPELINE_META: dict[str, dict[str, str]] = {
    "finance-news-workflow": {
        "description": "金融ニュース自動収集ワークフロー",
        "category": "news",
    },
    "wealth-scrape": {
        "description": "資産形成コンテンツスクレイピング",
        "category": "scrape",
    },
    "web-research": {
        "description": "アドホックWeb調査データ投入",
        "category": "research",
    },
    "pdf-archive": {
        "description": "PDF文書アーカイブ投入",
        "category": "archive",
    },
    "academic-fetch": {
        "description": "学術論文フェッチ",
        "category": "academic",
    },
    "pdf-extraction": {
        "description": "PDF構造化抽出",
        "category": "extraction",
    },
    "reddit-finance-topics": {
        "description": "Reddit金融コミュニティトピック発見",
        "category": "community",
    },
    "topic-discovery": {
        "description": "トピック自動発見",
        "category": "discovery",
    },
}
"""Pipeline node metadata (description, category)."""

AUTHOR_TYPE_META: dict[str, str] = {
    "analyst": "アナリスト",
    "sell_side": "セルサイドアナリスト",
    "buy_side": "バイサイドアナリスト",
    "journalist": "ジャーナリスト",
    "official": "公的機関",
    "researcher": "研究者",
    "blogger": "ブロガー",
    "editor": "編集者",
}
"""AuthorType name_ja metadata."""

FACT_TYPE_META: dict[str, str] = {
    "statistic": "統計",
    "financial_metric": "財務指標",
    "macro_indicator": "マクロ指標",
    "event": "イベント",
    "empirical": "実証データ",
    "regulatory": "規制",
    "market_data": "市場データ",
    "strategic": "戦略",
    "methodology": "方法論",
    "risk": "リスク",
}
"""FactType name_ja metadata."""

CLAIM_TYPE_META: dict[str, dict[str, str]] = {
    "fundamental": {"name_ja": "ファンダメンタル分析", "direction": "neutral"},
    "bullish": {"name_ja": "強気", "direction": "positive"},
    "bearish": {"name_ja": "弱気", "direction": "negative"},
    "technical": {"name_ja": "テクニカル分析", "direction": "neutral"},
    "risk_event": {"name_ja": "リスクイベント", "direction": "negative"},
    "policy_hawkish": {"name_ja": "タカ派", "direction": "negative"},
    "sector_rotation": {"name_ja": "セクターローテーション", "direction": "neutral"},
    "earnings_beat": {"name_ja": "決算上振れ", "direction": "positive"},
    "analyst_view": {"name_ja": "アナリスト見解", "direction": "neutral"},
    "political_risk": {"name_ja": "政治リスク", "direction": "negative"},
    "recommendation": {"name_ja": "推奨", "direction": "neutral"},
}
"""ClaimType node metadata (name_ja, direction)."""

DATAPOINT_TYPE_META: dict[str, str] = {
    "actual": "実績",
    "estimate": "会社予想",
    "forecast": "アナリスト予測",
    "consensus": "コンセンサス",
}
"""DataPointType name_ja metadata."""

V3_STRIP_FLAT_PROPS: bool = os.environ.get("GRAPH_QUEUE_V3_STRIP", "0") == "1"
"""When True, strip flat classification properties after post-processing."""


# ---------------------------------------------------------------------------
# URL domain extraction
# ---------------------------------------------------------------------------


def _extract_url_domain(url: str) -> str | None:
    """Extract the domain name from a URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        logger.debug("Failed to parse URL for domain extraction: %s", url)
        return None


# ---------------------------------------------------------------------------
# Classification node builders
# ---------------------------------------------------------------------------


def _make_classification_node(
    label: str,
    key_prop: str,
    key_value: str,
    **extra: Any,
) -> dict[str, Any]:
    """Build a classification node dict for graph-queue output."""
    props = {k: v for k, v in extra.items() if v is not None}
    return {
        "label": label,
        "key_property": key_prop,
        "key_value": key_value,
        "properties": props,
    }


def _make_source_type_node(name: str) -> dict[str, Any]:
    """Build a SourceType classification node."""
    return _make_classification_node("SourceType", "source_type_id", name, name=name)


def _make_domain_node(
    domain_name: str, *, base_url: str = "", default_language: str = ""
) -> dict[str, Any]:
    """Build a Domain classification node."""
    return _make_classification_node(
        "Domain",
        "domain_id",
        domain_name,
        name=domain_name,
        base_url=base_url,
        default_language=default_language,
    )


def _make_trust_level_node(name: str) -> dict[str, Any]:
    """Build a TrustLevel classification node."""
    meta = TRUST_LEVEL_META.get(name, {})
    return _make_classification_node(
        "TrustLevel",
        "trust_level_id",
        name,
        name=name,
        name_ja=meta.get("name_ja", ""),
        rank=meta.get("rank"),
    )


def _make_language_node(code: str) -> dict[str, Any]:
    """Build a Language classification node."""
    return _make_classification_node(
        "Language",
        "language_id",
        code,
        name=code,
        name_ja=LANGUAGE_META.get(code, ""),
    )


def _make_pipeline_node(pipeline_id: str) -> dict[str, Any]:
    """Build a Pipeline classification node."""
    meta = PIPELINE_META.get(pipeline_id, {})
    return _make_classification_node(
        "Pipeline",
        "pipeline_id",
        pipeline_id,
        name=pipeline_id,
        description=meta.get("description", ""),
        category=meta.get("category", ""),
    )


def _make_entity_type_node(name: str) -> dict[str, Any]:
    """Build an EntityType classification node."""
    return _make_classification_node(
        "EntityType",
        "entity_type_id",
        name,
        name=name,
        name_ja=ENTITY_TYPE_META.get(name, ""),
    )


def _make_identifier_node(
    identifier_id: str,
    *,
    id_type: str = "",
    value: str = "",
    scheme: str = "",
) -> dict[str, Any]:
    """Build an Identifier classification node."""
    return _make_classification_node(
        "Identifier",
        "identifier_id",
        identifier_id,
        type=id_type,
        value=value,
        scheme=scheme,
    )


def _make_fact_type_node(name: str) -> dict[str, Any]:
    """Build a FactType classification node."""
    return _make_classification_node(
        "FactType",
        "fact_type_id",
        name,
        name=name,
        name_ja=FACT_TYPE_META.get(name, ""),
    )


def _make_claim_type_node(name: str) -> dict[str, Any]:
    """Build a ClaimType classification node."""
    meta = CLAIM_TYPE_META.get(name, {})
    return _make_classification_node(
        "ClaimType",
        "claim_type_id",
        name,
        name=name,
        name_ja=meta.get("name_ja", ""),
        direction=meta.get("direction", ""),
    )


def _make_unit_of_measure_node(
    unit_id: str, *, name: str = "", symbol: str = "", dimension: str = ""
) -> dict[str, Any]:
    """Build a UnitOfMeasure classification node."""
    return _make_classification_node(
        "UnitOfMeasure",
        "unit_id",
        unit_id,
        name=name or unit_id,
        symbol=symbol,
        dimension=dimension,
    )


def _make_datapoint_type_node(name: str) -> dict[str, Any]:
    """Build a DataPointType classification node."""
    return _make_classification_node(
        "DataPointType",
        "datapoint_type_id",
        name,
        name=name,
        name_ja=DATAPOINT_TYPE_META.get(name, ""),
    )


def _make_concept_category_node(name: str) -> dict[str, Any]:
    """Build a ConceptCategory classification node."""
    meta = CONCEPT_CATEGORY_META.get(name, {})
    return _make_classification_node(
        "ConceptCategory",
        "concept_category_id",
        name,
        name=name,
        name_ja=meta.get("name_ja", ""),
        layer=meta.get("layer", ""),
    )


def _make_author_type_node(name: str) -> dict[str, Any]:
    """Build an AuthorType classification node."""
    return _make_classification_node(
        "AuthorType",
        "author_type_id",
        name,
        name=name,
        name_ja=AUTHOR_TYPE_META.get(name, ""),
    )


def _make_classification_rel(
    rel_type: str,
    from_id: str,
    to_id: str,
) -> dict[str, str]:
    """Build a classification relation dict."""
    return {"type": rel_type, "from_id": from_id, "to_id": to_id}


# ---------------------------------------------------------------------------
# Classification layer post-processor (v3.0)
# ---------------------------------------------------------------------------


def apply_classification_layer(  # noqa: PLR0912, PLR0915
    mapped: dict[str, Any],
    command: str,
) -> None:
    """Apply v3.0 classification layer to mapper output (in-place).

    Parameters
    ----------
    mapped : dict[str, Any]
        Output from a mapper function (mutated in-place).
    command : str
        Source command name (used for Pipeline node generation).
    """
    classification_nodes: list[dict[str, Any]] = []
    classification_rels: list[dict[str, str]] = []
    seen_nodes: set[tuple[str, str]] = set()

    def _add_node(node: dict[str, Any]) -> None:
        key = (node["label"], node["key_value"])
        if key not in seen_nodes:
            seen_nodes.add(key)
            classification_nodes.append(node)

    def _add_rel(rel: dict[str, str]) -> None:
        classification_rels.append(rel)

    # Sources -> SourceType, Domain, TrustLevel, Language, Pipeline
    for source in mapped.get("sources", []):
        source_id = source.get("source_id", "")
        if not source_id:
            continue

        raw_source_type = source.get("source_type", "")
        if raw_source_type:
            canonical_st: str = (
                SOURCE_TYPE_NORMALIZATION.get(raw_source_type) or raw_source_type
            )
            _add_node(_make_source_type_node(canonical_st))
            _add_rel(
                _make_classification_rel("IS_SOURCE_TYPE", source_id, canonical_st)
            )

        url = source.get("url", "")
        domain_name = _extract_url_domain(url)
        if domain_name:
            _add_node(_make_domain_node(domain_name, base_url=f"https://{domain_name}"))
            _add_rel(_make_classification_rel("FROM_DOMAIN", source_id, domain_name))

        raw_authority = source.get("authority_level", "")
        if raw_authority:
            canonical_tl = TRUST_LEVEL_NORMALIZATION.get(raw_authority, raw_authority)
            if canonical_tl in TRUST_LEVEL_META:
                _add_node(_make_trust_level_node(canonical_tl))
                _add_rel(_make_classification_rel("RATED_AS", source_id, canonical_tl))
            else:
                logger.debug(
                    "Unknown authority_level, skipping TrustLevel: %s", raw_authority
                )

        language = source.get("language", "")
        if language:
            _add_node(_make_language_node(language))
            _add_rel(_make_classification_rel("IN_LANGUAGE", source_id, language))

        _add_node(_make_pipeline_node(command))
        _add_rel(_make_classification_rel("INGESTED_VIA", source_id, command))

    # Entities -> EntityType, Identifier
    # v4.0: entity_key 廃止。entity_id または name を ref_id として使用
    for entity in mapped.get("entities", []):
        entity_id = entity.get("entity_id", "")
        # v4.0: entity_key 廃止。ref_id は entity_id を使用
        ref_id = entity_id
        if not ref_id:
            continue

        raw_etype = entity.get("entity_type", "")
        if raw_etype:
            canonical_etype: str = ENTITY_TYPE_CONSOLIDATION.get(raw_etype) or raw_etype
            _add_node(_make_entity_type_node(canonical_etype))
            _add_rel(_make_classification_rel("IS_TYPE", ref_id, canonical_etype))

        ticker = entity.get("ticker")
        if ticker:
            id_key = f"ticker:{ticker}"
            _add_node(
                _make_identifier_node(
                    id_key, id_type="ticker", value=ticker, scheme="exchange"
                )
            )
            _add_rel(_make_classification_rel("HAS_IDENTIFIER", ref_id, id_key))

    # Facts -> FactType
    for fact in mapped.get("facts", []):
        fact_id = fact.get("fact_id", "")
        if not fact_id:
            continue

        raw_fact_type = fact.get("fact_type", "")
        if raw_fact_type:
            _add_node(_make_fact_type_node(raw_fact_type))
            _add_rel(_make_classification_rel("IS_FACT_TYPE", fact_id, raw_fact_type))

    # Claims -> ClaimType
    for claim in mapped.get("claims", []):
        claim_id = claim.get("claim_id", "")
        if not claim_id:
            continue

        raw_claim_type = claim.get("claim_type", "")
        if raw_claim_type:
            _add_node(_make_claim_type_node(raw_claim_type))
            _add_rel(
                _make_classification_rel("IS_CLAIM_TYPE", claim_id, raw_claim_type)
            )

    # FinancialDataPoints -> UnitOfMeasure, DataPointType
    for dp in mapped.get("financial_datapoints", []):
        dp_id = dp.get("datapoint_id", "")
        if not dp_id:
            continue

        unit = dp.get("unit", "")
        if unit:
            _add_node(
                _make_unit_of_measure_node(unit, name=unit, dimension="monetary_value")
            )
            _add_rel(_make_classification_rel("IN_UNIT", dp_id, unit))

        dp_currency = dp.get("currency")
        if dp_currency and dp_currency != unit:
            _add_node(
                _make_unit_of_measure_node(
                    dp_currency, name=dp_currency, dimension="currency"
                )
            )
            _add_rel(_make_classification_rel("IN_UNIT", dp_id, dp_currency))

        is_estimate = dp.get("is_estimate")
        if is_estimate is not None:
            dp_type_name = DATAPOINT_TYPE_MAP.get(bool(is_estimate), "actual")
            _add_node(_make_datapoint_type_node(dp_type_name))
            _add_rel(_make_classification_rel("IS_DATAPOINT_TYPE", dp_id, dp_type_name))

    # Authors -> AuthorType
    for author in mapped.get("authors", []):
        author_id = author.get("author_id", "")
        if not author_id:
            continue

        raw_author_type = author.get("author_type", "")
        if raw_author_type:
            _add_node(_make_author_type_node(raw_author_type))
            _add_rel(
                _make_classification_rel("IS_AUTHOR_TYPE", author_id, raw_author_type)
            )

        org_name = author.get("organization")
        if org_name:
            entity_match = None
            for ent in mapped.get("entities", []):
                if ent.get("name") == org_name:
                    # v4.0: entity_key 廃止。entity_id を使用
                    entity_match = ent.get("entity_id")
                    break
            if entity_match:
                _add_rel(
                    _make_classification_rel("AFFILIATED_WITH", author_id, entity_match)
                )

    # Topics -> ConceptCategory
    for topic in mapped.get("topics", []):
        topic_id = topic.get("topic_id", "")
        topic_key = topic.get("topic_key", "")
        ref_id = topic_key or topic_id
        if not ref_id:
            continue

        raw_category = topic.get("category", "")
        if raw_category:
            concept_name = CONCEPT_CATEGORY_MAP.get(raw_category)
            if concept_name:
                _add_node(_make_concept_category_node(concept_name))
                _add_rel(_make_classification_rel("IS_CATEGORY", ref_id, concept_name))

    # Stances -> UnitOfMeasure (currency)
    for stance in mapped.get("stances", []):
        stance_id = stance.get("stance_id", "")
        if not stance_id:
            continue

        currency = stance.get("target_price_currency")
        if currency:
            _add_node(
                _make_unit_of_measure_node(
                    currency, name=currency, dimension="currency"
                )
            )
            _add_rel(_make_classification_rel("IN_UNIT", stance_id, currency))

    if V3_STRIP_FLAT_PROPS:
        _strip_flat_classification_props(mapped)

    mapped["classification_nodes"] = classification_nodes
    mapped["classification_rels"] = classification_rels

    logger.info(
        "Classification layer applied: %d nodes, %d rels",
        len(classification_nodes),
        len(classification_rels),
    )


# Alias for backward compatibility with emit_research_queue.py
_apply_classification_layer = apply_classification_layer


def _strip_flat_classification_props(mapped: dict[str, Any]) -> None:  # noqa: PLR0912
    """Strip flat classification properties from node dicts."""
    source_strip_keys = {"source_type", "authority_level", "language"}
    entity_strip_keys = {"entity_type"}
    fact_strip_keys = {"fact_type"}
    claim_strip_keys = {"claim_type"}
    dp_strip_keys = {"is_estimate", "currency", "unit"}
    author_strip_keys = {"author_type", "organization"}
    stance_strip_keys = {"target_price_currency"}

    for source in mapped.get("sources", []):
        for k in source_strip_keys:
            source.pop(k, None)
    for entity in mapped.get("entities", []):
        for k in entity_strip_keys:
            entity.pop(k, None)
    for fact in mapped.get("facts", []):
        for k in fact_strip_keys:
            fact.pop(k, None)
    for claim in mapped.get("claims", []):
        for k in claim_strip_keys:
            claim.pop(k, None)
    for dp in mapped.get("financial_datapoints", []):
        for k in dp_strip_keys:
            dp.pop(k, None)
    for author in mapped.get("authors", []):
        for k in author_strip_keys:
            author.pop(k, None)
    for stance in mapped.get("stances", []):
        for k in stance_strip_keys:
            stance.pop(k, None)

    logger.debug("Stripped flat classification properties from mapped data")


def get_schema_version() -> str:
    """Get schema version from YAML SSoT via ontology_loader.

    v4.0: ontology.yaml の schema_version フィールドを参照。

    Returns
    -------
    str
        Schema version string (e.g. "research-4.0"). Falls back to "4.0" on error.
    """
    try:
        import sys
        from pathlib import Path

        _scripts_dir = str(Path(__file__).resolve().parent.parent)
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        from ontology_loader import _DEFAULT_ONTOLOGY_PATH, _load_yaml

        data = _load_yaml(_DEFAULT_ONTOLOGY_PATH)
        return str(data.get("schema_version", "4.0"))
    except Exception as exc:
        logger.warning("Failed to load schema version from YAML: %s", exc)
        return "4.0"
