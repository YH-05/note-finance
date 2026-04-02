"""BaseMapper: 共通マッパーロジックの抽象基底クラス。

emit_research_queue.py の共通ヘルパー（ChunkProcessingContext・
_build_entity_nodes・_build_fact_nodes・_build_claim_nodes・
_build_chunk_nodes・_process_chunk・_apply_classification_layer）を
抽出し、再利用可能な抽象クラスとして提供する。

各プラグインマッパーはこのクラスを継承し、``map()`` を実装する。

Usage
-----
::

    class MyMapper(BaseMapper):
        def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
            ...

    mapper = MyMapper()
    result = mapper.map(data)
"""

from __future__ import annotations

import functools
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import yaml

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ontology loader (replaces direct knowledge-graph-schema.yaml reads)
# ---------------------------------------------------------------------------

import sys as _sys

# Ensure scripts/ is on the import path for ontology_loader
_scripts_dir = str(Path(__file__).parent.parent)
if _scripts_dir not in _sys.path:
    _sys.path.insert(0, _scripts_dir)

from ontology_loader import load_consolidation_mapping as _ol_load_consolidation_mapping  # noqa: E402, I001
from ontology_loader import load_multilabel_types as _ol_load_multilabel_types  # noqa: E402
from ontology_loader import load_source_type_normalization as _ol_load_source_type_normalization  # noqa: E402

# Internal mapping for backward-compatible multilabel_types structure
_CANONICAL_TO_LABEL_INTERNAL: dict[str, str] = {
    "company": "Company",
    "technology": "Technology",
    "organization": "Organization",
    "person": "Person",
    "index": "MarketIndex",
    "indicator": "Indicator",
    "instrument": "Instrument",
    "commodity": "Commodity",
    "country": "Country",
    "sector": "Sector",
    "concept": "Concept",
    "regulation": "Regulation",
    "broker": "Broker",
    "product": "Product",
}


# ---------------------------------------------------------------------------
# Cross-chunk shared state
# ---------------------------------------------------------------------------


@dataclass
class ChunkProcessingContext:
    """Cross-chunk shared state for ``_process_chunk``.

    Attributes
    ----------
    seen_entity_keys : set[str]
        Already-seen ``name::entity_type`` keys for entity deduplication.
        Deprecated: v4.0 では entity_key 廃止。seen_entity_names を使用すること。
    seen_entity_names : set[str]
        Already-seen normalized entity names for entity deduplication (v4.0).
    entity_name_to_id : dict[str, str]
        Mapping from entity name to entity ID.
    entity_name_to_ticker : dict[str, str]
        Mapping from entity name to ticker symbol.
    seen_period_ids : set[str]
        Already-seen period IDs for FiscalPeriod deduplication.
    seen_author_keys : set[str]
        Already-seen author keys for Author deduplication.
    author_name_to_id : dict[str, str]
        Mapping from author name to author ID.
    """

    seen_entity_keys: set[str] = field(default_factory=set)  # Deprecated: v4.0
    seen_entity_names: set[str] = field(default_factory=set)  # v4.0: name-based dedup
    entity_name_to_id: dict[str, str] = field(default_factory=dict)
    entity_name_to_ticker: dict[str, str] = field(default_factory=dict)
    seen_period_ids: set[str] = field(default_factory=set)
    seen_author_keys: set[str] = field(default_factory=set)
    author_name_to_id: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# BaseMapper
# ---------------------------------------------------------------------------


class BaseMapper(ABC):
    """共通マッパーロジックを提供する抽象基底クラス。

    サブクラスは ``map()`` を実装し、各コマンド固有のロジックを記述する。
    共通ロジック（YAML SSoT 読み込み・バリデーション・ノードビルダー等）は
    このクラスで提供される。

    Class Attributes
    ----------------
    _yaml_cache : dict[str, Any] | None
        YAML SSoT キャッシュ（起動時1回のみ読み込む）。
    """

    _yaml_cache: ClassVar[dict[str, Any] | None] = None

    # ------------------------------------------------------------------
    # Ontology SSoT (via ontology_loader)
    # ------------------------------------------------------------------

    @classmethod
    def load_yaml_ssot(cls) -> dict[str, Any]:
        """ontology_loader 経由でスキーマデータをキャッシュして返す。

        後方互換のため ``load_yaml_ssot`` の名前を維持するが、内部では
        ``ontology_loader`` の各関数から取得したデータを旧形式互換の dict に
        組み立てて返す。

        Returns
        -------
        dict[str, Any]
            旧 knowledge-graph-schema.yaml 互換の dict。
        """
        if cls._yaml_cache is not None:
            logger.debug("load_yaml_ssot: returning cached schema")
            return cls._yaml_cache

        consolidation = _ol_load_consolidation_mapping()
        multilabel_types = _ol_load_multilabel_types()
        source_norm = _ol_load_source_type_normalization()

        # Build backward-compatible structure
        data: dict[str, Any] = {
            "version": "3.0",
            "consolidation_rules": {
                "entity_type": {
                    "mapping": consolidation,
                }
            },
            "enum_validations": {
                "entity_type": {
                    "values": multilabel_types,
                },
                "source_type": {
                    "values": list({v for v in source_norm.values()}),
                },
            },
            "source_type_normalization": {
                "mapping": source_norm,
            },
            "multilabel_types": {
                "entity_labels": {
                    "labels": {
                        _CANONICAL_TO_LABEL_INTERNAL.get(k, k.title()): {"name_ja": ""}
                        for k in multilabel_types
                    }
                }
            },
        }

        cls._yaml_cache = data
        logger.info("load_yaml_ssot: loaded schema via ontology_loader")
        return data

    @classmethod
    def _get_consolidation_rules(cls) -> dict[str, str]:
        """ontology_loader から entity_type consolidation_rules を取得する。

        Returns
        -------
        dict[str, str]
            生 entity_type → 正規型マッピング。
        """
        return _ol_load_consolidation_mapping()

    @classmethod
    def _get_source_type_normalization(cls) -> dict[str, str]:
        """ontology_loader から source_type_normalization マッピングを取得する。

        Returns
        -------
        dict[str, str]
            生 source_type → 正規 source_type マッピング。
        """
        return _ol_load_source_type_normalization()

    @classmethod
    def _get_entity_type_enum(cls) -> frozenset[str]:
        """ontology_loader から有効な entity_type の frozenset を取得する。

        Returns
        -------
        frozenset[str]
            14種の正規 entity_type 値。
        """
        return frozenset(_ol_load_multilabel_types())

    @classmethod
    def _get_source_type_enum(cls) -> frozenset[str]:
        """ontology_loader から有効な source_type の frozenset を取得する。

        Returns
        -------
        frozenset[str]
            5種の正規 source_type 値。
        """
        norm = _ol_load_source_type_normalization()
        return frozenset(norm.values())

    # ------------------------------------------------------------------
    # Schema validation
    # ------------------------------------------------------------------

    @classmethod
    def validate_schema(
        cls,
        *,
        entity_type: str | None = None,
        source_type: str | None = None,
    ) -> None:
        """entity_type / source_type の値を YAML SSoT に基づいてバリデートする。

        Parameters
        ----------
        entity_type : str | None
            検証する entity_type 値。``None`` の場合はスキップ。
        source_type : str | None
            検証する source_type 値。``None`` の場合はスキップ。

        Raises
        ------
        ValueError
            不正な entity_type または source_type が渡された場合。
        """
        if entity_type is not None:
            valid_types = cls._get_entity_type_enum()
            if entity_type not in valid_types:
                raise ValueError(
                    f"Invalid entity_type: {entity_type!r}. "
                    f"Allowed: {sorted(valid_types)}"
                )
            logger.debug("validate_schema: entity_type=%r OK", entity_type)

        if source_type is not None:
            valid_types = cls._get_source_type_enum()
            if source_type not in valid_types:
                raise ValueError(
                    f"Invalid source_type: {source_type!r}. "
                    f"Allowed: {sorted(valid_types)}"
                )
            logger.debug("validate_schema: source_type=%r OK", source_type)

    # ------------------------------------------------------------------
    # build_result (formerly _mapped_result)
    # ------------------------------------------------------------------

    @classmethod
    def build_result(
        cls,
        data: dict[str, Any],
        batch_label: str,
        *,
        sources: list[dict[str, Any]] | None = None,
        topics: list[dict[str, Any]] | None = None,
        claims: list[dict[str, Any]] | None = None,
        facts: list[dict[str, Any]] | None = None,
        entities: list[dict[str, Any]] | None = None,
        chunks: list[dict[str, Any]] | None = None,
        financial_datapoints: list[dict[str, Any]] | None = None,
        fiscal_periods: list[dict[str, Any]] | None = None,
        authors: list[dict[str, Any]] | None = None,
        stances: list[dict[str, Any]] | None = None,
        questions: list[dict[str, Any]] | None = None,
        relations: dict[str, Any] | None = None,
        classification_nodes: list[dict[str, Any]] | None = None,
        classification_rels: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """標準マッパー結果 dict を生成する（旧 ``_mapped_result``）。

        Parameters
        ----------
        data : dict[str, Any]
            元の入力データ（``session_id`` の抽出に使用）。
        batch_label : str
            このバッチのラベル。
        sources, topics, claims, facts, entities, chunks,
        financial_datapoints, fiscal_periods, authors, stances,
        questions : list[dict] | None
            ノードリスト（デフォルト: 空リスト）。
        relations : dict | None
            リレーション dict（デフォルト: 空 dict）。
        classification_nodes : list[dict] | None
            分類ノードリスト（デフォルト: 空リスト）。
        classification_rels : list[dict] | None
            分類リレーションリスト（デフォルト: 空リスト）。

        Returns
        -------
        dict[str, Any]
            全キーを含む標準化された結果 dict。
        """
        return {
            "session_id": data.get("session_id", ""),
            "batch_label": batch_label,
            "sources": sources or [],
            "claims": claims or [],
            "facts": facts or [],
            "topics": topics or [],
            "entities": entities or [],
            "chunks": chunks or [],
            "financial_datapoints": financial_datapoints or [],
            "fiscal_periods": fiscal_periods or [],
            "authors": authors or [],
            "stances": stances or [],
            "questions": questions or [],
            "relations": relations or {},
            "classification_nodes": classification_nodes or [],
            "classification_rels": classification_rels or [],
        }

    # ------------------------------------------------------------------
    # Multi-label generation
    # ------------------------------------------------------------------

    @classmethod
    def get_extra_labels(cls, canonical_entity_type: str) -> list[str]:
        """正規 entity_type から multilabel_types の extra_labels を返す。

        ontology_loader 経由で取得した multilabel_types と内部マッピングを
        参照し、``canonical_entity_type`` に対応するラベルリストを返す。

        Parameters
        ----------
        canonical_entity_type : str
            14種の正規 entity_type 値（例: ``"company"``）。

        Returns
        -------
        list[str]
            付与すべき追加ラベルリスト（例: ``["Company"]``）。
            マッピングが見つからない場合は空リスト。
        """
        valid_types = frozenset(_ol_load_multilabel_types())
        label = _CANONICAL_TO_LABEL_INTERNAL.get(canonical_entity_type)
        if label and canonical_entity_type in valid_types:
            return [label]
        return []

    # ------------------------------------------------------------------
    # Node builders
    # ------------------------------------------------------------------

    @classmethod
    def build_entity_nodes(
        cls,
        chunk: dict[str, Any],
        seen_entity_keys: set[str],
        entity_name_to_id: dict[str, str],
        entity_name_to_ticker: dict[str, str],
        *,
        generate_entity_id_fn: Any,
    ) -> list[dict[str, Any]]:
        """チャンクから Entity ノードを生成する（旧 ``_build_entity_nodes``）。

        v4.0 変更: entity_key ("name::type") 廃止。name を重複排除キーとして使用。
        neo4j_label フィールドを entity_type から決定してノードに付与する。

        *seen_entity_keys*, *entity_name_to_id*, *entity_name_to_ticker*
        をインプレースに更新しながら重複排除を行う。

        Parameters
        ----------
        chunk : dict[str, Any]
            ``entities[]`` を含む生チャンクデータ。
        seen_entity_keys : set[str]
            Deprecated: v4.0 では seen_entity_names を使用。後方互換のため残す。
        entity_name_to_id : dict[str, str]
            名前→IDルックアップ（インプレース更新）。
        entity_name_to_ticker : dict[str, str]
            名前→ティッカールックアップ（インプレース更新）。
        generate_entity_id_fn : Callable[[str, str], str]
            エンティティID生成関数。

        Returns
        -------
        list[dict[str, Any]]
            新規作成されたエンティティノード dict のリスト。
            v4.0: ``entity_key`` フィールドなし、``neo4j_label`` フィールドあり。
        """
        from ontology_loader import ENTITY_TYPE_TO_LABEL, load_consolidation_mapping  # noqa: PLC0415

        consolidation_map = load_consolidation_mapping()
        entities: list[dict[str, Any]] = []

        for entity in chunk.get("entities", []):
            name = entity.get("name", "")
            entity_type = (
                entity.get("entity_type", "").lower()
                if entity.get("entity_type")
                else "concept"
            )

            # v4.0: name で重複排除（entity_key 廃止）
            if name in entity_name_to_id:
                continue

            # entity_type → canonical → Neo4j ラベル
            canonical_type = consolidation_map.get(entity_type, entity_type)
            neo4j_label = ENTITY_TYPE_TO_LABEL.get(canonical_type, "Concept")

            eid = generate_entity_id_fn(name, entity_type)
            entities.append(
                {
                    "entity_id": eid,
                    "name": name,
                    "entity_type": entity_type,
                    "neo4j_label": neo4j_label,
                    "ticker": entity.get("ticker"),
                    # v4.0: entity_key フィールドは生成しない
                }
            )
            entity_name_to_id[name] = eid
            # 後方互換: seen_entity_keys にも追加（呼び出し元が参照する可能性）
            seen_entity_keys.add(name)
            if entity.get("ticker"):
                entity_name_to_ticker[name] = entity["ticker"]

        logger.debug("build_entity_nodes: created %d entities", len(entities))
        return entities

    @classmethod
    def build_fact_nodes(
        cls,
        chunk: dict[str, Any],
        source_id: str,
        chunk_id: str,
        entity_name_to_id: dict[str, str],
        *,
        generate_fact_id_fn: Any,
        fact_type_meta: dict[str, Any],
        resolve_entity_rels_fn: Any,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, str]],
        list[dict[str, str]],
        list[dict[str, str]],
    ]:
        """チャンクから Fact ノードとリレーションを生成する（旧 ``_build_fact_nodes``）。

        Parameters
        ----------
        chunk : dict[str, Any]
            ``facts[]`` を含む生チャンクデータ。
        source_id : str
            親 Source ノードのID。
        chunk_id : str
            親 Chunk ノードのID。
        entity_name_to_id : dict[str, str]
            エンティティ解決用の名前→IDルックアップ。
        generate_fact_id_fn : Callable[[str], str]
            Fact ID 生成関数。
        fact_type_meta : dict[str, Any]
            有効な fact_type 値の辞書（バリデーション用）。
        resolve_entity_rels_fn : Callable
            エンティティリレーション解決関数。

        Returns
        -------
        tuple
            4タプル: (facts, source_fact_rels, extracted_from_fact_rels,
            fact_entity_rels)。
        """
        facts: list[dict[str, Any]] = []
        source_fact_rels: list[dict[str, str]] = []
        extracted_from_fact_rels: list[dict[str, str]] = []
        fact_entity_rels: list[dict[str, str]] = []

        for fact in chunk.get("facts", []):
            content = fact.get("content", "")
            fact_id = generate_fact_id_fn(content)
            raw_ft = fact.get("fact_type", "")
            validated_ft = raw_ft if raw_ft in fact_type_meta else "empirical"
            facts.append(
                {
                    "fact_id": fact_id,
                    "content": content,
                    "source_id": source_id,
                    "fact_type": validated_ft,
                    "as_of_date": fact.get("as_of_date"),
                }
            )
            source_fact_rels.append(
                {"from_id": source_id, "to_id": fact_id, "type": "STATES_FACT"}
            )
            extracted_from_fact_rels.append(
                {"from_id": fact_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
            )
            about = fact.get("about_entities", [])
            if not about:
                about = [
                    e.get("name", "")
                    for e in chunk.get("entities", [])
                    if e.get("name")
                ]
            fact_entity_rels.extend(
                resolve_entity_rels_fn(about, fact_id, "RELATES_TO", entity_name_to_id)
            )

        logger.debug("build_fact_nodes: created %d facts", len(facts))
        return facts, source_fact_rels, extracted_from_fact_rels, fact_entity_rels

    @classmethod
    def build_claim_nodes(
        cls,
        chunk: dict[str, Any],
        source_id: str,
        chunk_id: str,
        entity_name_to_id: dict[str, str],
        *,
        generate_claim_id_fn: Any,
        resolve_entity_rels_fn: Any,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, str]],
        list[dict[str, str]],
        list[dict[str, str]],
    ]:
        """チャンクから Claim ノードとリレーションを生成する（旧 ``_build_claim_nodes``）。

        Parameters
        ----------
        chunk : dict[str, Any]
            ``claims[]`` を含む生チャンクデータ。
        source_id : str
            親 Source ノードのID。
        chunk_id : str
            親 Chunk ノードのID。
        entity_name_to_id : dict[str, str]
            エンティティ解決用の名前→IDルックアップ。
        generate_claim_id_fn : Callable[[str], str]
            Claim ID 生成関数。
        resolve_entity_rels_fn : Callable
            エンティティリレーション解決関数。

        Returns
        -------
        tuple
            4タプル: (claims, source_claim_rels, extracted_from_claim_rels,
            claim_entity_rels)。
        """
        claims: list[dict[str, Any]] = []
        source_claim_rels: list[dict[str, str]] = []
        extracted_from_claim_rels: list[dict[str, str]] = []
        claim_entity_rels: list[dict[str, str]] = []

        for claim in chunk.get("claims", []):
            content = claim.get("content", "")
            claim_id = generate_claim_id_fn(content)
            claims.append(
                {
                    "claim_id": claim_id,
                    "content": content,
                    "source_id": source_id,
                    "category": "pdf-claim",
                    "claim_type": claim.get("claim_type", ""),
                    "sentiment": claim.get("sentiment"),
                    "magnitude": claim.get("magnitude"),
                    "target_price": claim.get("target_price"),
                    "rating": claim.get("rating"),
                    "time_horizon": claim.get("time_horizon"),
                }
            )
            source_claim_rels.append(
                {"from_id": source_id, "to_id": claim_id, "type": "MAKES_CLAIM"}
            )
            extracted_from_claim_rels.append(
                {"from_id": claim_id, "to_id": chunk_id, "type": "EXTRACTED_FROM"}
            )
            claim_entity_rels.extend(
                resolve_entity_rels_fn(
                    claim.get("about_entities", []),
                    claim_id,
                    "ABOUT",
                    entity_name_to_id,
                )
            )

        logger.debug("build_claim_nodes: created %d claims", len(claims))
        return claims, source_claim_rels, extracted_from_claim_rels, claim_entity_rels

    @classmethod
    def build_chunk_nodes(
        cls,
        chunk: dict[str, Any],
        source_hash: str,
        source_id: str,
        *,
        generate_chunk_id_fn: Any,
    ) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
        """Chunk ノードと CONTAINS_CHUNK リレーションを生成する（旧 ``_build_chunk_nodes``）。

        Parameters
        ----------
        chunk : dict[str, Any]
            生チャンクデータ。
        source_hash : str
            ソースドキュメントの SHA-256 ハッシュ。
        source_id : str
            親 Source ノードのID。
        generate_chunk_id_fn : Callable[[str, int], str]
            チャンクID生成関数。

        Returns
        -------
        tuple[dict[str, Any], str, list[dict[str, str]]]
            3タプル: (chunk_node, chunk_id, contains_chunk_rels)。
        """
        chunk_index = chunk.get("chunk_index", 0)
        chunk_id = generate_chunk_id_fn(source_hash, chunk_index)

        chunk_node = {
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "section_title": chunk.get("section_title"),
            "content": chunk.get("content", ""),
        }

        contains_chunk_rel = {
            "from_id": source_id,
            "to_id": chunk_id,
            "type": "CONTAINS_CHUNK",
        }

        logger.debug("build_chunk_nodes: chunk_id=%s", chunk_id)
        return chunk_node, chunk_id, [contains_chunk_rel]

    # ------------------------------------------------------------------
    # postprocess (formerly _apply_classification_layer)
    # ------------------------------------------------------------------

    @classmethod
    def _postprocess_sources(
        cls,
        mapped: dict[str, Any],
        command: str,
        source_type_normalization: dict[str, str],
        trust_level_normalization: dict[str, str],
        trust_level_meta: dict[str, Any],
        add_node: Any,
        add_rel: Any,
        make_source_type_node_fn: Any,
        make_domain_node_fn: Any,
        make_trust_level_node_fn: Any,
        make_language_node_fn: Any,
        make_pipeline_node_fn: Any,
        make_classification_rel_fn: Any,
        extract_url_domain_fn: Any,
    ) -> None:
        """Sources → SourceType / Domain / TrustLevel / Language / Pipeline。"""
        for source in mapped.get("sources", []):
            source_id = source.get("source_id", "")
            if not source_id:
                continue

            raw_st = source.get("source_type", "")
            if raw_st:
                canonical_st = source_type_normalization.get(raw_st, raw_st)
                add_node(make_source_type_node_fn(canonical_st))
                add_rel(
                    make_classification_rel_fn(
                        "IS_SOURCE_TYPE", source_id, canonical_st
                    )
                )

            domain_name = extract_url_domain_fn(source.get("url", ""))
            if domain_name:
                add_node(
                    make_domain_node_fn(domain_name, base_url=f"https://{domain_name}")
                )
                add_rel(
                    make_classification_rel_fn("FROM_DOMAIN", source_id, domain_name)
                )

            raw_auth = source.get("authority_level", "")
            if raw_auth:
                canonical_tl = trust_level_normalization.get(raw_auth, raw_auth)
                if canonical_tl in trust_level_meta:
                    add_node(make_trust_level_node_fn(canonical_tl))
                    add_rel(
                        make_classification_rel_fn("RATED_AS", source_id, canonical_tl)
                    )
                else:
                    logger.debug(
                        "Unknown authority_level, skipping TrustLevel: %s", raw_auth
                    )

            language = source.get("language", "")
            if language:
                add_node(make_language_node_fn(language))
                add_rel(make_classification_rel_fn("IN_LANGUAGE", source_id, language))

            add_node(make_pipeline_node_fn(command))
            add_rel(make_classification_rel_fn("INGESTED_VIA", source_id, command))

    @classmethod
    def _postprocess_entities(
        cls,
        mapped: dict[str, Any],
        entity_type_consolidation: dict[str, str],
        add_node: Any,
        add_rel: Any,
        make_entity_type_node_fn: Any,
        make_identifier_node_fn: Any,
        make_classification_rel_fn: Any,
    ) -> None:
        """Entities → EntityType / Identifier。"""
        for entity in mapped.get("entities", []):
            entity_id = entity.get("entity_id", "")
            entity_key = entity.get("entity_key", "")
            ref_id = entity_key or entity_id
            if not ref_id:
                continue

            raw_etype = entity.get("entity_type", "")
            if raw_etype:
                canonical_etype = entity_type_consolidation.get(raw_etype, raw_etype)
                add_node(make_entity_type_node_fn(canonical_etype))
                add_rel(make_classification_rel_fn("IS_TYPE", ref_id, canonical_etype))

            ticker = entity.get("ticker")
            if ticker:
                id_key = f"ticker:{ticker}"
                add_node(
                    make_identifier_node_fn(
                        id_key, id_type="ticker", value=ticker, scheme="exchange"
                    )
                )
                add_rel(make_classification_rel_fn("HAS_IDENTIFIER", ref_id, id_key))

    @classmethod
    def _postprocess_facts_claims(
        cls,
        mapped: dict[str, Any],
        add_node: Any,
        add_rel: Any,
        make_fact_type_node_fn: Any,
        make_claim_type_node_fn: Any,
        make_classification_rel_fn: Any,
    ) -> None:
        """Facts → FactType / Claims → ClaimType。"""
        for fact in mapped.get("facts", []):
            fact_id = fact.get("fact_id", "")
            if not fact_id:
                continue
            raw_ft = fact.get("fact_type", "")
            if raw_ft:
                add_node(make_fact_type_node_fn(raw_ft))
                add_rel(make_classification_rel_fn("IS_FACT_TYPE", fact_id, raw_ft))

        for claim in mapped.get("claims", []):
            claim_id = claim.get("claim_id", "")
            if not claim_id:
                continue
            raw_ct = claim.get("claim_type", "")
            if raw_ct:
                add_node(make_claim_type_node_fn(raw_ct))
                add_rel(make_classification_rel_fn("IS_CLAIM_TYPE", claim_id, raw_ct))

    @classmethod
    def _postprocess_datapoints(
        cls,
        mapped: dict[str, Any],
        datapoint_type_map: dict[bool, str],
        add_node: Any,
        add_rel: Any,
        make_unit_of_measure_node_fn: Any,
        make_datapoint_type_node_fn: Any,
        make_classification_rel_fn: Any,
    ) -> None:
        """FinancialDataPoints → UnitOfMeasure / DataPointType。"""
        for dp in mapped.get("financial_datapoints", []):
            dp_id = dp.get("datapoint_id", "")
            if not dp_id:
                continue

            unit = dp.get("unit", "")
            if unit:
                add_node(
                    make_unit_of_measure_node_fn(
                        unit, name=unit, dimension="monetary_value"
                    )
                )
                add_rel(make_classification_rel_fn("IN_UNIT", dp_id, unit))

            dp_currency = dp.get("currency")
            if dp_currency and dp_currency != unit:
                add_node(
                    make_unit_of_measure_node_fn(
                        dp_currency, name=dp_currency, dimension="currency"
                    )
                )
                add_rel(make_classification_rel_fn("IN_UNIT", dp_id, dp_currency))

            is_estimate = dp.get("is_estimate")
            if is_estimate is not None:
                dp_type_name = datapoint_type_map.get(bool(is_estimate), "actual")
                add_node(make_datapoint_type_node_fn(dp_type_name))
                add_rel(
                    make_classification_rel_fn("IS_DATAPOINT_TYPE", dp_id, dp_type_name)
                )

    @classmethod
    def _postprocess_authors(
        cls,
        mapped: dict[str, Any],
        add_node: Any,
        add_rel: Any,
        make_author_type_node_fn: Any,
        make_classification_rel_fn: Any,
    ) -> None:
        """Authors → AuthorType / AFFILIATED_WITH。"""
        entities = mapped.get("entities", [])
        for author in mapped.get("authors", []):
            author_id = author.get("author_id", "")
            if not author_id:
                continue
            raw_at = author.get("author_type", "")
            if raw_at:
                add_node(make_author_type_node_fn(raw_at))
                add_rel(make_classification_rel_fn("IS_AUTHOR_TYPE", author_id, raw_at))
            org_name = author.get("organization")
            if org_name:
                entity_match = next(
                    (
                        ent.get("entity_key") or ent.get("entity_id")
                        for ent in entities
                        if ent.get("name") == org_name
                    ),
                    None,
                )
                if entity_match:
                    add_rel(
                        make_classification_rel_fn(
                            "AFFILIATED_WITH", author_id, entity_match
                        )
                    )

    @classmethod
    def _postprocess_topics(
        cls,
        mapped: dict[str, Any],
        concept_category_map: dict[str, str],
        add_node: Any,
        add_rel: Any,
        make_concept_category_node_fn: Any,
        make_classification_rel_fn: Any,
    ) -> None:
        """Topics → ConceptCategory (IS_CATEGORY)。"""
        for topic in mapped.get("topics", []):
            topic_id = topic.get("topic_id", "")
            topic_key = topic.get("topic_key", "")
            ref_id = topic_key or topic_id
            if not ref_id:
                continue
            raw_cat = topic.get("category", "")
            if raw_cat:
                concept_name = concept_category_map.get(raw_cat)
                if concept_name:
                    add_node(make_concept_category_node_fn(concept_name))
                    add_rel(
                        make_classification_rel_fn("IS_CATEGORY", ref_id, concept_name)
                    )
                else:
                    logger.debug(
                        "No ConceptCategory mapping for topic.category=%r", raw_cat
                    )

    @classmethod
    def _postprocess_stances(
        cls,
        mapped: dict[str, Any],
        add_node: Any,
        add_rel: Any,
        make_unit_of_measure_node_fn: Any,
        make_classification_rel_fn: Any,
    ) -> None:
        """Stances → UnitOfMeasure (currency from target_price_currency)。"""
        for stance in mapped.get("stances", []):
            stance_id = stance.get("stance_id", "")
            if not stance_id:
                continue
            currency = stance.get("target_price_currency")
            if currency:
                add_node(
                    make_unit_of_measure_node_fn(
                        currency, name=currency, dimension="currency"
                    )
                )
                add_rel(make_classification_rel_fn("IN_UNIT", stance_id, currency))

    @classmethod
    def postprocess(
        cls,
        mapped: dict[str, Any],
        command: str,
        *,
        entity_type_consolidation: dict[str, str],
        source_type_normalization: dict[str, str],
        concept_category_map: dict[str, str],
        trust_level_normalization: dict[str, str],
        trust_level_meta: dict[str, Any],
        datapoint_type_map: dict[bool, str],
        v3_strip_flat_props: bool = False,
        make_source_type_node_fn: Any,
        make_domain_node_fn: Any,
        make_trust_level_node_fn: Any,
        make_language_node_fn: Any,
        make_pipeline_node_fn: Any,
        make_entity_type_node_fn: Any,
        make_identifier_node_fn: Any,
        make_fact_type_node_fn: Any,
        make_claim_type_node_fn: Any,
        make_unit_of_measure_node_fn: Any,
        make_datapoint_type_node_fn: Any,
        make_author_type_node_fn: Any,
        make_concept_category_node_fn: Any,
        make_classification_rel_fn: Any,
        extract_url_domain_fn: Any,
        strip_flat_props_fn: Any | None = None,
    ) -> None:
        """v3.0 分類ノード後処理をインプレースで適用する（旧 ``_apply_classification_layer``）。

        Source・Entity・Fact・Claim・FinancialDataPoint・Author・
        Topic・Stance を走査して分類ノードとリレーションを生成し、
        ``mapped["classification_nodes"]`` と
        ``mapped["classification_rels"]`` に追加する。

        Parameters
        ----------
        mapped : dict[str, Any]
            マッパー関数の出力（インプレースに変更される）。
        command : str
            ソースコマンド名（Pipeline ノード生成に使用）。
        entity_type_consolidation : dict[str, str]
            生 entity_type → 正規型マッピング。
        source_type_normalization : dict[str, str]
            生 source_type → 正規型マッピング。
        concept_category_map : dict[str, str]
            topic.category → ConceptCategory 名マッピング。
        trust_level_normalization : dict[str, str]
            authority_level → TrustLevel 正規化マッピング。
        trust_level_meta : dict[str, Any]
            有効な TrustLevel 値のメタデータ辞書。
        datapoint_type_map : dict[bool, str]
            is_estimate → DataPointType 名マッピング。
        v3_strip_flat_props : bool
            True の場合、後処理後にフラット分類プロパティを削除する。
        make_*_fn : Callable
            各種分類ノード・リレーション生成関数群。
        extract_url_domain_fn : Callable[[str], str]
            URLからドメインを抽出する関数。
        strip_flat_props_fn : Callable | None
            フラットプロパティ削除関数（v3_strip_flat_props が True の場合に使用）。
        """
        classification_nodes: list[dict[str, Any]] = []
        classification_rels: list[dict[str, str]] = []
        seen_nodes: set[tuple[str, str]] = set()

        def _add_node(node: dict[str, Any]) -> None:
            key = (node["label"], node["key_value"])
            if key not in seen_nodes:
                seen_nodes.add(key)
                classification_nodes.append(node)

        def _add_rel(rel: dict[str, str]) -> None:
            classification_rels.append(rel)

        cls._postprocess_sources(
            mapped,
            command,
            source_type_normalization,
            trust_level_normalization,
            trust_level_meta,
            _add_node,
            _add_rel,
            make_source_type_node_fn,
            make_domain_node_fn,
            make_trust_level_node_fn,
            make_language_node_fn,
            make_pipeline_node_fn,
            make_classification_rel_fn,
            extract_url_domain_fn,
        )
        cls._postprocess_entities(
            mapped,
            entity_type_consolidation,
            _add_node,
            _add_rel,
            make_entity_type_node_fn,
            make_identifier_node_fn,
            make_classification_rel_fn,
        )
        cls._postprocess_facts_claims(
            mapped,
            _add_node,
            _add_rel,
            make_fact_type_node_fn,
            make_claim_type_node_fn,
            make_classification_rel_fn,
        )
        cls._postprocess_datapoints(
            mapped,
            datapoint_type_map,
            _add_node,
            _add_rel,
            make_unit_of_measure_node_fn,
            make_datapoint_type_node_fn,
            make_classification_rel_fn,
        )
        cls._postprocess_authors(
            mapped,
            _add_node,
            _add_rel,
            make_author_type_node_fn,
            make_classification_rel_fn,
        )
        cls._postprocess_topics(
            mapped,
            concept_category_map,
            _add_node,
            _add_rel,
            make_concept_category_node_fn,
            make_classification_rel_fn,
        )
        cls._postprocess_stances(
            mapped,
            _add_node,
            _add_rel,
            make_unit_of_measure_node_fn,
            make_classification_rel_fn,
        )

        if v3_strip_flat_props and strip_flat_props_fn is not None:
            strip_flat_props_fn(mapped)

        mapped["classification_nodes"] = classification_nodes
        mapped["classification_rels"] = classification_rels

        logger.info(
            "postprocess: %d classification_nodes, %d classification_rels",
            len(classification_nodes),
            len(classification_rels),
        )

    # ------------------------------------------------------------------
    # Abstract method
    # ------------------------------------------------------------------

    @abstractmethod
    def map(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """入力データをグラフキューコンポーネントにマッピングする。

        Parameters
        ----------
        input_data : dict[str, Any]
            コマンド固有の入力データ。

        Returns
        -------
        dict[str, Any]
            ``build_result()`` と同一フォーマットのマッパー結果 dict。
        """
        ...
