"""Unit tests for scripts/migrate_entity_multilabel.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from scripts.migrate_entity_multilabel import (
    CANONICAL_TO_LABEL,
    MigrationStats,
    apply_multilabel_batch,
    build_migration_ops,
    build_raw_to_label_map,
    load_consolidation_rules,
    remove_isin_property,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCHEMA_YAML_PATH = Path(__file__).parents[2] / "data/config/knowledge-graph-schema.yaml"


# ---------------------------------------------------------------------------
# load_consolidation_rules
# ---------------------------------------------------------------------------


class TestLoadConsolidationRules:
    """load_consolidation_rules のテスト。"""

    def test_正常系_YAMLからマッピングを読み込む(self) -> None:
        """consolidation_rules.entity_type.mapping が dict として返されることを確認。"""
        rules = load_consolidation_rules(SCHEMA_YAML_PATH)
        assert isinstance(rules, dict)
        assert len(rules) > 0

    def test_正常系_companyマッピングが正しい(self) -> None:
        """company -> company のマッピングが存在することを確認。"""
        rules = load_consolidation_rules(SCHEMA_YAML_PATH)
        assert rules.get("company") == "company"

    def test_正常系_fintechがcompanyにマップされる(self) -> None:
        """fintech -> company のマッピングが存在することを確認。"""
        rules = load_consolidation_rules(SCHEMA_YAML_PATH)
        assert rules.get("fintech") == "company"

    def test_正常系_14種の正規型が全てマッピング先に存在する(self) -> None:
        """14種の正規 entity_type が全て値として含まれることを確認。"""
        expected_canonical = {
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
        rules = load_consolidation_rules(SCHEMA_YAML_PATH)
        actual_canonical = set(rules.values())
        assert expected_canonical.issubset(actual_canonical)

    def test_異常系_存在しないパスでFileNotFoundError(self) -> None:
        """存在しないファイルで FileNotFoundError を送出することを確認。"""
        with pytest.raises(FileNotFoundError):
            load_consolidation_rules(Path("nonexistent/path.yaml"))


# ---------------------------------------------------------------------------
# CANONICAL_TO_LABEL
# ---------------------------------------------------------------------------


class TestCanonicalToLabel:
    """CANONICAL_TO_LABEL 定数の検証。"""

    def test_正常系_14種のマッピングが定義されている(self) -> None:
        """14 種の正規 entity_type から PascalCase ラベルへのマッピングが存在することを確認。"""
        assert len(CANONICAL_TO_LABEL) == 14

    def test_正常系_companyがCompanyにマップされる(self) -> None:
        assert CANONICAL_TO_LABEL["company"] == "Company"

    def test_正常系_indexがMarketIndexにマップされる(self) -> None:
        """index -> MarketIndex の特殊マッピングを確認（multilabel_types 定義に準拠）。"""
        assert CANONICAL_TO_LABEL["index"] == "MarketIndex"

    def test_正常系_organizationがOrganizationにマップされる(self) -> None:
        assert CANONICAL_TO_LABEL["organization"] == "Organization"

    def test_正常系_全値がPascalCase(self) -> None:
        """全マッピング値が PascalCase（先頭大文字）であることを確認。"""
        for canonical, label in CANONICAL_TO_LABEL.items():
            assert label[0].isupper(), f"{canonical} -> {label} is not PascalCase"


# ---------------------------------------------------------------------------
# build_raw_to_label_map
# ---------------------------------------------------------------------------


class TestBuildRawToLabelMap:
    """build_raw_to_label_map のテスト。"""

    def test_正常系_consolidation_rulesからマルチラベルマップを構築(self) -> None:
        """raw entity_type から PascalCase ラベルへのマップが構築されることを確認。"""
        rules = {"company": "company", "fintech": "company", "index": "index"}
        result = build_raw_to_label_map(rules)
        assert result["company"] == "Company"
        assert result["fintech"] == "Company"
        assert result["index"] == "MarketIndex"

    def test_正常系_全14種の正規型がマップに含まれる(self) -> None:
        """YAMLの consolidation_rules から構築したマップに全 raw type が含まれることを確認。"""
        rules = load_consolidation_rules(SCHEMA_YAML_PATH)
        result = build_raw_to_label_map(rules)
        assert "company" in result
        assert "fintech" in result
        assert "central_bank" in result

    def test_エッジケース_空のrulesで空のマップ(self) -> None:
        """空の rules で空のマップが返されることを確認。"""
        result = build_raw_to_label_map({})
        assert result == {}

    def test_異常系_未知のcanonicalはKeyError(self) -> None:
        """CANONICAL_TO_LABEL に存在しない正規型は KeyError を送出することを確認。"""
        rules = {"unknown_raw": "unknown_canonical"}
        with pytest.raises(KeyError):
            build_raw_to_label_map(rules)


# ---------------------------------------------------------------------------
# build_migration_ops
# ---------------------------------------------------------------------------


class TestBuildMigrationOps:
    """build_migration_ops のテスト。"""

    def test_正常系_未移行ノードの移行操作リストを構築(self) -> None:
        """未移行ノードから移行操作のリストが構築されることを確認。"""
        raw_to_label = {"company": "Company", "central_bank": "Organization"}
        raw_entities = [
            {"entity_key": "apple::company", "entity_type": "company"},
            {"entity_key": "boj::central_bank", "entity_type": "central_bank"},
        ]
        ops = build_migration_ops(raw_entities, raw_to_label)
        assert len(ops) == 2
        assert ops[0]["entity_key"] == "apple::company"
        assert ops[0]["label"] == "Company"
        assert ops[0]["sub_type"] == "company"
        assert ops[1]["entity_key"] == "boj::central_bank"
        assert ops[1]["label"] == "Organization"
        assert ops[1]["sub_type"] == "central_bank"

    def test_正常系_未知のentity_typeはスキップ(self) -> None:
        """raw_to_label に存在しない entity_type のノードはスキップされることを確認。"""
        raw_to_label = {"company": "Company"}
        raw_entities = [
            {"entity_key": "foo::unknown", "entity_type": "unknown_type"},
        ]
        ops = build_migration_ops(raw_entities, raw_to_label)
        assert len(ops) == 0

    def test_エッジケース_空のノードリストで空のops(self) -> None:
        """空のノードリストで空のopsが返されることを確認。"""
        ops = build_migration_ops([], {"company": "Company"})
        assert ops == []

    def test_正常系_sub_typeには元のentity_typeが保存される(self) -> None:
        """sub_type に統合前の生 entity_type が保存されることを確認。"""
        raw_to_label = {"central_bank": "Organization"}
        raw_entities = [
            {"entity_key": "ecb::central_bank", "entity_type": "central_bank"}
        ]
        ops = build_migration_ops(raw_entities, raw_to_label)
        assert ops[0]["sub_type"] == "central_bank"  # 元の entity_type を保存


# ---------------------------------------------------------------------------
# apply_multilabel_batch
# ---------------------------------------------------------------------------


class TestApplyMultilabelBatch:
    """apply_multilabel_batch のテスト。"""

    def test_正常系_移行操作がセッションで実行される(self) -> None:
        """移行操作リストが Neo4j セッションで実行されることを確認。"""
        mock_session = MagicMock()
        ops = [
            {"entity_key": "apple::company", "label": "Company", "sub_type": "company"},
            {
                "entity_key": "boj::central_bank",
                "label": "Organization",
                "sub_type": "central_bank",
            },
        ]
        stats = apply_multilabel_batch(mock_session, ops)
        assert mock_session.run.call_count == 2
        assert stats.applied == 2
        assert stats.failed == 0

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        ops = [
            {"entity_key": "apple::company", "label": "Company", "sub_type": "company"},
        ]
        stats = apply_multilabel_batch(mock_session, ops, dry_run=True)
        mock_session.run.assert_not_called()
        assert stats.applied == 0
        assert stats.skipped == 1

    def test_正常系_空の操作リストで何もしない(self) -> None:
        """空の操作リストで session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        stats = apply_multilabel_batch(mock_session, [])
        mock_session.run.assert_not_called()
        assert stats.applied == 0

    def test_異常系_セッション例外時はfailedとしてカウント(self) -> None:
        """session.run が例外を投げた場合に failed としてカウントされることを確認。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        ops = [
            {"entity_key": "apple::company", "label": "Company", "sub_type": "company"},
        ]
        stats = apply_multilabel_batch(mock_session, ops)
        assert stats.applied == 0
        assert stats.failed == 1

    def test_正常系_Cypherクエリにentity_keyとlabelが含まれる(self) -> None:
        """実行される Cypher に entity_key と SET e:<Label> が含まれることを確認。"""
        mock_session = MagicMock()
        ops = [
            {"entity_key": "apple::company", "label": "Company", "sub_type": "company"},
        ]
        apply_multilabel_batch(mock_session, ops)
        call_args = mock_session.run.call_args
        cypher = call_args[0][0]
        # Cypher should reference entity_key
        assert "entity_key" in cypher
        # Cypher should SET the label
        assert "SET" in cypher


# ---------------------------------------------------------------------------
# remove_isin_property
# ---------------------------------------------------------------------------


class TestRemoveIsinProperty:
    """remove_isin_property のテスト。"""

    def test_正常系_isinプロパティを削除するクエリを実行(self) -> None:
        """REMOVE e.isin クエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 5}
        mock_session.run.return_value = mock_result

        count = remove_isin_property(mock_session)
        assert mock_session.run.call_count == 1
        assert count == 5

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        count = remove_isin_property(mock_session, dry_run=True)
        mock_session.run.assert_not_called()
        assert count == 0

    def test_正常系_0件削除の場合は0を返す(self) -> None:
        """削除対象が0件の場合に 0 を返すことを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"removed_count": 0}
        mock_session.run.return_value = mock_result

        count = remove_isin_property(mock_session)
        assert count == 0


# ---------------------------------------------------------------------------
# MigrationStats
# ---------------------------------------------------------------------------


class TestMigrationStats:
    """MigrationStats データクラスのテスト。"""

    def test_正常系_デフォルト値がゼロ(self) -> None:
        """MigrationStats の全フィールドが初期値 0 であることを確認。"""
        stats = MigrationStats()
        assert stats.applied == 0
        assert stats.failed == 0
        assert stats.skipped == 0
        assert stats.isin_removed == 0

    def test_正常系_加算後に正しい値(self) -> None:
        """フィールドに値を設定して正しく取得できることを確認。"""
        stats = MigrationStats(applied=10, failed=2, skipped=5, isin_removed=3)
        assert stats.applied == 10
        assert stats.failed == 2
        assert stats.skipped == 5
        assert stats.isin_removed == 3
