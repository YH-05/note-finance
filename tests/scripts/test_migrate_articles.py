"""Unit tests for scripts/migrate_articles.py."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from scripts.migrate_articles import (
    MIGRATION_MAP,
    _best_status,
    _build_neo4j_meta,
    _extract_critic_score,
    _extract_research_sources,
    _extract_target_wordcount,
    _find_entry_by_path,
    _infer_type,
    _map_status,
    _normalize_date_range,
    _phase_status,
    _simplify_workflow,
    convert_meta,
)

# ---------------------------------------------------------------------------
# _phase_status
# ---------------------------------------------------------------------------


class TestPhaseStatus:
    """_phase_status の単体テスト。"""

    def test_正常系_文字列をそのまま返す(self) -> None:
        """文字列入力はそのまま返されることを確認。"""
        assert _phase_status("done") == "done"
        assert _phase_status("in_progress") == "in_progress"

    def test_正常系_dict全doneでdone(self) -> None:
        """全サブステータスが done なら done を返すことを確認。"""
        assert _phase_status({"a": "done", "b": "done"}) == "done"

    def test_正常系_dict部分doneでin_progress(self) -> None:
        """一部が done なら in_progress を返すことを確認。"""
        assert _phase_status({"a": "done", "b": "pending"}) == "in_progress"

    def test_正常系_dict全pendingでpending(self) -> None:
        """全てが pending なら pending を返すことを確認。"""
        assert _phase_status({"a": "pending", "b": "pending"}) == "pending"

    def test_エッジケース_空dictでpending(self) -> None:
        """空の dict なら pending を返すことを確認。"""
        assert _phase_status({}) == "pending"

    def test_エッジケース_dict値に文字列以外がある場合は無視(self) -> None:
        """dict の値に非文字列が含まれる場合、文字列のみを評価することを確認。"""
        assert _phase_status({"a": "done", "b": 123}) == "done"

    def test_エッジケース_その他の型でpending(self) -> None:
        """int や None などの型は pending を返すことを確認。"""
        assert _phase_status(42) == "pending"
        assert _phase_status(None) == "pending"
        assert _phase_status([]) == "pending"


# ---------------------------------------------------------------------------
# _best_status
# ---------------------------------------------------------------------------


class TestBestStatus:
    """_best_status の単体テスト。"""

    def test_正常系_全キーdoneでdone(self) -> None:
        """全てのキーが done なら done を返すことを確認。"""
        workflow = {"data_collection": "done", "processing": "done"}
        assert _best_status(["data_collection", "processing"], workflow) == "done"

    def test_正常系_一部doneでin_progress(self) -> None:
        """一部が done なら in_progress を返すことを確認。"""
        workflow = {"data_collection": "done", "processing": "pending"}
        assert (
            _best_status(["data_collection", "processing"], workflow) == "in_progress"
        )

    def test_正常系_一部in_progressでin_progress(self) -> None:
        """一部が in_progress なら in_progress を返すことを確認。"""
        workflow = {"a": "in_progress", "b": "pending"}
        assert _best_status(["a", "b"], workflow) == "in_progress"

    def test_エッジケース_キーなしでpending(self) -> None:
        """指定キーが workflow に存在しない場合 pending を返すことを確認。"""
        workflow = {"other": "done"}
        assert _best_status(["missing_key"], workflow) == "pending"

    def test_エッジケース_空キーリストでpending(self) -> None:
        """空のキーリストなら pending を返すことを確認。"""
        assert _best_status([], {"a": "done"}) == "pending"


# ---------------------------------------------------------------------------
# _simplify_workflow
# ---------------------------------------------------------------------------


class TestSimplifyWorkflow:
    """_simplify_workflow の単体テスト。"""

    def test_正常系_完了済みワークフロー(self) -> None:
        """全フェーズが完了済みの場合の変換を確認。"""
        old = {
            "data_collection": "done",
            "processing": "done",
            "research": "done",
            "collecting": "done",
            "writing": "done",
            "critique": "done",
            "revision": "done",
            "publishing": "done",
        }
        result = _simplify_workflow(old)
        assert result["research"] == "done"
        assert result["draft"] == "done"
        assert result["publish"] == "done"

    def test_正常系_部分完了ワークフロー(self) -> None:
        """一部フェーズのみ完了の場合を確認。"""
        old = {"data_collection": "done", "processing": "pending", "writing": "pending"}
        result = _simplify_workflow(old)
        assert result["research"] == "in_progress"
        assert result["draft"] == "pending"

    def test_エッジケース_Noneで全pending(self) -> None:
        """None 入力で全 pending を返すことを確認。"""
        result = _simplify_workflow(None)
        assert all(v == "pending" for v in result.values())
        assert set(result.keys()) == {
            "research",
            "draft",
            "critique",
            "revision",
            "publish",
        }

    def test_エッジケース_空dictで全pending(self) -> None:
        """空 dict 入力で全 pending を返すことを確認。"""
        result = _simplify_workflow({})
        assert all(v == "pending" for v in result.values())


# ---------------------------------------------------------------------------
# _map_status
# ---------------------------------------------------------------------------


class TestMapStatus:
    """_map_status の単体テスト。"""

    @pytest.mark.parametrize(
        "old_status,expected",
        [
            ("research", "draft"),
            ("edit", "draft"),
            ("collecting", "draft"),
            ("revised", "review"),
            ("ready_for_publish", "review"),
            ("published", "published"),
        ],
    )
    def test_正常系_STATUS_MAPに含まれる値(
        self, old_status: str, expected: str
    ) -> None:
        """STATUS_MAP に定義された値が正しくマッピングされることを確認。"""
        assert _map_status(old_status) == expected

    def test_エッジケース_未知のステータスでデフォルトdraft(self) -> None:
        """STATUS_MAP にない値はデフォルト draft を返すことを確認。"""
        assert _map_status("unknown_status") == "draft"
        assert _map_status("") == "draft"


# ---------------------------------------------------------------------------
# _infer_type
# ---------------------------------------------------------------------------


class TestInferType:
    """_infer_type の単体テスト。"""

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("macro_economy", "column"),
            ("stock_analysis", "data_analysis"),
            ("asset_formation", "column"),
            ("side_business", "experience"),
            ("weekly_report", "weekly_report"),
            ("quant_analysis", "data_analysis"),
        ],
    )
    def test_正常系_TYPE_MAPに含まれる値(self, category: str, expected: str) -> None:
        """TYPE_MAP に定義されたカテゴリが正しくマッピングされることを確認。"""
        assert _infer_type(category) == expected

    def test_エッジケース_未知のカテゴリでデフォルトcolumn(self) -> None:
        """TYPE_MAP にないカテゴリはデフォルト column を返すことを確認。"""
        assert _infer_type("unknown_category") == "column"


# ---------------------------------------------------------------------------
# _normalize_date_range
# ---------------------------------------------------------------------------


class TestNormalizeDateRange:
    """_normalize_date_range の単体テスト。"""

    def test_正常系_新キーstart_end(self) -> None:
        """新キー start/end がそのまま使われることを確認。"""
        result = _normalize_date_range({"start": "2026-01-01", "end": "2026-01-31"})
        assert result == {"start": "2026-01-01", "end": "2026-01-31"}

    def test_正常系_旧キーstart_date_end_date(self) -> None:
        """旧キー start_date/end_date がフォールバックで使われることを確認。"""
        result = _normalize_date_range(
            {"start_date": "2025-12-01", "end_date": "2025-12-31"}
        )
        assert result == {"start": "2025-12-01", "end": "2025-12-31"}

    def test_エッジケース_Noneで空文字(self) -> None:
        """None 入力で空文字を含む dict を返すことを確認。"""
        result = _normalize_date_range(None)
        assert result == {"start": "", "end": ""}

    def test_エッジケース_空dictで空文字(self) -> None:
        """空 dict で空文字を含む dict を返すことを確認。"""
        result = _normalize_date_range({})
        assert result == {"start": "", "end": ""}


# ---------------------------------------------------------------------------
# _extract_critic_score
# ---------------------------------------------------------------------------


class TestExtractCriticScore:
    """_extract_critic_score の単体テスト。"""

    def test_正常系_total_scoreあり(self) -> None:
        """total_score が存在する場合に int で返されることを確認。"""
        workflow = {"critique": {"total_score": 85}}
        assert _extract_critic_score(workflow) == 85

    def test_正常系_total_scoreが文字列(self) -> None:
        """total_score が文字列の場合も int に変換されることを確認。"""
        workflow = {"critique": {"total_score": "72"}}
        assert _extract_critic_score(workflow) == 72

    def test_エッジケース_total_scoreなし(self) -> None:
        """total_score がない場合 None を返すことを確認。"""
        workflow = {"critique": {"other": "data"}}
        assert _extract_critic_score(workflow) is None

    def test_エッジケース_critiqueがdictでない(self) -> None:
        """critique が dict でない場合 None を返すことを確認。"""
        workflow = {"critique": "done"}
        assert _extract_critic_score(workflow) is None

    def test_エッジケース_critiqueキーなし(self) -> None:
        """critique キーが存在しない場合 None を返すことを確認。"""
        assert _extract_critic_score({}) is None


# ---------------------------------------------------------------------------
# _extract_research_sources
# ---------------------------------------------------------------------------


class TestExtractResearchSources:
    """_extract_research_sources の単体テスト。"""

    def test_正常系_source_countあり(self) -> None:
        """source_count が存在する場合にその値を返すことを確認。"""
        workflow = {"collecting": {"source_count": 5}}
        assert _extract_research_sources(workflow) == 5

    def test_エッジケース_source_countなし(self) -> None:
        """source_count がない場合 0 を返すことを確認。"""
        workflow = {"collecting": {"other": "data"}}
        assert _extract_research_sources(workflow) == 0

    def test_エッジケース_collectingがdictでない(self) -> None:
        """collecting が dict でない場合 0 を返すことを確認。"""
        workflow = {"collecting": "done"}
        assert _extract_research_sources(workflow) == 0

    def test_エッジケース_collectingキーなし(self) -> None:
        """collecting キーが存在しない場合 0 を返すことを確認。"""
        assert _extract_research_sources({}) == 0

    def test_エッジケース_source_countがNone(self) -> None:
        """source_count が None の場合 0 を返すことを確認。"""
        workflow = {"collecting": {"source_count": None}}
        assert _extract_research_sources(workflow) == 0


# ---------------------------------------------------------------------------
# _build_neo4j_meta
# ---------------------------------------------------------------------------


class TestBuildNeo4jMeta:
    """_build_neo4j_meta の単体テスト。"""

    def test_正常系_neo4jデータあり(self) -> None:
        """neo4j データが存在する場合に正しく変換されることを確認。"""
        old: dict[str, Any] = {
            "neo4j": {
                "pattern_node_id": "abc123",
                "source_node_ids": ["s1", "s2"],
                "embed_resource_ids": ["e1"],
            }
        }
        result = _build_neo4j_meta(old)
        assert result["pattern_node_id"] == "abc123"
        assert result["source_node_ids"] == ["s1", "s2"]
        assert result["embed_resource_ids"] == ["e1"]

    def test_エッジケース_neo4jキーなし(self) -> None:
        """neo4j キーがない場合にデフォルト値を返すことを確認。"""
        result = _build_neo4j_meta({})
        assert result["pattern_node_id"] is None
        assert result["source_node_ids"] == []
        assert result["embed_resource_ids"] == []

    def test_エッジケース_neo4j空dict(self) -> None:
        """neo4j が空 dict の場合にデフォルト値を返すことを確認。"""
        result = _build_neo4j_meta({"neo4j": {}})
        assert result["pattern_node_id"] is None
        assert result["source_node_ids"] == []
        assert result["embed_resource_ids"] == []


# ---------------------------------------------------------------------------
# _extract_target_wordcount
# ---------------------------------------------------------------------------


class TestExtractTargetWordcount:
    """_extract_target_wordcount の単体テスト。"""

    def test_正常系_wordcountあり(self) -> None:
        """wordcount が正の値で存在する場合にその値を返すことを確認。"""
        workflow = {"revision": {"wordcount": 5000}}
        assert _extract_target_wordcount(workflow) == 5000

    def test_エッジケース_wordcountなし(self) -> None:
        """wordcount がない場合にデフォルト 4000 を返すことを確認。"""
        workflow = {"revision": {"other": "data"}}
        assert _extract_target_wordcount(workflow) == 4000

    def test_エッジケース_wordcountが0(self) -> None:
        """wordcount が 0 の場合にデフォルト 4000 を返すことを確認。"""
        workflow = {"revision": {"wordcount": 0}}
        assert _extract_target_wordcount(workflow) == 4000

    def test_エッジケース_revisionがdictでない(self) -> None:
        """revision が dict でない場合にデフォルトを返すことを確認。"""
        workflow = {"revision": "done"}
        assert _extract_target_wordcount(workflow) == 4000

    def test_正常系_カスタムデフォルト値(self) -> None:
        """カスタムデフォルト値が使われることを確認。"""
        assert _extract_target_wordcount({}, default=3000) == 3000


# ---------------------------------------------------------------------------
# convert_meta
# ---------------------------------------------------------------------------


class TestConvertMeta:
    """convert_meta の単体テスト。"""

    def test_正常系_article_meta_jsonあり(self, tmp_path: Path) -> None:
        """article-meta.json が存在する場合に正しく変換されることを確認。"""
        meta_json = tmp_path / "article-meta.json"
        old_data = {
            "article_id": "test-001",
            "topic": "Test Topic",
            "status": "revised",
            "tags": ["finance", "test"],
            "created_at": "2026-01-01T00:00:00Z",
            "workflow": {
                "data_collection": "done",
                "writing": "done",
                "critique": {"total_score": 80},
                "collecting": {"source_count": 3},
            },
            "neo4j": {
                "pattern_node_id": "p1",
                "source_node_ids": ["s1"],
                "embed_resource_ids": [],
            },
        }
        meta_json.write_text(json.dumps(old_data), encoding="utf-8")

        result = convert_meta(meta_json, "macro_economy", "old/path")

        assert result["title"] == "Test Topic"
        assert result["category"] == "macro_economy"
        assert result["type"] == "column"
        assert result["status"] == "review"
        assert result["tags"] == ["finance", "test"]
        assert result["critic_score"] == 80
        assert result["research_sources"] == 3
        assert result["neo4j"]["pattern_node_id"] == "p1"
        assert result["legacy"]["old_path"] == "old/path"
        assert result["legacy"]["old_article_id"] == "test-001"

    def test_エッジケース_meta_jsonなし(self) -> None:
        """article-meta.json が None の場合にデフォルトメタを生成することを確認。"""
        result = convert_meta(None, "stock_analysis", "missing/path")

        assert result["title"] == ""
        assert result["category"] == "stock_analysis"
        assert result["type"] == "data_analysis"
        assert result["status"] == "draft"
        assert result["tags"] == []
        assert result["legacy"]["old_path"] == "missing/path"

    def test_エッジケース_存在しないパス(self, tmp_path: Path) -> None:
        """存在しないパスを渡した場合にデフォルトメタを生成することを確認。"""
        fake_path = tmp_path / "nonexistent.json"
        result = convert_meta(fake_path, "asset_formation", "old/dir")

        assert result["title"] == ""
        assert result["category"] == "asset_formation"
        assert result["status"] == "draft"


# ---------------------------------------------------------------------------
# _find_entry_by_path
# ---------------------------------------------------------------------------


class TestFindEntryByPath:
    """_find_entry_by_path の単体テスト。"""

    def test_正常系_一致あり(self) -> None:
        """MIGRATION_MAP に存在するパスで MigrationEntry を返すことを確認。"""
        entry = _find_entry_by_path(
            "economic_indicators_001_private-credit-bank-shadow-banking-risk"
        )
        assert entry is not None
        assert entry.new_category == "macro_economy"

    def test_正常系_末尾スラッシュの正規化(self) -> None:
        """末尾にスラッシュがあっても正しく一致することを確認。"""
        entry = _find_entry_by_path(
            "economic_indicators_001_private-credit-bank-shadow-banking-risk/"
        )
        assert entry is not None

    def test_正常系_ネストされたパス(self) -> None:
        """ネストされたパス（category/slug）で一致することを確認。"""
        entry = _find_entry_by_path("asset_management/fund_selection_age_based")
        assert entry is not None
        assert entry.new_category == "asset_formation"

    def test_異常系_一致なし(self) -> None:
        """MIGRATION_MAP に存在しないパスで None を返すことを確認。"""
        assert _find_entry_by_path("nonexistent_article") is None

    def test_異常系_空文字列(self) -> None:
        """空文字列で None を返すことを確認。"""
        assert _find_entry_by_path("") is None
