"""Tests for scripts/snapshot_pre_migration.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from snapshot_pre_migration import (
    QueryResult,
    SnapshotConfig,
    collect_counts,
    format_snapshot,
    parse_args,
    save_snapshot,
)

# ---------------------------------------------------------------------------
# TestSnapshotConfig
# ---------------------------------------------------------------------------


class TestSnapshotConfig:
    def test_正常系_デフォルト値が正しく設定される(self) -> None:
        config = SnapshotConfig()
        assert config.database == "research"
        assert config.uri == "bolt://localhost:7687"
        assert config.output_dir == Path("data/migration")

    def test_正常系_カスタム値で初期化できる(self) -> None:
        config = SnapshotConfig(
            database="test_db",
            uri="bolt://localhost:9999",
            output_dir=Path("custom/dir"),
        )
        assert config.database == "test_db"
        assert config.uri == "bolt://localhost:9999"
        assert config.output_dir == Path("custom/dir")


# ---------------------------------------------------------------------------
# TestParseArgs
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_引数なしでデフォルト設定が返る(self) -> None:
        args = parse_args([])
        assert args.database == "research"
        assert args.output_dir == "data/migration"

    def test_正常系_database引数を上書きできる(self) -> None:
        args = parse_args(["--database", "test"])
        assert args.database == "test"

    def test_正常系_output_dir引数を上書きできる(self) -> None:
        args = parse_args(["--output-dir", "custom/path"])
        assert args.output_dir == "custom/path"


# ---------------------------------------------------------------------------
# TestQueryResult
# ---------------------------------------------------------------------------


class TestQueryResult:
    def test_正常系_node_countとrel_countを持つ(self) -> None:
        result = QueryResult(node_count=100, rel_count=200)
        assert result.node_count == 100
        assert result.rel_count == 200

    def test_正常系_label_countsとrel_type_countsを持つ(self) -> None:
        result = QueryResult(
            node_count=5,
            rel_count=10,
            label_counts={"Entity": 3, "Fact": 2},
            rel_type_counts={"ABOUT": 10},
        )
        assert result.label_counts == {"Entity": 3, "Fact": 2}
        assert result.rel_type_counts == {"ABOUT": 10}


# ---------------------------------------------------------------------------
# TestCollectCounts
# ---------------------------------------------------------------------------


class TestCollectCounts:
    def test_正常系_Neo4jからノード数とリレーション数を取得する(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # ノード総数
        mock_node_result = MagicMock()
        mock_node_result.single.return_value = {"count": 1658}

        # リレーション総数
        mock_rel_result = MagicMock()
        mock_rel_result.single.return_value = {"count": 6268}

        # ラベル別件数（dictリストを直接返す）
        label_records = [
            {"label": "Entity", "count": 1658},
            {"label": "Fact", "count": 2000},
        ]

        # リレーションタイプ別件数
        rel_type_records = [
            {"type": "ABOUT", "count": 5343},
        ]

        def run_side_effect(query: str, **kwargs: object) -> object:
            q = query.strip()
            # 総数クエリは1行 (UNWIND/WITH を含まない)
            if q == "MATCH (n) RETURN COUNT(n) AS count":
                return mock_node_result
            elif q == "MATCH ()-[r]->() RETURN COUNT(r) AS count":
                return mock_rel_result
            elif "labels(n)" in q:
                return iter(label_records)
            elif "type(r)" in q:
                return iter(rel_type_records)
            return MagicMock()

        mock_session.run.side_effect = run_side_effect

        result = collect_counts(mock_driver, database="research")
        assert result.node_count == 1658
        assert result.rel_count == 6268

    def test_正常系_Entity件数が正しく取得される(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_node_result = MagicMock()
        mock_node_result.single.return_value = {"count": 100}
        mock_rel_result = MagicMock()
        mock_rel_result.single.return_value = {"count": 50}

        # ラベル別: Entity=1658件
        label_records = [{"label": "Entity", "count": 1658}]
        rel_type_records = [
            {"type": "ABOUT", "count": 5343},
            {"type": "MENTIONS", "count": 925},
        ]

        def run_side_effect(query: str, **kwargs: object) -> object:
            q = query.strip()
            if q == "MATCH (n) RETURN COUNT(n) AS count":
                return mock_node_result
            elif q == "MATCH ()-[r]->() RETURN COUNT(r) AS count":
                return mock_rel_result
            elif "labels(n)" in q:
                return iter(label_records)
            elif "type(r)" in q:
                return iter(rel_type_records)
            return MagicMock()

        mock_session.run.side_effect = run_side_effect

        result = collect_counts(mock_driver, database="research")
        assert result.label_counts.get("Entity") == 1658
        assert result.rel_type_counts.get("ABOUT") == 5343
        assert result.rel_type_counts.get("MENTIONS") == 925


# ---------------------------------------------------------------------------
# TestFormatSnapshot
# ---------------------------------------------------------------------------


class TestFormatSnapshot:
    def test_正常系_スナップショットJSONに必須フィールドが含まれる(self) -> None:
        result = QueryResult(
            node_count=1658,
            rel_count=6268,
            label_counts={"Entity": 1658, "Fact": 2000},
            rel_type_counts={"ABOUT": 5343, "MENTIONS": 925},
        )
        snapshot = format_snapshot(result, database="research", date_str="20260402")

        assert "snapshot_date" in snapshot
        assert "database" in snapshot
        assert snapshot["database"] == "research"
        assert "node_count" in snapshot
        assert snapshot["node_count"] == 1658
        assert "rel_count" in snapshot
        assert snapshot["rel_count"] == 6268
        assert "label_counts" in snapshot
        assert "rel_type_counts" in snapshot

    def test_正常系_label_countsにEntityが含まれる(self) -> None:
        result = QueryResult(
            node_count=1658,
            rel_count=6268,
            label_counts={"Entity": 1658},
            rel_type_counts={"ABOUT": 5343},
        )
        snapshot = format_snapshot(result, database="research", date_str="20260402")
        assert snapshot["label_counts"]["Entity"] == 1658

    def test_正常系_snapshot_dateが指定した日付を含む(self) -> None:
        result = QueryResult(node_count=0, rel_count=0)
        snapshot = format_snapshot(result, database="research", date_str="20260402")
        assert "20260402" in snapshot["snapshot_date"]


# ---------------------------------------------------------------------------
# TestSaveSnapshot
# ---------------------------------------------------------------------------


class TestSaveSnapshot:
    def test_正常系_JSONファイルが正しいパスに保存される(self, tmp_path: Path) -> None:
        snapshot = {
            "snapshot_date": "20260402",
            "database": "research",
            "node_count": 1658,
            "rel_count": 6268,
            "label_counts": {"Entity": 1658},
            "rel_type_counts": {"ABOUT": 5343},
        }
        output_path = save_snapshot(
            snapshot,
            output_dir=tmp_path,
            filename="20260402_pre_migration_counts.json",
        )

        assert output_path.exists()
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert loaded["node_count"] == 1658

    def test_正常系_出力ディレクトリが存在しない場合自動作成される(
        self, tmp_path: Path
    ) -> None:
        new_dir = tmp_path / "migration" / "sub"
        snapshot = {"node_count": 10, "rel_count": 5}
        output_path = save_snapshot(
            snapshot,
            output_dir=new_dir,
            filename="test.json",
        )
        assert output_path.exists()
        assert new_dir.is_dir()

    def test_正常系_UTF8エンコードで日本語が保存される(self, tmp_path: Path) -> None:
        snapshot = {"note": "移行前スナップショット", "node_count": 100}
        output_path = save_snapshot(
            snapshot,
            output_dir=tmp_path,
            filename="test.json",
        )
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert loaded["note"] == "移行前スナップショット"

    def test_正常系_JSONが整形されている(self, tmp_path: Path) -> None:
        snapshot = {"node_count": 10}
        output_path = save_snapshot(snapshot, output_dir=tmp_path, filename="test.json")
        content = output_path.read_text(encoding="utf-8")
        # インデント付きJSON（整形済み）
        assert "\n" in content
