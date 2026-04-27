"""mappers/own_articles.py — own-articles コマンド向けプラグインマッパー。

株投資ラボのnote記事（articles/{category}/{slug}/{meta.yaml + revised_draft.md}）を
research-neo4j 用の graph-queue JSON に変換する。

Source は ``source_type='blog'`` ＋ ``command_source='own-articles'`` で識別。
authority_level は ``'blog'`` 固定（自前コンテンツ）。

入力フォーマット
---------------
::

    {
        "session_id": "own-articles-20260427",
        "articles": [
            {
                "article_id": "2026-04-04_institutional-10y-treasury-rotation",
                "category": "macro_economy",
                "topic": "...",
                "type": "column",
                "target_audience": "intermediate",
                "target_wordcount": 4000,
                "status": "published",
                "created_at": "2026-04-04",
                "updated_at": "...",
                "published_at": "...",
                "draft_url": "https://editor.note.com/...",
                "symbols": ["DGS10", ...],
                "keywords": ["...", ...],
                "draft_chars": 8421,
                "meta_path": "articles/.../meta.yaml"
            }
        ]
    }

Usage
-----
::

    from mappers.own_articles import OwnArticlesMapper

    mapper = OwnArticlesMapper()
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


_FALLBACK_DOMAIN = "note.com/kabushiki-labo"


class OwnArticlesMapper(BaseMapper):
    """own-articles コマンド専用マッパー。

    株投資ラボのnote記事を Source + Topic として graph-queue に変換する。
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """own-articles 入力を graph-queue コンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``articles[]`` と ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``topics``, ``session_id``, ``batch_label`` を含む結果。
        """
        from mappers.helpers import _make_source, generate_topic_id

        articles = input_data.get("articles", [])
        sources: list[dict[str, Any]] = []
        topics: list[dict[str, Any]] = []
        category_seen: set[str] = set()

        logger.debug("OwnArticlesMapper.map: processing %d articles", len(articles))

        for art in articles:
            article_id = art.get("article_id") or ""
            if not article_id:
                logger.warning("Skipping article without article_id: %s", art)
                continue

            category = art.get("category") or "uncategorized"
            topic_title = art.get("topic") or art.get("title") or article_id
            url = art.get("draft_url") or f"local://articles/{category}/{article_id}"
            published = (
                art.get("published_at")
                or art.get("updated_at")
                or art.get("created_at")
                or ""
            )

            extras: dict[str, Any] = {
                "source_type": "blog",
                "authority_level": "blog",
                "command_source": "own-articles",
                "domain": _FALLBACK_DOMAIN,
                "article_id": article_id,
                "category": category,
                "article_type": art.get("type") or "",
                "target_audience": art.get("target_audience") or "",
                "target_wordcount": art.get("target_wordcount") or 0,
                "status": art.get("status") or "unknown",
                "created_at": art.get("created_at") or "",
                "updated_at": art.get("updated_at") or "",
                "draft_chars": art.get("draft_chars") or 0,
                "meta_path": art.get("meta_path") or "",
            }

            symbols = art.get("symbols") or []
            if symbols:
                extras["symbols"] = list(symbols)

            keywords = art.get("keywords") or []
            if keywords:
                extras["keywords"] = list(keywords)

            source = _make_source(
                url=url,
                title=topic_title,
                published=published,
                **extras,
            )
            sources.append(source)

            article_topic_id = generate_topic_id(topic_title, category)
            topics.append(
                {
                    "topic_id": article_topic_id,
                    "name": topic_title,
                    "category": category,
                    "topic_key": f"article:{article_id}",
                    "source_id": source["source_id"],
                }
            )

            if category not in category_seen:
                category_seen.add(category)
                category_topic_id = generate_topic_id(category, "category")
                topics.append(
                    {
                        "topic_id": category_topic_id,
                        "name": category,
                        "category": "own-article-category",
                        "topic_key": f"category:{category}",
                    }
                )

        logger.info(
            "OwnArticlesMapper: produced %d sources, %d topics from %d articles",
            len(sources),
            len(topics),
            len(articles),
        )

        return self.build_result(
            input_data,
            batch_label="own-articles",
            sources=sources,
            topics=topics,
        )
