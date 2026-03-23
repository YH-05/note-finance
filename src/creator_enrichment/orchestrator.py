"""creator_enrichment オーケストレーター.

Phase 1 (Gap Analysis) -> Phase 2 (Search) -> Phase 3 (Extract)
-> Phase 4 (Pipeline) -> Phase 4.5 (Cross-entity) のサイクルを制御する。

until_time / max_cycles でループ制御し、CycleError を隔離して
連続5回の失敗で FatalError を送出する。

Usage
-----
::

    from creator_enrichment.config import parse_args, load_config
    from creator_enrichment.orchestrator import CreatorEnrichmentOrchestrator

    args = parse_args()
    config = load_config(args)
    orchestrator = CreatorEnrichmentOrchestrator(config)
    orchestrator.run()
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from creator_enrichment.phases.pipeline import run_pipeline
from creator_enrichment.session_log import SessionLogger
from creator_enrichment.types import CycleError, CycleReport

if TYPE_CHECKING:
    from creator_enrichment.config import OrchestratorConfig
    from creator_enrichment.phases.cross_entity import CrossEntityEnricher
    from creator_enrichment.phases.extract import ContentExtractor
    from creator_enrichment.phases.gap_analysis import GapAnalyzer
    from creator_enrichment.phases.search import ClaudeCodeSearcher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------
class FatalError(Exception):
    """連続サイクル失敗による回復不能エラー.

    5回連続で CycleError が発生した場合に送出する。
    """


# ---------------------------------------------------------------------------
# オーケストレーター
# ---------------------------------------------------------------------------
class CreatorEnrichmentOrchestrator:
    """creator-enrichment サイクルを制御するオーケストレーター.

    Parameters
    ----------
    config : OrchestratorConfig
        オーケストレーター設定
    gap_analyzer : GapAnalyzer | None
        Phase 1 ギャップ分析（None の場合は内部で生成）
    searcher : ClaudeCodeSearcher | None
        Phase 2 検索（None の場合は内部で生成）
    extractor : ContentExtractor | None
        Phase 3 抽出（None の場合は内部で生成）
    cross_enricher : CrossEntityEnricher | None
        Phase 4.5 Cross-entity（None の場合は内部で生成）
    neo4j_client : Any
        Neo4j クライアント
    neo4j_driver : Any
        Neo4j ドライバ
    """

    def __init__(
        self,
        config: OrchestratorConfig,
        *,
        gap_analyzer: GapAnalyzer | None = None,
        searcher: ClaudeCodeSearcher | None = None,
        extractor: ContentExtractor | None = None,
        cross_enricher: CrossEntityEnricher | None = None,
        neo4j_client: Any = None,
        neo4j_driver: Any = None,
    ) -> None:
        self._config = config
        self._gap_analyzer = gap_analyzer
        self._searcher = searcher
        self._extractor = extractor
        self._cross_enricher = cross_enricher
        self._neo4j_client = neo4j_client
        self._neo4j_driver = neo4j_driver

        logger.info(
            "CreatorEnrichmentOrchestrator initialized: "
            "genre=%s, until=%s, dry_run=%s, max_cycles=%s",
            config.genre,
            config.until_time,
            config.dry_run,
            config.max_cycles,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        """メインループを実行する.

        until_time / max_cycles の条件を満たすまでサイクルを繰り返す。
        連続5回の CycleError で FatalError を送出する。
        連続 max_consecutive_empty_cycles 回の空結果でループを終了する。

        Raises
        ------
        FatalError
            5回連続でサイクルが失敗した場合
        """
        cycle_count = 0
        consecutive_errors = 0
        consecutive_empty = 0
        prev_genre: str | None = None
        session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        session_logger = SessionLogger(session_id)

        logger.info("Orchestrator run started: session_id=%s", session_id)

        while datetime.now().time() < self._config.until_time:
            if self._config.max_cycles > 0 and cycle_count >= self._config.max_cycles:
                logger.info(
                    "Max cycles reached: %d/%d",
                    cycle_count,
                    self._config.max_cycles,
                )
                break

            cycle_start = time.monotonic()
            cycle_count += 1

            logger.info("Cycle %d started", cycle_count)

            try:
                # Phase 1: Gap Analysis
                gap_result = self._gap_analyzer.analyze(  # type: ignore[union-attr]
                    prev_genre, self._config.genre
                )
                prev_genre = gap_result["genre"]

                # Phase 2: Search
                queries = gap_result["low_coverage_concepts"][:5]
                raw_items = self._searcher.search(  # type: ignore[union-attr]
                    queries, gap_result["genre"]
                )

                if not raw_items:
                    consecutive_empty += 1
                    logger.warning(
                        "Empty search results: consecutive_empty=%d/%d",
                        consecutive_empty,
                        self._config.cycle_settings.max_consecutive_empty_cycles,
                    )
                    if (
                        consecutive_empty
                        >= self._config.cycle_settings.max_consecutive_empty_cycles
                    ):
                        logger.info(
                            "Max consecutive empty cycles reached, stopping",
                        )
                        break
                    time.sleep(self._config.cycle_settings.empty_cycle_wait_seconds)
                    continue

                consecutive_empty = 0

                # Phase 3: Extract
                cycle_data = self._extractor.extract_batch(  # type: ignore[union-attr]
                    items=raw_items, genre=gap_result["genre"]
                )

                # Phase 4: Pipeline
                run_pipeline(
                    cycle_data,
                    self._neo4j_client,
                    self._neo4j_driver,
                    self._config.dry_run,
                )

                # Phase 4.5: Cross-entity (every 3 cycles)
                cross_added = 0
                if cycle_count % 3 == 0 and not self._config.dry_run:
                    cross_added = self._cross_enricher.run(  # type: ignore[union-attr]
                        cycle_count
                    )

                # Record cycle
                report = CycleReport(
                    genre=gap_result["genre"],
                    search_results=len(raw_items),
                    contents_created={
                        "Fact": len(cycle_data["facts"]),
                        "Tip": len(cycle_data["tips"]),
                        "Story": len(cycle_data["stories"]),
                    },
                    entities_extracted=len(cycle_data["entities"]),
                    relations_detected=len(cycle_data["concept_relations"]),
                    pipeline_status=("dry-run" if self._config.dry_run else "success"),
                    cross_entity_added=cross_added,
                )
                session_logger.record_cycle(cycle_count, report)
                consecutive_errors = 0

                logger.info(
                    "Cycle %d completed: genre=%s, search=%d, cross=%d",
                    cycle_count,
                    gap_result["genre"],
                    len(raw_items),
                    cross_added,
                )

            except CycleError as e:
                consecutive_errors += 1
                session_logger.record_error(cycle_count, e)
                logger.error(
                    "Cycle %d failed: consecutive_errors=%d/5, error=%s",
                    cycle_count,
                    consecutive_errors,
                    e,
                )
                if consecutive_errors >= 5:
                    raise FatalError("5 consecutive cycle errors") from e

            # Enforce minimum interval
            self._enforce_min_interval(cycle_start)

        session_logger.finalize(cycle_count)
        logger.info(
            "Orchestrator run finished: total_cycles=%d",
            cycle_count,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _enforce_min_interval(self, cycle_start: float) -> None:
        """サイクル間の最小間隔を強制する.

        Parameters
        ----------
        cycle_start : float
            サイクル開始時の ``time.monotonic()`` 値
        """
        elapsed = time.monotonic() - cycle_start
        min_interval = self._config.cycle_settings.min_cycle_interval_seconds
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(
                "Enforcing min interval: sleeping %.1fs (elapsed=%.1fs, min=%ds)",
                sleep_time,
                elapsed,
                min_interval,
            )
            time.sleep(sleep_time)
