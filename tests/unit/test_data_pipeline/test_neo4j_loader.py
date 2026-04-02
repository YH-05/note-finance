"""Unit tests for data_pipeline.neo4j_loader (Issue #288).

テスト対象:
- _ingest_nodes(): ノード投入処理
- _ingest_rels(): リレーション投入処理
- _ingest_multilabel(): マルチラベル投入（APOC）
- _merge_node() の extra_labels 引数
- ingest_to_neo4j() の関数分割後の構造
- apply_constraints_from_yaml(): YAML制約/インデックス自動適用
- --skip-schema-check フラグ
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_queue_data() -> dict[str, Any]:
    """シンプルな graph-queue JSON データ."""
    return {
        "schema_version": "3.0",
        "queue_id": "gq-20260330-test",
        "created_at": "2026-03-30T00:00:00+09:00",
        "command_source": "test",
        "sources": [
            {
                "source_id": "src-001",
                "title": "Test Source",
                "source_type": "web",
                "authority_level": "media",
                "fetched_at": "2026-03-30T00:00:00+09:00",
            }
        ],
        "entities": [
            {
                "entity_id": "ent-uuid-001",
                "entity_key": "apple-inc",
                "name": "Apple Inc.",
                "entity_type": "company",
            }
        ],
        "topics": [
            {
                "topic_id": "top-uuid-001",
                "topic_key": "us-tech",
                "name": "US Tech",
                "category": "sector",
            }
        ],
        "facts": [],
        "claims": [],
        "chunks": [],
        "financial_datapoints": [],
        "fiscal_periods": [],
        "authors": [],
        "classification_nodes": [],
        "classification_rels": [],
        "relations": {
            "source_fact": [],
            "source_claim": [],
            "extracted_from_fact": [],
            "extracted_from_claim": [],
            "fact_entity": [],
            "claim_entity": [],
            "tagged": [{"source_id": "src-001", "topic_key": "us-tech"}],
            "contains_chunk": [],
            "has_datapoint": [],
            "for_period": [],
            "datapoint_entity": [],
            "authored_by": [],
        },
    }


@pytest.fixture
def multilabel_queue_data() -> dict[str, Any]:
    """マルチラベルエンティティを含む graph-queue JSON データ."""
    return {
        "schema_version": "3.0",
        "queue_id": "gq-20260330-multilabel",
        "created_at": "2026-03-30T00:00:00+09:00",
        "command_source": "test",
        "sources": [],
        "entities": [
            {
                "entity_id": "ent-uuid-002",
                "entity_key": "apple-inc",
                "name": "Apple Inc.",
                "entity_type": "company",
                "extra_labels": ["Company"],
            },
            {
                "entity_id": "ent-uuid-003",
                "entity_key": "fed-reserve",
                "name": "Federal Reserve",
                "entity_type": "central_bank",
                "extra_labels": ["Organization"],
            },
        ],
        "topics": [],
        "facts": [],
        "claims": [],
        "chunks": [],
        "financial_datapoints": [],
        "fiscal_periods": [],
        "authors": [],
        "classification_nodes": [],
        "classification_rels": [],
        "relations": {},
    }


@pytest.fixture
def mock_driver() -> MagicMock:
    """Neo4j ドライバーのモック."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    session.execute_write.return_value = None
    return driver


# ---------------------------------------------------------------------------
# Tests: _merge_node with extra_labels
# ---------------------------------------------------------------------------


class TestMergeNodeExtraLabels:
    """_merge_node() に extra_labels 引数が追加されていることを確認するテスト."""

    def test_正常系_extra_labelsなしでマージされる(self) -> None:
        """extra_labels なしの場合、既存の動作と同じ."""
        from data_pipeline.neo4j_loader import _merge_node

        tx = MagicMock()
        props = {"source_id": "src-001", "title": "Test"}
        _merge_node(tx, "Source", "source_id", props)

        tx.run.assert_called_once()
        query = tx.run.call_args[0][0]
        assert "MERGE (n:Source" in query
        assert "apoc" not in query.lower()

    def test_正常系_extra_labels指定でAPOCクエリが生成される(self) -> None:
        """extra_labels が指定された場合、APOC クエリが生成される."""
        from data_pipeline.neo4j_loader import _merge_node

        tx = MagicMock()
        props = {
            "entity_id": "ent-001",
            "entity_key": "apple-inc",
            "name": "Apple Inc.",
        }
        _merge_node(tx, "Entity", "entity_key", props, extra_labels=["Company"])

        tx.run.assert_called()
        # APOC または MATCH+SET でマルチラベルが処理される
        calls_str = str(tx.run.call_args_list)
        assert "Company" in calls_str

    def test_正常系_extra_labels空リストはシングルラベルと同じ(self) -> None:
        """extra_labels=[] はシングルラベル投入と同じ動作をする."""
        from data_pipeline.neo4j_loader import _merge_node

        tx = MagicMock()
        props = {"entity_key": "test-key", "name": "Test"}
        _merge_node(tx, "Entity", "entity_key", props, extra_labels=[])

        tx.run.assert_called_once()
        query = tx.run.call_args[0][0]
        assert "MERGE (n:Entity" in query

    def test_正常系_extra_labels引数のデフォルト値はNone(self) -> None:
        """extra_labels 引数が存在し、デフォルト値が None であること."""
        import inspect

        from data_pipeline.neo4j_loader import _merge_node

        sig = inspect.signature(_merge_node)
        assert "extra_labels" in sig.parameters
        assert sig.parameters["extra_labels"].default is None


# ---------------------------------------------------------------------------
# Tests: _ingest_nodes
# ---------------------------------------------------------------------------


class TestIngestNodes:
    """_ingest_nodes() サブ関数のテスト."""

    def test_正常系_ノードが投入される(
        self, simple_queue_data: dict, mock_driver: MagicMock
    ) -> None:
        """_ingest_nodes() が Source/Entity/Topic を投入する."""
        from data_pipeline.neo4j_loader import _ingest_nodes

        result = _ingest_nodes(simple_queue_data, mock_driver)

        assert result["node_count"] >= 3  # Source + Entity + Topic
        assert mock_driver.session.call_count > 0

    def test_正常系_dry_runでドライバーが呼ばれない(
        self, simple_queue_data: dict
    ) -> None:
        """dry_run=True の場合、ドライバーが None でもカウントのみ返す."""
        from data_pipeline.neo4j_loader import _ingest_nodes

        result = _ingest_nodes(simple_queue_data, None)

        assert result["node_count"] >= 3  # カウントは実行される

    def test_正常系_空のデータは0件(self) -> None:
        """全セクションが空の場合、node_count=0 を返す."""
        from data_pipeline.neo4j_loader import _ingest_nodes

        empty_data: dict[str, Any] = {
            "sources": [],
            "entities": [],
            "topics": [],
            "facts": [],
            "claims": [],
            "chunks": [],
            "financial_datapoints": [],
            "fiscal_periods": [],
            "authors": [],
            "classification_nodes": [],
        }
        result = _ingest_nodes(empty_data, None)

        assert result["node_count"] == 0

    def test_正常系_extra_labelsがあればマルチラベル投入される(
        self, multilabel_queue_data: dict, mock_driver: MagicMock
    ) -> None:
        """extra_labels フィールドがある Entity が適切に処理される."""
        from data_pipeline.neo4j_loader import _ingest_nodes

        result = _ingest_nodes(multilabel_queue_data, mock_driver)

        # Entity 2件が投入される
        assert result["node_count"] >= 2


# ---------------------------------------------------------------------------
# Tests: _ingest_rels
# ---------------------------------------------------------------------------


class TestIngestRels:
    """_ingest_rels() サブ関数のテスト."""

    def test_正常系_リレーションが投入される(
        self, simple_queue_data: dict, mock_driver: MagicMock
    ) -> None:
        """_ingest_rels() が TAGGED リレーションを投入する."""
        from data_pipeline.neo4j_loader import _ingest_rels

        mock_session = mock_driver.session.return_value.__enter__.return_value
        mock_session.execute_write.return_value = 1  # 1件作成

        id_to_key: dict[str, str] = {"top-uuid-001": "us-tech"}
        result = _ingest_rels(simple_queue_data, mock_driver, id_to_key)

        assert result["rel_count"] >= 1

    def test_正常系_dry_runでドライバーが呼ばれない(
        self, simple_queue_data: dict
    ) -> None:
        """dry_run=True の場合、ドライバーが None でも rel_count を返す."""
        from data_pipeline.neo4j_loader import _ingest_rels

        id_to_key: dict[str, str] = {}
        result = _ingest_rels(simple_queue_data, None, id_to_key)

        assert "rel_count" in result
        assert "rel_verification" in result

    def test_正常系_空のリレーションは0件(self) -> None:
        """全リレーションが空の場合、rel_count=0 を返す."""
        from data_pipeline.neo4j_loader import _ingest_rels

        empty_data: dict[str, Any] = {
            "sources": [],
            "relations": {},
            "classification_rels": [],
            "chunks": [],
        }
        result = _ingest_rels(empty_data, None, {})

        assert result["rel_count"] == 0


# ---------------------------------------------------------------------------
# Tests: _ingest_multilabel
# ---------------------------------------------------------------------------


class TestIngestMultilabel:
    """_ingest_multilabel() のテスト."""

    def test_正常系_APOCが利用可能な場合APOCクエリが実行される(
        self, mock_driver: MagicMock
    ) -> None:
        """APOC 利用可能な場合、apoc.merge.node が呼ばれる."""
        from data_pipeline.neo4j_loader import _ingest_multilabel

        mock_session = mock_driver.session.return_value.__enter__.return_value
        # APOC 利用可能を模擬
        mock_result = MagicMock()
        mock_result.single.return_value = {"n": MagicMock()}
        mock_session.run.return_value = mock_result

        _ingest_multilabel(
            mock_session,
            "Entity",
            "entity_key",
            "apple-inc",
            ["Company"],
            apoc_available=True,
        )

        mock_session.run.assert_called()
        calls_str = str(mock_session.run.call_args_list)
        assert "apoc.merge.node" in calls_str

    def test_正常系_APOCが不在の場合フォールバック実行(
        self, mock_driver: MagicMock
    ) -> None:
        """APOC 不在の場合、MATCH+SET の2クエリが実行される."""
        from data_pipeline.neo4j_loader import _ingest_multilabel

        mock_session = mock_driver.session.return_value.__enter__.return_value

        _ingest_multilabel(
            mock_session,
            "Entity",
            "entity_key",
            "apple-inc",
            ["Company"],
            apoc_available=False,
        )

        # フォールバックは MATCH (n:Entity ...) SET n:Company の形
        mock_session.run.assert_called()
        calls_str = str(mock_session.run.call_args_list)
        assert "Company" in calls_str

    def test_正常系_extra_labelsが空の場合は何もしない(
        self, mock_driver: MagicMock
    ) -> None:
        """extra_labels=[] の場合、セッションのrunは呼ばれない."""
        from data_pipeline.neo4j_loader import _ingest_multilabel

        mock_session = mock_driver.session.return_value.__enter__.return_value

        _ingest_multilabel(
            mock_session,
            "Entity",
            "entity_key",
            "apple-inc",
            [],
            apoc_available=True,
        )

        mock_session.run.assert_not_called()


# ---------------------------------------------------------------------------
# Tests: ingest_to_neo4j function decomposition
# ---------------------------------------------------------------------------


class TestIngestToNeo4jDecomposition:
    """ingest_to_neo4j() が関数分割されていることを確認するテスト."""

    def test_正常系_dry_runでノードとリレーション数が返される(
        self, simple_queue_data: dict
    ) -> None:
        """dry_run=True で正しい件数が返される."""
        from data_pipeline.neo4j_loader import ingest_to_neo4j

        result = ingest_to_neo4j(simple_queue_data, dry_run=True)

        assert "nodes" in result
        assert "relations" in result
        assert "rel_verification" in result
        assert result["nodes"] >= 3  # Source + Entity + Topic
        assert result["relations"] >= 1  # TAGGED

    def test_正常系_サブ関数が存在する(self) -> None:
        """_ingest_nodes, _ingest_rels, _ingest_multilabel が公開されている."""
        from data_pipeline import neo4j_loader

        assert hasattr(neo4j_loader, "_ingest_nodes"), "_ingest_nodes が存在しない"
        assert hasattr(neo4j_loader, "_ingest_rels"), "_ingest_rels が存在しない"
        assert hasattr(neo4j_loader, "_ingest_multilabel"), (
            "_ingest_multilabel が存在しない"
        )

    def test_正常系_extra_labelsを含むエンティティが処理される(
        self, multilabel_queue_data: dict
    ) -> None:
        """extra_labels を含む Entity が dry_run でカウントされる."""
        from data_pipeline.neo4j_loader import ingest_to_neo4j

        result = ingest_to_neo4j(multilabel_queue_data, dry_run=True)

        assert result["nodes"] >= 2  # Entity 2件


# ---------------------------------------------------------------------------
# Tests: apply_constraints_from_yaml
# ---------------------------------------------------------------------------


class TestApplyConstraintsFromYaml:
    """apply_constraints_from_yaml() のテスト."""

    def test_正常系_関数が存在する(self) -> None:
        """apply_constraints_from_yaml 関数が存在する."""
        from data_pipeline import neo4j_loader

        assert hasattr(neo4j_loader, "apply_constraints_from_yaml"), (
            "apply_constraints_from_yaml が存在しない"
        )

    def test_正常系_ontology_loaderからCypher文が生成される(self) -> None:
        """ontology_loader 経由で CREATE CONSTRAINT / CREATE INDEX Cypher が生成される."""
        from data_pipeline.neo4j_loader import apply_constraints_from_yaml

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(
            return_value=mock_session
        )
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        result = apply_constraints_from_yaml(mock_driver)

        assert mock_session.run.call_count >= 2  # 制約 + インデックス
        assert result["constraints_applied"] >= 1
        assert result["indices_applied"] >= 1

    def test_正常系_dry_runでCypherが実行されない(self) -> None:
        """dry_run=True の場合、Cypher は実行されずカウントだけ返る."""
        from data_pipeline.neo4j_loader import apply_constraints_from_yaml

        mock_driver = MagicMock()
        result = apply_constraints_from_yaml(mock_driver, dry_run=True)

        mock_driver.session.assert_not_called()
        # ontology_loader のデフォルト制約数（15件）を確認
        assert result["constraints_applied"] >= 1
        assert result["indices_applied"] >= 0

    def test_正常系_ontology_loaderデフォルトで正しい件数が返される(self) -> None:
        """ontology_loader の制約/インデックス件数が dry_run で返される.

        v4.0: 13個別ラベルの NODE KEY 制約 + その他 UNIQUE 制約が含まれる。
        """
        from data_pipeline.neo4j_loader import apply_constraints_from_yaml

        mock_driver = MagicMock()
        result = apply_constraints_from_yaml(mock_driver, dry_run=True)

        # v4.0: 13個別ラベル NODE KEY + その他 UNIQUE 制約
        # 実際の件数は ontology.yaml に依存するため、範囲チェック
        assert result["constraints_applied"] >= 13, "13個別ラベルの NODE KEY 制約が不足"
        # ontology_loader の _DEFAULT_INDICES は 23 件
        assert result["indices_applied"] >= 1


# ---------------------------------------------------------------------------
# Tests: ingest_to_neo4j flags
# ---------------------------------------------------------------------------


class TestIngestToNeo4jFlags:
    """ingest_to_neo4j() の skip_schema_check フラグのテスト."""

    def test_正常系_skip_schema_checkフラグが存在する(self) -> None:
        """ingest_to_neo4j() が skip_schema_check パラメータを持つ."""
        import inspect

        from data_pipeline.neo4j_loader import ingest_to_neo4j

        sig = inspect.signature(ingest_to_neo4j)
        assert "skip_schema_check" in sig.parameters, (
            "skip_schema_check パラメータが存在しない"
        )

    def test_正常系_apply_constraintsフラグが存在する(self) -> None:
        """ingest_to_neo4j() が apply_constraints パラメータを持つ."""
        import inspect

        from data_pipeline.neo4j_loader import ingest_to_neo4j

        sig = inspect.signature(ingest_to_neo4j)
        assert "apply_constraints" in sig.parameters, (
            "apply_constraints パラメータが存在しない"
        )


# ---------------------------------------------------------------------------
# Tests: PLR0912/PLR0915 compliance (line count)
# ---------------------------------------------------------------------------


class TestCodeQuality:
    """コード品質のテスト."""

    def test_正常系_neo4j_loaderの行数が規定範囲内(self) -> None:
        """neo4j_loader.py の行数が規定範囲内であること.

        v4.0: _ingest_entity_nodes / _ingest_entity_rels 追加により上限を引き上げ。
        """
        from pathlib import Path

        loader_path = (
            Path(__file__).parents[3] / "src" / "data_pipeline" / "neo4j_loader.py"
        )
        lines = loader_path.read_text().splitlines()
        line_count = len(lines)

        assert 400 <= line_count <= 1400, (
            f"neo4j_loader.py の行数 ({line_count}) が想定外です（400-1400行の範囲内）"
        )

    def test_正常系_ingest_to_neo4j関数の分岐数が減少している(self) -> None:
        """ingest_to_neo4j() の分岐数（if/for/while）が合理的な範囲内."""
        import ast
        from pathlib import Path

        loader_path = (
            Path(__file__).parents[3] / "src" / "data_pipeline" / "neo4j_loader.py"
        )
        tree = ast.parse(loader_path.read_text())

        # ingest_to_neo4j 関数定義を探す
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "ingest_to_neo4j":
                branches = sum(
                    1
                    for n in ast.walk(node)
                    if isinstance(n, (ast.If, ast.For, ast.While))
                )
                assert branches <= 15, (
                    f"ingest_to_neo4j の分岐数 ({branches}) が多すぎます（PLR0912 違反のリスク）"
                )
                break
