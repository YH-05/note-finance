"""mappers/finance_news.py — finance-news-workflow コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command finance-news-workflow`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "news": [
            {
                "url": "https://...",
                "title": "...",
                "summary": "...",
                "published": "2026-01-01T00:00:00+00:00",
                "source": "cnbc",
                "category": "markets",
                "tags": ["inflation"],
                "author": "John Smith",
                "content": "Full article body..."
            }
        ],
        "collected_at": "2026-01-01T00:00:00+00:00",
        "total_count": 1
    }

Usage
-----
::

    from mappers.finance_news import FinanceNewsMapper

    mapper = FinanceNewsMapper()
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


class FinanceNewsMapper(BaseMapper):
    """finance-news-workflow コマンド専用マッパー。

    ``news[]`` から Source, Claim, Chunk, Topic, Author ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: 各記事1件につき1ノード
    - Claim: ``summary`` が存在する場合のみ生成
    - Chunk: ``content`` (本文) が存在する場合のみ生成
    - Topic: ``category`` および ``tags`` から生成（重複排除済み）
    - Author: ``author`` が存在する場合のみ生成（重複排除済み）
    - ``batch_label`` を ``category`` として使用（省略時は空文字）
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """finance-news-workflow 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``news[]``, ``collected_at``, ``total_count`` を含む入力データ。
            scrape_finance_news.py の出力形式に直接対応する。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``claims``, ``chunks``, ``topics``, ``authors``,
            ``relations`` を含む標準化されたマッパー結果。
        """
        # 遅延インポートで循環依存を回避
        from mappers.helpers import (
            _make_source,
            generate_claim_id,
            generate_chunk_id,
            generate_source_id,
            generate_topic_id,
            resolve_category,
        )

        articles = input_data.get("news", [])
        sources: list[dict[str, Any]] = []
        claims: list[dict[str, Any]] = []
        chunks: list[dict[str, Any]] = []
        topics: list[dict[str, Any]] = []
        authors: list[dict[str, Any]] = []

        # Relations
        tagged_rels: list[dict[str, str]] = []
        contains_chunk_rels: list[dict[str, str]] = []
        authored_by_rels: list[dict[str, str]] = []

        # Dedup tracking
        seen_topic_ids: set[str] = set()
        seen_author_names: set[str] = set()

        logger.debug("FinanceNewsMapper.map: processing %d articles", len(articles))

        batch_category = resolve_category(input_data.get("batch_label", ""))

        for article in articles:
            url = article.get("url", "")
            source_id = generate_source_id(url)

            sources.append(
                _make_source(
                    url,
                    title=article.get("title", ""),
                    published=article.get("published", ""),
                    feed_source=article.get("source", ""),
                    source_type="news",
                )
            )

            # Claim from summary
            summary = article.get("summary", "")
            if summary:
                claims.append(
                    {
                        "claim_id": generate_claim_id(summary),
                        "content": summary,
                        "source_id": source_id,
                        "category": batch_category,
                    }
                )

            # Chunk from content (full article body)
            content = article.get("content", "")
            if content:
                chunk_id = generate_chunk_id(source_id, 0)
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "source_id": source_id,
                        "content": content,
                        "index": 0,
                    }
                )
                contains_chunk_rels.append(
                    {"from_id": source_id, "to_id": chunk_id}
                )

            # Topics from category and tags
            topic_names: list[str] = []
            category = article.get("category", "")
            if category:
                topic_names.append(category)
            for tag in article.get("tags", []):
                if tag and tag not in topic_names:
                    topic_names.append(tag)

            for topic_name in topic_names:
                topic_id = generate_topic_id(topic_name, batch_category)
                if topic_id not in seen_topic_ids:
                    seen_topic_ids.add(topic_id)
                    topics.append(
                        {
                            "topic_key": topic_id,
                            "name": topic_name,
                            "category": batch_category,
                        }
                    )
                tagged_rels.append({"from_id": source_id, "to_id": topic_id})

            # Author
            author_name = article.get("author", "")
            if author_name:
                from pdf_pipeline.services.id_generator import generate_author_id

                author_id = generate_author_id(author_name, "journalist")
                if author_name not in seen_author_names:
                    seen_author_names.add(author_name)
                    authors.append(
                        {
                            "author_id": author_id,
                            "name": author_name,
                            "author_type": "journalist",
                        }
                    )
                authored_by_rels.append(
                    {"from_id": source_id, "to_id": author_id}
                )

        logger.info(
            "FinanceNewsMapper.map: sources=%d, claims=%d, chunks=%d, "
            "topics=%d, authors=%d",
            len(sources),
            len(claims),
            len(chunks),
            len(topics),
            len(authors),
        )

        relations: dict[str, list[dict[str, str]]] = {}
        if tagged_rels:
            relations["tagged"] = tagged_rels
        if contains_chunk_rels:
            relations["contains_chunk"] = contains_chunk_rels
        if authored_by_rels:
            relations["authored_by"] = authored_by_rels

        return self.build_result(
            input_data,
            input_data.get("batch_label", ""),
            sources=sources,
            claims=claims,
            chunks=chunks,
            topics=topics,
            authors=authors,
            relations=relations,
        )
