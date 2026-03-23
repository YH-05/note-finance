"""creator_enrichment Phase 4: パイプライン統合.

entity_linker.resolve_all() -> emit_creator_queue_v2.map_creator_enrichment_v2()
-> CreatorGraphWriter.ingest() の3ステップを接続し、
中間 JSON を ``.tmp/`` に保存するパイプライン関数。

Usage
-----
::

    from creator_enrichment.phases.pipeline import run_pipeline

    result = run_pipeline(
        cycle_data=cycle_data,
        neo4j_client=client,
        neo4j_driver=driver,
        dry_run=False,
    )
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from creator_enrichment.config import GENRE_NAMES
from creator_enrichment.neo4j_writer import CreatorGraphWriter
from creator_enrichment.types import CycleData, IngestResult, PhaseError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 遅延インポートラッパー（テスト時にパッチ可能）
# ---------------------------------------------------------------------------
def _import_resolve_all() -> Any:
    """scripts.entity_linker.resolve_all を遅延インポートする.

    Returns
    -------
    Callable
        resolve_all 関数
    """
    from scripts.entity_linker import resolve_all

    return resolve_all


def _import_map_v2() -> Any:
    """scripts.emit_creator_queue_v2.map_creator_enrichment_v2 を遅延インポートする.

    Returns
    -------
    Callable
        map_creator_enrichment_v2 関数
    """
    from scripts.emit_creator_queue_v2 import map_creator_enrichment_v2

    return map_creator_enrichment_v2


# ---------------------------------------------------------------------------
# 中間 JSON 保存ヘルパー
# ---------------------------------------------------------------------------
def _save_intermediate(data: dict[str, Any], cycle_id: str, step: int) -> None:
    """中間結果を JSON ファイルに保存する.

    Parameters
    ----------
    data : dict[str, Any]
        保存対象のデータ
    cycle_id : str
        サイクル識別子
    step : int
        ステップ番号 (0, 1, 2)
    """
    path = Path(".tmp") / f"creator-pipeline-{cycle_id}-step{step}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    logger.debug("Saved intermediate JSON: %s", path)


# ---------------------------------------------------------------------------
# パイプライン関数
# ---------------------------------------------------------------------------
def run_pipeline(
    cycle_data: CycleData,
    neo4j_client: Any,
    neo4j_driver: Any,
    dry_run: bool = False,
) -> IngestResult:
    """Phase 4 パイプラインを実行する.

    Step 4.0: entity_linker.resolve_all() で Entity/Concept を解決
    Step 4.1: emit_creator_queue_v2.map_creator_enrichment_v2() で queue_doc 生成
    Step 4.2: CreatorGraphWriter.ingest() で Neo4j MERGE（dry_run 時はスキップ）

    Parameters
    ----------
    cycle_data : CycleData
        Phase 3 の抽出結果
    neo4j_client : Any
        Neo4j クライアント（entity_linker 用）
    neo4j_driver : Any
        Neo4j ドライバ（CreatorGraphWriter 用）
    dry_run : bool
        True の場合 Step 4.2 をスキップ

    Returns
    -------
    IngestResult
        ノード・リレーション作成件数

    Raises
    ------
    PhaseError
        ジャンルが不正な場合、または各ステップでエラーが発生した場合
    """
    cycle_id = cycle_data["cycle_id"]
    logger.info("Pipeline started: cycle_id=%s, dry_run=%s", cycle_id, dry_run)

    # --- ジャンル事前バリデーション ---
    genre = cycle_data.get("genre", "")
    if genre not in GENRE_NAMES:
        msg = f"Invalid genre: {genre!r}. Valid genres: {GENRE_NAMES}"
        logger.error(msg)
        raise PhaseError(msg)

    # --- Step 4.0: Entity linking ---
    logger.info("Step 4.0: Entity linking started")
    resolve_all = _import_resolve_all()
    resolved_data = resolve_all(neo4j_client, dict(cycle_data), use_embedding=False)
    _save_intermediate(resolved_data, cycle_id, 0)
    logger.info("Step 4.0: Entity linking completed")

    # --- Step 4.1: Queue mapping ---
    logger.info("Step 4.1: Queue mapping started")
    map_creator_enrichment_v2 = _import_map_v2()
    queue_doc = map_creator_enrichment_v2(resolved_data)
    _save_intermediate(queue_doc, cycle_id, 1)
    logger.info("Step 4.1: Queue mapping completed")

    # --- Step 4.2: Graph ingest ---
    if dry_run:
        logger.info("Dry run: skipping graph ingest (Step 4.2)")
        return IngestResult(nodes_created=0, relations_created=0)

    logger.info("Step 4.2: Graph ingest started")
    writer = CreatorGraphWriter(neo4j_driver)
    result = writer.ingest(queue_doc, cycle_id=cycle_id)
    _save_intermediate(
        {
            "nodes_created": result["nodes_created"],
            "relations_created": result["relations_created"],
        },
        cycle_id,
        2,
    )
    logger.info(
        "Step 4.2: Graph ingest completed: nodes_created=%d, relations_created=%d",
        result["nodes_created"],
        result["relations_created"],
    )
    return result
