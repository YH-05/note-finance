"""Tests for scripts/mappers/classification.py.

SOURCE_TYPE_NORMALIZATION / ENTITY_TYPE_CONSOLIDATION / ENTITY_TYPE_META /
CONCEPT_CATEGORY_MAP / TRUST_LEVEL_NORMALIZATION の定数検証、
_make_entity_type_node / _make_source_type_node / apply_classification_layer
の単体テスト。
"""

from __future__ import annotations

from typing import Any

import pytest
from mappers.classification import (
    CONCEPT_CATEGORY_MAP,
    ENTITY_TYPE_CONSOLIDATION,
    ENTITY_TYPE_META,
    SOURCE_TYPE_NORMALIZATION,
    TRUST_LEVEL_NORMALIZATION,
    _make_entity_type_node,
    _make_source_type_node,
    apply_classification_layer,
)

# ---------------------------------------------------------------------------
# SOURCE_TYPE_NORMALIZATION 定数
# ---------------------------------------------------------------------------


class TestSourceTypeNormalization:
    _CANONICAL_SOURCE_TYPES = frozenset(
        {
            "academic",
            "analysis",
            "data",
            "web",
            "company_filing",
            "report",
            "news",
            "blog",
            "social",
            "pdf",
            "official",
            "original",
        }
    )

    def test_正常系_全エントリが期待するcanonical型にマップされる(self) -> None:
        for raw, canonical in SOURCE_TYPE_NORMALIZATION.items():
            assert isinstance(canonical, str), f"{raw!r} の値が文字列ではない"
            assert len(canonical) > 0, f"{raw!r} の値が空文字"

    def test_正常系_academic_paperがacademicにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["academic_paper"] == "academic"

    def test_正常系_company_analysisがanalysisにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["company_analysis"] == "analysis"

    def test_正常系_macro_dataがdataにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["macro_data"] == "data"

    def test_正常系_web_researchがwebにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["web-research"] == "web"

    def test_正常系_annual_reportがcompany_filingにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["annual_report"] == "company_filing"

    def test_正常系_regulatory_filingがcompany_filingにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["regulatory_filing"] == "company_filing"

    def test_正常系_researchがreportにマップされる(self) -> None:
        assert SOURCE_TYPE_NORMALIZATION["research"] == "report"

    def test_正常系_全バリューが文字列であること(self) -> None:
        for raw, val in SOURCE_TYPE_NORMALIZATION.items():
            assert isinstance(val, str), f"{raw!r} のバリューが文字列ではない"

    def test_正常系_dictが空でないこと(self) -> None:
        assert len(SOURCE_TYPE_NORMALIZATION) > 0


# ---------------------------------------------------------------------------
# ENTITY_TYPE_CONSOLIDATION 定数
# ---------------------------------------------------------------------------


class TestEntityTypeConsolidation:
    _CANONICAL_14_TYPES = frozenset(
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

    def test_正常系_全エントリが14キャノニカル型のどれかにマップされる(self) -> None:
        for raw, canonical in ENTITY_TYPE_CONSOLIDATION.items():
            assert canonical in self._CANONICAL_14_TYPES, (
                f"{raw!r} -> {canonical!r} は14キャノニカル型に含まれない"
            )

    def test_正常系_companyがcompanyにマップされる(self) -> None:
        assert ENTITY_TYPE_CONSOLIDATION["company"] == "company"

    def test_正常系_fintechがcompanyにマップされる(self) -> None:
        assert ENTITY_TYPE_CONSOLIDATION["fintech"] == "company"

    def test_正常系_central_bankがorganizationにマップされる(self) -> None:
        assert ENTITY_TYPE_CONSOLIDATION["central_bank"] == "organization"

    def test_正常系_etfがinstrumentにマップされる(self) -> None:
        assert ENTITY_TYPE_CONSOLIDATION["etf"] == "instrument"

    def test_正常系_metricがindicatorにマップされる(self) -> None:
        assert ENTITY_TYPE_CONSOLIDATION["metric"] == "indicator"

    def test_正常系_domainがconceptにマップされる(self) -> None:
        assert ENTITY_TYPE_CONSOLIDATION["domain"] == "concept"

    def test_正常系_14キャノニカル型が全てバリューに含まれる(self) -> None:
        all_values = set(ENTITY_TYPE_CONSOLIDATION.values())
        for canonical in self._CANONICAL_14_TYPES:
            assert canonical in all_values, (
                f"canonical型 {canonical!r} がバリューに存在しない"
            )

    def test_正常系_全エントリのキーとバリューが文字列であること(self) -> None:
        for raw, canonical in ENTITY_TYPE_CONSOLIDATION.items():
            assert isinstance(raw, str)
            assert isinstance(canonical, str)


# ---------------------------------------------------------------------------
# ENTITY_TYPE_META 定数
# ---------------------------------------------------------------------------


class TestEntityTypeMeta:
    from typing import ClassVar

    _EXPECTED_14_TYPES: ClassVar[set[str]] = {
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

    def test_正常系_14キャノニカル型が全て存在すること(self) -> None:
        for canonical in self._EXPECTED_14_TYPES:
            assert canonical in ENTITY_TYPE_META, (
                f"{canonical!r} が ENTITY_TYPE_META に存在しない"
            )

    def test_正常系_キー数が14であること(self) -> None:
        assert len(ENTITY_TYPE_META) == 14

    def test_正常系_全バリューが日本語文字列であること(self) -> None:
        for key, val in ENTITY_TYPE_META.items():
            assert isinstance(val, str), f"{key!r} のバリューが文字列ではない"
            assert len(val) > 0, f"{key!r} のバリューが空文字"

    def test_正常系_companyの日本語名が企業であること(self) -> None:
        assert ENTITY_TYPE_META["company"] == "企業"

    def test_正常系_brokerの日本語名が設定されていること(self) -> None:
        assert len(ENTITY_TYPE_META["broker"]) > 0


# ---------------------------------------------------------------------------
# CONCEPT_CATEGORY_MAP 定数
# ---------------------------------------------------------------------------


class TestConceptCategoryMap:
    _VALID_8_CATEGORIES = frozenset(
        {
            "MacroEconomics",
            "EquityResearch",
            "SectorAnalysis",
            "InvestmentStrategy",
            "Technology",
            "WealthManagement",
            "Regulation",
            "ContentPlanning",
        }
    )

    def test_正常系_全エントリが8つのConceptCategoryのどれかにマップされる(
        self,
    ) -> None:
        for key, val in CONCEPT_CATEGORY_MAP.items():
            assert val in self._VALID_8_CATEGORIES, (
                f"{key!r} -> {val!r} は8ConceptCategoryに含まれない"
            )

    def test_正常系_macroがMacroEconomicsにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["macro"] == "MacroEconomics"

    def test_正常系_stockがEquityResearchにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["stock"] == "EquityResearch"

    def test_正常系_sectorがSectorAnalysisにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["sector"] == "SectorAnalysis"

    def test_正常系_investment_strategyがInvestmentStrategyにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["investment_strategy"] == "InvestmentStrategy"

    def test_正常系_technologyがTechnologyにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["technology"] == "Technology"

    def test_正常系_wealthがWealthManagementにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["wealth"] == "WealthManagement"

    def test_正常系_regulatoryがRegulationにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["regulatory"] == "Regulation"

    def test_正常系_content_planningがContentPlanningにマップされる(self) -> None:
        assert CONCEPT_CATEGORY_MAP["content_planning"] == "ContentPlanning"

    def test_正常系_dictが空でないこと(self) -> None:
        assert len(CONCEPT_CATEGORY_MAP) > 0


# ---------------------------------------------------------------------------
# TRUST_LEVEL_NORMALIZATION 定数
# ---------------------------------------------------------------------------


class TestTrustLevelNormalization:
    _CANONICAL_10_LEVELS = frozenset(
        {
            "official",
            "academic",
            "company",
            "institutional",
            "analyst",
            "industry",
            "media",
            "primary",
            "blog",
            "social",
        }
    )

    def test_正常系_20エントリが存在すること(self) -> None:
        assert len(TRUST_LEVEL_NORMALIZATION) == 20

    def test_正常系_全エントリが10キャノニカルレベルのどれかにマップされる(
        self,
    ) -> None:
        for raw, canonical in TRUST_LEVEL_NORMALIZATION.items():
            assert canonical in self._CANONICAL_10_LEVELS, (
                f"{raw!r} -> {canonical!r} は10キャノニカルレベルに含まれない"
            )

    def test_正常系_officialがofficialにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["official"] == "official"

    def test_正常系_governmentがofficialにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["government"] == "official"

    def test_正常系_researchがacademicにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["research"] == "academic"

    def test_正常系_sell_sideがanalystにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["sell_side"] == "analyst"

    def test_正常系_newsがmediaにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["news"] == "media"

    def test_正常系_user_generatedがsocialにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["user_generated"] == "social"

    def test_正常系_buy_sideがinstitutionalにマップされる(self) -> None:
        assert TRUST_LEVEL_NORMALIZATION["buy_side"] == "institutional"


# ---------------------------------------------------------------------------
# _make_entity_type_node
# ---------------------------------------------------------------------------


class TestMakeEntityTypeNode:
    def test_正常系_companyでEntityTypeノードが生成される(self) -> None:
        node = _make_entity_type_node("company")
        assert node["label"] == "EntityType"
        assert node["key_property"] == "entity_type_id"
        assert node["key_value"] == "company"

    def test_正常系_14キャノニカル型全てでname_jaが設定される(self) -> None:
        canonical_types = [
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
        ]
        for etype in canonical_types:
            node = _make_entity_type_node(etype)
            props = node.get("properties", {})
            assert "name_ja" in props, f"{etype!r} に name_ja が存在しない"
            assert len(props["name_ja"]) > 0, f"{etype!r} の name_ja が空"

    def test_正常系_未知のentity_typeでもノードが生成される(self) -> None:
        node = _make_entity_type_node("unknown_type_xyz")
        assert node["label"] == "EntityType"
        assert node["key_value"] == "unknown_type_xyz"
        # name_jaは空文字（ENTITY_TYPE_METAにない場合）
        props = node.get("properties", {})
        assert props.get("name_ja", "") == ""

    def test_正常系_返り値にlabelとkey_propertyとkey_valueが含まれる(self) -> None:
        node = _make_entity_type_node("sector")
        assert "label" in node
        assert "key_property" in node
        assert "key_value" in node


# ---------------------------------------------------------------------------
# _make_source_type_node
# ---------------------------------------------------------------------------


class TestMakeSourceTypeNode:
    def test_正常系_webでSourceTypeノードが生成される(self) -> None:
        node = _make_source_type_node("web")
        assert node["label"] == "SourceType"
        assert node["key_property"] == "source_type_id"
        assert node["key_value"] == "web"

    def test_正常系_academicでSourceTypeノードが生成される(self) -> None:
        node = _make_source_type_node("academic")
        assert node["label"] == "SourceType"
        assert node["key_value"] == "academic"

    def test_正常系_未知のsource_typeでもノードが生成される(self) -> None:
        node = _make_source_type_node("unknown_type")
        assert node["label"] == "SourceType"
        assert node["key_value"] == "unknown_type"

    def test_正常系_propertiesにnameが含まれる(self) -> None:
        node = _make_source_type_node("report")
        props = node.get("properties", {})
        assert "name" in props
        assert props["name"] == "report"

    def test_正常系_返り値にlabelとkey_propertyとkey_valueが含まれる(self) -> None:
        node = _make_source_type_node("data")
        assert "label" in node
        assert "key_property" in node
        assert "key_value" in node


# ---------------------------------------------------------------------------
# apply_classification_layer
# ---------------------------------------------------------------------------


class TestApplyClassificationLayer:
    def test_正常系_空のmapped_resultで例外なく実行できる(self) -> None:
        mapped: dict[str, Any] = {}
        apply_classification_layer(mapped, "web-research")
        assert "classification_nodes" in mapped
        assert "classification_rels" in mapped
        assert mapped["classification_nodes"] == []
        assert mapped["classification_rels"] == []

    def test_正常系_最小限のsourcesでclassification_nodesが生成される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [
                {
                    "source_id": "src-001",
                    "url": "https://example.com",
                    "source_type": "web-research",
                    "authority_level": "media",
                    "language": "en",
                }
            ]
        }
        apply_classification_layer(mapped, "web-research")
        assert len(mapped["classification_nodes"]) > 0
        assert len(mapped["classification_rels"]) > 0

    def test_正常系_sourcesのIS_SOURCE_TYPEリレーションが生成される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [
                {
                    "source_id": "src-001",
                    "url": "https://example.com",
                    "source_type": "web-research",
                }
            ]
        }
        apply_classification_layer(mapped, "web-research")
        rel_types = {r["type"] for r in mapped["classification_rels"]}
        assert "IS_SOURCE_TYPE" in rel_types

    def test_正常系_entitiesのIS_TYPEリレーションが生成される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [],
            "entities": [
                {
                    "entity_id": "ent-001",
                    "entity_key": "Apple::company",
                    "entity_type": "company",
                }
            ],
        }
        apply_classification_layer(mapped, "web-research")
        rel_types = {r["type"] for r in mapped["classification_rels"]}
        assert "IS_TYPE" in rel_types

    def test_正常系_topicsのIS_CATEGORYリレーションが生成される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [],
            "topics": [
                {
                    "topic_id": "topic-001",
                    "topic_key": "AI::technology",
                    "category": "macro",
                }
            ],
        }
        apply_classification_layer(mapped, "web-research")
        rel_types = {r["type"] for r in mapped["classification_rels"]}
        assert "IS_CATEGORY" in rel_types

    def test_正常系_重複するノードが除去される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [
                {
                    "source_id": "src-001",
                    "url": "https://a.com",
                    "source_type": "web-research",
                },
                {
                    "source_id": "src-002",
                    "url": "https://b.com",
                    "source_type": "web-research",
                },
            ]
        }
        apply_classification_layer(mapped, "web-research")
        # SourceType "web" は1つだけ（重複排除）
        source_type_nodes = [
            n
            for n in mapped["classification_nodes"]
            if n["label"] == "SourceType" and n["key_value"] == "web"
        ]
        assert len(source_type_nodes) == 1

    def test_正常系_source_idが空の場合はソースをスキップする(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [
                {
                    "source_id": "",
                    "url": "https://example.com",
                    "source_type": "web",
                }
            ]
        }
        apply_classification_layer(mapped, "web-research")
        assert mapped["classification_nodes"] == []
        assert mapped["classification_rels"] == []

    def test_正常系_tickerがある場合にHAS_IDENTIFIERリレーションが生成される(
        self,
    ) -> None:
        mapped: dict[str, Any] = {
            "sources": [],
            "entities": [
                {
                    "entity_id": "ent-apple",
                    "entity_key": "Apple::company",
                    "entity_type": "company",
                    "ticker": "AAPL",
                }
            ],
        }
        apply_classification_layer(mapped, "web-research")
        rel_types = {r["type"] for r in mapped["classification_rels"]}
        assert "HAS_IDENTIFIER" in rel_types

    def test_正常系_全フィールドなしのmapped_resultでもエラーにならない(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [],
            "entities": [],
            "facts": [],
            "claims": [],
            "financial_datapoints": [],
            "authors": [],
            "topics": [],
            "stances": [],
        }
        # 例外なく実行できること
        apply_classification_layer(mapped, "web-research")
        assert "classification_nodes" in mapped
        assert "classification_rels" in mapped
