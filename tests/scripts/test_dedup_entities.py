"""Tests for scripts/dedup_entities.py.

Issue #303 - Wave 2: 同ラベル同名重複エンティティの名寄せ
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from dedup_entities import (
    DedupConfig,
    DedupResult,
    DuplicateGroup,
    NodeInfo,
    collect_duplicate_groups,
    format_dedup_mapping,
    merge_duplicate_groups,
    parse_args,
    save_mapping,
    select_survivor,
    verify_no_duplicates,
)

# ---------------------------------------------------------------------------
# TestDedupConfig
# ---------------------------------------------------------------------------


class TestDedupConfig:
    def test_正常系_デフォルト値が正しく設定される(self) -> None:
        config = DedupConfig()
        assert config.database == "research"
        assert config.uri == "bolt://localhost:7687"
        assert config.output_dir == Path("data/migration")
        assert config.dry_run is False

    def test_正常系_カスタム値で初期化できる(self) -> None:
        config = DedupConfig(
            database="test",
            uri="bolt://localhost:9999",
            output_dir=Path("custom/dir"),
            dry_run=True,
        )
        assert config.database == "test"
        assert config.dry_run is True


# ---------------------------------------------------------------------------
# TestNodeInfo
# ---------------------------------------------------------------------------


class TestNodeInfo:
    def test_正常系_必須フィールドで初期化できる(self) -> None:
        node = NodeInfo(
            element_id="4:abc:123",
            rel_count=10,
            props={"name": "Federal Reserve", "entity_id": "fed-001"},
        )
        assert node.element_id == "4:abc:123"
        assert node.rel_count == 10
        assert node.props["name"] == "Federal Reserve"

    def test_正常系_rel_count_0でも初期化できる(self) -> None:
        node = NodeInfo(element_id="4:abc:999", rel_count=0, props={"name": "test"})
        assert node.rel_count == 0


# ---------------------------------------------------------------------------
# TestDuplicateGroup
# ---------------------------------------------------------------------------


class TestDuplicateGroup:
    def test_正常系_複数ノードを持つグループを初期化できる(self) -> None:
        nodes = [
            NodeInfo(element_id="4:abc:1", rel_count=10, props={"name": "Japan"}),
            NodeInfo(element_id="4:abc:2", rel_count=5, props={"name": "Japan"}),
        ]
        group = DuplicateGroup(labels=["Entity", "Country"], name="Japan", nodes=nodes)
        assert group.labels == ["Entity", "Country"]
        assert group.name == "Japan"
        assert len(group.nodes) == 2

    def test_正常系_3ノードグループを初期化できる(self) -> None:
        nodes = [
            NodeInfo(element_id="4:abc:1", rel_count=20, props={}),
            NodeInfo(element_id="4:abc:2", rel_count=3, props={}),
            NodeInfo(element_id="4:abc:3", rel_count=2, props={}),
        ]
        group = DuplicateGroup(labels=["Entity"], name="米国株", nodes=nodes)
        assert len(group.nodes) == 3


# ---------------------------------------------------------------------------
# TestSelectSurvivor
# ---------------------------------------------------------------------------


class TestSelectSurvivor:
    def test_正常系_リレーション数が多い方がサバイバーになる(self) -> None:
        nodes = [
            NodeInfo(element_id="4:abc:1", rel_count=10, props={"name": "Japan"}),
            NodeInfo(element_id="4:abc:2", rel_count=50, props={"name": "Japan"}),
        ]
        group = DuplicateGroup(labels=["Entity"], name="Japan", nodes=nodes)
        survivor, to_delete = select_survivor(group)
        assert survivor.element_id == "4:abc:2"
        assert len(to_delete) == 1
        assert to_delete[0].element_id == "4:abc:1"

    def test_正常系_3ノードのうちリレーション最多がサバイバー(self) -> None:
        nodes = [
            NodeInfo(element_id="4:abc:1", rel_count=20, props={}),
            NodeInfo(element_id="4:abc:2", rel_count=3, props={}),
            NodeInfo(element_id="4:abc:3", rel_count=100, props={}),
        ]
        group = DuplicateGroup(labels=["Topic"], name="Earnings", nodes=nodes)
        survivor, to_delete = select_survivor(group)
        assert survivor.element_id == "4:abc:3"
        assert len(to_delete) == 2

    def test_正常系_リレーション数が同数の場合は最初のノードがサバイバー(self) -> None:
        nodes = [
            NodeInfo(element_id="4:abc:1", rel_count=5, props={}),
            NodeInfo(element_id="4:abc:2", rel_count=5, props={}),
        ]
        group = DuplicateGroup(labels=["Entity"], name="test", nodes=nodes)
        survivor, to_delete = select_survivor(group)
        assert survivor.element_id == "4:abc:1"
        assert len(to_delete) == 1


# ---------------------------------------------------------------------------
# TestCollectDuplicateGroups
# ---------------------------------------------------------------------------


class TestCollectDuplicateGroups:
    def test_正常系_重複グループを取得できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_records = [
            {
                "lbls": ["Entity", "Organization"],
                "name": "Federal Reserve",
                "node_list": [
                    {
                        "id": "4:abc:1",
                        "rel_count": 45,
                        "props": {
                            "entity_key": "Federal Reserve::organization",
                            "entity_id": "entity-fed",
                        },
                    },
                    {
                        "id": "4:abc:2",
                        "rel_count": 10,
                        "props": {
                            "entity_key": "Federal Reserve::central_bank",
                            "entity_id": "fed-002",
                        },
                    },
                ],
            }
        ]
        mock_session.run.return_value = iter(mock_records)

        groups = collect_duplicate_groups(mock_driver, database="research")
        assert len(groups) == 1
        assert groups[0].name == "Federal Reserve"
        assert len(groups[0].nodes) == 2

    def test_正常系_重複なしの場合空リストを返す(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = iter([])

        groups = collect_duplicate_groups(mock_driver, database="research")
        assert groups == []

    def test_正常系_3ノードグループも取得できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_records = [
            {
                "lbls": ["Topic"],
                "name": "Earnings",
                "node_list": [
                    {"id": "4:abc:1", "rel_count": 167, "props": {}},
                    {"id": "4:abc:2", "rel_count": 118, "props": {}},
                    {"id": "4:abc:3", "rel_count": 24, "props": {}},
                ],
            }
        ]
        mock_session.run.return_value = iter(mock_records)

        groups = collect_duplicate_groups(mock_driver, database="research")
        assert len(groups) == 1
        assert len(groups[0].nodes) == 3


# ---------------------------------------------------------------------------
# TestMergeDuplicateGroups
# ---------------------------------------------------------------------------


class TestMergeDuplicateGroups:
    def test_正常系_dry_runモードではNeo4jに書き込まない(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        nodes = [
            NodeInfo(
                element_id="4:abc:1", rel_count=45, props={"name": "Federal Reserve"}
            ),
            NodeInfo(
                element_id="4:abc:2", rel_count=10, props={"name": "Federal Reserve"}
            ),
        ]
        groups = [
            DuplicateGroup(
                labels=["Entity", "Organization"], name="Federal Reserve", nodes=nodes
            )
        ]

        result = merge_duplicate_groups(
            mock_driver, groups=groups, database="research", dry_run=True
        )
        # dry_run=True なので Neo4j 書き込みは呼ばれない
        mock_session.run.assert_not_called()
        assert result.merged_count == 1
        assert result.dry_run is True

    def test_正常系_空グループリストで0件マージを返す(self) -> None:
        mock_driver = MagicMock()
        result = merge_duplicate_groups(
            mock_driver, groups=[], database="research", dry_run=True
        )
        assert result.merged_count == 0
        assert result.total_deleted == 0

    def test_正常系_dry_runFalseでNeo4jに書き込む(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        # run() の戻り値（MATCH/MERGE Cypher の summary）
        mock_run_result = MagicMock()
        mock_session.run.return_value = mock_run_result

        nodes = [
            NodeInfo(
                element_id="4:abc:1", rel_count=45, props={"name": "Federal Reserve"}
            ),
            NodeInfo(
                element_id="4:abc:2", rel_count=10, props={"name": "Federal Reserve"}
            ),
        ]
        groups = [
            DuplicateGroup(
                labels=["Entity", "Organization"], name="Federal Reserve", nodes=nodes
            )
        ]

        result = merge_duplicate_groups(
            mock_driver, groups=groups, database="research", dry_run=False
        )
        # dry_run=False なので Neo4j 書き込みが呼ばれる
        assert mock_session.run.called
        assert result.merged_count == 1
        assert result.dry_run is False


# ---------------------------------------------------------------------------
# TestVerifyNoDuplicates
# ---------------------------------------------------------------------------


class TestVerifyNoDuplicates:
    def test_正常系_重複0件で検証成功を返す(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.single.return_value = {"dup_count": 0}
        mock_session.run.return_value = mock_result

        count = verify_no_duplicates(mock_driver, database="research")
        assert count == 0

    def test_正常系_重複が残っている場合件数を返す(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.single.return_value = {"dup_count": 5}
        mock_session.run.return_value = mock_result

        count = verify_no_duplicates(mock_driver, database="research")
        assert count == 5


# ---------------------------------------------------------------------------
# TestFormatDedupMapping
# ---------------------------------------------------------------------------


class TestFormatDedupMapping:
    def test_正常系_マッピングJSONに必須フィールドが含まれる(self) -> None:
        nodes_group1 = [
            NodeInfo(
                element_id="4:abc:1",
                rel_count=45,
                props={
                    "entity_key": "Federal Reserve::organization",
                    "entity_id": "entity-fed",
                },
            ),
            NodeInfo(
                element_id="4:abc:2",
                rel_count=10,
                props={
                    "entity_key": "Federal Reserve::central_bank",
                    "entity_id": "fed-002",
                },
            ),
        ]
        groups = [
            DuplicateGroup(
                labels=["Entity", "Organization"],
                name="Federal Reserve",
                nodes=nodes_group1,
            )
        ]
        result = DedupResult(
            merged_count=1,
            total_deleted=1,
            dry_run=False,
            merged_groups=[
                {
                    "labels": ["Entity", "Organization"],
                    "name": "Federal Reserve",
                    "survivor_id": "4:abc:1",
                    "deleted_ids": ["4:abc:2"],
                }
            ],
        )
        mapping = format_dedup_mapping(
            groups=groups, result=result, date_str="20260402"
        )

        assert "generated_at" in mapping
        assert "20260402" in mapping["generated_at"]
        assert "total_merged_groups" in mapping
        assert mapping["total_merged_groups"] == 1
        assert "total_deleted_nodes" in mapping
        assert mapping["total_deleted_nodes"] == 1
        assert "mappings" in mapping
        assert len(mapping["mappings"]) == 1

    def test_正常系_マッピングエントリに必須フィールドがある(self) -> None:
        nodes = [
            NodeInfo(element_id="4:abc:1", rel_count=45, props={"entity_key": "fed"}),
            NodeInfo(element_id="4:abc:2", rel_count=10, props={}),
        ]
        groups = [DuplicateGroup(labels=["Entity"], name="FedRes", nodes=nodes)]
        result = DedupResult(
            merged_count=1,
            total_deleted=1,
            dry_run=False,
            merged_groups=[
                {
                    "labels": ["Entity"],
                    "name": "FedRes",
                    "survivor_id": "4:abc:1",
                    "deleted_ids": ["4:abc:2"],
                }
            ],
        )
        mapping = format_dedup_mapping(
            groups=groups, result=result, date_str="20260402"
        )

        entry = mapping["mappings"][0]
        assert "labels" in entry
        assert "name" in entry
        assert "survivor_id" in entry
        assert "deleted_ids" in entry
        assert "survivor_props" in entry

    def test_正常系_空グループで空マッピングを返す(self) -> None:
        result = DedupResult(
            merged_count=0, total_deleted=0, dry_run=True, merged_groups=[]
        )
        mapping = format_dedup_mapping(groups=[], result=result, date_str="20260402")
        assert mapping["total_merged_groups"] == 0
        assert mapping["mappings"] == []


# ---------------------------------------------------------------------------
# TestSaveMapping
# ---------------------------------------------------------------------------


class TestSaveMapping:
    def test_正常系_JSONファイルが正しいパスに保存される(self, tmp_path: Path) -> None:
        mapping = {
            "generated_at": "20260402",
            "total_merged_groups": 1,
            "total_deleted_nodes": 1,
            "mappings": [],
        }
        output_path = save_mapping(
            mapping=mapping,
            output_dir=tmp_path,
            filename="dedup_entity_mapping.json",
        )
        assert output_path.exists()
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert loaded["total_merged_groups"] == 1

    def test_正常系_出力ディレクトリが存在しない場合自動作成される(
        self, tmp_path: Path
    ) -> None:
        new_dir = tmp_path / "migration" / "sub"
        mapping = {"total_merged_groups": 0, "mappings": []}
        output_path = save_mapping(
            mapping=mapping,
            output_dir=new_dir,
            filename="test.json",
        )
        assert output_path.exists()
        assert new_dir.is_dir()

    def test_正常系_UTF8エンコードで日本語が保存される(self, tmp_path: Path) -> None:
        mapping = {"note": "名寄せマッピング", "total_merged_groups": 5}
        output_path = save_mapping(
            mapping=mapping,
            output_dir=tmp_path,
            filename="test.json",
        )
        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        assert loaded["note"] == "名寄せマッピング"

    def test_正常系_JSONが整形されている(self, tmp_path: Path) -> None:
        mapping = {"total_merged_groups": 0}
        output_path = save_mapping(
            mapping=mapping, output_dir=tmp_path, filename="test.json"
        )
        content = output_path.read_text(encoding="utf-8")
        assert "\n" in content


# ---------------------------------------------------------------------------
# TestParseArgs
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_引数なしでデフォルト設定が返る(self) -> None:
        args = parse_args([])
        assert args.database == "research"
        assert args.dry_run is False
        assert args.output_dir == "data/migration"

    def test_正常系_dry_runフラグが正しくパースされる(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_正常系_database引数を上書きできる(self) -> None:
        args = parse_args(["--database", "test"])
        assert args.database == "test"

    def test_正常系_output_dir引数を上書きできる(self) -> None:
        args = parse_args(["--output-dir", "custom/path"])
        assert args.output_dir == "custom/path"


# ---------------------------------------------------------------------------
# TestDedupResult
# ---------------------------------------------------------------------------


class TestDedupResult:
    def test_正常系_必須フィールドで初期化できる(self) -> None:
        result = DedupResult(
            merged_count=3,
            total_deleted=5,
            dry_run=False,
            merged_groups=[],
        )
        assert result.merged_count == 3
        assert result.total_deleted == 5
        assert result.dry_run is False

    def test_正常系_dry_runTrueで初期化できる(self) -> None:
        result = DedupResult(
            merged_count=0, total_deleted=0, dry_run=True, merged_groups=[]
        )
        assert result.dry_run is True
