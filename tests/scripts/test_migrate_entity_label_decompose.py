"""Unit tests for scripts/migrate_entity_label_decompose.py.

Wave 4: Entity ラベル分解・entity_key 廃止・NODE KEY 制約導入

テスト対象:
- convert_sector_to_topic: Entity:Sector テーマ的ノード → Topic ラベル変換
- create_node_key_constraints: 13 ラベル全てに NODE KEY 制約作成
- remove_entity_key_property: entity_key プロパティ削除
- delete_entity_type_nodes: EntityType ノード + IS_TYPE リレーション削除
- delete_instrument_class_nodes: InstrumentClass ノード + IS_INSTRUMENT_CLASS リレーション削除
- remove_entity_label: Entity ラベル削除（最終ステップ）
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from scripts.migrate_entity_label_decompose import (
    INDIVIDUAL_LABELS,
    DecompositionStats,
    convert_sector_to_topic,
    create_node_key_constraints,
    delete_entity_type_nodes,
    delete_instrument_class_nodes,
    fetch_thematic_sector_entities,
    remove_entity_key_property,
    remove_entity_label,
)

# ---------------------------------------------------------------------------
# INDIVIDUAL_LABELS 定数
# ---------------------------------------------------------------------------


class TestIndividualLabels:
    """INDIVIDUAL_LABELS 定数の検証。"""

    def test_正常系_13種のラベルが定義されている(self) -> None:
        """13 種の個別ラベルが定義されていることを確認。"""
        assert len(INDIVIDUAL_LABELS) == 13

    def test_正常系_Company含まれる(self) -> None:
        assert "Company" in INDIVIDUAL_LABELS

    def test_正常系_MarketIndex含まれる(self) -> None:
        """index → MarketIndex の特殊マッピングに対応する。"""
        assert "MarketIndex" in INDIVIDUAL_LABELS

    def test_正常系_全て大文字始まりPascalCase(self) -> None:
        for label in INDIVIDUAL_LABELS:
            assert label[0].isupper(), f"{label} is not PascalCase"

    def test_正常系_Product含まれる(self) -> None:
        assert "Product" in INDIVIDUAL_LABELS

    def test_正常系_Broker含まれる(self) -> None:
        assert "Broker" in INDIVIDUAL_LABELS


# ---------------------------------------------------------------------------
# DecompositionStats
# ---------------------------------------------------------------------------


class TestDecompositionStats:
    """DecompositionStats データクラスのテスト。"""

    def test_正常系_デフォルト値がゼロ(self) -> None:
        stats = DecompositionStats()
        assert stats.sector_converted == 0
        assert stats.constraints_created == 0
        assert stats.entity_key_removed == 0
        assert stats.entity_type_nodes_deleted == 0
        assert stats.instrument_class_nodes_deleted == 0
        assert stats.entity_label_removed == 0
        assert stats.failed == 0

    def test_正常系_値を設定して取得できる(self) -> None:
        stats = DecompositionStats(
            sector_converted=5,
            constraints_created=13,
            entity_key_removed=100,
            entity_type_nodes_deleted=1597,
            instrument_class_nodes_deleted=106,
            entity_label_removed=500,
            failed=2,
        )
        assert stats.sector_converted == 5
        assert stats.constraints_created == 13
        assert stats.entity_key_removed == 100
        assert stats.entity_type_nodes_deleted == 1597
        assert stats.instrument_class_nodes_deleted == 106
        assert stats.entity_label_removed == 500
        assert stats.failed == 2


# ---------------------------------------------------------------------------
# fetch_thematic_sector_entities
# ---------------------------------------------------------------------------


class TestFetchThematicSectorEntities:
    """fetch_thematic_sector_entities のテスト。"""

    def test_正常系_テーマ的Sectorノードを取得する(self) -> None:
        """Entity:Sector ノードのリストを返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"entity_key": "AI::sector", "name": "AI"},
                    {"entity_key": "Fintech::sector", "name": "Fintech"},
                ]
            )
        )
        mock_session.run.return_value = mock_result

        results = fetch_thematic_sector_entities(mock_session)
        assert len(results) == 2
        assert results[0]["entity_key"] == "AI::sector"
        mock_session.run.assert_called_once()

    def test_正常系_0件の場合は空リスト(self) -> None:
        """テーマ的Sectorノードが0件の場合に空リストを返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_result

        results = fetch_thematic_sector_entities(mock_session)
        assert results == []

    def test_正常系_クエリにEntityとSectorが含まれる(self) -> None:
        """実行される Cypher に Entity と Sector が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_result

        fetch_thematic_sector_entities(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "Entity" in cypher or "entity" in cypher.lower()
        assert "Sector" in cypher


# ---------------------------------------------------------------------------
# convert_sector_to_topic
# ---------------------------------------------------------------------------


class TestConvertSectorToTopic:
    """convert_sector_to_topic のテスト。"""

    def test_正常系_テーマ的SectorをTopicに変換する(self) -> None:
        """Entity:Sector ノードに Topic ラベルを追加し Sector を削除することを確認。"""
        mock_session = MagicMock()
        entities = [
            {"entity_key": "AI::sector", "name": "AI"},
            {"entity_key": "Fintech::sector", "name": "Fintech"},
        ]
        count = convert_sector_to_topic(mock_session, entities)
        assert mock_session.run.call_count == 2
        assert count == 2

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        entities = [{"entity_key": "AI::sector", "name": "AI"}]
        count = convert_sector_to_topic(mock_session, entities, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_空のノードリストで0を返す(self) -> None:
        """空のノードリストで 0 を返すことを確認。"""
        mock_session = MagicMock()
        count = convert_sector_to_topic(mock_session, [])
        mock_session.run.assert_not_called()
        assert count == 0

    def test_異常系_セッション例外時は継続してfailed_countを返す(self) -> None:
        """session.run が例外を投げた場合でも処理を継続することを確認。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        entities = [{"entity_key": "AI::sector", "name": "AI"}]
        count = convert_sector_to_topic(mock_session, entities)
        # 例外が発生しても count=0（applied のみカウント）
        assert count == 0

    def test_正常系_CypherにTopicとSectorが含まれる(self) -> None:
        """実行される Cypher に Topic と Sector が含まれることを確認。"""
        mock_session = MagicMock()
        entities = [{"entity_key": "AI::sector", "name": "AI"}]
        convert_sector_to_topic(mock_session, entities)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "Topic" in cypher
        assert "Sector" in cypher


# ---------------------------------------------------------------------------
# create_node_key_constraints
# ---------------------------------------------------------------------------


class TestCreateNodeKeyConstraints:
    """create_node_key_constraints のテスト。"""

    def test_正常系_13ラベル分のNODE_KEY制約を作成する(self) -> None:
        """13 ラベル分の NODE KEY 制約が作成されることを確認。"""
        mock_session = MagicMock()
        count = create_node_key_constraints(mock_session)
        assert mock_session.run.call_count == 13
        assert count == 13

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = create_node_key_constraints(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_CypherにNODE_KEYが含まれる(self) -> None:
        """実行される Cypher に NODE KEY が含まれることを確認。"""
        mock_session = MagicMock()
        create_node_key_constraints(mock_session)
        first_call_cypher = mock_session.run.call_args_list[0][0][0]
        assert "NODE KEY" in first_call_cypher

    def test_異常系_制約作成時の例外はスキップして継続(self) -> None:
        """制約が既に存在する場合（例外）でも残りの制約を作成し続けることを確認。"""
        mock_session = MagicMock()
        # 最初の2回だけ例外
        mock_session.run.side_effect = [
            Exception("constraint already exists"),
            Exception("constraint already exists"),
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        ]
        count = create_node_key_constraints(mock_session)
        # 全 13 回呼ばれる（スキップ分も試行）
        assert mock_session.run.call_count == 13
        # 成功分 11 件のみカウント
        assert count == 11


# ---------------------------------------------------------------------------
# remove_entity_key_property
# ---------------------------------------------------------------------------


class TestRemoveEntityKeyProperty:
    """remove_entity_key_property のテスト。"""

    def test_正常系_entity_keyプロパティを削除するクエリを実行(self) -> None:
        """REMOVE entity_key クエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 100}
        mock_session.run.return_value = mock_result

        count = remove_entity_key_property(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 100

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = remove_entity_key_property(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_0件の場合は0を返す(self) -> None:
        """削除対象が 0 件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 0}
        mock_session.run.return_value = mock_result

        count = remove_entity_key_property(mock_session)
        assert count == 0

    def test_正常系_CypherにREMOVEとentity_keyが含まれる(self) -> None:
        """実行される Cypher に REMOVE と entity_key が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 5}
        mock_session.run.return_value = mock_result

        remove_entity_key_property(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "REMOVE" in cypher or "remove" in cypher.lower()
        assert "entity_key" in cypher


# ---------------------------------------------------------------------------
# delete_entity_type_nodes
# ---------------------------------------------------------------------------


class TestDeleteEntityTypeNodes:
    """delete_entity_type_nodes のテスト。"""

    def test_正常系_EntityTypeノードとIS_TYPEリレーションを削除する(self) -> None:
        """EntityType ノードと IS_TYPE リレーションを削除するクエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 1597}
        mock_session.run.return_value = mock_result

        count = delete_entity_type_nodes(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 1597

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = delete_entity_type_nodes(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_CypherにEntityTypeが含まれる(self) -> None:
        """実行される Cypher に EntityType が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 0}
        mock_session.run.return_value = mock_result

        delete_entity_type_nodes(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "EntityType" in cypher

    def test_正常系_0件の場合は0を返す(self) -> None:
        """削除対象が 0 件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 0}
        mock_session.run.return_value = mock_result

        count = delete_entity_type_nodes(mock_session)
        assert count == 0


# ---------------------------------------------------------------------------
# delete_instrument_class_nodes
# ---------------------------------------------------------------------------


class TestDeleteInstrumentClassNodes:
    """delete_instrument_class_nodes のテスト。"""

    def test_正常系_InstrumentClassノードとIS_INSTRUMENT_CLASSリレーションを削除する(
        self,
    ) -> None:
        """InstrumentClass ノードと IS_INSTRUMENT_CLASS リレーションを削除するクエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 106}
        mock_session.run.return_value = mock_result

        count = delete_instrument_class_nodes(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 106

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = delete_instrument_class_nodes(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_CypherにInstrumentClassが含まれる(self) -> None:
        """実行される Cypher に InstrumentClass が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 0}
        mock_session.run.return_value = mock_result

        delete_instrument_class_nodes(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "InstrumentClass" in cypher

    def test_正常系_0件の場合は0を返す(self) -> None:
        """削除対象が 0 件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"deleted_count": 0}
        mock_session.run.return_value = mock_result

        count = delete_instrument_class_nodes(mock_session)
        assert count == 0


# ---------------------------------------------------------------------------
# remove_entity_label
# ---------------------------------------------------------------------------


class TestRemoveEntityLabel:
    """remove_entity_label のテスト（最終ステップ）。"""

    def test_正常系_EntityラベルをREMOVEするクエリを実行(self) -> None:
        """全個別ラベル付きノードから Entity ラベルを削除するクエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 500}
        mock_session.run.return_value = mock_result

        count = remove_entity_label(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 500

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = remove_entity_label(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_CypherにEntityラベルREMOVEが含まれる(self) -> None:
        """実行される Cypher に REMOVE e:Entity が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 0}
        mock_session.run.return_value = mock_result

        remove_entity_label(mock_session)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        assert "Entity" in cypher
        assert "REMOVE" in cypher or "remove" in cypher.lower()

    def test_正常系_0件の場合は0を返す(self) -> None:
        """削除対象が 0 件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 0}
        mock_session.run.return_value = mock_result

        count = remove_entity_label(mock_session)
        assert count == 0
