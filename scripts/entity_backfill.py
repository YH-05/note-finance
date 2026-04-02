#!/usr/bin/env python3
"""Entity backfill for creator-neo4j.

既存の Fact/Tip/Story コンテンツに対して Entity の MENTIONS リレーションを
後付けで作成するバッチスクリプト。

Phase 1: サブストリングマッチング
  - 既存 Entity 名がコンテンツの content テキストに含まれるかチェック
  - 3文字未満や曖昧な名前は除外

Phase 2: LLM ベース抽出（--llm フラグ）
  - Phase 1 で MENTIONS が付かなかったコンテンツに対して
  - Claude API で Entity/Concept を抽出
  - entity_linker.py で既存ノードに解決

Usage
-----
::

    # Phase 1: サブストリングマッチのみ（ドライラン）
    python scripts/entity_backfill.py --dry-run

    # Phase 1: 実行
    python scripts/entity_backfill.py

    # Phase 2: LLM抽出（未実装、将来用）
    python scripts/entity_backfill.py --llm --batch-size 20

"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Any

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "gomasuke"

# 短すぎる名前や一般的な英単語と衝突する Entity 名を除外
EXCLUDE_ENTITY_NAMES: frozenset[str] = frozenset({
    "with",  # 婚活アプリだが英単語 "with" と衝突
})

# 最小Entity名長（文字数）
MIN_ENTITY_NAME_LENGTH = 3


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class ContentNode:
    """Fact/Tip/Story ノードの情報."""

    node_id: str  # fact_id / tip_id / story_id
    label: str  # Fact / Tip / Story
    content: str
    genre: str
    id_field: str  # プロパティ名（fact_id, tip_id, story_id）


@dataclass
class EntityNode:
    """Entity ノードの情報."""

    entity_id: str
    entity_key: str
    name: str
    entity_type: str


@dataclass
class MentionMatch:
    """マッチ結果."""

    content: ContentNode
    entity: EntityNode
    match_type: str = "substring"


@dataclass
class BackfillStats:
    """バッチ実行統計."""

    total_content: int = 0
    already_has_mentions: int = 0
    target_content: int = 0
    matched_content: int = 0
    total_mentions_created: int = 0
    entities_matched: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Neo4j Client
# ---------------------------------------------------------------------------


class CreatorNeo4jClient:
    """Neo4j client for creator-neo4j."""

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
    ) -> None:
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self.driver.close()

    def query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    def write(self, cypher: str, **params: Any) -> dict[str, Any]:
        with self.driver.session() as session:
            result = session.run(cypher, **params)
            summary = result.consume()
            return {
                "relationships_created": summary.counters.relationships_created,
                "properties_set": summary.counters.properties_set,
            }


# ---------------------------------------------------------------------------
# Phase 1: Substring Matching
# ---------------------------------------------------------------------------


def load_entities(client: CreatorNeo4jClient) -> list[EntityNode]:
    """全 Entity ノードを取得."""
    results = client.query(
        "MATCH (e:Entity) "
        "RETURN e.entity_id AS entity_id, e.entity_key AS entity_key, "
        "e.name AS name, e.entity_type AS entity_type "
        "ORDER BY size(e.name) DESC"  # 長い名前を先にマッチ
    )
    entities = []
    for r in results:
        name = r["name"]
        if name in EXCLUDE_ENTITY_NAMES:
            logger.info("Excluded entity: %s (ambiguous)", name)
            continue
        if len(name) < MIN_ENTITY_NAME_LENGTH:
            logger.info("Excluded entity: %s (too short)", name)
            continue
        entities.append(
            EntityNode(
                entity_id=r["entity_id"],
                entity_key=r["entity_key"],
                name=name,
                entity_type=r["entity_type"],
            )
        )
    logger.info("Loaded %d entities (excluded %d)", len(entities), len(results) - len(entities))
    return entities


def load_content_without_mentions(client: CreatorNeo4jClient) -> list[ContentNode]:
    """MENTIONS リレーションがないコンテンツを取得."""
    content_nodes = []

    for label, id_field in [("Fact", "fact_id"), ("Tip", "tip_id"), ("Story", "story_id")]:
        results = client.query(
            f"MATCH (c:{label}) "
            f"WHERE NOT (c)<-[:MENTIONS]-() "
            f"AND c.content IS NOT NULL AND c.content <> '' "
            f"RETURN c.{id_field} AS node_id, c.content AS content, "
            f"c.genre AS genre",
        )
        for r in results:
            content_nodes.append(
                ContentNode(
                    node_id=r["node_id"],
                    label=label,
                    content=r["content"],
                    genre=r.get("genre", ""),
                    id_field=id_field,
                )
            )

    logger.info("Loaded %d content nodes without MENTIONS", len(content_nodes))
    return content_nodes


def find_substring_matches(
    content_nodes: list[ContentNode],
    entities: list[EntityNode],
) -> list[MentionMatch]:
    """Entity 名によるサブストリングマッチング."""
    matches: list[MentionMatch] = []
    matched_content_ids: set[str] = set()

    for content in content_nodes:
        text = content.content
        for entity in entities:
            if entity.name in text:
                matches.append(MentionMatch(content=content, entity=entity))
                matched_content_ids.add(content.node_id)

    logger.info(
        "Found %d matches across %d content nodes",
        len(matches),
        len(matched_content_ids),
    )
    return matches


def create_mentions_batch(
    client: CreatorNeo4jClient,
    matches: list[MentionMatch],
    dry_run: bool = False,
) -> BackfillStats:
    """MENTIONS リレーションをバッチ作成."""
    stats = BackfillStats()
    matched_content_ids: set[str] = set()

    for match in matches:
        c = match.content
        e = match.entity

        # 統計更新
        entity_name = e.name
        stats.entities_matched[entity_name] = stats.entities_matched.get(entity_name, 0) + 1
        matched_content_ids.add(c.node_id)

        if dry_run:
            logger.debug(
                "[DRY-RUN] MENTIONS: %s[%s] <- %s (%s)",
                c.label, c.node_id[:8], e.name, e.entity_type,
            )
            continue

        # MERGE で冪等に作成
        cypher = (
            f"MATCH (c:{c.label} {{{c.id_field}: $content_id}}) "
            f"MATCH (e:Entity {{entity_id: $entity_id}}) "
            f"MERGE (e)-[:MENTIONS]->(c) "
        )
        result = client.write(
            cypher,
            content_id=c.node_id,
            entity_id=e.entity_id,
        )
        stats.total_mentions_created += result["relationships_created"]

    stats.matched_content = len(matched_content_ids)
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Entity backfill for creator-neo4j")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="マッチ結果を表示するのみ（書き込みなし）",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="LLMベース抽出を実行（Phase 2、未実装）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="LLM抽出時のバッチサイズ（デフォルト: 20）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログ出力",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.llm:
        logger.error("LLM-based extraction (Phase 2) is not yet implemented")
        sys.exit(1)

    client = CreatorNeo4jClient()
    try:
        # 全体統計
        total_result = client.query(
            "MATCH (c) WHERE c:Fact OR c:Tip OR c:Story "
            "RETURN count(c) AS total"
        )
        total_content = total_result[0]["total"] if total_result else 0

        has_mentions_result = client.query(
            "MATCH (c)<-[:MENTIONS]-() "
            "WHERE c:Fact OR c:Tip OR c:Story "
            "RETURN count(DISTINCT c) AS cnt"
        )
        has_mentions = has_mentions_result[0]["cnt"] if has_mentions_result else 0

        # Phase 1: サブストリングマッチ
        logger.info("=== Phase 1: Substring Matching ===")
        entities = load_entities(client)
        content_nodes = load_content_without_mentions(client)

        matches = find_substring_matches(content_nodes, entities)

        if args.dry_run:
            logger.info("=== DRY-RUN Results ===")

        stats = create_mentions_batch(client, matches, dry_run=args.dry_run)
        stats.total_content = total_content
        stats.already_has_mentions = has_mentions
        stats.target_content = len(content_nodes)

        # 結果レポート
        print("\n" + "=" * 60)
        print("Entity Backfill Report")
        print("=" * 60)
        print(f"Total content nodes:        {stats.total_content}")
        print(f"Already has MENTIONS:       {stats.already_has_mentions}")
        print(f"Target (no MENTIONS):       {stats.target_content}")
        print(f"Matched by substring:       {stats.matched_content}")
        print(f"MENTIONS created:           {stats.total_mentions_created}")
        print(f"Mode:                       {'DRY-RUN' if args.dry_run else 'EXECUTED'}")
        print()
        print("Entity match distribution:")
        for name, count in sorted(
            stats.entities_matched.items(), key=lambda x: -x[1]
        ):
            print(f"  {name:30s}  {count:4d}")
        print()

        # MENTIONS/コンテンツ比率
        new_mentions = has_mentions_result[0]["cnt"] if has_mentions_result else 0
        if not args.dry_run:
            after_result = client.query(
                "MATCH ()-[m:MENTIONS]->() RETURN count(m) AS total"
            )
            total_m = after_result[0]["total"] if after_result else 0
            ratio = total_m / total_content if total_content > 0 else 0
            print(f"MENTIONS total (after):     {total_m}")
            print(f"MENTIONS/content ratio:     {ratio:.2f}")
        else:
            estimated_new = len(matches)
            estimated_total = 34 + estimated_new  # 既存34 + 新規
            ratio = estimated_total / total_content if total_content > 0 else 0
            print(f"MENTIONS estimated (after): {estimated_total}")
            print(f"MENTIONS/content ratio:     {ratio:.2f} (estimated)")

        print("=" * 60)

    finally:
        client.close()


if __name__ == "__main__":
    main()
