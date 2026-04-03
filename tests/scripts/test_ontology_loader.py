"""ontology_loader のユニットテスト.

``scripts/ontology_loader.py`` の 6 つの公開関数を検証する。
実際の ``ontology.yaml`` を読み込むテストと、一時 YAML を使用した
エッジケーステストの両方を含む。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from yaml import dump

from scripts.ontology_loader import (
    _DEFAULT_CONSTRAINTS,
    _DEFAULT_INDICES,
    _DEFAULT_NAMESPACES,
    invalidate_cache,
    load_consolidation_mapping,
    load_constraints,
    load_indices,
    load_multilabel_types,
    load_namespaces,
    load_source_type_normalization,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """各テスト前に YAML キャッシュをクリアする。"""
    invalidate_cache()


@pytest.fixture
def real_ontology_path() -> Path:
    """実際の ontology.yaml パスを返す（絶対パスで実行ディレクトリ非依存）。"""
    return (
        Path(__file__).parents[2]
        / "data"
        / "lifecycle-state"
        / "research"
        / "ontology.yaml"
    )


@pytest.fixture
def minimal_ontology(tmp_path: Path) -> Path:
    """最小限の ontology.yaml を一時ディレクトリに作成して返す。"""
    data: dict[str, Any] = {
        "schema_version": "test-1.0",
        "entity_classification_nodes": [
            {
                "label": "EntityType",
                "canonical_values": [
                    {
                        "key": "company",
                        "name_ja": "企業",
                        "consolidates": ["company", "fintech", "subsidiary"],
                    },
                    {"key": "person", "name_ja": "人物"},
                ],
            },
        ],
        "source_classification_nodes": [
            {
                "label": "SourceType",
                "canonical_values": ["news", "blog", "web"],
            },
        ],
    }
    yaml_path = tmp_path / "ontology.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        dump(data, f, allow_unicode=True)
    return yaml_path


@pytest.fixture
def empty_entity_type_ontology(tmp_path: Path) -> Path:
    """EntityType canonical_values が空の ontology.yaml。"""
    data: dict[str, Any] = {
        "entity_classification_nodes": [
            {
                "label": "EntityType",
                "canonical_values": [],
            },
        ],
    }
    yaml_path = tmp_path / "ontology.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        dump(data, f, allow_unicode=True)
    return yaml_path


@pytest.fixture
def missing_section_ontology(tmp_path: Path) -> Path:
    """entity_classification_nodes セクションがない ontology.yaml。"""
    data: dict[str, Any] = {
        "schema_version": "test-1.0",
    }
    yaml_path = tmp_path / "ontology.yaml"
    with yaml_path.open("w", encoding="utf-8") as f:
        dump(data, f, allow_unicode=True)
    return yaml_path


# =========================================================================
# load_consolidation_mapping
# =========================================================================


class TestLoadConsolidationMapping:
    """load_consolidation_mapping のテスト。"""

    def test_正常系_実ファイルからマッピングを読み込める(
        self, real_ontology_path: Path
    ) -> None:
        mapping = load_consolidation_mapping(real_ontology_path)

        # 14 種の正規型が自分自身にマッピングされている
        assert mapping["company"] == "company"
        assert mapping["technology"] == "technology"
        assert mapping["organization"] == "organization"
        assert mapping["person"] == "person"
        assert mapping["index"] == "index"
        assert mapping["indicator"] == "indicator"
        assert mapping["instrument"] == "instrument"
        assert mapping["commodity"] == "commodity"
        assert mapping["country"] == "country"
        assert mapping["sector"] == "sector"
        assert mapping["concept"] == "concept"
        assert mapping["regulation"] == "regulation"
        assert mapping["broker"] == "broker"
        assert mapping["product"] == "product"

    def test_正常系_統合対象が正規型にマッピングされる(
        self, real_ontology_path: Path
    ) -> None:
        mapping = load_consolidation_mapping(real_ontology_path)

        # company クラスタ
        assert mapping["fintech"] == "company"
        assert mapping["subsidiary"] == "company"
        assert mapping["digital_bank"] == "company"
        assert mapping["it_services"] == "company"

        # technology クラスタ
        assert mapping["system"] == "technology"

        # organization クラスタ
        assert mapping["central_bank"] == "organization"
        assert mapping["government"] == "organization"
        assert mapping["exchange"] == "organization"

        # instrument クラスタ
        assert mapping["etf"] == "instrument"
        assert mapping["currency"] == "instrument"
        assert mapping["bond"] == "instrument"

        # concept クラスタ
        assert mapping["theme"] == "concept"
        assert mapping["model"] == "concept"
        assert mapping["method"] == "concept"
        assert mapping["article_proposal"] == "concept"
        assert mapping["event"] == "concept"

    def test_正常系_最小YAMLから読み込める(self, minimal_ontology: Path) -> None:
        # Wave10: load_consolidation_mapping はハードコード定数を使用するため
        # minimal_ontology の内容に関わらず全14種のマッピングを返す
        mapping = load_consolidation_mapping(minimal_ontology)
        assert mapping["company"] == "company"
        assert mapping["fintech"] == "company"
        assert mapping["subsidiary"] == "company"
        assert mapping["person"] == "person"
        # 全14正規型が含まれること
        assert mapping["technology"] == "technology"
        assert mapping["broker"] == "broker"

    def test_正常系_consolidatesなしの項目は自己マッピングのみ(
        self, minimal_ontology: Path
    ) -> None:
        # Wave10: ハードコード定数から返すため person は self-mapping のみ
        mapping = load_consolidation_mapping(minimal_ontology)
        assert mapping["person"] == "person"
        # person には consolidates がないので person のみ
        person_mappings = [k for k, v in mapping.items() if v == "person"]
        assert person_mappings == ["person"]

    def test_異常系_ファイルが存在しない場合でもマッピングを返す(self) -> None:
        # Wave10: load_consolidation_mapping はハードコード定数を使用するため
        # ファイルが存在しなくてもマッピングを返す
        mapping = load_consolidation_mapping(Path("/nonexistent/ontology.yaml"))
        assert mapping["company"] == "company"
        assert mapping["fintech"] == "company"

    def test_異常系_EntityTypeセクションが空の場合でもマッピングを返す(
        self, empty_entity_type_ontology: Path
    ) -> None:
        # Wave10: load_consolidation_mapping はハードコード定数を使用するため
        # ontology.yaml の EntityType セクションが空でもマッピングを返す
        mapping = load_consolidation_mapping(empty_entity_type_ontology)
        assert mapping["company"] == "company"

    def test_異常系_セクション自体がない場合でもマッピングを返す(
        self, missing_section_ontology: Path
    ) -> None:
        # Wave10: load_consolidation_mapping はハードコード定数を使用するため
        # ontology.yaml にセクションがなくてもマッピングを返す
        mapping = load_consolidation_mapping(missing_section_ontology)
        assert mapping["company"] == "company"


# =========================================================================
# load_source_type_normalization
# =========================================================================


class TestLoadSourceTypeNormalization:
    """load_source_type_normalization のテスト。"""

    def test_正常系_実ファイルから正規source_typeを読み込める(
        self, real_ontology_path: Path
    ) -> None:
        mapping = load_source_type_normalization(real_ontology_path)

        # 12 種の正規値が自己マッピング
        canonical = [
            "news",
            "blog",
            "web",
            "pdf",
            "analysis",
            "company_filing",
            "data",
            "academic",
            "presentation",
            "financial_statement",
            "report",
            "transcript",
        ]
        for st in canonical:
            assert mapping[st] == st

    def test_正常系_レガシー異表記マッピングが含まれる(
        self, real_ontology_path: Path
    ) -> None:
        mapping = load_source_type_normalization(real_ontology_path)

        # legacy variant -> canonical
        assert mapping["web-research"] == "web"
        assert mapping["web_research"] == "web"
        assert mapping["rss"] == "news"
        assert mapping["news_article"] == "news"
        assert mapping["sec_filing"] == "pdf"
        assert mapping["academic_paper"] == "pdf"
        assert mapping["white_paper"] == "pdf"
        assert mapping["original"] == "original"

    def test_正常系_正規値はレガシーで上書きされない(
        self, real_ontology_path: Path
    ) -> None:
        mapping = load_source_type_normalization(real_ontology_path)

        # ontology.yaml に "analysis" が正規値として存在する場合、
        # レガシーの "analysis" -> "web" で上書きされないことを確認
        assert mapping["analysis"] == "analysis"

        # "report" も同様
        assert mapping["report"] == "report"

        # "transcript" も同様
        assert mapping["transcript"] == "transcript"

    def test_正常系_最小YAMLから読み込める(self, minimal_ontology: Path) -> None:
        mapping = load_source_type_normalization(minimal_ontology)
        assert mapping["news"] == "news"
        assert mapping["blog"] == "blog"
        assert mapping["web"] == "web"
        # legacy variants also available
        assert mapping["rss"] == "news"

    def test_異常系_ファイルが存在しない場合FileNotFoundError(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_source_type_normalization(Path("/nonexistent/ontology.yaml"))


# =========================================================================
# load_multilabel_types
# =========================================================================


class TestLoadMultilabelTypes:
    """load_multilabel_types のテスト。"""

    def test_正常系_実ファイルから14種のキーを読み込める(
        self, real_ontology_path: Path
    ) -> None:
        keys = load_multilabel_types(real_ontology_path)
        assert len(keys) == 14
        assert "company" in keys
        assert "technology" in keys
        assert "organization" in keys
        assert "person" in keys
        assert "index" in keys
        assert "indicator" in keys
        assert "instrument" in keys
        assert "commodity" in keys
        assert "country" in keys
        assert "sector" in keys
        assert "concept" in keys
        assert "regulation" in keys
        assert "broker" in keys
        assert "product" in keys

    def test_正常系_ソート順で返される(self, real_ontology_path: Path) -> None:
        # Wave10: load_multilabel_types はハードコード定数をソートして返す
        keys = load_multilabel_types(real_ontology_path)
        assert keys == sorted(keys), "keys should be in sorted order"

    def test_正常系_最小YAMLから読み込める(self, minimal_ontology: Path) -> None:
        # Wave10: load_multilabel_types はハードコード定数を使用するため
        # minimal_ontology の内容に関わらず全14種を返す
        keys = load_multilabel_types(minimal_ontology)
        assert len(keys) == 14
        assert "company" in keys
        assert "person" in keys

    def test_異常系_EntityTypeが空でもリストが返される(
        self, empty_entity_type_ontology: Path
    ) -> None:
        # Wave10: load_multilabel_types はハードコード定数を使用するため
        # empty_entity_type_ontology でも ValueError にならない
        keys = load_multilabel_types(empty_entity_type_ontology)
        assert len(keys) == 14


# =========================================================================
# load_constraints
# =========================================================================


class TestLoadConstraints:
    """load_constraints のテスト。v4.0: Entity ラベル廃止、13個別ラベルに NODE KEY 制約追加。"""

    def test_正常系_制約が返される(self) -> None:
        """load_constraints() がリストを返すこと。"""
        constraints = load_constraints()
        assert isinstance(constraints, list)
        assert len(constraints) > 0

    def test_正常系_NODE_KEY制約が含まれる(self) -> None:
        """v4.0: 個別エンティティラベルの NODE KEY 制約が含まれること。"""
        constraints = load_constraints()
        node_key_labels = {c["label"] for c in constraints if c["type"] == "NODE_KEY"}
        # 13個別ラベルすべてが NODE KEY 制約を持つこと
        expected_labels = {
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
        }
        assert expected_labels.issubset(node_key_labels)

    def test_正常系_Entityラベルが含まれない(self) -> None:
        """v4.0: Entity 汎用ラベルの制約は廃止されていること。"""
        constraints = load_constraints()
        entity_constraints = [c for c in constraints if c["label"] == "Entity"]
        assert len(entity_constraints) == 0, "Entity ラベルの制約は v4.0 で廃止"

    def test_正常系_必須ラベルが含まれる(self) -> None:
        """Source / Fact / Claim 等の UNIQUE 制約が含まれること。"""
        constraints = load_constraints()
        labels = {c["label"] for c in constraints}
        expected = {
            "Source",
            "Author",
            "Chunk",
            "Fact",
            "Claim",
            "FinancialDataPoint",
            "FiscalPeriod",
            "Topic",
            "Insight",
            "Stance",
            "Question",
            "SkillRun",
        }
        assert expected.issubset(labels)

    def test_正常系_返り値は独立コピーである(self) -> None:
        """load_constraints() が毎回独立したリストを返すこと。"""
        c1 = load_constraints()
        c2 = load_constraints()
        original_len = len(c2)
        c1.append({"label": "Test", "property": "test_id", "type": "UNIQUE"})
        assert len(c2) == original_len


# =========================================================================
# load_indices
# =========================================================================


class TestLoadIndices:
    """load_indices のテスト。"""

    def test_正常系_デフォルトインデックスが返される(self) -> None:
        indices = load_indices()
        assert len(indices) == len(_DEFAULT_INDICES)
        assert indices == _DEFAULT_INDICES

    def test_正常系_必須インデックスが含まれる(self) -> None:
        indices = load_indices()
        index_set = {(i["label"], i["property"]) for i in indices}
        assert ("Fact", "fact_type") in index_set
        # Wave10: Entity ラベル廃止により Entity.entity_type インデックスは削除済み
        assert ("Entity", "entity_type") not in index_set
        assert ("Source", "source_type") in index_set
        assert ("SkillRun", "skill_name") in index_set

    def test_正常系_返り値は独立コピーである(self) -> None:
        i1 = load_indices()
        i2 = load_indices()
        i1.append({"label": "Test", "property": "test_prop"})
        assert len(i2) == len(_DEFAULT_INDICES)


# =========================================================================
# load_namespaces
# =========================================================================


class TestLoadNamespaces:
    """load_namespaces のテスト。"""

    def test_正常系_4つの名前空間が返される(self) -> None:
        ns = load_namespaces()
        assert set(ns.keys()) == {"kg_v2", "conversation", "memory", "archived"}

    def test_正常系_kg_v2に個別エンティティラベルが含まれる(self) -> None:
        # Wave10: Entity ラベル廃止 → 13個別ラベルに変更。合計ラベル数が増加。
        ns = load_namespaces()
        assert "Source" in ns["kg_v2"]["labels"]
        # Wave10: Entity ラベルは廃止済み
        assert "Entity" not in ns["kg_v2"]["labels"]
        assert "Company" in ns["kg_v2"]["labels"]
        assert "Technology" in ns["kg_v2"]["labels"]
        assert "Organization" in ns["kg_v2"]["labels"]
        assert "Claim" in ns["kg_v2"]["labels"]
        # 13個別ラベル + 元のラベルで合計が増加している
        assert len(ns["kg_v2"]["labels"]) > 12

    def test_正常系_memoryにroot_labelとsub_labelsがある(self) -> None:
        ns = load_namespaces()
        assert ns["memory"]["root_label"] == "Memory"
        assert "Decision" in ns["memory"]["sub_labels"]
        assert "SkillRun" in ns["memory"]["sub_labels"]

    def test_正常系_全名前空間がPascalCase命名(self) -> None:
        ns = load_namespaces()
        for name, ns_data in ns.items():
            assert ns_data["naming"] == "PascalCase", f"{name} has wrong naming"

    def test_正常系_返り値はディープコピーである(self) -> None:
        ns1 = load_namespaces()
        ns2 = load_namespaces()
        ns1["kg_v2"]["labels"].append("TestLabel")
        assert "TestLabel" not in ns2["kg_v2"]["labels"]


# =========================================================================
# invalidate_cache
# =========================================================================


class TestInvalidateCache:
    """invalidate_cache のテスト。"""

    def test_正常系_キャッシュ無効化後も同じ結果を返す(self, tmp_path: Path) -> None:
        # Wave10: load_multilabel_types はハードコード定数を使用するため
        # YAML の内容に関わらず常に同じ14種を返す。キャッシュ無効化しても同じ。
        yaml_path = tmp_path / "ontology.yaml"
        data: dict[str, Any] = {"schema_version": "test-1.0"}
        with yaml_path.open("w", encoding="utf-8") as f:
            dump(data, f, allow_unicode=True)

        keys_v1 = load_multilabel_types(yaml_path)
        assert len(keys_v1) == 14

        # After invalidation: still returns hardcoded 14 types
        invalidate_cache()
        keys_v2 = load_multilabel_types(yaml_path)
        assert len(keys_v2) == 14
        assert keys_v1 == keys_v2


# =========================================================================
# 旧 knowledge-graph-schema.yaml との互換性テスト
# =========================================================================


class TestBackwardCompatibility:
    """旧 knowledge-graph-schema.yaml とのデータ互換性を検証するテスト。"""

    def test_正常系_consolidation_mappingがontologyのキーを網羅(
        self, real_ontology_path: Path
    ) -> None:
        """ontology.yaml の entity_classification_nodes に含まれる全キーが
        ontology_loader でも取得できることを検証する。

        Notes
        -----
        旧 knowledge-graph-schema.yaml には ``macro``, ``demographic``,
        ``domain``, ``sovereign_wealth_fund`` 等が含まれていたが、ontology.yaml
        (v3.0) では統合対象から除外されている。このテストは ontology.yaml の
        実際の内容に基づいて検証する。
        """
        mapping = load_consolidation_mapping(real_ontology_path)

        # ontology.yaml v3.0 に含まれるキー
        expected_keys = [
            # company cluster
            "company",
            "fintech",
            "subsidiary",
            "fintech_holding",
            "digital_bank",
            "it_services",
            # technology cluster
            "technology",
            "system",
            # organization cluster
            "organization",
            "central_bank",
            "government",
            "government_agency",
            "institution",
            "exchange",
            # person
            "person",
            # index
            "index",
            # indicator cluster
            "indicator",
            "metric",
            # instrument cluster
            "instrument",
            "etf",
            "currency",
            "currency_pair",
            "fund",
            "bond",
            "asset",
            # commodity
            "commodity",
            # country cluster
            "country",
            "region",
            # sector cluster
            "sector",
            "market",
            # concept cluster
            "concept",
            "model",
            "method",
            "theme",
            "article_proposal",
            "event",
            # regulation
            "regulation",
            # broker
            "broker",
            # product cluster
            "product",
            "dataset",
            "data_center",
        ]
        for key in expected_keys:
            assert key in mapping, f"Missing key in consolidation mapping: {key}"

    def test_正常系_source_type_normalizationが旧YAMLのキーを網羅(
        self, real_ontology_path: Path
    ) -> None:
        """旧 knowledge-graph-schema.yaml の source_type_normalization に含まれていた
        全キーが ontology_loader でも取得できることを検証する。"""
        mapping = load_source_type_normalization(real_ontology_path)

        legacy_keys = [
            "web",
            "web-research",
            "web_research",
            "news",
            "rss",
            "news_article",
            "article",
            "pdf",
            "sec_filing",
            "annual_report",
            "academic_paper",
            "paper",
            "blog",
            "original",
        ]
        for key in legacy_keys:
            assert key in mapping, f"Missing key in source_type normalization: {key}"
