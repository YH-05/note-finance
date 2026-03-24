"""note-neo4j 向け 4層エンティティリンカー.

``scripts/entity_linker.py`` の 4層照合戦略を session_memory パッケージ用に
適応した実装。note-neo4j インスタンスの Entity / Decision ノードに対して
多段マッチングを行い、既存ノードへのリンクを試行する。

照合レイヤー
-----------
Layer 1: ``entity_key`` 完全一致（``Name::type`` 形式）
Layer 2: ``note_entity_fulltext`` + Levenshtein 類似度 (> 0.8)
Layer 3: ``note_alias_fulltext`` + ``ALIAS_OF`` リレーション辿り
Layer 4: e5-small embedding cosine 類似度 (> 0.8)

参照パターン
-----------
- 4層マッチング: ``scripts/entity_linker.py``
- Alias設計: ``docs/plan/SideBusiness/2026-03-22_entity-normalization.md``
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from session_memory._logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_ENTITY_FULLTEXT_INDEX = "note_entity_fulltext"
"""デフォルトの Entity fulltext インデックス名."""

_DEFAULT_ALIAS_FULLTEXT_INDEX = "note_alias_fulltext"
"""デフォルトの Alias fulltext インデックス名."""

_DEFAULT_LEVENSHTEIN_THRESHOLD = 0.8
"""Levenshtein 類似度の閾値."""

_DEFAULT_EMBEDDING_THRESHOLD = 0.8
"""Embedding cosine 類似度の閾値."""

_DEFAULT_MAX_CANDIDATES = 10
"""fulltext 検索の最大候補数."""

_DEFAULT_FULLTEXT_SCORE_THRESHOLD = 0.3
"""fulltext スコアの最小閾値."""

_ALLOWED_FULLTEXT_INDEXES: frozenset[str] = frozenset(
    {
        "note_entity_fulltext",
        "note_alias_fulltext",
    }
)
"""許可された fulltext インデックス名（Cypher インジェクション防止）."""


# ---------------------------------------------------------------------------
# 名前正規化
# ---------------------------------------------------------------------------


def normalize_name(name: str) -> str:
    """エンティティ名を正規化する.

    正規化ルール:
    1. 全角英数字を半角に変換（NFKC 正規化）
    2. 前後空白の除去・内部空白の圧縮
    3. 末尾 CJK 句読点の除去

    Parameters
    ----------
    name : str
        正規化前のエンティティ名

    Returns
    -------
    str
        正規化後のエンティティ名
    """
    if not name:
        return name

    # Rule 1: NFKC 正規化（全角→半角）
    normalized = unicodedata.normalize("NFKC", name)

    # Rule 2: 空白の正規化
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # Rule 3: 末尾 CJK 句読点の除去
    normalized = re.sub(r"[。、．，,;:]+$", "", normalized)

    return normalized


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinkerConfig:
    """リンカーの設定パラメータ.

    Parameters
    ----------
    entity_fulltext_index : str
        Entity ノードの fulltext インデックス名
    alias_fulltext_index : str
        Alias ノードの fulltext インデックス名
    levenshtein_threshold : float
        Levenshtein 類似度の閾値（Layer 2, 3 で使用）
    embedding_threshold : float
        Embedding cosine 類似度の閾値（Layer 4 で使用）
    max_candidates : int
        fulltext 検索の最大候補数
    fulltext_score_threshold : float
        fulltext スコアの最小閾値
    """

    entity_fulltext_index: str = _DEFAULT_ENTITY_FULLTEXT_INDEX
    alias_fulltext_index: str = _DEFAULT_ALIAS_FULLTEXT_INDEX
    levenshtein_threshold: float = _DEFAULT_LEVENSHTEIN_THRESHOLD
    embedding_threshold: float = _DEFAULT_EMBEDDING_THRESHOLD
    max_candidates: int = _DEFAULT_MAX_CANDIDATES
    fulltext_score_threshold: float = _DEFAULT_FULLTEXT_SCORE_THRESHOLD


@dataclass(frozen=True)
class LinkResult:
    """リンク結果の1件を表す不変データクラス.

    Parameters
    ----------
    name : str
        入力エンティティ名
    resolved : bool
        既存ノードにリンクできたかどうか
    match_layer : str
        マッチしたレイヤー（exact / fulltext / alias / embedding / new）
    matched_name : str | None
        マッチしたノードの名前（resolved=True の場合）
    node_id : str | None
        マッチしたノードの ID（resolved=True の場合）
    similarity : float | None
        類似度スコア（Layer 2-4 の場合）
    """

    name: str
    resolved: bool
    match_layer: str
    matched_name: str | None = None
    node_id: str | None = None
    similarity: float | None = None


# ---------------------------------------------------------------------------
# NoteLinker
# ---------------------------------------------------------------------------


class NoteLinker:
    """note-neo4j 向け 4層エンティティリンカー.

    Neo4j ドライバーを受け取り、Entity / Decision ノードに対して
    4層の照合戦略を実行する。

    Parameters
    ----------
    driver : Any
        Neo4j ドライバーインスタンス
    config : LinkerConfig
        リンカー設定
    embedder : Any | None
        SentenceTransformer モデルインスタンス（Layer 4 用）。
        None の場合、Layer 4 はスキップされる。

    Examples
    --------
    >>> from neo4j import GraphDatabase
    >>> driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "pass"))
    >>> linker = NoteLinker(driver=driver, config=LinkerConfig())
    >>> result = linker.link_entity("Python", "language")
    >>> print(result.resolved, result.match_layer)
    """

    def __init__(
        self,
        *,
        driver: Any,
        config: LinkerConfig | None = None,
        embedder: Any | None = None,
    ) -> None:
        """NoteLinker を初期化する.

        Parameters
        ----------
        driver : Any
            Neo4j ドライバーインスタンス
        config : LinkerConfig | None
            リンカー設定（None の場合はデフォルト値を使用）
        embedder : Any | None
            SentenceTransformer モデル（None の場合 Layer 4 スキップ）
        """
        self._driver = driver
        self._config = config or LinkerConfig()
        self._embedder = embedder
        logger.debug(
            "NoteLinker initialized",
            entity_fulltext_index=self._config.entity_fulltext_index,
            alias_fulltext_index=self._config.alias_fulltext_index,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_indexes(self) -> None:
        """必要な fulltext index が存在するか検証する.

        Raises
        ------
        RuntimeError
            必要な fulltext index が存在しない場合
        """
        required = {
            self._config.entity_fulltext_index,
            self._config.alias_fulltext_index,
        }

        existing = self._query(
            "SHOW INDEXES YIELD name WHERE type = 'FULLTEXT' RETURN name"
        )
        existing_names = {r["name"] for r in existing}

        missing = required - existing_names
        if missing:
            msg = (
                f"Required fulltext index(es) not found: {', '.join(sorted(missing))}. "
                f"Create them before using NoteLinker."
            )
            raise RuntimeError(msg)

        logger.info(
            "All required fulltext indexes verified",
            indexes=sorted(required),
        )

    def link_entity(self, name: str, entity_type: str) -> LinkResult:
        """エンティティを4層照合で既存ノードにリンクする.

        Parameters
        ----------
        name : str
            エンティティ名
        entity_type : str
            エンティティ種別

        Returns
        -------
        LinkResult
            リンク結果
        """
        normalized = normalize_name(name)
        entity_key = f"{normalized}::{entity_type}"

        logger.debug(
            "Linking entity",
            name=normalized,
            entity_type=entity_type,
            entity_key=entity_key,
        )

        # Layer 1: entity_key 完全一致
        result = self._layer1_exact(entity_key)
        if result is not None:
            logger.info(
                "Entity resolved (Layer 1: exact)",
                name=normalized,
                matched=result.matched_name,
            )
            return result

        # Layer 2: fulltext + Levenshtein
        result = self._layer2_fulltext(normalized)
        if result is not None:
            logger.info(
                "Entity resolved (Layer 2: fulltext)",
                name=normalized,
                matched=result.matched_name,
                similarity=result.similarity,
            )
            return result

        # Layer 3: alias fulltext + ALIAS_OF
        result = self._layer3_alias(normalized)
        if result is not None:
            logger.info(
                "Entity resolved (Layer 3: alias)",
                name=normalized,
                matched=result.matched_name,
                similarity=result.similarity,
            )
            return result

        # Layer 4: embedding cosine
        result = self._resolve_by_embedding(normalized)
        if result is not None:
            logger.info(
                "Entity resolved (Layer 4: embedding)",
                name=normalized,
                matched=result.matched_name,
                similarity=result.similarity,
            )
            return result

        logger.info("Entity unresolved (new)", name=normalized)
        return LinkResult(name=normalized, resolved=False, match_layer="new")

    def link_decision(self, summary: str) -> LinkResult:
        """Decision ノードへのリンクを試行する.

        既存の Decision ノードの summary に対して fulltext 検索を行い、
        マッチするものがあればリンクする。

        Parameters
        ----------
        summary : str
            決定事項の要約テキスト

        Returns
        -------
        LinkResult
            リンク結果
        """
        normalized = normalize_name(summary)
        logger.debug("Linking decision", summary=normalized)

        results = self._query(
            "MATCH (d:Decision) "
            "WHERE d.summary = $summary "
            "RETURN d.id AS id, d.summary AS summary",
            summary=normalized,
        )

        if results:
            row = results[0]
            logger.info(
                "Decision resolved",
                summary=normalized,
                matched_id=row["id"],
            )
            return LinkResult(
                name=normalized,
                resolved=True,
                match_layer="exact",
                matched_name=row["summary"],
                node_id=row["id"],
            )

        logger.info("Decision unresolved (new)", summary=normalized)
        return LinkResult(name=normalized, resolved=False, match_layer="new")

    def link_entities_batch(self, entities: list[dict[str, Any]]) -> list[LinkResult]:
        """複数エンティティを一括でリンクする.

        Parameters
        ----------
        entities : list[dict[str, Any]]
            エンティティ辞書のリスト。各辞書に ``name`` と ``entity_type`` が必要。

        Returns
        -------
        list[LinkResult]
            リンク結果のリスト（入力順序を保持）
        """
        if not entities:
            return []

        results: list[LinkResult] = []
        for entity in entities:
            name = entity["name"]
            entity_type = entity.get("entity_type", "unknown")
            result = self.link_entity(name, entity_type)
            results.append(result)

        resolved_count = sum(1 for r in results if r.resolved)
        logger.info(
            "Batch link completed",
            total=len(results),
            resolved=resolved_count,
            new=len(results) - resolved_count,
        )
        return results

    # ------------------------------------------------------------------
    # Layer 実装
    # ------------------------------------------------------------------

    def _layer1_exact(self, entity_key: str) -> LinkResult | None:
        """Layer 1: entity_key 完全一致.

        Parameters
        ----------
        entity_key : str
            ``Name::type`` 形式のエンティティキー

        Returns
        -------
        LinkResult | None
            マッチした場合は LinkResult、不一致の場合は None
        """
        results = self._query(
            "MATCH (n:Entity {entity_key: $key}) "
            "RETURN n.id AS id, n.name AS name, n.entity_key AS entity_key",
            key=entity_key,
        )
        if not results:
            return None

        row = results[0]
        return LinkResult(
            name=entity_key.split("::", maxsplit=1)[0],
            resolved=True,
            match_layer="exact",
            matched_name=row["name"],
            node_id=row["id"],
        )

    def _layer2_fulltext(self, name: str) -> LinkResult | None:
        """Layer 2: fulltext 検索 + Levenshtein 類似度フィルタ.

        Parameters
        ----------
        name : str
            正規化済みエンティティ名

        Returns
        -------
        LinkResult | None
            マッチした場合は LinkResult、不一致の場合は None
        """
        index_name = self._config.entity_fulltext_index
        if index_name not in _ALLOWED_FULLTEXT_INDEXES:
            msg = f"Disallowed fulltext index: {index_name!r}"
            raise ValueError(msg)
        results = self._query(
            f'CALL db.index.fulltext.queryNodes("{index_name}", $name) '
            f"YIELD node AS n, score "
            f"WHERE score > $ft_threshold "
            f"WITH n, score, "
            f"     apoc.text.levenshteinSimilarity(n.name, $name) AS lev "
            f"WHERE lev > $sim_threshold "
            f"RETURN n.id AS id, n.name AS name, "
            f"       n.entity_key AS entity_key, lev AS similarity "
            f"ORDER BY lev DESC LIMIT $max_candidates",
            name=name,
            ft_threshold=self._config.fulltext_score_threshold,
            sim_threshold=self._config.levenshtein_threshold,
            max_candidates=self._config.max_candidates,
        )
        if not results:
            return None

        row = results[0]
        return LinkResult(
            name=name,
            resolved=True,
            match_layer="fulltext",
            matched_name=row["name"],
            node_id=row["id"],
            similarity=row["similarity"],
        )

    def _layer3_alias(self, name: str) -> LinkResult | None:
        """Layer 3: alias fulltext 検索 + ALIAS_OF リレーション辿り.

        Parameters
        ----------
        name : str
            正規化済みエンティティ名

        Returns
        -------
        LinkResult | None
            マッチした場合は LinkResult、不一致の場合は None
        """
        index_name = self._config.alias_fulltext_index
        if index_name not in _ALLOWED_FULLTEXT_INDEXES:
            msg = f"Disallowed fulltext index: {index_name!r}"
            raise ValueError(msg)
        results = self._query(
            f'CALL db.index.fulltext.queryNodes("{index_name}", $name) '
            f"YIELD node AS alias, score "
            f"WHERE score > $ft_threshold "
            f"MATCH (alias)-[:ALIAS_OF]->(n:Entity) "
            f"WITH n, alias, score, "
            f"     apoc.text.levenshteinSimilarity(alias.value, $name) AS lev "
            f"WHERE lev > $sim_threshold "
            f"RETURN n.id AS id, n.name AS name, "
            f"       n.entity_key AS entity_key, "
            f"       alias.value AS matched_alias, lev AS similarity "
            f"ORDER BY lev DESC LIMIT $max_candidates",
            name=name,
            ft_threshold=self._config.fulltext_score_threshold,
            sim_threshold=self._config.levenshtein_threshold,
            max_candidates=self._config.max_candidates,
        )
        if not results:
            return None

        row = results[0]
        return LinkResult(
            name=name,
            resolved=True,
            match_layer="alias",
            matched_name=row["name"],
            node_id=row["id"],
            similarity=row["similarity"],
        )

    def _resolve_by_embedding(self, name: str) -> LinkResult | None:
        """Layer 4: embedding cosine 類似度.

        SentenceTransformer モデルで名前をエンコードし、
        Neo4j 内の embedding ベクトルと cosine 類似度を比較する。

        Parameters
        ----------
        name : str
            正規化済みエンティティ名

        Returns
        -------
        LinkResult | None
            マッチした場合は LinkResult、None の場合はスキップ
        """
        if self._embedder is None:
            return None

        try:
            target_emb = self._embedder.encode(name, normalize_embeddings=True)
        except Exception:
            logger.warning(
                "Embedding encode failed, skipping Layer 4",
                name=name,
                exc_info=True,
            )
            return None

        # Vector Index による検索を試行
        result = self._embedding_vector_index(target_emb)
        if result is not None:
            return result

        # フォールバック: ブルートフォース cosine
        return self._embedding_brute_force(name, target_emb)

    def _embedding_vector_index(self, target_emb: Any) -> LinkResult | None:
        """Neo4j Vector Index による embedding 検索.

        Parameters
        ----------
        target_emb : Any
            エンコード済みの embedding ベクトル

        Returns
        -------
        LinkResult | None
            マッチした場合は LinkResult、不一致の場合は None
        """
        try:
            results = self._query(
                'CALL db.index.vector.queryNodes("entity_embedding_idx", $top_k, $embedding) '
                "YIELD node AS n, score "
                "WHERE score >= $threshold "
                "RETURN n.id AS id, n.name AS name, score AS similarity",
                top_k=5,
                embedding=target_emb.tolist(),
                threshold=self._config.embedding_threshold,
            )
            if results:
                row = results[0]
                return LinkResult(
                    name="",
                    resolved=True,
                    match_layer="embedding",
                    matched_name=row["name"],
                    node_id=row["id"],
                    similarity=round(row["similarity"], 4),
                )
        except Exception:
            logger.debug(
                "Vector index not available, falling back to brute-force",
                exc_info=True,
            )

        return None

    def _embedding_brute_force(self, name: str, target_emb: Any) -> LinkResult | None:
        """ブルートフォースの embedding cosine 比較.

        Parameters
        ----------
        name : str
            正規化済みエンティティ名
        target_emb : Any
            エンコード済みの embedding ベクトル

        Returns
        -------
        LinkResult | None
            マッチした場合は LinkResult、不一致の場合は None
        """
        try:
            import numpy as np
        except ImportError:
            logger.warning("numpy not installed, skipping brute-force embedding")
            return None

        candidates = self._query(
            "MATCH (n:Entity) WHERE n.embedding IS NOT NULL "
            "RETURN n.id AS id, n.name AS name, n.embedding AS emb "
            "LIMIT 5000"
        )
        if not candidates:
            return None

        embs = np.array([c["emb"] for c in candidates], dtype=np.float32)
        sims = embs @ target_emb
        best_idx = int(np.argmax(sims))
        best_sim = float(sims[best_idx])

        if best_sim >= self._config.embedding_threshold:
            row = candidates[best_idx]
            return LinkResult(
                name=name,
                resolved=True,
                match_layer="embedding",
                matched_name=row["name"],
                node_id=row["id"],
                similarity=round(best_sim, 4),
            )

        return None

    # ------------------------------------------------------------------
    # Neo4j ヘルパー
    # ------------------------------------------------------------------

    def _query(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        """読み取り専用 Cypher クエリを実行する.

        ``session.execute_read`` を使用し、トランザクション制御と
        リトライを自動化する。

        Parameters
        ----------
        cypher : str
            Cypher クエリ文字列
        **params : Any
            クエリパラメータ

        Returns
        -------
        list[dict[str, Any]]
            クエリ結果の辞書リスト
        """

        def _run(tx: Any) -> list[dict[str, Any]]:
            return [dict(r) for r in tx.run(cypher, **params)]

        with self._driver.session() as session:
            return session.execute_read(_run)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "LinkResult",
    "LinkerConfig",
    "NoteLinker",
    "normalize_name",
]
