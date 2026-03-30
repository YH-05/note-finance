"""Tests for scripts/mappers/base.py.

BaseMapper 抽象クラスの単体テスト。
load_yaml_ssot キャッシュ / validate_schema バリデーション /
build_result リグレッション / ChunkProcessingContext /
build_entity_nodes / build_fact_nodes / build_claim_nodes /
build_chunk_nodes / postprocess / get_extra_labels を検証する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
import yaml
from mappers.base import BaseMapper, ChunkProcessingContext

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Concrete subclass for testing
# ---------------------------------------------------------------------------


class _ConcreteMapper(BaseMapper):
    """テスト用具体実装 — map() は入力をそのまま返す。"""

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return self.build_result(input_data, "test")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_yaml_cache() -> None:
    """各テスト前後に YAML キャッシュをクリアする。"""
    BaseMapper._yaml_cache = None
    yield
    BaseMapper._yaml_cache = None


@pytest.fixture
def minimal_schema_yaml(tmp_path: Path) -> Path:
    """テスト用最小 YAML スキーマファイルを生成する。"""
    schema = {
        "version": "3.0",
        "consolidation_rules": {
            "entity_type": {
                "mapping": {
                    "company": "company",
                    "fintech": "company",
                    "technology": "technology",
                    "organization": "organization",
                    "central_bank": "organization",
                    "person": "person",
                    "index": "index",
                    "indicator": "indicator",
                    "metric": "indicator",
                    "instrument": "instrument",
                    "etf": "instrument",
                    "commodity": "commodity",
                    "country": "country",
                    "region": "country",
                    "sector": "sector",
                    "market": "sector",
                    "concept": "concept",
                    "regulation": "regulation",
                    "broker": "broker",
                    "product": "product",
                    "domain": "concept",
                }
            }
        },
        "enum_validations": {
            "entity_type": {
                "values": [
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
            },
            "source_type": {"values": ["web", "news", "pdf", "original", "blog"]},
        },
        "source_type_normalization": {
            "mapping": {
                "web-research": "web",
                "annual_report": "pdf",
                "news_article": "news",
                "blog_post": "blog",
            }
        },
        "multilabel_types": {
            "entity_labels": {
                "labels": {
                    "Company": {"name_ja": "企業"},
                    "Technology": {"name_ja": "テクノロジー"},
                    "Organization": {"name_ja": "機関"},
                    "Person": {"name_ja": "人物"},
                    "MarketIndex": {"name_ja": "株価指数"},
                    "Indicator": {"name_ja": "経済指標"},
                    "Instrument": {"name_ja": "金融商品"},
                    "Commodity": {"name_ja": "コモディティ"},
                    "Country": {"name_ja": "国・地域"},
                    "Sector": {"name_ja": "セクター"},
                    "Concept": {"name_ja": "概念"},
                    "Regulation": {"name_ja": "規制・政策"},
                    "Broker": {"name_ja": "ブローカー"},
                    "Product": {"name_ja": "プロダクト"},
                }
            }
        },
    }
    yaml_path = tmp_path / "knowledge-graph-schema.yaml"
    yaml_path.write_text(yaml.dump(schema, allow_unicode=True), encoding="utf-8")
    return yaml_path


# ---------------------------------------------------------------------------
# Tests: ChunkProcessingContext
# ---------------------------------------------------------------------------


class TestChunkProcessingContext:
    def test_正常系_デフォルト値で初期化できる(self) -> None:
        ctx = ChunkProcessingContext()
        assert ctx.seen_entity_keys == set()
        assert ctx.entity_name_to_id == {}
        assert ctx.entity_name_to_ticker == {}
        assert ctx.seen_period_ids == set()
        assert ctx.seen_author_keys == set()
        assert ctx.author_name_to_id == {}

    def test_正常系_フィールドを更新できる(self) -> None:
        ctx = ChunkProcessingContext()
        ctx.seen_entity_keys.add("Apple::company")
        ctx.entity_name_to_id["Apple"] = "entity-001"
        assert "Apple::company" in ctx.seen_entity_keys
        assert ctx.entity_name_to_id["Apple"] == "entity-001"


# ---------------------------------------------------------------------------
# Tests: load_yaml_ssot
# ---------------------------------------------------------------------------


class TestLoadYamlSsot:
    def test_正常系_YAMLを読み込める(self, minimal_schema_yaml: Path) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            schema = BaseMapper.load_yaml_ssot()
        assert schema["version"] == "3.0"
        assert "consolidation_rules" in schema

    def test_正常系_2回目以降はキャッシュを返す(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            first = BaseMapper.load_yaml_ssot()
            second = BaseMapper.load_yaml_ssot()
        assert first is second  # 同じオブジェクト

    def test_正常系_ファイル読み込みは1回のみ(
        self, minimal_schema_yaml: Path, tmp_path: Path
    ) -> None:
        """2回呼び出しても yaml.safe_load は1回しか呼ばれないことをキャッシュで確認。"""
        with (
            patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml),
            patch("yaml.safe_load", wraps=yaml.safe_load) as mock_safe_load,
        ):
            BaseMapper.load_yaml_ssot()
            BaseMapper.load_yaml_ssot()
            # キャッシュにより2回目は yaml.safe_load が呼ばれないことを確認
            assert mock_safe_load.call_count == 1

    def test_異常系_ファイルが存在しない場合FileNotFoundError(
        self, tmp_path: Path
    ) -> None:
        nonexistent = tmp_path / "nonexistent.yaml"
        with (
            patch("mappers.base._SCHEMA_YAML_PATH", nonexistent),
            pytest.raises(FileNotFoundError, match=r"knowledge-graph-schema\.yaml"),
        ):
            BaseMapper.load_yaml_ssot()


# ---------------------------------------------------------------------------
# Tests: validate_schema
# ---------------------------------------------------------------------------


class TestValidateSchema:
    def test_正常系_有効なentity_typeはエラーなし(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            # should not raise
            BaseMapper.validate_schema(entity_type="company")
            BaseMapper.validate_schema(entity_type="technology")
            BaseMapper.validate_schema(entity_type="product")

    def test_正常系_有効なsource_typeはエラーなし(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            BaseMapper.validate_schema(source_type="web")
            BaseMapper.validate_schema(source_type="pdf")
            BaseMapper.validate_schema(source_type="blog")

    def test_正常系_Noneはスキップ(self, minimal_schema_yaml: Path) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            BaseMapper.validate_schema(entity_type=None, source_type=None)

    def test_異常系_不正なentity_typeでValueError(
        self, minimal_schema_yaml: Path
    ) -> None:
        with (
            patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml),
            pytest.raises(ValueError, match="Invalid entity_type"),
        ):
            BaseMapper.validate_schema(entity_type="invalid_type")

    def test_異常系_不正なsource_typeでValueError(
        self, minimal_schema_yaml: Path
    ) -> None:
        with (
            patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml),
            pytest.raises(ValueError, match="Invalid source_type"),
        ):
            BaseMapper.validate_schema(source_type="invalid_source")

    def test_異常系_生source_typeはValueError(self, minimal_schema_yaml: Path) -> None:
        """正規化前の生 source_type（例: web-research）はバリデーション失敗。"""
        with (
            patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml),
            pytest.raises(ValueError, match="Invalid source_type"),
        ):
            BaseMapper.validate_schema(source_type="web-research")


# ---------------------------------------------------------------------------
# Tests: build_result (regression against _mapped_result)
# ---------------------------------------------------------------------------


class TestBuildResult:
    def test_正常系_全キーが含まれる(self) -> None:
        data = {"session_id": "sess-001"}
        result = BaseMapper.build_result(data, "test-batch")
        expected_keys = {
            "session_id",
            "batch_label",
            "sources",
            "claims",
            "facts",
            "topics",
            "entities",
            "chunks",
            "financial_datapoints",
            "fiscal_periods",
            "authors",
            "stances",
            "questions",
            "relations",
            "classification_nodes",
            "classification_rels",
        }
        assert set(result.keys()) == expected_keys

    def test_正常系_session_idが正しく設定される(self) -> None:
        data = {"session_id": "sess-xyz"}
        result = BaseMapper.build_result(data, "label")
        assert result["session_id"] == "sess-xyz"

    def test_正常系_batch_labelが正しく設定される(self) -> None:
        data = {}
        result = BaseMapper.build_result(data, "pdf-extraction")
        assert result["batch_label"] == "pdf-extraction"

    def test_正常系_省略時はデフォルト空値(self) -> None:
        data = {}
        result = BaseMapper.build_result(data, "x")
        assert result["sources"] == []
        assert result["claims"] == []
        assert result["relations"] == {}
        assert result["classification_nodes"] == []

    def test_正常系_ノードリストが正しく設定される(self) -> None:
        data = {"session_id": "s1"}
        sources = [{"source_id": "s001"}]
        entities = [{"entity_id": "e001"}]
        result = BaseMapper.build_result(
            data, "test", sources=sources, entities=entities
        )
        assert result["sources"] == sources
        assert result["entities"] == entities

    def test_正常系_mapped_resultと同一出力(self) -> None:
        """_mapped_result との互換性リグレッションテスト。"""
        data = {"session_id": "sess-regression"}
        sources = [{"source_id": "src-001", "title": "Test"}]
        facts = [{"fact_id": "fact-001", "content": "Some fact"}]

        result = BaseMapper.build_result(
            data, "regression-test", sources=sources, facts=facts
        )

        assert result["session_id"] == "sess-regression"
        assert result["batch_label"] == "regression-test"
        assert result["sources"] == sources
        assert result["facts"] == facts
        assert result["claims"] == []
        assert result["topics"] == []
        assert result["entities"] == []
        assert result["chunks"] == []
        assert result["financial_datapoints"] == []
        assert result["fiscal_periods"] == []
        assert result["authors"] == []
        assert result["stances"] == []
        assert result["questions"] == []
        assert result["relations"] == {}
        assert result["classification_nodes"] == []
        assert result["classification_rels"] == []


# ---------------------------------------------------------------------------
# Tests: build_entity_nodes
# ---------------------------------------------------------------------------


class TestBuildEntityNodes:
    def _make_entity_id(self, name: str, entity_type: str) -> str:
        return f"eid-{name}-{entity_type}"

    def test_正常系_Entityノードが生成される(self) -> None:
        chunk = {
            "entities": [
                {"name": "Apple", "entity_type": "company", "ticker": "AAPL"},
            ]
        }
        seen_keys: set[str] = set()
        name_to_id: dict[str, str] = {}
        name_to_ticker: dict[str, str] = {}

        entities = BaseMapper.build_entity_nodes(
            chunk,
            seen_keys,
            name_to_id,
            name_to_ticker,
            generate_entity_id_fn=self._make_entity_id,
        )

        assert len(entities) == 1
        assert entities[0]["name"] == "Apple"
        assert entities[0]["entity_type"] == "company"
        assert entities[0]["ticker"] == "AAPL"
        assert entities[0]["entity_key"] == "Apple::company"
        assert "Apple::company" in seen_keys
        assert name_to_id["Apple"] == "eid-Apple-company"
        assert name_to_ticker["Apple"] == "AAPL"

    def test_正常系_重複エンティティはスキップされる(self) -> None:
        chunk = {
            "entities": [
                {"name": "Apple", "entity_type": "company"},
                {"name": "Apple", "entity_type": "company"},  # duplicate
            ]
        }
        seen_keys: set[str] = set()
        entities = BaseMapper.build_entity_nodes(
            chunk,
            seen_keys,
            {},
            {},
            generate_entity_id_fn=self._make_entity_id,
        )
        assert len(entities) == 1

    def test_正常系_クロスチャンク重複排除(self) -> None:
        seen_keys: set[str] = {"Apple::company"}  # pre-populated
        chunk = {
            "entities": [
                {"name": "Apple", "entity_type": "company"},
            ]
        }
        entities = BaseMapper.build_entity_nodes(
            chunk,
            seen_keys,
            {},
            {},
            generate_entity_id_fn=self._make_entity_id,
        )
        assert entities == []

    def test_正常系_entity_typeは小文字に正規化される(self) -> None:
        chunk = {
            "entities": [
                {"name": "Tesla", "entity_type": "COMPANY"},
            ]
        }
        entities = BaseMapper.build_entity_nodes(
            chunk,
            set(),
            {},
            {},
            generate_entity_id_fn=self._make_entity_id,
        )
        assert entities[0]["entity_type"] == "company"

    def test_エッジケース_entitiesが空の場合は空リスト(self) -> None:
        chunk: dict[str, Any] = {}
        entities = BaseMapper.build_entity_nodes(
            chunk,
            set(),
            {},
            {},
            generate_entity_id_fn=self._make_entity_id,
        )
        assert entities == []


# ---------------------------------------------------------------------------
# Tests: build_fact_nodes
# ---------------------------------------------------------------------------


class TestBuildFactNodes:
    def _make_fact_id(self, content: str) -> str:
        return f"fact-{hash(content) % 10000:04d}"

    def _resolve_entity_rels(
        self,
        about: list[Any],
        from_id: str,
        rel_type: str,
        name_to_id: dict[str, str],
    ) -> list[dict[str, str]]:
        result = []
        for item in about:
            name = item.get("name", "") if isinstance(item, dict) else item
            resolved = name_to_id.get(name)
            if resolved:
                result.append({"from_id": from_id, "to_id": resolved, "type": rel_type})
        return result

    def test_正常系_Factノードが生成される(self) -> None:
        chunk = {
            "facts": [{"content": "Apple revenue grew 10%", "fact_type": "empirical"}]
        }
        facts, sf, ef, _fe = BaseMapper.build_fact_nodes(
            chunk,
            "src-001",
            "chunk-001",
            {},
            generate_fact_id_fn=self._make_fact_id,
            fact_type_meta={"empirical": True, "quantitative": True},
            resolve_entity_rels_fn=self._resolve_entity_rels,
        )
        assert len(facts) == 1
        assert facts[0]["fact_type"] == "empirical"
        assert len(sf) == 1
        assert sf[0]["type"] == "STATES_FACT"
        assert len(ef) == 1
        assert ef[0]["type"] == "EXTRACTED_FROM"

    def test_正常系_不正なfact_typeはempiricalにフォールバック(self) -> None:
        chunk = {"facts": [{"content": "Some fact", "fact_type": "unknown_type"}]}
        facts, _, _, _ = BaseMapper.build_fact_nodes(
            chunk,
            "src-001",
            "chunk-001",
            {},
            generate_fact_id_fn=self._make_fact_id,
            fact_type_meta={"empirical": True},
            resolve_entity_rels_fn=self._resolve_entity_rels,
        )
        assert facts[0]["fact_type"] == "empirical"

    def test_正常系_about_entities未設定時はチャンク内エンティティにフォールバック(
        self,
    ) -> None:
        chunk = {
            "entities": [{"name": "Apple"}],
            "facts": [{"content": "Apple revenue grew", "fact_type": "empirical"}],
        }
        name_to_id = {"Apple": "e-001"}
        _, _, _, fe = BaseMapper.build_fact_nodes(
            chunk,
            "src-001",
            "chunk-001",
            name_to_id,
            generate_fact_id_fn=self._make_fact_id,
            fact_type_meta={"empirical": True},
            resolve_entity_rels_fn=self._resolve_entity_rels,
        )
        assert any(r["to_id"] == "e-001" for r in fe)

    def test_エッジケース_factsが空の場合は空タプル(self) -> None:
        chunk: dict[str, Any] = {}
        facts, sf, ef, fe = BaseMapper.build_fact_nodes(
            chunk,
            "src-001",
            "chunk-001",
            {},
            generate_fact_id_fn=self._make_fact_id,
            fact_type_meta={"empirical": True},
            resolve_entity_rels_fn=self._resolve_entity_rels,
        )
        assert facts == []
        assert sf == []
        assert ef == []
        assert fe == []


# ---------------------------------------------------------------------------
# Tests: build_claim_nodes
# ---------------------------------------------------------------------------


class TestBuildClaimNodes:
    def _make_claim_id(self, content: str) -> str:
        return f"claim-{hash(content) % 10000:04d}"

    def _resolve_entity_rels(
        self,
        about: list[Any],
        from_id: str,
        rel_type: str,
        name_to_id: dict[str, str],
    ) -> list[dict[str, str]]:
        result = []
        for item in about:
            name = item.get("name", "") if isinstance(item, dict) else item
            resolved = name_to_id.get(name)
            if resolved:
                result.append({"from_id": from_id, "to_id": resolved, "type": rel_type})
        return result

    def test_正常系_Claimノードが生成される(self) -> None:
        chunk = {
            "claims": [
                {
                    "content": "Apple will grow",
                    "claim_type": "outlook",
                    "sentiment": "positive",
                }
            ]
        }
        claims, sc, ec, _ce = BaseMapper.build_claim_nodes(
            chunk,
            "src-001",
            "chunk-001",
            {},
            generate_claim_id_fn=self._make_claim_id,
            resolve_entity_rels_fn=self._resolve_entity_rels,
        )
        assert len(claims) == 1
        assert claims[0]["category"] == "pdf-claim"
        assert claims[0]["claim_type"] == "outlook"
        assert claims[0]["sentiment"] == "positive"
        assert sc[0]["type"] == "MAKES_CLAIM"
        assert ec[0]["type"] == "EXTRACTED_FROM"

    def test_エッジケース_claimsが空の場合は空タプル(self) -> None:
        chunk: dict[str, Any] = {}
        claims, sc, ec, ce = BaseMapper.build_claim_nodes(
            chunk,
            "src-001",
            "chunk-001",
            {},
            generate_claim_id_fn=self._make_claim_id,
            resolve_entity_rels_fn=self._resolve_entity_rels,
        )
        assert claims == []
        assert sc == []
        assert ec == []
        assert ce == []


# ---------------------------------------------------------------------------
# Tests: build_chunk_nodes
# ---------------------------------------------------------------------------


class TestBuildChunkNodes:
    def _make_chunk_id(self, source_hash: str, chunk_index: int) -> str:
        return f"chunk-{source_hash[:8]}-{chunk_index}"

    def test_正常系_Chunkノードが生成される(self) -> None:
        chunk = {
            "chunk_index": 0,
            "section_title": "Introduction",
            "content": "This is the introduction.",
        }
        chunk_node, chunk_id, rels = BaseMapper.build_chunk_nodes(
            chunk,
            "abc123hash",
            "src-001",
            generate_chunk_id_fn=self._make_chunk_id,
        )
        assert chunk_node["chunk_index"] == 0
        assert chunk_node["section_title"] == "Introduction"
        assert chunk_node["content"] == "This is the introduction."
        assert chunk_id == "chunk-abc123ha-0"
        assert len(rels) == 1
        assert rels[0]["type"] == "CONTAINS_CHUNK"
        assert rels[0]["from_id"] == "src-001"
        assert rels[0]["to_id"] == chunk_id

    def test_正常系_chunk_indexデフォルトは0(self) -> None:
        chunk: dict[str, Any] = {"content": "content"}
        chunk_node, _chunk_id, _ = BaseMapper.build_chunk_nodes(
            chunk,
            "hash001",
            "src-001",
            generate_chunk_id_fn=self._make_chunk_id,
        )
        assert chunk_node["chunk_index"] == 0

    def test_正常系_section_titleがNoneの場合(self) -> None:
        chunk = {"chunk_index": 1, "content": ""}
        chunk_node, _, _ = BaseMapper.build_chunk_nodes(
            chunk,
            "hash001",
            "src-001",
            generate_chunk_id_fn=self._make_chunk_id,
        )
        assert chunk_node["section_title"] is None


# ---------------------------------------------------------------------------
# Tests: get_extra_labels
# ---------------------------------------------------------------------------


class TestGetExtraLabels:
    def test_正常系_companyはCompanyラベルを返す(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            labels = BaseMapper.get_extra_labels("company")
        assert labels == ["Company"]

    def test_正常系_indexはMarketIndexラベルを返す(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            labels = BaseMapper.get_extra_labels("index")
        assert labels == ["MarketIndex"]

    def test_正常系_organizationはOrganizationラベルを返す(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            labels = BaseMapper.get_extra_labels("organization")
        assert labels == ["Organization"]

    def test_エッジケース_不明なentity_typeは空リスト(
        self, minimal_schema_yaml: Path
    ) -> None:
        with patch("mappers.base._SCHEMA_YAML_PATH", minimal_schema_yaml):
            labels = BaseMapper.get_extra_labels("unknown_type")
        assert labels == []


# ---------------------------------------------------------------------------
# Tests: postprocess
# ---------------------------------------------------------------------------


class TestPostprocess:
    """postprocess が _apply_classification_layer と同一動作を行うことを検証。"""

    def _make_helpers(self) -> dict[str, Any]:
        """テスト用のダミーノード生成ヘルパー群を返す。"""

        def _make_node(label: str, key_value: str, **kwargs: Any) -> dict[str, Any]:
            return {"label": label, "key_value": key_value, **kwargs}

        def _make_rel(rel_type: str, from_id: str, to_id: str) -> dict[str, str]:
            return {"type": rel_type, "from_id": from_id, "to_id": to_id}

        return {
            "make_source_type_node_fn": lambda st: _make_node("SourceType", st),
            "make_domain_node_fn": lambda domain, base_url="": _make_node(
                "Domain", domain
            ),
            "make_trust_level_node_fn": lambda tl: _make_node("TrustLevel", tl),
            "make_language_node_fn": lambda lang: _make_node("Language", lang),
            "make_pipeline_node_fn": lambda cmd: _make_node("Pipeline", cmd),
            "make_entity_type_node_fn": lambda et: _make_node("EntityType", et),
            "make_identifier_node_fn": lambda key, id_type="", value="", scheme="": (
                _make_node("Identifier", key)
            ),
            "make_fact_type_node_fn": lambda ft: _make_node("FactType", ft),
            "make_claim_type_node_fn": lambda ct: _make_node("ClaimType", ct),
            "make_unit_of_measure_node_fn": lambda key, name="", dimension="": (
                _make_node("UnitOfMeasure", key)
            ),
            "make_datapoint_type_node_fn": lambda dt: _make_node("DataPointType", dt),
            "make_author_type_node_fn": lambda at: _make_node("AuthorType", at),
            "make_concept_category_node_fn": lambda cc: _make_node(
                "ConceptCategory", cc
            ),
            "make_classification_rel_fn": _make_rel,
            "extract_url_domain_fn": lambda url: "example.com" if url else "",
        }

    def test_正常系_Sourceからクラスノードが生成される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [
                {
                    "source_id": "src-001",
                    "source_type": "web",
                    "url": "https://example.com/article",
                    "authority_level": "media",
                }
            ],
            "entities": [],
            "facts": [],
            "claims": [],
            "financial_datapoints": [],
            "authors": [],
            "topics": [],
            "stances": [],
        }

        helpers = self._make_helpers()
        BaseMapper.postprocess(
            mapped,
            "test-command",
            entity_type_consolidation={"company": "company"},
            source_type_normalization={"web-research": "web"},
            concept_category_map={},
            trust_level_normalization={},
            trust_level_meta={"media": True, "official": True},
            datapoint_type_map={True: "estimate", False: "actual"},
            **helpers,
        )

        labels = {n["label"] for n in mapped["classification_nodes"]}
        assert "SourceType" in labels
        assert "Domain" in labels
        assert "TrustLevel" in labels
        assert "Pipeline" in labels

        rel_types = {r["type"] for r in mapped["classification_rels"]}
        assert "IS_SOURCE_TYPE" in rel_types
        assert "FROM_DOMAIN" in rel_types
        assert "RATED_AS" in rel_types
        assert "INGESTED_VIA" in rel_types

    def test_正常系_Entityからクラスノードが生成される(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [],
            "entities": [
                {
                    "entity_id": "e-001",
                    "entity_key": "Apple::company",
                    "entity_type": "company",
                    "ticker": "AAPL",
                }
            ],
            "facts": [],
            "claims": [],
            "financial_datapoints": [],
            "authors": [],
            "topics": [],
            "stances": [],
        }

        helpers = self._make_helpers()
        BaseMapper.postprocess(
            mapped,
            "test-command",
            entity_type_consolidation={"company": "company"},
            source_type_normalization={},
            concept_category_map={},
            trust_level_normalization={},
            trust_level_meta={},
            datapoint_type_map={True: "estimate", False: "actual"},
            **helpers,
        )

        labels = {n["label"] for n in mapped["classification_nodes"]}
        assert "EntityType" in labels
        assert "Identifier" in labels

        rel_types = {r["type"] for r in mapped["classification_rels"]}
        assert "IS_TYPE" in rel_types
        assert "HAS_IDENTIFIER" in rel_types

    def test_正常系_重複ノードは排除される(self) -> None:
        """同一 source_type を持つ複数 Source は SourceType ノードを1つだけ生成。"""
        mapped: dict[str, Any] = {
            "sources": [
                {"source_id": "src-001", "source_type": "web", "url": ""},
                {"source_id": "src-002", "source_type": "web", "url": ""},
            ],
            "entities": [],
            "facts": [],
            "claims": [],
            "financial_datapoints": [],
            "authors": [],
            "topics": [],
            "stances": [],
        }

        helpers = self._make_helpers()
        BaseMapper.postprocess(
            mapped,
            "cmd",
            entity_type_consolidation={},
            source_type_normalization={},
            concept_category_map={},
            trust_level_normalization={},
            trust_level_meta={},
            datapoint_type_map={True: "estimate", False: "actual"},
            **helpers,
        )

        source_type_nodes = [
            n for n in mapped["classification_nodes"] if n["label"] == "SourceType"
        ]
        assert len(source_type_nodes) == 1  # deduplicated

    def test_正常系_source_idなしのSourceはスキップ(self) -> None:
        mapped: dict[str, Any] = {
            "sources": [{"source_type": "web", "url": ""}],  # no source_id
            "entities": [],
            "facts": [],
            "claims": [],
            "financial_datapoints": [],
            "authors": [],
            "topics": [],
            "stances": [],
        }

        helpers = self._make_helpers()
        BaseMapper.postprocess(
            mapped,
            "cmd",
            entity_type_consolidation={},
            source_type_normalization={},
            concept_category_map={},
            trust_level_normalization={},
            trust_level_meta={},
            datapoint_type_map={True: "estimate", False: "actual"},
            **helpers,
        )

        assert mapped["classification_nodes"] == []
        assert mapped["classification_rels"] == []


# ---------------------------------------------------------------------------
# Tests: BaseMapper abstract method
# ---------------------------------------------------------------------------


class TestBaseMapperAbstract:
    def test_正常系_サブクラスはmapを実装できる(self) -> None:
        mapper = _ConcreteMapper()
        result = mapper.map({"session_id": "s1"})
        assert result["session_id"] == "s1"
        assert result["batch_label"] == "test"

    def test_異常系_abstractクラスは直接インスタンス化できない(self) -> None:
        with pytest.raises(TypeError):
            BaseMapper()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Tests: COMMAND_MAPPERS from __init__
# ---------------------------------------------------------------------------


class TestCommandMappers:
    def test_正常系_COMMAND_MAPPERSが11コマンドを含む(self) -> None:
        from mappers import COMMAND_MAPPERS

        expected_commands = {
            "finance-news-workflow",
            "ai-research-collect",
            "generate-market-report",
            "asset-management",
            "reddit-finance-topics",
            "finance-full",
            "pdf-extraction",
            "wealth-scrape",
            "topic-discovery",
            "web-research",
            "academic-fetch",
        }
        assert set(COMMAND_MAPPERS.keys()) == expected_commands

    def test_正常系_全マッパーはcallable(self) -> None:
        from mappers import COMMAND_MAPPERS

        for name, fn in COMMAND_MAPPERS.items():
            assert callable(fn), f"{name} mapper is not callable"
