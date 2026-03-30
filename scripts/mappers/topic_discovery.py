"""mappers/topic_discovery.py — topic-discovery コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command topic-discovery`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "session_id": "topic-discovery-20260307",
        "generated_at": "2026-03-07T12:00:00+00:00",
        "suggestions": [
            {
                "category": "macro",
                "title": "...",
                "reason": "...",
                "scores": {"total": 85},
                "suggested_symbols": ["SPY", "QQQ"]
            }
        ],
        "search_insights": {
            "queries_executed": 3,
            "trends": [
                {"name": "Fed policy", "description": "..."}
            ]
        },
        "recommendation": "...",
        "parameters": {"no_search": false}
    }

Usage
-----
::

    from mappers.topic_discovery import TopicDiscoveryMapper

    mapper = TopicDiscoveryMapper()
    result = mapper.map(data)
"""

from __future__ import annotations

import logging
from typing import Any

from mappers.base import BaseMapper

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


class TopicDiscoveryMapper(BaseMapper):
    """topic-discovery コマンド専用マッパー。

    トピック提案セッションデータから Source・Topic・Claim・Entity・Fact ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: セッション1件につき1ノード（string-based ID = session_id）
    - Topics: suggestion の category ごとに1ノード（MERGE セマンティクス）
    - Claims: suggestion ごとに1ノード
    - Entities: suggested_symbols から生成
    - Facts: search_insights.trends から生成（no_search=True 時はスキップ）
    - ``batch_label`` は ``"topic-discovery"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """topic-discovery 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``session_id``, ``generated_at``, ``suggestions[]``,
            ``search_insights``, ``recommendation``, ``parameters`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``topics``, ``claims``, ``entities``, ``facts``,
            ``relations``, ``session_id``, ``batch_label`` を含む
            標準化されたマッパー結果。
        """
        from emit_research_queue import (  # type: ignore[import]
            TOPIC_DISCOVERY_CATEGORIES,
            _build_td_claim,
            _build_td_entities,
            _build_td_facts,
        )

        session_id = input_data.get("session_id", "")
        generated_at = input_data.get("generated_at", "")
        suggestions = input_data.get("suggestions", [])
        search_insights = input_data.get("search_insights") or {}
        recommendation = input_data.get("recommendation", "")
        no_search = (input_data.get("parameters") or {}).get("no_search", False)

        logger.debug(
            "TopicDiscoveryMapper.map: session_id=%s, suggestions=%d",
            session_id,
            len(suggestions),
        )

        # --- Source node (1 per session) ---
        top_score = max(
            (s.get("scores", {}).get("total", 0) for s in suggestions), default=0
        )
        search_queries_count = (
            search_insights.get("queries_executed", 0) if not no_search else 0
        )
        generated_at_date = generated_at[:10] if generated_at else ""

        sources: list[dict[str, Any]] = [
            {
                "source_id": session_id,
                "title": f"トピック提案セッション {generated_at_date}",
                "source_type": "report",
                "fetched_at": generated_at,
                "language": "ja",
                "command_source": "topic-discovery",
                "suggestion_count": len(suggestions),
                "top_score": top_score,
                "search_queries_count": search_queries_count,
                "recommendation": recommendation,
            }
        ]

        # Accumulators for nodes and relations
        seen_categories: set[str] = set()
        topics: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        tagged_rels: list[dict[str, str]] = []
        source_claim_rels: list[dict[str, str]] = []

        for suggestion in suggestions:
            category_key = suggestion.get("category", "")
            topic_id = f"content:{category_key}"

            # Topic node (MERGE semantics via dedup)
            if category_key and category_key not in seen_categories:
                seen_categories.add(category_key)
                topics.append(
                    {
                        "topic_id": topic_id,
                        "name": TOPIC_DISCOVERY_CATEGORIES.get(
                            category_key, category_key
                        ),
                        "category": "content_planning",
                        "topic_key": f"{TOPIC_DISCOVERY_CATEGORIES.get(category_key, category_key)}::content_planning",
                    }
                )
                tagged_rels.append(
                    {"from_id": session_id, "to_id": topic_id, "type": "TAGGED"}
                )

            # Claim node
            claim = _build_td_claim(suggestion, session_id, generated_at)
            claims.append(claim)
            source_claim_rels.append(
                {
                    "from_id": session_id,
                    "to_id": claim["claim_id"],
                    "type": "MAKES_CLAIM",
                }
            )
            if category_key:
                tagged_rels.append(
                    {
                        "from_id": claim["claim_id"],
                        "to_id": topic_id,
                        "type": "TAGGED",
                    }
                )

        # Entity nodes from suggested_symbols (delegated to helper)
        entities, _seen_tickers, claim_entity_rels = _build_td_entities(
            suggestions, claims
        )

        # Fact nodes from search_insights.trends (skip when no_search)
        if no_search:
            facts: list[dict[str, Any]] = []
            source_fact_rels: list[dict[str, str]] = []
        else:
            facts, source_fact_rels = _build_td_facts(
                search_insights, session_id, generated_at
            )

        logger.info(
            "TopicDiscoveryMapper.map: sources=%d, topics=%d, claims=%d, entities=%d, facts=%d",
            len(sources),
            len(topics),
            len(claims),
            len(entities),
            len(facts),
        )

        return self.build_result(
            input_data,
            "topic-discovery",
            sources=sources,
            topics=topics,
            claims=claims,
            entities=entities,
            facts=facts,
            relations={
                "tagged": tagged_rels,
                "source_claim": source_claim_rels,
                "claim_entity": claim_entity_rels,
                "source_fact": source_fact_rels,
            },
        )
