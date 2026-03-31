"""mappers/reddit_topics.py — reddit-finance-topics コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command reddit-finance-topics`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "groups": {
            "group_key": {
                "topics": [
                    {
                        "name": "...",
                        "url": "https://reddit.com/...",
                        "title": "...",
                        "subreddit": "r/investing",
                        "score": 245,
                        "created_at": "2026-01-01T00:00:00+00:00"
                    }
                ]
            }
        },
        "session_id": "reddit-topics-20260307"
    }

または::

    {
        "topics": [...],
        "session_id": "reddit-topics-20260307"
    }

Usage
-----
::

    from mappers.reddit_topics import RedditTopicsMapper

    mapper = RedditTopicsMapper()
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


class RedditTopicsMapper(BaseMapper):
    """reddit-finance-topics コマンド専用マッパー。

    Reddit ディスカッショントピックデータから Source と Topic ノードを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - ``groups.{key}.topics[]`` をサポート（ネスト形式）
    - フォールバックとして ``topics[]`` も受け付ける（フラット形式）
    - 各トピックは Source（Reddit投稿）と Topic ノードの両方を生成
    - ``batch_label`` は ``"reddit"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """reddit-finance-topics 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``groups.{key}.topics[]`` または ``topics[]``、``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``topics``, ``session_id``, ``batch_label`` を含む
            標準化されたマッパー結果。
        """
        from mappers.helpers import (
            _make_source,
            generate_topic_id,
        )

        input_topics: list[dict[str, Any]] = []

        # Handle nested topics in groups
        groups = input_data.get("groups", {})
        if groups:
            for group_data in groups.values():
                input_topics.extend(group_data.get("topics", []))
        else:
            # Fallback to root topics
            input_topics = input_data.get("topics", [])

        sources: list[dict[str, Any]] = []
        topics: list[dict[str, Any]] = []

        logger.debug("RedditTopicsMapper.map: processing %d topics", len(input_topics))

        for topic in input_topics:
            # Use title as name if name is missing (Reddit posts have title)
            name = topic.get("name", topic.get("title", ""))
            url = topic.get("url", "")

            # Create topic
            topics.append(
                {
                    "topic_id": generate_topic_id(name, "reddit"),
                    "name": name,
                    "category": "reddit",
                    "subreddit": topic.get("subreddit", ""),
                    "topic_key": f"{name}::reddit",
                }
            )

            # Create source from Reddit post
            if url:
                sources.append(
                    _make_source(
                        url,
                        title=topic.get("title", ""),
                        published=topic.get("created_at", ""),
                        subreddit=topic.get("subreddit", ""),
                        score=topic.get("score", 0),
                    )
                )

        logger.info(
            "RedditTopicsMapper.map: sources=%d, topics=%d",
            len(sources),
            len(topics),
        )

        return self.build_result(
            input_data,
            "reddit",
            sources=sources,
            topics=topics,
        )
