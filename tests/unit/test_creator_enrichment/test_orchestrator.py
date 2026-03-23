"""creator_enrichment.orchestrator のテスト.

CreatorEnrichmentOrchestrator のメインループ制御を検証する。
全フェーズ（GapAnalyzer, ClaudeCodeSearcher, ContentExtractor,
CrossEntityEnricher, run_pipeline, SessionLogger）をモックし、
ループ終了条件・エラーハンドリング・最小間隔制御を単体テストする。
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

from creator_enrichment.config import CycleSettings, OrchestratorConfig
from creator_enrichment.orchestrator import (
    CreatorEnrichmentOrchestrator,
    FatalError,
)
from creator_enrichment.types import (
    CycleData,
    CycleError,
    GapAnalysisResult,
    IngestResult,
    RawItem,
)


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------
def _make_config(
    *,
    max_cycles: int = 1,
    dry_run: bool = False,
    min_interval: int = 0,
    max_empty: int = 3,
    empty_wait: int = 0,
    genre: str | None = None,
) -> OrchestratorConfig:
    """テスト用の OrchestratorConfig を生成する.

    Parameters
    ----------
    max_cycles : int
        最大サイクル数
    dry_run : bool
        ドライランフラグ
    min_interval : int
        最小サイクル間隔（秒）
    max_empty : int
        連続空サイクル上限
    empty_wait : int
        空サイクル後の待機時間（秒）
    genre : str | None
        固定ジャンル

    Returns
    -------
    OrchestratorConfig
        テスト用設定
    """
    return OrchestratorConfig(
        until_time=datetime.time(23, 59),
        genre=genre,
        dry_run=dry_run,
        max_cycles=max_cycles,
        cycle_settings=CycleSettings(
            min_cycle_interval_seconds=min_interval,
            max_consecutive_empty_cycles=max_empty,
            empty_cycle_wait_seconds=empty_wait,
        ),
    )


def _make_gap_result(genre: str = "career") -> GapAnalysisResult:
    """テスト用の GapAnalysisResult を生成する.

    Parameters
    ----------
    genre : str
        ジャンル名

    Returns
    -------
    GapAnalysisResult
        ギャップ分析結果
    """
    return GapAnalysisResult(
        genre=genre,
        low_coverage_concepts=[
            "転職活動の始め方",
            "副業の税金対策",
            "リモートワーク",
        ],
        existing_samples=["sample-1"],
    )


def _make_raw_items() -> list[RawItem]:
    """テスト用の RawItem リストを生成する.

    Returns
    -------
    list[RawItem]
        検索結果アイテム
    """
    return [
        RawItem(
            url="https://example.com/article-1",
            title="テスト記事",
            content="テストコンテンツ",
            source="tavily_search",
        ),
    ]


def _make_cycle_data(genre: str = "career") -> CycleData:
    """テスト用の CycleData を生成する.

    Parameters
    ----------
    genre : str
        ジャンル名

    Returns
    -------
    CycleData
        抽出結果
    """
    return CycleData(
        genre=genre,
        cycle_id="cycle-test-001",
        sources=[{"url": "https://example.com", "title": "Test"}],
        facts=[{"text": "test fact", "source_url": "https://example.com"}],
        tips=[],
        stories=[],
        entities=[{"name": "TestEntity", "entity_type": "company"}],
        concepts=[{"name": "TestConcept", "category": "Skill"}],
        serves_as=[],
        concept_relations=[{"from": "A", "to": "B", "rel_type": "ENABLES"}],
    )


def _make_ingest_result() -> IngestResult:
    """テスト用の IngestResult を生成する.

    Returns
    -------
    IngestResult
        パイプライン投入結果
    """
    return IngestResult(nodes_created=5, relations_created=3)


def _build_orchestrator(
    config: OrchestratorConfig,
    *,
    gap_analyzer: MagicMock | None = None,
    searcher: MagicMock | None = None,
    extractor: MagicMock | None = None,
    cross_enricher: MagicMock | None = None,
) -> CreatorEnrichmentOrchestrator:
    """テスト用のオーケストレーターを構築する.

    Parameters
    ----------
    config : OrchestratorConfig
        設定
    gap_analyzer : MagicMock | None
        ギャップ分析モック
    searcher : MagicMock | None
        検索モック
    extractor : MagicMock | None
        抽出モック
    cross_enricher : MagicMock | None
        Cross-entity モック

    Returns
    -------
    CreatorEnrichmentOrchestrator
        テスト用オーケストレーター
    """
    if gap_analyzer is None:
        gap_analyzer = MagicMock()
        gap_analyzer.analyze.return_value = _make_gap_result()

    if searcher is None:
        searcher = MagicMock()
        searcher.search.return_value = _make_raw_items()

    if extractor is None:
        extractor = MagicMock()
        extractor.extract_batch.return_value = _make_cycle_data()

    if cross_enricher is None:
        cross_enricher = MagicMock()
        cross_enricher.run.return_value = 0

    return CreatorEnrichmentOrchestrator(
        config,
        gap_analyzer=gap_analyzer,
        searcher=searcher,
        extractor=extractor,
        cross_enricher=cross_enricher,
        neo4j_client=MagicMock(),
        neo4j_driver=MagicMock(),
    )


# ---------------------------------------------------------------------------
# max_cycles によるループ制御
# ---------------------------------------------------------------------------
class TestMaxCyclesLimit:
    """max_cycles によるループ終了条件のテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_maxCycles1で1サイクルのみ実行(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """max_cycles=1 の場合、1サイクルだけ実行して終了する."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        config = _make_config(max_cycles=1)
        orch = _build_orchestrator(config)
        orch.run()

        mock_run_pipeline.assert_called_once()
        mock_logger.record_cycle.assert_called_once()
        mock_logger.finalize.assert_called_once_with(1)

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_maxCycles3で3サイクル実行(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """max_cycles=3 の場合、3サイクル実行して終了する."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        config = _make_config(max_cycles=3)
        orch = _build_orchestrator(config)
        orch.run()

        assert mock_run_pipeline.call_count == 3
        assert mock_logger.record_cycle.call_count == 3
        mock_logger.finalize.assert_called_once_with(3)


# ---------------------------------------------------------------------------
# until_time によるループ制御
# ---------------------------------------------------------------------------
class TestUntilTimeTermination:
    """until_time によるループ終了条件のテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    @patch("creator_enrichment.orchestrator.datetime")
    def test_正常系_untilTimeを超えるとループ終了(
        self,
        mock_datetime: MagicMock,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """datetime.now().time() が until_time を超えるとループが終了する."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        # strftime を正常に動かすため now() の戻り値を設定
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20260323-120000"
        # 1回目: ループに入れる (12:00)、2回目: ループに入れない (13:01)
        mock_now.time.side_effect = [
            datetime.time(12, 0),
            datetime.time(13, 1),
        ]
        mock_datetime.now.return_value = mock_now

        config = OrchestratorConfig(
            until_time=datetime.time(13, 0),
            genre=None,
            dry_run=True,
            max_cycles=0,  # 無制限
            cycle_settings=CycleSettings(
                min_cycle_interval_seconds=0,
                max_consecutive_empty_cycles=3,
                empty_cycle_wait_seconds=0,
            ),
        )

        orch = _build_orchestrator(config)
        orch.run()

        mock_run_pipeline.assert_called_once()
        mock_logger.finalize.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# 連続 CycleError -> FatalError
# ---------------------------------------------------------------------------
class TestConsecutiveErrorsFatalError:
    """5回連続 CycleError で FatalError が発生するテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    def test_異常系_5回連続CycleErrorでFatalError(
        self,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """5回連続の CycleError で FatalError が送出される."""
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        gap_analyzer = MagicMock()
        gap_analyzer.analyze.side_effect = CycleError(
            cycle_num=0, cause=RuntimeError("test error")
        )

        config = _make_config(max_cycles=10)
        orch = _build_orchestrator(config, gap_analyzer=gap_analyzer)

        with pytest.raises(FatalError, match="5 consecutive cycle errors"):
            orch.run()

        assert mock_logger.record_error.call_count == 5

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_成功が挟まれば連続エラーカウントがリセット(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """成功サイクルが挟まれば consecutive_errors がリセットされる."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        gap_analyzer = MagicMock()
        # 4 errors, 1 success, 4 errors, then max_cycles reached
        error = CycleError(cycle_num=0, cause=RuntimeError("test"))
        gap_result = _make_gap_result()
        gap_analyzer.analyze.side_effect = [
            error,
            error,
            error,
            error,
            gap_result,  # success
            error,
            error,
            error,
            error,
            gap_result,  # success
        ]

        config = _make_config(max_cycles=10)
        orch = _build_orchestrator(config, gap_analyzer=gap_analyzer)
        orch.run()

        # Should NOT raise FatalError because success resets the counter
        assert mock_logger.record_error.call_count == 8
        assert mock_logger.record_cycle.call_count == 2


# ---------------------------------------------------------------------------
# 連続空結果 -> 停止
# ---------------------------------------------------------------------------
class TestConsecutiveEmptyStop:
    """連続空結果でループが停止するテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    def test_正常系_3回連続空結果でループ停止(
        self,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """max_consecutive_empty_cycles=3 で3回連続空結果でループ終了."""
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        searcher = MagicMock()
        searcher.search.return_value = []  # 常に空

        config = _make_config(max_cycles=10, max_empty=3)
        orch = _build_orchestrator(config, searcher=searcher)
        orch.run()

        # 3回の空結果後に停止 -> finalize(3)
        mock_logger.finalize.assert_called_once_with(3)
        # record_cycle は呼ばれない（全て空で continue）
        mock_logger.record_cycle.assert_not_called()

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_空結果後に成功があれば連続カウントがリセット(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """空結果後に非空結果があれば consecutive_empty がリセットされる."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        searcher = MagicMock()
        raw_items = _make_raw_items()
        # empty, empty, non-empty, empty, empty, non-empty
        searcher.search.side_effect = [
            [],
            [],
            raw_items,
            [],
            [],
            raw_items,
        ]

        config = _make_config(max_cycles=6, max_empty=3)
        orch = _build_orchestrator(config, searcher=searcher)
        orch.run()

        # 2 successful cycles recorded
        assert mock_logger.record_cycle.call_count == 2
        mock_logger.finalize.assert_called_once_with(6)


# ---------------------------------------------------------------------------
# 最小間隔制御
# ---------------------------------------------------------------------------
class TestMinIntervalEnforcement:
    """_enforce_min_interval のテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    @patch("creator_enrichment.orchestrator.time")
    def test_正常系_最小間隔未満でsleepが呼ばれる(
        self,
        mock_time: MagicMock,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """サイクル所要時間が min_interval 未満の場合、sleep で調整される."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        # monotonic(): start=100.0, after cycle=105.0 -> elapsed=5s
        mock_time.monotonic.side_effect = [100.0, 105.0]
        mock_time.sleep = MagicMock()

        config = _make_config(max_cycles=1, min_interval=30)
        orch = _build_orchestrator(config)
        orch.run()

        # sleep(30 - 5) = sleep(25)
        mock_time.sleep.assert_called_once_with(25.0)

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    @patch("creator_enrichment.orchestrator.time")
    def test_正常系_最小間隔超過でsleepが呼ばれない(
        self,
        mock_time: MagicMock,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """サイクル所要時間が min_interval を超えていれば sleep しない."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        # monotonic(): start=100.0, after cycle=135.0 -> elapsed=35s > 30s
        mock_time.monotonic.side_effect = [100.0, 135.0]
        mock_time.sleep = MagicMock()

        config = _make_config(max_cycles=1, min_interval=30)
        orch = _build_orchestrator(config)
        orch.run()

        mock_time.sleep.assert_not_called()


# ---------------------------------------------------------------------------
# CrossEntityEnricher 呼び出しタイミング
# ---------------------------------------------------------------------------
class TestCrossEntityTiming:
    """CrossEntityEnricher が3サイクルごとに呼ばれるテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_3サイクル目でCrossEntityが呼ばれる(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """cycle_count=3 で cross_enricher.run() が呼ばれる."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        cross_enricher = MagicMock()
        cross_enricher.run.return_value = 5

        config = _make_config(max_cycles=3, dry_run=False)
        orch = _build_orchestrator(config, cross_enricher=cross_enricher)
        orch.run()

        # cycle 1: not called, cycle 2: not called, cycle 3: called
        cross_enricher.run.assert_called_once_with(3)

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_6サイクルで2回CrossEntityが呼ばれる(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """6サイクル実行で cycle 3 と cycle 6 の2回呼ばれる."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        cross_enricher = MagicMock()
        cross_enricher.run.return_value = 2

        config = _make_config(max_cycles=6, dry_run=False)
        orch = _build_orchestrator(config, cross_enricher=cross_enricher)
        orch.run()

        assert cross_enricher.run.call_count == 2

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_dryRunではCrossEntityが呼ばれない(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """dry_run=True では cross_enricher.run() が呼ばれない."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        cross_enricher = MagicMock()

        config = _make_config(max_cycles=3, dry_run=True)
        orch = _build_orchestrator(config, cross_enricher=cross_enricher)
        orch.run()

        cross_enricher.run.assert_not_called()


# ---------------------------------------------------------------------------
# dry_run がパイプラインに渡される
# ---------------------------------------------------------------------------
class TestDryRunPassthrough:
    """dry_run がパイプラインに正しく渡されるテスト."""

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_dryRunTrueがpipelineに渡される(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """dry_run=True が run_pipeline の第4引数に渡される."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        config = _make_config(max_cycles=1, dry_run=True)
        orch = _build_orchestrator(config)
        orch.run()

        call_args = mock_run_pipeline.call_args
        assert call_args[0][3] is True  # dry_run positional arg

    @patch("creator_enrichment.orchestrator.SessionLogger")
    @patch("creator_enrichment.orchestrator.run_pipeline")
    def test_正常系_dryRunFalseがpipelineに渡される(
        self,
        mock_run_pipeline: MagicMock,
        mock_session_logger_cls: MagicMock,
    ) -> None:
        """dry_run=False が run_pipeline の第4引数に渡される."""
        mock_run_pipeline.return_value = _make_ingest_result()
        mock_logger = MagicMock()
        mock_session_logger_cls.return_value = mock_logger

        config = _make_config(max_cycles=1, dry_run=False)
        orch = _build_orchestrator(config)
        orch.run()

        call_args = mock_run_pipeline.call_args
        assert call_args[0][3] is False  # dry_run positional arg


# ---------------------------------------------------------------------------
# FatalError 例外クラス
# ---------------------------------------------------------------------------
class TestFatalError:
    """FatalError 例外クラスのテスト."""

    def test_正常系_FatalErrorはExceptionを継承(self) -> None:
        """FatalError は Exception のサブクラスである."""
        assert issubclass(FatalError, Exception)

    def test_正常系_FatalErrorのメッセージ(self) -> None:
        """FatalError にメッセージを渡して取得できる."""
        err = FatalError("test message")
        assert str(err) == "test message"
