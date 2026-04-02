"""Tests for scripts/process_isolated_nodes.py.

Issue #306 - Wave 2: 孤立ノード処理（Entity 64 件・Fact 577 件）
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from process_isolated_nodes import (
    IsolatedEntityNode,
    IsolatedFactNode,
    ProcessConfig,
    ProcessResult,
    archive_nodes,
    collect_isolated_entities,
    collect_isolated_facts,
    format_process_report,
    parse_args,
    save_report,
    verify_isolation_resolved,
)

# ---------------------------------------------------------------------------
# TestProcessConfig
# ---------------------------------------------------------------------------


class TestProcessConfig:
    def test_正常系_デフォルト値が正しく設定される(self) -> None:
        config = ProcessConfig()
        assert config.database == "research"
        assert config.uri == "bolt://localhost:7687"
        assert config.output_dir == Path("data/migration")
        assert config.dry_run is False
        assert config.batch_size == 100

    def test_正常系_カスタム値で初期化できる(self) -> None:
        config = ProcessConfig(
            database="test_db",
            uri="bolt://localhost:9999",
            output_dir=Path("custom/dir"),
            dry_run=True,
            batch_size=50,
        )
        assert config.database == "test_db"
        assert config.dry_run is True
        assert config.batch_size == 50


# ---------------------------------------------------------------------------
# TestIsolatedEntityNode
# ---------------------------------------------------------------------------


class TestIsolatedEntityNode:
    def test_正常系_必須フィールドで初期化できる(self) -> None:
        node = IsolatedEntityNode(
            element_id="4:abc:123",
            name="Arthur Angelo Syailendra",
            entity_key="Arthur Angelo Syailendra::person",
            entity_type="person",
        )
        assert node.element_id == "4:abc:123"
        assert node.name == "Arthur Angelo Syailendra"
        assert node.entity_key == "Arthur Angelo Syailendra::person"
        assert node.entity_type == "person"

    def test_正常系_オプションフィールドがNoneでも初期化できる(self) -> None:
        node = IsolatedEntityNode(
            element_id="4:abc:999",
            name="Unknown Person",
            entity_key=None,
            entity_type=None,
        )
        assert node.entity_key is None
        assert node.entity_type is None


# ---------------------------------------------------------------------------
# TestIsolatedFactNode
# ---------------------------------------------------------------------------


class TestIsolatedFactNode:
    def test_正常系_全フィールドで初期化できる(self) -> None:
        node = IsolatedFactNode(
            element_id="4:def:456",
            fact_id="fact-001",
            content="S&P 500 rose 1.2% on Monday.",
            source_type="news",
            source_url="https://example.com/article",
        )
        assert node.element_id == "4:def:456"
        assert node.fact_id == "fact-001"
        assert node.source_type == "news"

    def test_正常系_オプションフィールドがNoneでも初期化できる(self) -> None:
        node = IsolatedFactNode(
            element_id="4:def:789",
            fact_id=None,
            content=None,
            source_type=None,
            source_url=None,
        )
        assert node.fact_id is None
        assert node.source_type is None


# ---------------------------------------------------------------------------
# TestProcessResult
# ---------------------------------------------------------------------------


class TestProcessResult:
    def test_正常系_デフォルト値が0で初期化される(self) -> None:
        result = ProcessResult()
        assert result.entity_archived == 0
        assert result.fact_archived == 0
        assert result.entity_remaining == 0
        assert result.fact_remaining == 0
        assert result.dry_run is False

    def test_正常系_dry_run_Trueで初期化できる(self) -> None:
        result = ProcessResult(dry_run=True, entity_archived=18, fact_archived=550)
        assert result.dry_run is True
        assert result.entity_archived == 18
        assert result.fact_archived == 550


# ---------------------------------------------------------------------------
# TestCollectIsolatedEntities
# ---------------------------------------------------------------------------


class TestCollectIsolatedEntities:
    def test_正常系_孤立Entityノードを取得できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_records = [
            {
                "element_id": "4:abc:1",
                "name": "Didier Sornette",
                "entity_key": "Didier Sornette::person",
                "entity_type": "person",
            },
            {
                "element_id": "4:abc:2",
                "name": "Kiyoshi Izumi",
                "entity_key": "Kiyoshi Izumi::person",
                "entity_type": "person",
            },
        ]
        mock_session.run.return_value = mock_records

        nodes = collect_isolated_entities(mock_driver, database="research")

        assert len(nodes) == 2
        assert nodes[0].element_id == "4:abc:1"
        assert nodes[0].name == "Didier Sornette"
        assert nodes[1].name == "Kiyoshi Izumi"

    def test_正常系_孤立ノードがない場合は空リストを返す(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []

        nodes = collect_isolated_entities(mock_driver)
        assert nodes == []

    def test_正常系_nameがNoneの場合は空文字として処理される(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_records = [
            {
                "element_id": "4:abc:3",
                "name": None,
                "entity_key": "unknown::person",
                "entity_type": "person",
            },
        ]
        mock_session.run.return_value = mock_records

        nodes = collect_isolated_entities(mock_driver)
        assert len(nodes) == 1
        assert nodes[0].name == ""


# ---------------------------------------------------------------------------
# TestCollectIsolatedFacts
# ---------------------------------------------------------------------------


class TestCollectIsolatedFacts:
    def test_正常系_孤立Factノードを取得できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_records = [
            {
                "element_id": "4:ghi:10",
                "fact_id": "fact-001",
                "content": "The Federal Reserve raised rates.",
                "source_type": "news",
                "source_url": "https://example.com/1",
            },
            {
                "element_id": "4:ghi:11",
                "fact_id": "fact-002",
                "content": "S&P 500 reached new highs.",
                "source_type": "web",
                "source_url": "https://example.com/2",
            },
        ]
        mock_session.run.return_value = mock_records

        facts = collect_isolated_facts(mock_driver, database="research")

        assert len(facts) == 2
        assert facts[0].element_id == "4:ghi:10"
        assert facts[0].source_type == "news"
        assert facts[1].source_type == "web"

    def test_正常系_content100文字超はプレビューに切り詰められる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        long_content = "A" * 150
        mock_records = [
            {
                "element_id": "4:ghi:20",
                "fact_id": None,
                "content": long_content,
                "source_type": "pdf",
                "source_url": None,
            },
        ]
        mock_session.run.return_value = mock_records

        facts = collect_isolated_facts(mock_driver)
        assert facts[0].content is not None
        assert len(facts[0].content) == 103  # 100 + "..."
        assert facts[0].content.endswith("...")

    def test_正常系_content100文字以内はそのまま保持される(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        short_content = "Short content."
        mock_records = [
            {
                "element_id": "4:ghi:21",
                "fact_id": None,
                "content": short_content,
                "source_type": "web",
                "source_url": None,
            },
        ]
        mock_session.run.return_value = mock_records

        facts = collect_isolated_facts(mock_driver)
        assert facts[0].content == short_content

    def test_正常系_孤立ノードがない場合は空リストを返す(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = []

        facts = collect_isolated_facts(mock_driver)
        assert facts == []


# ---------------------------------------------------------------------------
# TestArchiveNodes
# ---------------------------------------------------------------------------


class TestArchiveNodes:
    def test_正常系_entityノードにArchivedラベルを付与できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_record = {"archived_count": 3}
        mock_session.run.return_value.single.return_value = mock_record

        count = archive_nodes(
            mock_driver,
            element_ids=["4:abc:1", "4:abc:2", "4:abc:3"],
            node_type="entity",
            database="research",
        )
        assert count == 3

    def test_正常系_factノードにArchivedラベルを付与できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_record = {"archived_count": 5}
        mock_session.run.return_value.single.return_value = mock_record

        count = archive_nodes(
            mock_driver,
            element_ids=["4:def:1", "4:def:2", "4:def:3", "4:def:4", "4:def:5"],
            node_type="fact",
            database="research",
        )
        assert count == 5

    def test_正常系_空リストの場合は0を返す(self) -> None:
        mock_driver = MagicMock()
        count = archive_nodes(mock_driver, element_ids=[], node_type="entity")
        assert count == 0
        mock_driver.session.assert_not_called()

    def test_正常系_バッチサイズで分割処理される(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_record = {"archived_count": 2}
        mock_session.run.return_value.single.return_value = mock_record

        # 5件を batch_size=2 で処理 → 3バッチ
        element_ids = ["4:abc:1", "4:abc:2", "4:abc:3", "4:abc:4", "4:abc:5"]
        archive_nodes(
            mock_driver,
            element_ids=element_ids,
            node_type="entity",
            batch_size=2,
        )
        # 3バッチ × 2件 = 6 (最後のバッチは1件だが mock は常に2を返す)
        assert mock_driver.session.call_count == 3

    def test_正常系_resultがNoneの場合は0を加算する(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value.single.return_value = None

        count = archive_nodes(
            mock_driver,
            element_ids=["4:abc:1"],
            node_type="entity",
        )
        assert count == 0


# ---------------------------------------------------------------------------
# TestVerifyIsolationResolved
# ---------------------------------------------------------------------------


class TestVerifyIsolationResolved:
    def test_正常系_孤立ノードが0件の場合を確認できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value.single.side_effect = [
            {"remaining_count": 0},  # entity query
            {"remaining_count": 0},  # fact query
        ]

        entity_rem, fact_rem = verify_isolation_resolved(mock_driver)
        assert entity_rem == 0
        assert fact_rem == 0

    def test_正常系_孤立ノードが残存する場合を検出できる(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value.single.side_effect = [
            {"remaining_count": 5},
            {"remaining_count": 100},
        ]

        entity_rem, fact_rem = verify_isolation_resolved(mock_driver)
        assert entity_rem == 5
        assert fact_rem == 100

    def test_正常系_resultがNoneの場合は0を返す(self) -> None:
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__.return_value = mock_session

        mock_session.run.return_value.single.side_effect = [None, None]

        entity_rem, fact_rem = verify_isolation_resolved(mock_driver)
        assert entity_rem == 0
        assert fact_rem == 0


# ---------------------------------------------------------------------------
# TestFormatProcessReport
# ---------------------------------------------------------------------------


class TestFormatProcessReport:
    def _make_entities(self, count: int = 3) -> list[IsolatedEntityNode]:
        return [
            IsolatedEntityNode(
                element_id=f"4:abc:{i}",
                name=f"Person {i}",
                entity_key=f"person_{i}::person",
                entity_type="person",
            )
            for i in range(count)
        ]

    def _make_facts(
        self, count: int = 5, source_types: list[str] | None = None
    ) -> list[IsolatedFactNode]:
        types = source_types or ["news", "web", "null", "pdf", "news"]
        return [
            IsolatedFactNode(
                element_id=f"4:def:{i}",
                fact_id=f"fact-{i:03d}",
                content=f"Content {i}",
                source_type=types[i % len(types)],
                source_url=f"https://example.com/{i}",
            )
            for i in range(count)
        ]

    def test_正常系_レポートに必須フィールドが含まれる(self) -> None:
        entities = self._make_entities(3)
        facts = self._make_facts(5)
        result = ProcessResult(entity_archived=3, fact_archived=5)

        report = format_process_report(entities, facts, result, "20260402")

        assert report["database"] == "research"
        assert report["issue"] == "#306"
        assert "policy" in report
        assert "summary" in report
        assert report["summary"]["entity_detected"] == 3
        assert report["summary"]["fact_detected"] == 5

    def test_正常系_summary統計が正しく集計される(self) -> None:
        entities = self._make_entities(2)
        facts = self._make_facts(4, source_types=["news", "news", "web", "pdf"])
        result = ProcessResult(
            entity_archived=2,
            fact_archived=4,
            entity_remaining=0,
            fact_remaining=0,
        )

        report = format_process_report(entities, facts, result, "20260402")
        summary = report["summary"]

        assert summary["entity_archived"] == 2
        assert summary["fact_archived"] == 4
        assert summary["entity_remaining_after"] == 0
        assert summary["fact_remaining_after"] == 0
        assert summary["fact_by_source_type"]["news"] == 2
        assert summary["fact_by_source_type"]["web"] == 1
        assert summary["fact_by_source_type"]["pdf"] == 1

    def test_正常系_50件超のFactはサンプルのみ記録される(self) -> None:
        entities = self._make_entities(1)
        facts = self._make_facts(80)
        result = ProcessResult()

        report = format_process_report(entities, facts, result, "20260402")
        assert len(report["isolated_facts_sample"]) == 50

    def test_正常系_Fact50件以下は全件記録される(self) -> None:
        entities = self._make_entities(1)
        facts = self._make_facts(30)
        result = ProcessResult()

        report = format_process_report(entities, facts, result, "20260402")
        assert len(report["isolated_facts_sample"]) == 30

    def test_正常系_dry_runフラグが反映される(self) -> None:
        report = format_process_report([], [], ProcessResult(dry_run=True), "20260402")
        assert report["dry_run"] is True

    def test_正常系_全Entityが記録される(self) -> None:
        entities = self._make_entities(5)
        report = format_process_report(entities, [], ProcessResult(), "20260402")
        assert len(report["isolated_entities"]) == 5

    def test_正常系_source_typeがNullの場合はnullキーで集計される(self) -> None:
        facts = [
            IsolatedFactNode(
                element_id="4:def:0",
                fact_id=None,
                content=None,
                source_type=None,
                source_url=None,
            )
        ]
        report = format_process_report([], facts, ProcessResult(), "20260402")
        assert report["summary"]["fact_by_source_type"]["null"] == 1


# ---------------------------------------------------------------------------
# TestSaveReport
# ---------------------------------------------------------------------------


class TestSaveReport:
    def test_正常系_レポートをJSONファイルに保存できる(self, tmp_path: Path) -> None:
        report = {
            "generated_at": "20260402",
            "database": "research",
            "summary": {"entity_archived": 18, "fact_archived": 550},
        }
        output_path = save_report(
            report, output_dir=tmp_path, filename="test_report.json"
        )

        assert output_path.exists()
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved["summary"]["entity_archived"] == 18

    def test_正常系_出力ディレクトリが存在しない場合も自動作成される(
        self, tmp_path: Path
    ) -> None:
        new_dir = tmp_path / "subdir" / "nested"
        report = {"key": "value"}
        output_path = save_report(report, output_dir=new_dir, filename="out.json")

        assert output_path.exists()
        assert output_path.parent == new_dir

    def test_正常系_日本語コンテンツがUTF8で保存される(self, tmp_path: Path) -> None:
        report = {"content": "テスト孤立ノード処理"}
        output_path = save_report(report, output_dir=tmp_path, filename="jp_test.json")

        raw = output_path.read_text(encoding="utf-8")
        assert "テスト孤立ノード処理" in raw


# ---------------------------------------------------------------------------
# TestParseArgs
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_正常系_デフォルト引数で初期化できる(self) -> None:
        args = parse_args([])
        assert args.database == "research"
        assert args.dry_run is False
        assert args.batch_size == 100
        assert args.log_level == "INFO"

    def test_正常系_dry_runフラグを指定できる(self) -> None:
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_正常系_databaseを指定できる(self) -> None:
        args = parse_args(["--database", "custom_db"])
        assert args.database == "custom_db"

    def test_正常系_output_dirを指定できる(self) -> None:
        args = parse_args(["--output-dir", "custom/output"])
        assert args.output_dir == "custom/output"

    def test_正常系_batch_sizeを指定できる(self) -> None:
        args = parse_args(["--batch-size", "50"])
        assert args.batch_size == 50

    def test_正常系_log_levelを指定できる(self) -> None:
        args = parse_args(["--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"
