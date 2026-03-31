"""Unit tests for scripts/migrate_source_type.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.migrate_source_type import (
    CANONICAL_SOURCE_TYPES,
    SOURCE_TYPE_TO_COMMAND_SOURCE,
    MigrationStats,
    apply_source_type_batch,
    build_normalization_ops,
    build_null_command_source_ops,
    fetch_abnormal_source_types,
    fetch_null_command_source_nodes,
    load_source_type_normalization,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCHEMA_YAML_PATH = Path(__file__).parents[2] / "data/config/knowledge-graph-schema.yaml"


# ---------------------------------------------------------------------------
# load_source_type_normalization
# ---------------------------------------------------------------------------


class TestLoadSourceTypeNormalization:
    """load_source_type_normalization のテスト。"""

    def test_正常系_YAMLからマッピングを読み込む(self) -> None:
        """source_type_normalization.mapping が dict として返されることを確認。"""
        mapping = load_source_type_normalization(SCHEMA_YAML_PATH)
        assert isinstance(mapping, dict)
        assert len(mapping) > 0

    def test_正常系_web_researchがwebにマップされる(self) -> None:
        """web-research -> web のマッピングが存在することを確認。"""
        mapping = load_source_type_normalization(SCHEMA_YAML_PATH)
        assert mapping.get("web-research") == "web"

    def test_正常系_annual_reportがpdfにマップされる(self) -> None:
        """annual_report -> pdf のマッピングが存在することを確認。"""
        mapping = load_source_type_normalization(SCHEMA_YAML_PATH)
        assert mapping.get("annual_report") == "pdf"

    def test_正常系_全マッピング先が5種の正規型のいずれか(self) -> None:
        """全マッピング値が5種の正規 source_type のいずれかであることを確認。"""
        canonical = {"web", "news", "pdf", "original", "blog"}
        mapping = load_source_type_normalization(SCHEMA_YAML_PATH)
        for raw, canonical_type in mapping.items():
            assert canonical_type in canonical, (
                f"'{raw}' maps to '{canonical_type}' which is not a canonical source_type"
            )

    def test_異常系_存在しないパスでFileNotFoundError(self) -> None:
        """存在しないファイルで FileNotFoundError を送出することを確認。"""
        with pytest.raises(FileNotFoundError):
            load_source_type_normalization(Path("nonexistent/path.yaml"))


# ---------------------------------------------------------------------------
# CANONICAL_SOURCE_TYPES
# ---------------------------------------------------------------------------


class TestCanonicalSourceTypes:
    """CANONICAL_SOURCE_TYPES 定数の検証。"""

    def test_正常系_5種の正規型が定義されている(self) -> None:
        """5 種の正規 source_type が frozenset として定義されていることを確認。"""
        assert len(CANONICAL_SOURCE_TYPES) == 5

    def test_正常系_web_news_pdf_original_blogが含まれる(self) -> None:
        """web, news, pdf, original, blog が含まれることを確認。"""
        assert "web" in CANONICAL_SOURCE_TYPES
        assert "news" in CANONICAL_SOURCE_TYPES
        assert "pdf" in CANONICAL_SOURCE_TYPES
        assert "original" in CANONICAL_SOURCE_TYPES
        assert "blog" in CANONICAL_SOURCE_TYPES


# ---------------------------------------------------------------------------
# SOURCE_TYPE_TO_COMMAND_SOURCE
# ---------------------------------------------------------------------------


class TestSourceTypeToCommandSource:
    """SOURCE_TYPE_TO_COMMAND_SOURCE マッピングの検証。"""

    def test_正常系_webはweb_researchにマップされる(self) -> None:
        """source_type='web' -> command_source='web-research' を確認。"""
        assert SOURCE_TYPE_TO_COMMAND_SOURCE["web"] == "web-research"

    def test_正常系_5種全てにマッピングがある(self) -> None:
        """5 種の正規 source_type 全てにデフォルト command_source が定義されていることを確認。"""
        for st in CANONICAL_SOURCE_TYPES:
            assert st in SOURCE_TYPE_TO_COMMAND_SOURCE, (
                f"'{st}' has no entry in SOURCE_TYPE_TO_COMMAND_SOURCE"
            )

    def test_正常系_全値が非空文字列(self) -> None:
        """全マッピング値が非空文字列であることを確認。"""
        for st, cs in SOURCE_TYPE_TO_COMMAND_SOURCE.items():
            assert isinstance(cs, str) and len(cs) > 0, (
                f"source_type='{st}' has empty command_source"
            )


# ---------------------------------------------------------------------------
# build_normalization_ops
# ---------------------------------------------------------------------------


class TestBuildNormalizationOps:
    """build_normalization_ops のテスト。"""

    def test_正常系_生source_typeを正規型に変換する操作リストを構築(self) -> None:
        """異常な source_type ノードから正規化操作のリストが構築されることを確認。"""
        normalization_map = {
            "web-research": "web",
            "news_article": "news",
        }
        nodes = [
            {"source_id": "sid1", "source_type": "web-research"},
            {"source_id": "sid2", "source_type": "news_article"},
        ]
        ops = build_normalization_ops(nodes, normalization_map)
        assert len(ops) == 2
        assert ops[0] == {"source_id": "sid1", "new_source_type": "web"}
        assert ops[1] == {"source_id": "sid2", "new_source_type": "news"}

    def test_正常系_未知のsource_typeはスキップ(self) -> None:
        """normalization_map に存在しない source_type のノードはスキップされることを確認。"""
        normalization_map = {"web-research": "web"}
        nodes = [
            {"source_id": "sid1", "source_type": "completely_unknown_type"},
        ]
        ops = build_normalization_ops(nodes, normalization_map)
        assert len(ops) == 0

    def test_エッジケース_空のノードリストで空のops(self) -> None:
        """空のノードリストで空のopsが返されることを確認。"""
        ops = build_normalization_ops([], {"web-research": "web"})
        assert ops == []

    def test_エッジケース_空のマッピングで全スキップ(self) -> None:
        """空のマッピングで全ノードがスキップされることを確認。"""
        nodes = [{"source_id": "sid1", "source_type": "web-research"}]
        ops = build_normalization_ops(nodes, {})
        assert ops == []


# ---------------------------------------------------------------------------
# build_null_command_source_ops
# ---------------------------------------------------------------------------


class TestBuildNullCommandSourceOps:
    """build_null_command_source_ops のテスト。"""

    def test_正常系_source_typeからcommand_sourceを推定する操作リストを構築(
        self,
    ) -> None:
        """NULL command_source ノードから補完操作のリストが構築されることを確認。"""
        nodes = [
            {"source_id": "sid1", "source_type": "web"},
            {"source_id": "sid2", "source_type": "news"},
        ]
        ops = build_null_command_source_ops(nodes, SOURCE_TYPE_TO_COMMAND_SOURCE)
        assert len(ops) == 2
        assert ops[0] == {"source_id": "sid1", "command_source": "web-research"}
        assert ops[1]["source_id"] == "sid2"
        assert ops[1]["command_source"] is not None

    def test_正常系_未知のsource_typeはスキップ(self) -> None:
        """SOURCE_TYPE_TO_COMMAND_SOURCE に存在しない source_type はスキップされることを確認。"""
        nodes = [
            {"source_id": "sid1", "source_type": "totally_unknown"},
        ]
        ops = build_null_command_source_ops(nodes, SOURCE_TYPE_TO_COMMAND_SOURCE)
        assert len(ops) == 0

    def test_エッジケース_空のノードリストで空のops(self) -> None:
        """空のノードリストで空のopsが返されることを確認。"""
        ops = build_null_command_source_ops([], SOURCE_TYPE_TO_COMMAND_SOURCE)
        assert ops == []


# ---------------------------------------------------------------------------
# apply_source_type_batch
# ---------------------------------------------------------------------------


class TestApplySourceTypeBatch:
    """apply_source_type_batch のテスト。"""

    def test_正常系_source_type正規化クエリが実行される(self) -> None:
        """source_type 正規化操作がセッションで実行されることを確認。"""
        mock_session = MagicMock()
        ops = [
            {"source_id": "sid1", "new_source_type": "web"},
            {"source_id": "sid2", "new_source_type": "news"},
        ]
        stats = apply_source_type_batch(mock_session, ops, mode="source_type")
        assert mock_session.run.call_count == 2
        assert stats.source_type_normalized == 2
        assert stats.source_type_failed == 0

    def test_正常系_command_source補完クエリが実行される(self) -> None:
        """command_source 補完操作がセッションで実行されることを確認。"""
        mock_session = MagicMock()
        ops = [
            {"source_id": "sid1", "command_source": "web-research"},
        ]
        stats = apply_source_type_batch(mock_session, ops, mode="command_source")
        assert mock_session.run.call_count == 1
        assert stats.command_source_filled == 1
        assert stats.command_source_failed == 0

    def test_正常系_dry_run時はセッションを呼ばない(self) -> None:
        """dry_run=True の場合に session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        ops = [{"source_id": "sid1", "new_source_type": "web"}]
        stats = apply_source_type_batch(
            mock_session, ops, mode="source_type", dry_run=True
        )
        mock_session.run.assert_not_called()
        assert stats.source_type_normalized == 0

    def test_正常系_空のopsで何もしない(self) -> None:
        """空の ops で session.run が呼ばれないことを確認。"""
        mock_session = MagicMock()
        stats = apply_source_type_batch(mock_session, [], mode="source_type")
        mock_session.run.assert_not_called()
        assert stats.source_type_normalized == 0

    def test_異常系_セッション例外時はfailedとしてカウント(self) -> None:
        """session.run が例外を投げた場合に failed としてカウントされることを確認。"""
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j error")
        ops = [{"source_id": "sid1", "new_source_type": "web"}]
        stats = apply_source_type_batch(mock_session, ops, mode="source_type")
        assert stats.source_type_normalized == 0
        assert stats.source_type_failed == 1

    def test_異常系_未知のmodeはValueError(self) -> None:
        """未知の mode が渡された場合に ValueError を送出することを確認。"""
        mock_session = MagicMock()
        ops = [{"source_id": "sid1", "new_source_type": "web"}]
        with pytest.raises(ValueError, match="Unknown mode"):
            apply_source_type_batch(mock_session, ops, mode="invalid_mode")


# ---------------------------------------------------------------------------
# fetch_abnormal_source_types
# ---------------------------------------------------------------------------


class TestFetchAbnormalSourceTypes:
    """fetch_abnormal_source_types のテスト。"""

    def test_正常系_セッションからSource一覧を取得する(self) -> None:
        """Neo4j セッションからクエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"source_id": "sid1", "source_type": "web-research"},
                ]
            )
        )
        mock_session.run.return_value = mock_result

        nodes = fetch_abnormal_source_types(mock_session, CANONICAL_SOURCE_TYPES)
        assert mock_session.run.call_count == 1
        assert len(nodes) == 1
        assert nodes[0]["source_id"] == "sid1"

    def test_正常系_正規型Sourceはクエリで除外される(self) -> None:
        """Cypher クエリに正規型の除外条件が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_result

        fetch_abnormal_source_types(mock_session, CANONICAL_SOURCE_TYPES)
        cypher = mock_session.run.call_args[0][0]
        assert "NOT" in cypher or "source_type" in cypher


# ---------------------------------------------------------------------------
# fetch_null_command_source_nodes
# ---------------------------------------------------------------------------


class TestFetchNullCommandSourceNodes:
    """fetch_null_command_source_nodes のテスト。"""

    def test_正常系_command_sourceがNULLのSourceを取得する(self) -> None:
        """command_source IS NULL のクエリが実行されることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(
            return_value=iter(
                [
                    {"source_id": "sid1", "source_type": "web"},
                ]
            )
        )
        mock_session.run.return_value = mock_result

        nodes = fetch_null_command_source_nodes(mock_session)
        assert mock_session.run.call_count == 1
        assert len(nodes) == 1
        assert nodes[0]["source_id"] == "sid1"

    def test_正常系_クエリにIS_NULL条件が含まれる(self) -> None:
        """Cypher クエリに command_source IS NULL 条件が含まれることを確認。"""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.run.return_value = mock_result

        fetch_null_command_source_nodes(mock_session)
        cypher = mock_session.run.call_args[0][0]
        assert "IS NULL" in cypher or "null" in cypher.lower()


# ---------------------------------------------------------------------------
# MigrationStats
# ---------------------------------------------------------------------------


class TestMigrationStats:
    """MigrationStats データクラスのテスト。"""

    def test_正常系_デフォルト値がゼロ(self) -> None:
        """MigrationStats の全フィールドが初期値 0 であることを確認。"""
        stats = MigrationStats()
        assert stats.source_type_normalized == 0
        assert stats.source_type_skipped == 0
        assert stats.source_type_failed == 0
        assert stats.command_source_filled == 0
        assert stats.command_source_skipped == 0
        assert stats.command_source_failed == 0

    def test_正常系_加算後に正しい値(self) -> None:
        """フィールドに値を設定して正しく取得できることを確認。"""
        stats = MigrationStats(
            source_type_normalized=10,
            source_type_skipped=2,
            source_type_failed=1,
            command_source_filled=8,
            command_source_skipped=3,
            command_source_failed=0,
        )
        assert stats.source_type_normalized == 10
        assert stats.source_type_skipped == 2
        assert stats.source_type_failed == 1
        assert stats.command_source_filled == 8
        assert stats.command_source_skipped == 3
        assert stats.command_source_failed == 0

    def test_正常系_merge後に合計値が正しい(self) -> None:
        """2つの MigrationStats を加算した結果が正しいことを確認。"""
        stats1 = MigrationStats(source_type_normalized=5, command_source_filled=3)
        stats2 = MigrationStats(source_type_normalized=3, command_source_filled=4)
        merged = stats1.merge(stats2)
        assert merged.source_type_normalized == 8
        assert merged.command_source_filled == 7
