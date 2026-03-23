"""creator_enrichment.phases.pipeline のテスト.

run_pipeline() の Step 4.0 -> 4.1 -> 4.2 パイプライン実行、
ジャンル事前バリデーション、dry_run スキップ、中間 JSON 保存を検証する。

遅延インポートラッパー (_import_resolve_all / _import_map_v2) をパッチして
外部スクリプトへの依存を排除する。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from creator_enrichment.phases.pipeline import _save_intermediate, run_pipeline
from creator_enrichment.types import CycleData, CycleError, IngestResult

# ---------------------------------------------------------------------------
# パッチターゲット定数
# ---------------------------------------------------------------------------
_PATCH_IMPORT_RESOLVE = "creator_enrichment.phases.pipeline._import_resolve_all"
_PATCH_IMPORT_MAP_V2 = "creator_enrichment.phases.pipeline._import_map_v2"
_PATCH_WRITER_CLS = "creator_enrichment.phases.pipeline.CreatorGraphWriter"
_PATCH_SAVE = "creator_enrichment.phases.pipeline._save_intermediate"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_cycle_data() -> CycleData:
    """パイプラインテスト用の CycleData サンプル.

    Returns
    -------
    CycleData
        career ジャンルの抽出結果サンプル
    """
    return CycleData(
        genre="career",
        cycle_id="cycle-test-pipeline-001",
        sources=[{"url": "https://example.com/article-1", "title": "Test Article"}],
        facts=[{"text": "Test fact", "category": "statistics"}],
        tips=[{"text": "Test tip", "category": "strategy"}],
        stories=[{"text": "Test story", "outcome": "success"}],
        entities=[{"name": "TestEntity", "entity_type": "company"}],
        concepts=[{"name": "TestConcept", "category": "Skill"}],
        serves_as=[{"entity": "TestEntity", "concept": "TestConcept"}],
        concept_relations=[],
    )


@pytest.fixture
def mock_neo4j_client() -> MagicMock:
    """Neo4j クライアントのモック.

    Returns
    -------
    MagicMock
        entity_linker 用のクライアントモック
    """
    return MagicMock()


@pytest.fixture
def mock_neo4j_driver() -> MagicMock:
    """Neo4j ドライバのモック.

    Returns
    -------
    MagicMock
        CreatorGraphWriter 用のドライバモック
    """
    driver = MagicMock()
    session = MagicMock()

    counters = MagicMock()
    counters.nodes_created = 5
    counters.relationships_created = 3
    summary = MagicMock()
    summary.counters = counters
    run_result = MagicMock()
    run_result.consume.return_value = summary

    session.run.return_value = run_result

    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)

    return driver


@pytest.fixture
def mock_resolved_data() -> dict:
    """resolve_all の戻り値モック.

    Returns
    -------
    dict
        Entity/Concept 解決済みデータ
    """
    return {
        "genre": "career",
        "cycle_id": "cycle-test-pipeline-001",
        "sources": [{"url": "https://example.com/article-1", "title": "Test Article"}],
        "facts": [{"text": "Test fact", "category": "statistics"}],
        "tips": [{"text": "Test tip", "category": "strategy"}],
        "stories": [{"text": "Test story", "outcome": "success"}],
        "entities": [
            {
                "name": "TestEntity",
                "entity_type": "company",
                "entity_key": "TestEntity::company",
            },
        ],
        "concepts": [
            {
                "name": "TestConcept",
                "category": "Skill",
                "concept_id": "concept-abc123",
            },
        ],
        "serves_as": [{"entity": "TestEntity", "concept": "TestConcept"}],
        "concept_relations": [],
    }


@pytest.fixture
def mock_queue_doc() -> dict:
    """map_creator_enrichment_v2 の戻り値モック.

    Returns
    -------
    dict
        creator-2.0 形式の queue_doc
    """
    return {
        "schema_version": "creator-2.0",
        "queue_id": "cq-test-001",
        "genre_id": "career",
        "genres": [{"genre_id": "career", "name": "転職・副業"}],
        "concept_categories": [],
        "concepts": [],
        "entities": [],
        "sources": [],
        "domains": [],
        "facts": [{"fact_id": "fact-001", "text": "Test fact"}],
        "tips": [],
        "stories": [],
        "aliases": [],
        "relations": {},
    }


# ---------------------------------------------------------------------------
# ジャンル事前バリデーション
# ---------------------------------------------------------------------------
class TestGenrePreValidation:
    """ジャンル事前バリデーションのテスト."""

    def test_異常系_不正ジャンルでCycleError(
        self,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
    ) -> None:
        """不正なジャンル名で CycleError が発生する."""
        invalid_data = CycleData(
            genre="invalid-genre",
            cycle_id="cycle-invalid",
            sources=[],
            facts=[],
            tips=[],
            stories=[],
            entities=[],
            concepts=[],
            serves_as=[],
            concept_relations=[],
        )

        with pytest.raises(CycleError) as exc_info:
            run_pipeline(
                cycle_data=invalid_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
            )

        assert exc_info.value.cycle_num == 0
        assert "Invalid genre" in str(exc_info.value.cause)

    def test_異常系_空ジャンルでCycleError(
        self,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
    ) -> None:
        """空文字のジャンル名で CycleError が発生する."""
        empty_genre_data = CycleData(
            genre="",
            cycle_id="cycle-empty-genre",
            sources=[],
            facts=[],
            tips=[],
            stories=[],
            entities=[],
            concepts=[],
            serves_as=[],
            concept_relations=[],
        )

        with pytest.raises(CycleError) as exc_info:
            run_pipeline(
                cycle_data=empty_genre_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
            )

        assert exc_info.value.cycle_num == 0

    def test_正常系_バリデーション通過後にresolve_allが呼ばれる(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """有効なジャンルではバリデーションを通過し resolve_all が呼ばれる."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        mock_resolve_fn.assert_called_once()


# ---------------------------------------------------------------------------
# dry_run モード
# ---------------------------------------------------------------------------
class TestDryRun:
    """dry_run=True 時のテスト."""

    def test_正常系_dryRunでStep42がスキップされる(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """dry_run=True では CreatorGraphWriter.ingest() が呼ばれない."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
        ):
            result = run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        assert result["nodes_created"] == 0
        assert result["relations_created"] == 0
        # driver.session() が呼ばれていない = ingest スキップ
        mock_neo4j_driver.session.assert_not_called()

    def test_正常系_dryRunでIngestResultがゼロ(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """dry_run=True では nodes_created=0, relations_created=0 が返る."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
        ):
            result = run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        assert result == IngestResult(nodes_created=0, relations_created=0)


# ---------------------------------------------------------------------------
# Step 呼び出し順序
# ---------------------------------------------------------------------------
class TestStepCallOrder:
    """Step 4.0 -> 4.1 -> 4.2 の呼び出し順序テスト."""

    def test_正常系_Step40が最初に呼ばれ順序が正しい(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """resolve_all -> map_v2 -> ingest の順序で呼ばれることを確認."""
        call_order: list[str] = []

        mock_resolve_fn = MagicMock(
            side_effect=lambda *a, **kw: (
                call_order.append("resolve_all"),
                mock_resolved_data,
            )[-1],
        )
        mock_map_fn = MagicMock(
            side_effect=lambda *a, **kw: (
                call_order.append("map_v2"),
                mock_queue_doc,
            )[-1],
        )
        mock_writer_instance = MagicMock()
        mock_writer_instance.ingest.side_effect = lambda *a, **kw: (
            call_order.append("ingest"),
            IngestResult(nodes_created=5, relations_created=3),
        )[-1]

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_WRITER_CLS, return_value=mock_writer_instance),
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=False,
            )

        assert call_order == ["resolve_all", "map_v2", "ingest"]

    def test_正常系_resolve_allにclient_dataが渡される(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """resolve_all に正しい引数が渡されることを確認."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        mock_resolve_fn.assert_called_once_with(
            mock_neo4j_client,
            dict(sample_cycle_data),
            use_embedding=False,
        )

    def test_正常系_map_v2にresolved_dataが渡される(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """map_creator_enrichment_v2 に resolve_all の結果が渡されることを確認."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        mock_map_fn.assert_called_once_with(mock_resolved_data)


# ---------------------------------------------------------------------------
# IngestResult 返却
# ---------------------------------------------------------------------------
class TestIngestResultReturned:
    """IngestResult が正しく返却されるテスト."""

    def test_正常系_ingestの結果が返される(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """dry_run=False の場合、writer.ingest() の結果が返される."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)
        expected_result = IngestResult(nodes_created=10, relations_created=7)
        mock_writer_instance = MagicMock()
        mock_writer_instance.ingest.return_value = expected_result

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_WRITER_CLS, return_value=mock_writer_instance),
        ):
            result = run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=False,
            )

        assert result["nodes_created"] == 10
        assert result["relations_created"] == 7

    def test_正常系_writerにcycleIdが渡される(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """CreatorGraphWriter.ingest() に cycle_id が渡されることを確認."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)
        mock_writer_instance = MagicMock()
        mock_writer_instance.ingest.return_value = IngestResult(
            nodes_created=0,
            relations_created=0,
        )

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_WRITER_CLS, return_value=mock_writer_instance),
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=False,
            )

        mock_writer_instance.ingest.assert_called_once_with(
            mock_queue_doc,
            cycle_id="cycle-test-pipeline-001",
        )


# ---------------------------------------------------------------------------
# 中間 JSON 保存
# ---------------------------------------------------------------------------
class TestIntermediateJsonSave:
    """中間 JSON ファイル保存のテスト."""

    def test_正常系_Step40でsave_intermediateが呼ばれる(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """Step 4.0 後に中間 JSON が保存される."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_SAVE) as mock_save,
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        calls = mock_save.call_args_list
        step_numbers = [c.args[2] for c in calls]
        assert 0 in step_numbers

    def test_正常系_Step41でsave_intermediateが呼ばれる(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """Step 4.1 後に中間 JSON が保存される."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_SAVE) as mock_save,
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        calls = mock_save.call_args_list
        step_numbers = [c.args[2] for c in calls]
        assert 1 in step_numbers

    def test_正常系_Step42でsave_intermediateが呼ばれる(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """Step 4.2 後に中間 JSON が保存される（dry_run=False）."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)
        mock_writer_instance = MagicMock()
        mock_writer_instance.ingest.return_value = IngestResult(
            nodes_created=5,
            relations_created=3,
        )

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_WRITER_CLS, return_value=mock_writer_instance),
            patch(_PATCH_SAVE) as mock_save,
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=False,
            )

        calls = mock_save.call_args_list
        step_numbers = [c.args[2] for c in calls]
        assert 2 in step_numbers

    def test_正常系_dryRunではStep42のsaveが呼ばれない(
        self,
        sample_cycle_data: CycleData,
        mock_neo4j_client: MagicMock,
        mock_neo4j_driver: MagicMock,
        mock_resolved_data: dict,
        mock_queue_doc: dict,
    ) -> None:
        """dry_run=True では Step 4.2 の save は呼ばれない."""
        mock_resolve_fn = MagicMock(return_value=mock_resolved_data)
        mock_map_fn = MagicMock(return_value=mock_queue_doc)

        with (
            patch(_PATCH_IMPORT_RESOLVE, return_value=mock_resolve_fn),
            patch(_PATCH_IMPORT_MAP_V2, return_value=mock_map_fn),
            patch(_PATCH_SAVE) as mock_save,
        ):
            run_pipeline(
                cycle_data=sample_cycle_data,
                neo4j_client=mock_neo4j_client,
                neo4j_driver=mock_neo4j_driver,
                dry_run=True,
            )

        calls = mock_save.call_args_list
        step_numbers = [c.args[2] for c in calls]
        # Step 0 と Step 1 のみ
        assert 2 not in step_numbers
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# _save_intermediate 直接テスト
# ---------------------------------------------------------------------------
class TestSaveIntermediateDirectly:
    """_save_intermediate 関数の直接テスト."""

    def test_正常系_JSONファイルが作成される(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_save_intermediate が指定パスに JSON を書き出す."""
        monkeypatch.chdir(tmp_path)

        data = {"genre": "career", "count": 42}
        _save_intermediate(data, "cycle-direct-test", 0)

        path = tmp_path / ".tmp" / "creator-pipeline-cycle-direct-test-step0.json"
        assert path.exists()

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["genre"] == "career"
        assert loaded["count"] == 42

    def test_正常系_tmpディレクトリが自動作成される(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`.tmp` ディレクトリが存在しなくても自動作成される."""
        monkeypatch.chdir(tmp_path)

        _save_intermediate({"test": True}, "cycle-mkdir-test", 1)

        tmp_dir = tmp_path / ".tmp"
        assert tmp_dir.exists()
        assert tmp_dir.is_dir()

    def test_正常系_datetimeがstrにシリアライズされる(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """datetime オブジェクトが default=str で文字列にシリアライズされる."""
        from datetime import datetime

        monkeypatch.chdir(tmp_path)

        data = {"timestamp": datetime(2026, 3, 23, 14, 0, 0)}
        _save_intermediate(data, "cycle-datetime-test", 0)

        path = tmp_path / ".tmp" / "creator-pipeline-cycle-datetime-test-step0.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert "2026-03-23" in loaded["timestamp"]

    def test_正常系_日本語がensure_asciiなしで保存される(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """日本語がエスケープされず保存される（ensure_ascii=False）."""
        monkeypatch.chdir(tmp_path)

        data = {"text": "転職市場の最新動向"}
        _save_intermediate(data, "cycle-ja-test", 0)

        path = tmp_path / ".tmp" / "creator-pipeline-cycle-ja-test-step0.json"
        raw = path.read_text(encoding="utf-8")
        assert "転職市場" in raw
