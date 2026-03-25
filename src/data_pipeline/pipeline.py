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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

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
    tips_total: int = 0
    stories_total: int = 0
    emit_input_path: Path | None = None
    graph_queue_path: Path | None = None
    neo4j_nodes: int = 0
    neo4j_relations: int = 0
    target: str = "research"
    errors: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return len(self.errors) == 0


def run_pipeline(  # noqa: PLR0912, PLR0915
    *,
    target: str = "research",
    source_ids: list[str] | None = None,
    method: str | list[str] = "rss",
    extract: bool = True,
    authority_level: int = 3,
    max_items_per_feed: int = 10,
    ingest_neo4j: bool = True,
    dry_run: bool = False,
    genre: str = "career",
    link_entities: bool = False,
) -> PipelineResult:
    """一気通貫パイプラインを実行する.

    Parameters
    ----------
    target : str
        投入先 ("research" or "creator")。
    source_ids : list[str] | None
        処理対象の source_id リスト。None の場合は指定 method の全有効ソース。
    method : str | list[str]
        収集方法。"rss", "scraping", またはリストで複数指定。
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
    genre : str
        creator target のジャンル (default: "career")。
    link_entities : bool
        True の場合、Entity Linker を実行する。

    Returns
    -------
    PipelineResult
        実行結果。
    """
    result = PipelineResult(target=target)

    # === Layer 0: ソースレジストリ ===
    logger.info("=== Layer 0: Source Registry ===")
    try:
        from data_pipeline.registry import RegistryLoader

        loader = RegistryLoader()
        registry = loader.load_source_registry()

        if source_ids:
            sources = [
                s for s in registry.sources if s.source_id in source_ids and s.enabled
            ]
        else:
            methods = [method] if isinstance(method, str) else method
            sources = []
            for m in methods:
                sources.extend(s for s in registry.filter_by_method(m) if s.enabled)

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
        from data_pipeline.collectors.scraper import ScrapingCollector

        # 収集方法ごとにコレクターを選択
        rss_collector = RssCollector(
            config_dir=loader.config_dir,
            max_items_per_feed=max_items_per_feed,
            fetch_if_empty=True,
            request_delay=0.5,
            feed_timeout=10.0,
        )
        scraping_collector = ScrapingCollector(
            config_dir=loader.config_dir,
            max_articles_per_site=max_items_per_feed,
            request_delay=1.0,
        )
        collectors: dict[str, Any] = {
            "rss": rss_collector,
            "scraping": scraping_collector,
        }

        # note-com コレクター（Playwright 必須のため遅延インポート）
        try:
            from data_pipeline.collectors.note_com import NoteComCollector

            collectors["note-com"] = NoteComCollector(
                config_dir=loader.config_dir,
                max_articles=max_items_per_feed,
                headless=True,
            )
        except ImportError:
            logger.debug("NoteComCollector not available (playwright not installed)")

        all_items = []
        for source in sources:
            collector = collectors.get(source.collection_method)
            if collector is None:
                logger.warning(
                    "No collector for method '%s', skipping %s",
                    source.collection_method,
                    source.source_id,
                )
                continue
            collection = collector.collect(source)
            all_items.extend(collection.items)
            logger.info(
                "  %s: %d items, %d errors",
                source.source_id,
                collection.success_count,
                collection.error_count,
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
            logger.info(
                "  %s: saved=%d, dup=%d, empty=%d",
                sid,
                sr.saved,
                sr.skipped_duplicate,
                sr.skipped_empty,
            )

        result.items_saved = total_saved
    except Exception as e:
        result.errors.append(f"Layer 2 failed: {e}")
        return result

    # === Layer 3+4: target で分岐 ===
    if target == "creator":
        _run_creator_layers(
            all_items,
            result,
            genre=genre,
            link_entities=link_entities,
            ingest_neo4j=ingest_neo4j,
            dry_run=dry_run,
        )
    else:
        _run_research_layers(
            all_items,
            result,
            extract=extract,
            authority_level=authority_level,
            link_entities=link_entities,
            ingest_neo4j=ingest_neo4j,
            dry_run=dry_run,
        )

    logger.info("=== Pipeline Complete ===")
    return result


# ---------------------------------------------------------------------------
# research target (Layer 3-4)
# ---------------------------------------------------------------------------


def _run_research_layers(  # noqa: PLR0915
    all_items: list,
    result: PipelineResult,
    *,
    extract: bool,
    authority_level: int,
    link_entities: bool,
    ingest_neo4j: bool,
    dry_run: bool,
) -> None:
    """research-neo4j 向け Layer 3-4."""
    # Layer 3: 構造化出力
    logger.info("=== Layer 3: Structuring (research) ===")
    try:
        if extract:
            from data_pipeline.structurer.converter import build_from_extracted
            from data_pipeline.structurer.extractor import LlmExtractor

            text_items = [i for i in all_items if i.raw_text.strip()]
            logger.info("Extracting from %d items (LLM)", len(text_items))
            extractor = LlmExtractor(request_delay=1.0)
            extractions = extractor.extract_many(text_items)
            output = build_from_extracted(
                text_items, extractions, authority_level=authority_level
            )
            result.items_extracted = len(text_items)
        else:
            from data_pipeline.structurer.converter import build_minimal_output

            text_items = [i for i in all_items if i.raw_text.strip()]
            output = build_minimal_output(text_items, authority_level=authority_level)

        result.facts_total = output.fact_count
        result.claims_total = output.claim_count
        logger.info(
            "Structured: %d facts, %d claims, %d topics, %d entities",
            output.fact_count,
            output.claim_count,
            len(output.topics),
            len(output.entity_names),
        )

        from data_pipeline.structurer.emitter import save_emit_input

        emit_path = save_emit_input(output)
        result.emit_input_path = emit_path
        logger.info("Emit input saved: %s", emit_path)
    except Exception as e:
        result.errors.append(f"Layer 3 failed: {e}")
        return

    # Layer 3.5: Entity Linking (optional)
    if link_entities:
        logger.info("=== Layer 3.5: Entity Linking (research) ===")
        try:
            import os

            from scripts.entity_linker import Neo4jClient, resolve_all

            uri = os.environ.get("NEO4J_RESEARCH_URI", "bolt://localhost:7688")
            user = os.environ.get("NEO4J_RESEARCH_USER", "neo4j")
            password = os.environ.get("NEO4J_RESEARCH_PASSWORD", "gomasuke")
            client = Neo4jClient(uri, user, password)
            try:
                import json

                emit_data = json.loads(emit_path.read_text(encoding="utf-8"))
                resolved = resolve_all(
                    client, emit_data, use_embedding=False, use_v3=True
                )
                emit_path.write_text(
                    json.dumps(resolved, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info("Entity linking completed")
            finally:
                client.close()
        except Exception as e:
            logger.warning("Entity linking failed (non-blocking): %s", e)

    # Layer 4a: emit_research_queue.py
    logger.info("=== Layer 4a: emit_research_queue.py ===")
    try:
        from data_pipeline.structurer.emitter import run_emit_graph_queue

        gq_path = run_emit_graph_queue(emit_path)
        if gq_path:
            result.graph_queue_path = gq_path
            logger.info("Graph queue generated: %s", gq_path)
        else:
            result.errors.append(
                "emit_research_queue.py failed to generate graph-queue"
            )
            return
    except Exception as e:
        result.errors.append(f"Layer 4a failed: {e}")
        return

    # Layer 4b: Neo4j 投入
    _ingest_neo4j(
        gq_path, result, target="research", ingest_neo4j=ingest_neo4j, dry_run=dry_run
    )


# ---------------------------------------------------------------------------
# creator target (Layer 3-4)
# ---------------------------------------------------------------------------


def _run_creator_layers(  # noqa: PLR0915
    all_items: list,
    result: PipelineResult,
    *,
    genre: str,
    link_entities: bool,
    ingest_neo4j: bool,
    dry_run: bool,
) -> None:
    """creator-neo4j 向け Layer 3-4."""
    from pathlib import Path

    text_items = [i for i in all_items if i.raw_text.strip()]
    if not text_items:
        result.errors.append("No items with text for creator extraction")
        return

    # Layer 3: creator 向け構造化
    logger.info("=== Layer 3: Structuring (creator) ===")
    try:
        from creator_enrichment.llm_client import SdkLLMClient
        from creator_enrichment.phases.extract import ContentExtractor
        from creator_enrichment.types import RawItem

        # CollectedItem → RawItem 変換
        raw_items = [
            RawItem(
                url=item.url,
                title=item.title,
                content=item.raw_text,
                source=item.collection_method or "web",
            )
            for item in text_items
        ]

        extractor = ContentExtractor(llm_client=SdkLLMClient())
        cycle_data = extractor.extract_batch(items=raw_items, genre=genre)
        cycle_data_dict = dict(cycle_data)

        result.items_extracted = len(text_items)
        result.facts_total = len(cycle_data.get("facts", []))
        result.tips_total = len(cycle_data.get("tips", []))
        result.stories_total = len(cycle_data.get("stories", []))
        logger.info(
            "Structured: %d facts, %d tips, %d stories",
            result.facts_total,
            result.tips_total,
            result.stories_total,
        )
    except Exception as e:
        result.errors.append(f"Layer 3 (creator) failed: {e}")
        return

    # Layer 3.5: Entity Linking
    if link_entities:
        logger.info("=== Layer 3.5: Entity Linking (creator) ===")
        try:
            import os

            from scripts.entity_linker import Neo4jClient, resolve_all

            uri = os.environ.get("NEO4J_CREATOR_URI", "bolt://localhost:7689")
            user = os.environ.get("NEO4J_CREATOR_USER", "neo4j")
            password = os.environ.get("NEO4J_CREATOR_PASSWORD", "gomasuke")
            client = Neo4jClient(uri, user, password)
            try:
                cycle_data_dict = resolve_all(
                    client, cycle_data_dict, use_embedding=False
                )
                logger.info("Entity linking completed")
            finally:
                client.close()
        except Exception as e:
            logger.warning("Entity linking failed (non-blocking): %s", e)

    # Layer 4a: emit_creator_queue_v2
    logger.info("=== Layer 4a: emit_creator_queue_v2 ===")
    try:
        from scripts.emit_creator_queue_v2 import map_creator_enrichment_v2

        queue_doc = map_creator_enrichment_v2(cycle_data_dict)

        # graph-queue JSON 保存
        output_dir = Path(".tmp/creator-graph-queue")
        output_dir.mkdir(parents=True, exist_ok=True)
        gq_path = output_dir / f"{queue_doc['queue_id']}.json"
        gq_path.write_text(
            json.dumps(queue_doc, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result.graph_queue_path = gq_path
        logger.info("Creator graph queue generated: %s", gq_path)
    except Exception as e:
        result.errors.append(f"Layer 4a (creator) failed: {e}")
        return

    # Layer 4b: creator-neo4j 投入
    _ingest_neo4j(
        gq_path, result, target="creator", ingest_neo4j=ingest_neo4j, dry_run=dry_run
    )


# ---------------------------------------------------------------------------
# 共通: Neo4j 投入
# ---------------------------------------------------------------------------


def _ingest_neo4j(
    gq_path: Path,
    result: PipelineResult,
    *,
    target: str,
    ingest_neo4j: bool,
    dry_run: bool,
) -> None:
    """Neo4j 投入の共通ロジック."""
    if not ingest_neo4j and not dry_run:
        return

    from data_pipeline.neo4j_loader import (
        ingest_to_creator_neo4j,
        ingest_to_neo4j,
        load_graph_queue,
    )

    label = "dry-run" if dry_run else "ingestion"
    logger.info("=== Layer 4b: Neo4j %s (%s) ===", label, target)

    try:
        queue_data = load_graph_queue(gq_path)
        if target == "creator":
            counts = ingest_to_creator_neo4j(
                queue_data, dry_run=dry_run or not ingest_neo4j
            )
        else:
            counts = ingest_to_neo4j(queue_data, dry_run=dry_run or not ingest_neo4j)
        result.neo4j_nodes = counts["nodes"]
        result.neo4j_relations = counts["relations"]
        logger.info(
            "Neo4j (%s): %d nodes, %d relations",
            target,
            counts["nodes"],
            counts["relations"],
        )
    except Exception as e:
        result.errors.append(f"Layer 4b ({target}) failed: {e}")


# ---------------------------------------------------------------------------
# RawStore → Neo4j 投入（2ステップ分離の ingest 側）
# ---------------------------------------------------------------------------


def run_ingest_from_rawstore(
    *,
    source_id: str,
    target: str = "research",
    date: str | None = None,
    genre: str = "career",
    link_entities: bool = False,
    dry_run: bool = False,
) -> PipelineResult:
    """RawStore に保存済みのデータを読み出し Layer 3-4 を実行する.

    収集（collect）と投入（ingest）を分離した2ステップフローの後半。
    ``run_pipeline()`` の Layer 0-2 をスキップし、RawStore から直接読み出す。

    Parameters
    ----------
    source_id : str
        RawStore 内の source_id（例: "note-com-yukihata"）。
    target : str
        投入先 ("research" or "creator")。
    date : str | None
        日付フィルタ (YYYY-MM-DD)。None の場合は全日付。
    genre : str
        creator target のジャンル (default: "career")。
    link_entities : bool
        True の場合、Entity Linker を実行する。
    dry_run : bool
        True の場合、Neo4j 投入をスキップ。

    Returns
    -------
    PipelineResult
        実行結果。
    """
    from data_pipeline.storage.raw_store import RawStore

    result = PipelineResult(target=target)

    # === RawStore からデータ読み出し ===
    logger.info(
        "=== Ingest: Loading from RawStore (source=%s, date=%s) ===", source_id, date
    )
    try:
        store = RawStore()
        all_items = store.load_items(source_id, date)
        result.items_collected = len(all_items)
        result.items_saved = len(all_items)
        logger.info("Loaded %d items from RawStore", len(all_items))

        if not all_items:
            result.errors.append(
                f"No items found in RawStore for source={source_id}, date={date}"
            )
            return result
    except Exception as e:
        result.errors.append(f"RawStore load failed: {e}")
        return result

    # === Layer 3-4: target で分岐 ===
    if target == "creator":
        _run_creator_layers(
            all_items,
            result,
            genre=genre,
            link_entities=link_entities,
            ingest_neo4j=True,
            dry_run=dry_run,
        )
    else:
        _run_research_layers(
            all_items,
            result,
            extract=True,
            authority_level=3,
            link_entities=link_entities,
            ingest_neo4j=True,
            dry_run=dry_run,
        )

    logger.info("=== Ingest Complete ===")
    return result
