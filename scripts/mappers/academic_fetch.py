"""mappers/academic_fetch.py — academic-fetch コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command academic-fetch`` 固有のロジックのみを実装する。

入力フォーマット
---------------
::

    {
        "papers": [
            {
                "arxiv_id": "2401.00001",
                "title": "...",
                "authors": ["Author A", "Author B"],
                "abstract": "...",
                "url": "https://arxiv.org/abs/2401.00001",
                "published": "2024-01-01T00:00:00+00:00"
            }
        ],
        "existing_source_ids": ["src-001", "src-002"]
    }

Usage
-----
::

    from mappers.academic_fetch import AcademicFetchMapper

    mapper = AcademicFetchMapper()
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


class AcademicFetchMapper(BaseMapper):
    """academic-fetch コマンド専用マッパー。

    arXiv 論文メタデータから Source・Author ノードと関連リレーションを生成する。
    実際のマッピングロジックは ``academic.mapper.map_academic_papers`` に委譲する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: 論文ごとに1ノード
    - Authors: 著者ごとに1ノード（AUTHORED_BY リレーション付き）
    - ``batch_label`` は ``"academic-fetch"`` 固定
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """academic-fetch 入力データをグラフキューコンポーネントにマップする。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``papers[]``, ``existing_source_ids[]`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``authors``, ``relations``, ``session_id``, ``batch_label``
            を含む標準化されたマッパー結果。
        """
        from academic.mapper import map_academic_papers  # type: ignore[import]

        logger.debug(
            "AcademicFetchMapper.map: papers=%d",
            len(input_data.get("papers", [])),
        )

        mapped = map_academic_papers(input_data)

        sources = mapped.get("sources", [])
        authors = mapped.get("authors", [])
        relations = mapped.get("relations", {})

        logger.info(
            "AcademicFetchMapper.map: sources=%d, authors=%d",
            len(sources),
            len(authors),
        )

        return self.build_result(
            input_data,
            "academic-fetch",
            sources=sources,
            authors=authors,
            relations=relations,
        )
