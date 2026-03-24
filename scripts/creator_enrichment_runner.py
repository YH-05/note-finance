#!/usr/bin/env python3
"""Creator enrichment CLI runner.

Usage
-----
::

    uv run python scripts/creator_enrichment_runner.py --until 23:30
    uv run python scripts/creator_enrichment_runner.py --until 23:30 --genre career --dry-run
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

# プロジェクトルートと src/ をインポートパスに追加
# (scripts/ は __init__.py を持つパッケージとしてプロジェクトルートから参照)
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


def _setup_logging() -> None:
    """プロジェクト標準のロギング設定を適用する."""
    import os

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Neo4j 接続定数
# ---------------------------------------------------------------------------
_CREATOR_NEO4J_URI = "bolt://localhost:7689"
_CREATOR_NEO4J_USER = "neo4j"
_CREATOR_NEO4J_PASSWORD = "gomasuke"


# ---------------------------------------------------------------------------
# Neo4j Client Adapter
# ---------------------------------------------------------------------------
class _Neo4jClientAdapter:
    """entity_linker.Neo4jClient を GapAnalyzer の Neo4jClientProtocol に適合させる.

    GapAnalyzer は ``execute_query(query, params)`` を期待するが、
    entity_linker.Neo4jClient は ``query(cypher, **params)`` を使う。
    このアダプタが両方のインターフェースを橋渡しする。
    """

    def __init__(self, neo4j_client: Any) -> None:
        self._client = neo4j_client

    def execute_query(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Neo4jClientProtocol 準拠の execute_query."""
        if params:
            return self._client.query(query, **params)
        return self._client.query(query)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def _bootstrap() -> tuple[Any, Any]:
    """Neo4j ドライバ / クライアントを生成する.

    Returns
    -------
    tuple[neo4j.Driver, entity_linker.Neo4jClient]
    """
    from neo4j import GraphDatabase

    from scripts.entity_linker import Neo4jClient

    logger.info("Connecting to creator-neo4j at %s", _CREATOR_NEO4J_URI)

    driver = GraphDatabase.driver(
        _CREATOR_NEO4J_URI,
        auth=(_CREATOR_NEO4J_USER, _CREATOR_NEO4J_PASSWORD),
    )
    driver.verify_connectivity()
    logger.info("Neo4j connection verified")

    neo4j_client = Neo4jClient(
        uri=_CREATOR_NEO4J_URI,
        user=_CREATOR_NEO4J_USER,
        password=_CREATOR_NEO4J_PASSWORD,
    )

    return driver, neo4j_client


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entrypoint for creator-enrichment orchestrator."""
    _setup_logging()

    from creator_enrichment.config import load_config, parse_args
    from creator_enrichment.orchestrator import (
        CreatorEnrichmentOrchestrator,
        FatalError,
    )
    import json as _json

    from creator_enrichment.llm_client import SdkLLMClient
    from creator_enrichment.phases.cross_entity import CrossEntityEnricher
    from creator_enrichment.phases.extract import ContentExtractor
    from creator_enrichment.phases.gap_analysis import GapAnalyzer
    from creator_enrichment.phases.search import DirectSearcher

    args = parse_args()

    try:
        config = load_config(args)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)

    logger.info(
        "Starting creator enrichment: until=%s, genre=%s, dry_run=%s",
        config.until_time,
        config.genre,
        config.dry_run,
    )

    # --- Bootstrap: 外部リソースの初期化 ---
    try:
        driver, neo4j_client = _bootstrap()
    except Exception as e:
        logger.error("Bootstrap failed: %s", e)
        sys.exit(1)

    # --- TAVILY_API_KEY チェック ---
    import os

    tavily_api_key = os.environ.get("TAVILY_API_KEY", "")
    if not tavily_api_key:
        logger.error("TAVILY_API_KEY が未設定です")
        sys.exit(1)

    # --- genre_config 読み込み ---
    config_path = Path(__file__).resolve().parent.parent / "data" / "config" / "creator-enrichment-config.json"
    genre_config = _json.loads(config_path.read_text(encoding="utf-8")).get("genres", {})

    # --- 各フェーズの実クラスをワイヤリング ---
    gap_adapter = _Neo4jClientAdapter(neo4j_client)
    llm_client = SdkLLMClient()
    logger.info("SdkLLMClient initialized (model=Sonnet)")

    orchestrator = CreatorEnrichmentOrchestrator(
        config,
        gap_analyzer=GapAnalyzer(gap_adapter),
        searcher=DirectSearcher(
            llm_client=llm_client,
            genre_config=genre_config,
            tavily_api_key=tavily_api_key,
        ),
        extractor=ContentExtractor(llm_client=llm_client),
        cross_enricher=CrossEntityEnricher(driver, llm_client=llm_client),
        neo4j_client=neo4j_client,
        neo4j_driver=driver,
    )

    try:
        orchestrator.run()
    except FatalError as e:
        logger.error("Fatal error: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    finally:
        neo4j_client.close()
        driver.close()
        logger.info("Neo4j connections closed")

    logger.info("Creator enrichment completed")


if __name__ == "__main__":
    main()
