"""一気通貫パイプライン: Layer 0 → 1 → 2 → 3 → 4.

ソース選択 → RSS収集 → 原文保存 → LLM抽出 → 構造化出力 → emit → Neo4j投入
の全ステップを1回の呼び出しで実行する。

Usage
-----
::

    from data_pipeline.pipeline import run_pipeline

    # 全RSSソースを処理（LLM抽出あり）
    result = run_pipeline(extract=True)

    # 特定ソースのみ（LLM抽出なし、原文保存+emit まで）
    result = run_pipeline(source_ids=["jp-finance"], extract=False)

    # dry-run（Neo4j投入なし）
    result = run_pipeline(dry_run=True)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """パイプライン実行結果."""

    sources_processed: int = 0
    items_collected: int = 0
    items_saved: int = 0
    items_extracted: int = 0
    facts_total: int = 0
    claims_total: int = 0
    emit_input_path: Path | None = None
    graph_queue_path: Path | None = None
    neo4j_nodes: int = 0
    neo4j_relations: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0


def run_pipeline(
    *,
    source_ids: list[str] | None = None,
    method: str = "rss",
    extract: bool = True,
    authority_level: int = 3,
    max_items_per_feed: int = 10,
    ingest_neo4j: bool = True,
    dry_run: bool = False,
) -> PipelineResult:
    """一気通貫パイプラインを実行する.

    Parameters
    ----------
    source_ids : list[str] | None
        処理対象の source_id リスト。None の場合は指定 method の全有効ソース。
    method : str
        収集方法（"rss" のみ現在対応）。
    extract : bool
        True の場合、LLM抽出を実行する。False の場合は minimal output。
    authority_level : int
        StructuredOutput の authority_level。
    max_items_per_feed : int
        1フィードあたりの最大取得件数。
    ingest_neo4j : bool
        True の場合、Neo4j に投入する。
    dry_run : bool
        True の場合、Neo4j 投入をスキップ。

    Returns
    -------
    PipelineResult
        実行結果。
    """
    result = PipelineResult()

    # === Layer 0: ソースレジストリ ===
    logger.info("=== Layer 0: Source Registry ===")
    try:
        from data_pipeline.registry import RegistryLoader

        loader = RegistryLoader()
        registry = loader.load_source_registry()

        if source_ids:
            sources = [s for s in registry.sources if s.source_id in source_ids and s.enabled]
        else:
            sources = [s for s in registry.filter_by_method(method) if s.enabled]

        logger.info("Selected %d sources", len(sources))
        result.sources_processed = len(sources)

        if not sources:
            result.errors.append("No sources selected")
            return result
    except Exception as e:
        result.errors.append(f"Layer 0 failed: {e}")
        return result

    # === Layer 1: 収集 ===
    logger.info("=== Layer 1: Collection ===")
    try:
        from data_pipeline.collectors.rss import RssCollector

        collector = RssCollector(
            config_dir=loader.config_dir,
            max_items_per_feed=max_items_per_feed,
            fetch_if_empty=True,
            request_delay=0.5,
            feed_timeout=10.0,
        )

        all_items = []
        for source in sources:
            collection = collector.collect(source)
            all_items.extend(collection.items)
            logger.info(
                "  %s: %d items, %d errors",
                source.source_id, collection.success_count, collection.error_count,
            )
            if collection.errors:
                for e in collection.errors:
                    result.errors.append(f"[{source.source_id}] {e}")

        result.items_collected = len(all_items)
        logger.info("Total collected: %d items", len(all_items))

        if not all_items:
            result.errors.append("No items collected")
            return result
    except Exception as e:
        result.errors.append(f"Layer 1 failed: {e}")
        return result

    # === Layer 2: 原文保存 ===
    logger.info("=== Layer 2: Raw Store ===")
    try:
        from data_pipeline.collectors.base import CollectionResult
        from data_pipeline.storage.raw_store import RawStore

        store = RawStore()

        # ソースごとにバッチ保存
        items_by_source: dict[str, list] = {}
        for item in all_items:
            items_by_source.setdefault(item.source_id, []).append(item)

        total_saved = 0
        for sid, items in items_by_source.items():
            cr = CollectionResult(source_id=sid)
            cr.items = items
            sr = store.save(cr)
            total_saved += sr.saved
            logger.info("  %s: saved=%d, dup=%d, empty=%d", sid, sr.saved, sr.skipped_duplicate, sr.skipped_empty)

        result.items_saved = total_saved
    except Exception as e:
        result.errors.append(f"Layer 2 failed: {e}")
        return result

    # === Layer 3: 構造化出力 ===
    logger.info("=== Layer 3: Structuring ===")
    try:
        if extract:
            from data_pipeline.structurer.extractor import LlmExtractor
            from data_pipeline.structurer.converter import build_from_extracted

            # テキストがあるアイテムのみ抽出
            text_items = [i for i in all_items if i.raw_text.strip()]
            logger.info("Extracting from %d items (LLM)", len(text_items))

            extractor = LlmExtractor(request_delay=1.0)
            extractions = extractor.extract_many(text_items)
            output = build_from_extracted(text_items, extractions, authority_level=authority_level)
            result.items_extracted = len(text_items)
        else:
            from data_pipeline.structurer.converter import build_minimal_output

            text_items = [i for i in all_items if i.raw_text.strip()]
            output = build_minimal_output(text_items, authority_level=authority_level)

        result.facts_total = output.fact_count
        result.claims_total = output.claim_count
        logger.info(
            "Structured: %d facts, %d claims, %d topics, %d entities",
            output.fact_count, output.claim_count, len(output.topics), len(output.entity_names),
        )

        # emit 入力 JSON 保存
        from data_pipeline.structurer.emitter import save_emit_input

        emit_path = save_emit_input(output)
        result.emit_input_path = emit_path
        logger.info("Emit input saved: %s", emit_path)
    except Exception as e:
        result.errors.append(f"Layer 3 failed: {e}")
        return result

    # === Layer 4: emit_research_queue.py 実行 ===
    logger.info("=== Layer 4a: emit_research_queue.py ===")
    try:
        from data_pipeline.structurer.emitter import run_emit_graph_queue

        gq_path = run_emit_graph_queue(emit_path)
        if gq_path:
            result.graph_queue_path = gq_path
            logger.info("Graph queue generated: %s", gq_path)
        else:
            result.errors.append("emit_research_queue.py failed to generate graph-queue")
            return result
    except Exception as e:
        result.errors.append(f"Layer 4a failed: {e}")
        return result

    # === Layer 4: Neo4j 投入 ===
    if ingest_neo4j and not dry_run:
        logger.info("=== Layer 4b: Neo4j Ingestion ===")
        try:
            from data_pipeline.neo4j_loader import ingest_to_neo4j, load_graph_queue

            queue_data = load_graph_queue(gq_path)
            counts = ingest_to_neo4j(queue_data, dry_run=dry_run)
            result.neo4j_nodes = counts["nodes"]
            result.neo4j_relations = counts["relations"]
            logger.info("Neo4j: %d nodes, %d relations", counts["nodes"], counts["relations"])
        except Exception as e:
            result.errors.append(f"Layer 4b failed: {e}")
    elif dry_run:
        logger.info("=== Layer 4b: SKIPPED (dry-run) ===")
        try:
            from data_pipeline.neo4j_loader import ingest_to_neo4j, load_graph_queue

            queue_data = load_graph_queue(gq_path)
            counts = ingest_to_neo4j(queue_data, dry_run=True)
            result.neo4j_nodes = counts["nodes"]
            result.neo4j_relations = counts["relations"]
            logger.info("Neo4j (dry-run): would ingest %d nodes, %d relations", counts["nodes"], counts["relations"])
        except Exception as e:
            result.errors.append(f"Layer 4b dry-run failed: {e}")

    logger.info("=== Pipeline Complete ===")
    return result
