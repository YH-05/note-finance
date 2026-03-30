"""mappers/pdf_extraction.py — pdf-extraction コマンドのプラグインマッパー。

``BaseMapper`` を継承し、``map()`` メソッドに
``--command pdf-extraction`` および ``--command pdf-archive`` 固有のロジックのみを実装する。

PDF チャンク処理は ``ChunkProcessingContext`` を用いたクロスチャンク共有状態管理を行う。
各チャンクの処理を ``_process_chunk`` に委譲し、全チャンク処理後に
SUPERSEDES チェーン・AUTHORED_BY リレーション・NEXT_PERIOD チェーン・
TREND エッジを構築する。

入力フォーマット
---------------
::

    {
        "source_hash": "sha256hex...",
        "publisher": "発行体名",
        "chunks": [
            {
                "chunk_index": 0,
                "section_title": "Introduction",
                "content": "...",
                "entities": [...],
                "facts": [...],
                "claims": [...],
                "financial_data": [...],
                "stances": [...],
                "questions": [...]
            }
        ],
        "session_id": "..."
    }

Usage
-----
::

    from mappers.pdf_extraction import PdfExtractionMapper

    mapper = PdfExtractionMapper()
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


class PdfExtractionMapper(BaseMapper):
    """pdf-extraction / pdf-archive コマンド専用マッパー。

    各 PDF チャンクをクロスチャンク共有状態（``ChunkProcessingContext``）で
    逐次処理し、全ノードタイプとリレーションタイプを生成する。
    共通処理（``build_result``）は ``BaseMapper`` に委譲する。

    Notes
    -----
    - Source: ``pdf:{source_hash}`` をキーとする単一ノード
    - Chunk: チャンクインデックスで識別される
    - Entity: クロスチャンク重複排除
    - Fact / Claim: チャンクから抽出
    - FinancialDataPoint / FiscalPeriod: 財務データポイント
    - Stance: アナリスト見解
    - Question: 問いかけ
    - SUPERSEDES チェーン: Stance ノード間に自動構築
    - AUTHORED_BY: ``publisher`` フィールドから構築
    - NEXT_PERIOD チェーン: FiscalPeriod ノード間に構築
    - TREND エッジ: FinancialDataPoint ノード間に構築
    """

    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """pdf-extraction 入力データをグラフキューコンポーネントにマップする。

        ``chunks[]`` を逐次処理し、クロスチャンク共有状態を維持しながら
        全ノード・リレーションを構築する。

        Parameters
        ----------
        input_data : dict[str, Any]
            ``source_hash``, ``chunks[]``, ``publisher``（オプション）,
            ``session_id`` を含む入力データ。

        Returns
        -------
        dict[str, Any]
            ``sources``, ``entities``, ``facts``, ``claims``, ``chunks``,
            ``financial_datapoints``, ``fiscal_periods``, ``authors``,
            ``stances``, ``questions``, および全 21 リレーションタイプを含む
            標準化された結果。
        """
        # 遅延インポートで循環依存を回避
        # AIDEV-NOTE: ChunkProcessingContext は emit_research_queue と mappers.base の両方で定義されているが、
        # _process_chunk は emit_research_queue.ChunkProcessingContext を期待するため、ここで直接インポートする。
        from emit_research_queue import (  # type: ignore[import]
            ChunkProcessingContext,
            _NODE_KEYS,
            _build_authored_by_rels,
            _build_next_period_chain,
            _build_supersedes_chain,
            _build_trend_edges,
            _empty_rels,
            _extend_rels,
            _make_source,
            _process_chunk,
            generate_source_id,
        )

        source_hash = input_data.get("source_hash", "")
        source_id = generate_source_id(f"pdf:{source_hash}")
        publisher = input_data.get("publisher", "")
        sources = [
            _make_source(f"pdf:{source_hash}", source_type="pdf", publisher=publisher)
        ]

        ctx = ChunkProcessingContext()
        nodes: dict[str, list[Any]] = {k: [] for k in _NODE_KEYS}
        rels = _empty_rels()

        chunks = input_data.get("chunks", [])
        logger.debug("PdfExtractionMapper.map: processing %d chunks", len(chunks))

        for chunk in chunks:
            chunk_result = _process_chunk(
                chunk,
                source_hash,
                source_id,
                ctx,
            )
            for k in _NODE_KEYS:
                nodes[k].extend(chunk_result[k])
            _extend_rels(rels, chunk_result["rels"])

        # 全チャンク処理後に SUPERSEDES チェーンを構築
        supersedes = _build_supersedes_chain(nodes["stances"])
        rels["supersedes"].extend(supersedes)

        # Source.publisher から AUTHORED_BY を構築 (Phase 2 Step A-1)
        if publisher:
            new_authors, authored_by = _build_authored_by_rels(
                source_id, publisher, ctx.seen_author_keys, ctx.author_name_to_id
            )
            nodes["authors"].extend(new_authors)
            rels["authored_by"].extend(authored_by)

        # NEXT_PERIOD チェーンを構築 (Wave 3)
        next_period = _build_next_period_chain(nodes["periods"])
        rels["next_period"].extend(next_period)

        # TREND エッジを構築 (Wave 3)
        trend = _build_trend_edges(
            nodes["datapoints"], nodes["periods"], rels["for_period"]
        )
        rels["trend"].extend(trend)

        logger.info(
            "PdfExtractionMapper.map: chunks=%d, entities=%d, facts=%d, claims=%d",
            len(nodes["chunks"]),
            len(nodes["entities"]),
            len(nodes["facts"]),
            len(nodes["claims"]),
        )

        return self.build_result(
            input_data,
            "pdf-extraction",
            sources=sources,
            entities=nodes["entities"],
            facts=nodes["facts"],
            claims=nodes["claims"],
            chunks=nodes["chunks"],
            financial_datapoints=nodes["datapoints"],
            fiscal_periods=nodes["periods"],
            authors=nodes["authors"],
            stances=nodes["stances"],
            questions=nodes["questions"],
            relations=rels,
        )
