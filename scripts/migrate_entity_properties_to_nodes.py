#!/usr/bin/env python3
"""Entity プロパティのノード分離移行スクリプト。

以下の4つの移行フェーズを実行する:

1. **Ticker ノード作成**: Entity.ticker プロパティ → Ticker ノード + HAS_TICKER リレーション（120件想定）
2. **Country ノード作成**: Entity.country プロパティ → Country ノード + IN_COUNTRY リレーション（68件想定）
   英語名・日本語名の正規化も適用する。
3. **Sector 正規化**: 既存 Sector ノードを GICS 11 種に統合する（21種→11種）
4. **Industry ノード作成**: IN_INDUSTRY リレーション確認・Entity と Sector の紐付け整備
5. **Identifier 統合**: Identifier(ticker種別) 144件を Ticker ノードに統合する

Usage
-----
::

    # 対象件数確認（DB への書き込みなし）
    uv run python scripts/migrate_entity_properties_to_nodes.py --dry-run

    # 本番実行
    uv run python scripts/migrate_entity_properties_to_nodes.py

    # 特定フェーズのみ実行
    uv run python scripts/migrate_entity_properties_to_nodes.py --phase ticker
    uv run python scripts/migrate_entity_properties_to_nodes.py --phase country
    uv run python scripts/migrate_entity_properties_to_nodes.py --phase sector
    uv run python scripts/migrate_entity_properties_to_nodes.py --phase industry
    uv run python scripts/migrate_entity_properties_to_nodes.py --phase identifier

    # 接続先を指定
    uv run python scripts/migrate_entity_properties_to_nodes.py --neo4j-uri bolt://localhost:7688

設計方針
--------
- 冪等実行可能: MERGE を使用し、既存ノード・リレーションは重複作成しない
- --dry-run フラグで書き込みをスキップして件数のみ確認
- neo4j-write-rules.md 例外適用: 本スクリプトは移行専用（ユーザー明示承認済み）
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)

try:
    from utils_core.logging.config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_NEO4J_URI = "bolt://localhost:7688"
_DEFAULT_NEO4J_USER = "neo4j"

# GICS 11セクター正規マッピング (生値 → GICS正規名)
# 21種のバラバラなSectorノード名をGICS 11種に統一
GICS_SECTOR_NORMALIZATION: dict[str, str] = {
    # Information Technology
    "technology": "Information Technology",
    "info_tech": "Information Technology",
    "information_technology": "Information Technology",
    "it": "Information Technology",
    "tech": "Information Technology",
    # Communication Services
    "telecom": "Communication Services",
    "communication": "Communication Services",
    "communication_services": "Communication Services",
    "telecommunications": "Communication Services",
    # Health Care
    "healthcare": "Health Care",
    "health_care": "Health Care",
    "health": "Health Care",
    # Consumer Discretionary
    "consumer_discretionary": "Consumer Discretionary",
    "consumer": "Consumer Discretionary",
    "discretionary": "Consumer Discretionary",
    # Consumer Staples
    "consumer_staples": "Consumer Staples",
    "staples": "Consumer Staples",
    # Energy
    "energy": "Energy",
    # Financials
    "financials": "Financials",
    "financial": "Financials",
    "finance": "Financials",
    "banking": "Financials",
    # Industrials
    "industrials": "Industrials",
    "industrial": "Industrials",
    # Materials
    "materials": "Materials",
    "material": "Materials",
    # Real Estate
    "real_estate": "Real Estate",
    "realestate": "Real Estate",
    # Utilities
    "utilities": "Utilities",
    "utility": "Utilities",
    # Identity mapping (GICSがそのまま正しい場合)
    "Information Technology": "Information Technology",
    "Communication Services": "Communication Services",
    "Health Care": "Health Care",
    "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples": "Consumer Staples",
    "Energy": "Energy",
    "Financials": "Financials",
    "Industrials": "Industrials",
    "Materials": "Materials",
    "Real Estate": "Real Estate",
    "Utilities": "Utilities",
}
"""生 Sector 名 → GICS 11セクター正規名へのマッピング。"""

# 11種のGICS正規セクター名
GICS_SECTORS: frozenset[str] = frozenset(
    [
        "Information Technology",
        "Communication Services",
        "Health Care",
        "Consumer Discretionary",
        "Consumer Staples",
        "Energy",
        "Financials",
        "Industrials",
        "Materials",
        "Real Estate",
        "Utilities",
    ]
)
"""GICS 11セクターの正規名セット。"""

# 国名の英日対応マッピング（正規化用）
# Entity.country に格納されているバラバラな表記 → (英語正規名, 日本語名)
COUNTRY_NORMALIZATION: dict[str, tuple[str, str]] = {
    # Japan
    "japan": ("Japan", "日本"),
    "japan, inc": ("Japan", "日本"),
    "japanese": ("Japan", "日本"),
    "日本": ("Japan", "日本"),
    # United States
    "us": ("United States", "米国"),
    "usa": ("United States", "米国"),
    "united states": ("United States", "米国"),
    "united states of america": ("United States", "米国"),
    "america": ("United States", "米国"),
    "米国": ("United States", "米国"),
    "アメリカ": ("United States", "米国"),
    # China
    "china": ("China", "中国"),
    "prc": ("China", "中国"),
    "中国": ("China", "中国"),
    # Indonesia
    "indonesia": ("Indonesia", "インドネシア"),
    "インドネシア": ("Indonesia", "インドネシア"),
    # India
    "india": ("India", "インド"),
    "インド": ("India", "インド"),
    # South Korea
    "south korea": ("South Korea", "韓国"),
    "korea": ("South Korea", "韓国"),
    "韓国": ("South Korea", "韓国"),
    # Singapore
    "singapore": ("Singapore", "シンガポール"),
    "シンガポール": ("Singapore", "シンガポール"),
    # Hong Kong
    "hong kong": ("Hong Kong", "香港"),
    "香港": ("Hong Kong", "香港"),
    # Taiwan
    "taiwan": ("Taiwan", "台湾"),
    "台湾": ("Taiwan", "台湾"),
    # Germany
    "germany": ("Germany", "ドイツ"),
    "ドイツ": ("Germany", "ドイツ"),
    # United Kingdom
    "uk": ("United Kingdom", "英国"),
    "united kingdom": ("United Kingdom", "英国"),
    "britain": ("United Kingdom", "英国"),
    "英国": ("United Kingdom", "英国"),
    # France
    "france": ("France", "フランス"),
    "フランス": ("France", "フランス"),
    # Australia
    "australia": ("Australia", "オーストラリア"),
    "オーストラリア": ("Australia", "オーストラリア"),
    # Canada
    "canada": ("Canada", "カナダ"),
    "カナダ": ("Canada", "カナダ"),
    # Netherlands
    "netherlands": ("Netherlands", "オランダ"),
    "オランダ": ("Netherlands", "オランダ"),
    # Switzerland
    "switzerland": ("Switzerland", "スイス"),
    "スイス": ("Switzerland", "スイス"),
    # Brazil
    "brazil": ("Brazil", "ブラジル"),
    "ブラジル": ("Brazil", "ブラジル"),
    # Malaysia
    "malaysia": ("Malaysia", "マレーシア"),
    "マレーシア": ("Malaysia", "マレーシア"),
    # Philippines
    "philippines": ("Philippines", "フィリピン"),
    "フィリピン": ("Philippines", "フィリピン"),
    # Thailand
    "thailand": ("Thailand", "タイ"),
    "タイ": ("Thailand", "タイ"),
    # Vietnam
    "vietnam": ("Vietnam", "ベトナム"),
    "ベトナム": ("Vietnam", "ベトナム"),
    # Sweden
    "sweden": ("Sweden", "スウェーデン"),
    "スウェーデン": ("Sweden", "スウェーデン"),
    # Denmark
    "denmark": ("Denmark", "デンマーク"),
    "デンマーク": ("Denmark", "デンマーク"),
    # Norway
    "norway": ("Norway", "ノルウェー"),
    "ノルウェー": ("Norway", "ノルウェー"),
    # Finland
    "finland": ("Finland", "フィンランド"),
    "フィンランド": ("Finland", "フィンランド"),
    # Mexico
    "mexico": ("Mexico", "メキシコ"),
    "メキシコ": ("Mexico", "メキシコ"),
    # Russia
    "russia": ("Russia", "ロシア"),
    "ロシア": ("Russia", "ロシア"),
    # Saudi Arabia
    "saudi arabia": ("Saudi Arabia", "サウジアラビア"),
    "サウジアラビア": ("Saudi Arabia", "サウジアラビア"),
    # Global / International
    "global": ("Global", "グローバル"),
    "international": ("International", "国際"),
    "グローバル": ("Global", "グローバル"),
}
"""Entity.country 生値 → (英語正規名, 日本語名) マッピング。"""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class MigrationStats:
    """全フェーズの移行統計情報。"""

    # Phase 1: Ticker
    ticker_nodes_created: int = 0
    ticker_rels_created: int = 0
    ticker_skipped: int = 0
    ticker_failed: int = 0

    # Phase 2: Country
    country_nodes_created: int = 0
    country_rels_created: int = 0
    country_skipped: int = 0
    country_failed: int = 0

    # Phase 3: Sector
    sector_normalized: int = 0
    sector_skipped: int = 0
    sector_failed: int = 0

    # Phase 4: Industry (確認フェーズ)
    industry_rels_confirmed: int = 0

    # Phase 5: Identifier → Ticker
    identifier_migrated: int = 0
    identifier_skipped: int = 0
    identifier_failed: int = 0


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------


def normalize_country(raw_country: str) -> tuple[str, str] | None:
    """Country 生値を正規化する。

    Parameters
    ----------
    raw_country : str
        Entity.country の生値（大文字小文字混在、英日両方あり）。

    Returns
    -------
    tuple[str, str] | None
        ``(英語正規名, 日本語名)`` のタプル。マッピング未定義の場合は None。
    """
    key = raw_country.strip().lower()
    # 完全一致まず試みる
    if key in COUNTRY_NORMALIZATION:
        return COUNTRY_NORMALIZATION[key]
    # 元の値（大文字小文字そのまま）でも試みる
    if raw_country.strip() in COUNTRY_NORMALIZATION:
        return COUNTRY_NORMALIZATION[raw_country.strip()]
    return None


def normalize_sector(raw_sector: str) -> str | None:
    """Sector 生名をGICS 11種の正規名に変換する。

    Parameters
    ----------
    raw_sector : str
        Sector ノードの name プロパティ（バラバラな表記）。

    Returns
    -------
    str | None
        GICS 正規セクター名。マッピング未定義の場合は None。
    """
    # 完全一致（元の大文字小文字で）
    if raw_sector in GICS_SECTOR_NORMALIZATION:
        return GICS_SECTOR_NORMALIZATION[raw_sector]
    # 小文字化で試みる
    key = raw_sector.strip().lower()
    return GICS_SECTOR_NORMALIZATION.get(key)


# ---------------------------------------------------------------------------
# Phase 1: Ticker ノード作成
# ---------------------------------------------------------------------------


def fetch_entities_with_ticker(session: Any) -> list[dict[str, Any]]:
    """ticker プロパティを持つ Entity ノードを取得する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        各要素に ``entity_key``, ``name``, ``ticker`` を含むリスト。
    """
    cypher = (
        "MATCH (e:Entity) "
        "WHERE e.ticker IS NOT NULL AND trim(e.ticker) <> '' "
        "RETURN e.entity_key AS entity_key, e.name AS name, e.ticker AS ticker"
    )
    result = session.run(cypher)
    records = [
        {
            "entity_key": r["entity_key"],
            "name": r["name"],
            "ticker": r["ticker"],
        }
        for r in result
    ]
    logger.info("Found %d Entity nodes with ticker property", len(records))
    return records


def create_ticker_nodes(
    session: Any,
    entities: list[dict[str, Any]],
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Ticker ノードを作成し HAS_TICKER リレーションを付与する。

    冪等設計: MERGE を使用するため重複作成しない。
    Ticker.ticker_id は ``ticker_{value}_{exchange}`` 形式の決定論的ID。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    entities : list[dict[str, Any]]
        fetch_entities_with_ticker の戻り値。
    dry_run : bool
        True の場合、DB への書き込みをスキップ。

    Returns
    -------
    tuple[int, int, int]
        ``(nodes_created, rels_created, failed)`` のタプル。
    """
    nodes_created = 0
    rels_created = 0
    failed = 0

    for entity in entities:
        entity_key = entity["entity_key"]
        ticker_value = entity["ticker"].strip()
        # ticker_id は値ベースの決定論的ID
        ticker_id = f"ticker_{ticker_value.lower().replace(' ', '_')}"

        if dry_run:
            logger.debug(
                "[dry-run] Would create Ticker: ticker_id=%s value=%s for entity_key=%s",
                ticker_id,
                ticker_value,
                entity_key,
            )
            nodes_created += 1
            rels_created += 1
            continue

        try:
            # Ticker ノード MERGE + HAS_TICKER リレーション MERGE
            cypher = (
                "MATCH (e:Entity {entity_key: $entity_key}) "
                "MERGE (t:Ticker {ticker_id: $ticker_id}) "
                "  ON CREATE SET t.value = $value, t.type = 'ticker', t.scheme = 'exchange_ticker' "
                "MERGE (e)-[:HAS_TICKER]->(t) "
                "RETURN t.ticker_id AS tid"
            )
            result = session.run(
                cypher,
                entity_key=entity_key,
                ticker_id=ticker_id,
                value=ticker_value,
            )
            record = result.single()
            if record:
                nodes_created += 1
                rels_created += 1
                logger.debug(
                    "Created Ticker: ticker_id=%s for entity_key=%s",
                    ticker_id,
                    entity_key,
                )
            else:
                logger.warning(
                    "Entity not found: entity_key=%s (skipping Ticker creation)",
                    entity_key,
                )
        except Exception:
            failed += 1
            logger.exception(
                "Failed to create Ticker for entity_key=%s ticker=%s",
                entity_key,
                ticker_value,
            )

    return nodes_created, rels_created, failed


# ---------------------------------------------------------------------------
# Phase 2: Country ノード作成
# ---------------------------------------------------------------------------


def fetch_entities_with_country(session: Any) -> list[dict[str, Any]]:
    """country プロパティを持つ Entity ノードを取得する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        各要素に ``entity_key``, ``name``, ``country`` を含むリスト。
    """
    cypher = (
        "MATCH (e:Entity) "
        "WHERE e.country IS NOT NULL AND trim(e.country) <> '' "
        "RETURN e.entity_key AS entity_key, e.name AS name, e.country AS country"
    )
    result = session.run(cypher)
    records = [
        {
            "entity_key": r["entity_key"],
            "name": r["name"],
            "country": r["country"],
        }
        for r in result
    ]
    logger.info("Found %d Entity nodes with country property", len(records))
    return records


def create_country_nodes(
    session: Any,
    entities: list[dict[str, Any]],
    dry_run: bool = False,
) -> tuple[int, int, int, int]:
    """Country ノードを作成し IN_COUNTRY リレーションを付与する。

    英日名寄せを適用する。COUNTRY_NORMALIZATION に未定義の場合は生値を使用。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    entities : list[dict[str, Any]]
        fetch_entities_with_country の戻り値。
    dry_run : bool
        True の場合、DB への書き込みをスキップ。

    Returns
    -------
    tuple[int, int, int, int]
        ``(nodes_created, rels_created, skipped, failed)`` のタプル。
    """
    nodes_created = 0
    rels_created = 0
    skipped = 0
    failed = 0

    for entity in entities:
        entity_key = entity["entity_key"]
        raw_country = entity["country"]

        normalized = normalize_country(raw_country)
        if normalized is None:
            # 未定義の場合は生値を英語名として使用
            en_name = raw_country.strip()
            ja_name = raw_country.strip()
            logger.warning(
                "Unknown country value, using as-is: entity_key=%s country=%s",
                entity_key,
                raw_country,
            )
        else:
            en_name, ja_name = normalized

        country_id = f"country_{en_name.lower().replace(' ', '_')}"

        if dry_run:
            logger.debug(
                "[dry-run] Would create Country: country_id=%s name=%s name_ja=%s for entity_key=%s",
                country_id,
                en_name,
                ja_name,
                entity_key,
            )
            nodes_created += 1
            rels_created += 1
            continue

        try:
            cypher = (
                "MATCH (e:Entity {entity_key: $entity_key}) "
                "MERGE (c:Country {country_id: $country_id}) "
                "  ON CREATE SET c.name = $name, c.name_ja = $name_ja "
                "MERGE (e)-[:IN_COUNTRY]->(c) "
                "RETURN c.country_id AS cid"
            )
            result = session.run(
                cypher,
                entity_key=entity_key,
                country_id=country_id,
                name=en_name,
                name_ja=ja_name,
            )
            record = result.single()
            if record:
                nodes_created += 1
                rels_created += 1
                logger.debug(
                    "Created Country node: country_id=%s for entity_key=%s",
                    country_id,
                    entity_key,
                )
            else:
                skipped += 1
                logger.warning(
                    "Entity not found: entity_key=%s (skipping Country creation)",
                    entity_key,
                )
        except Exception:
            failed += 1
            logger.exception(
                "Failed to create Country for entity_key=%s country=%s",
                entity_key,
                raw_country,
            )

    return nodes_created, rels_created, skipped, failed


# ---------------------------------------------------------------------------
# Phase 3: Sector 正規化
# ---------------------------------------------------------------------------


def fetch_all_sectors(session: Any) -> list[dict[str, Any]]:
    """全 Sector ノードを取得する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        各要素に ``sector_id``, ``name`` を含むリスト。
    """
    cypher = (
        "MATCH (s:Sector) "
        "RETURN s.sector_id AS sector_id, s.name AS name"
    )
    result = session.run(cypher)
    records = [
        {"sector_id": r["sector_id"], "name": r["name"]} for r in result
    ]
    logger.info("Found %d Sector nodes", len(records))
    return records


def build_sector_normalization_ops(
    sectors: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Sector 正規化操作リストを構築する。

    Parameters
    ----------
    sectors : list[dict[str, Any]]
        fetch_all_sectors の戻り値。

    Returns
    -------
    list[dict[str, str]]
        各要素に ``sector_id``, ``raw_name``, ``canonical_name`` を含む操作リスト。
        GICS 11種にマッピング可能なセクターのみ含まれる。
    """
    ops: list[dict[str, str]] = []
    for sector in sectors:
        raw_name = sector.get("name") or ""
        canonical = normalize_sector(raw_name)
        if canonical is None:
            logger.warning(
                "Unknown Sector name, skipping normalization: sector_id=%s name=%s",
                sector.get("sector_id"),
                raw_name,
            )
            continue
        if canonical == raw_name:
            # 既に正規名
            logger.debug(
                "Sector already canonical: sector_id=%s name=%s",
                sector.get("sector_id"),
                raw_name,
            )
            ops.append(
                {
                    "sector_id": sector["sector_id"],
                    "raw_name": raw_name,
                    "canonical_name": canonical,
                }
            )
            continue
        ops.append(
            {
                "sector_id": sector["sector_id"],
                "raw_name": raw_name,
                "canonical_name": canonical,
            }
        )
    return ops


def apply_sector_normalization(
    session: Any,
    ops: list[dict[str, str]],
    dry_run: bool = False,
) -> tuple[int, int]:
    """Sector 正規化操作を Neo4j で実行する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    ops : list[dict[str, str]]
        build_sector_normalization_ops の戻り値。
    dry_run : bool
        True の場合、DB への書き込みをスキップ。

    Returns
    -------
    tuple[int, int]
        ``(normalized, failed)`` のタプル。
    """
    normalized = 0
    failed = 0

    for op in ops:
        sector_id = op["sector_id"]
        raw_name = op["raw_name"]
        canonical = op["canonical_name"]

        if raw_name == canonical:
            # 既に正規名のためスキップ
            logger.debug(
                "Sector already has canonical name: sector_id=%s name=%s",
                sector_id,
                canonical,
            )
            normalized += 1
            continue

        if dry_run:
            logger.debug(
                "[dry-run] Would normalize Sector: sector_id=%s '%s' → '%s'",
                sector_id,
                raw_name,
                canonical,
            )
            normalized += 1
            continue

        try:
            cypher = (
                "MATCH (s:Sector {sector_id: $sector_id}) "
                "SET s.name = $canonical_name "
                "RETURN s.sector_id AS sid"
            )
            result = session.run(
                cypher,
                sector_id=sector_id,
                canonical_name=canonical,
            )
            record = result.single()
            if record:
                normalized += 1
                logger.debug(
                    "Normalized Sector: sector_id=%s '%s' → '%s'",
                    sector_id,
                    raw_name,
                    canonical,
                )
            else:
                logger.warning(
                    "Sector not found: sector_id=%s (skipping)", sector_id
                )
        except Exception:
            failed += 1
            logger.exception(
                "Failed to normalize Sector: sector_id=%s name=%s",
                sector_id,
                raw_name,
            )

    return normalized, failed


# ---------------------------------------------------------------------------
# Phase 4: Industry ノード確認
# ---------------------------------------------------------------------------


def count_industry_relationships(session: Any) -> int:
    """IN_INDUSTRY リレーションの件数を確認する（読み取り専用）。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    int
        IN_INDUSTRY リレーションの件数。
    """
    cypher = (
        "MATCH (e:Entity)-[:IN_INDUSTRY]->(i:Industry) "
        "RETURN count(*) AS cnt"
    )
    result = session.run(cypher)
    record = result.single()
    cnt: int = record["cnt"] if record else 0
    logger.info("IN_INDUSTRY relationships: %d", cnt)
    return cnt


def count_industry_nodes(session: Any) -> int:
    """Industry ノードの件数を確認する（読み取り専用）。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    int
        Industry ノードの件数。
    """
    cypher = "MATCH (i:Industry) RETURN count(i) AS cnt"
    result = session.run(cypher)
    record = result.single()
    cnt: int = record["cnt"] if record else 0
    logger.info("Industry nodes: %d", cnt)
    return cnt


# ---------------------------------------------------------------------------
# Phase 5: Identifier → Ticker 統合
# ---------------------------------------------------------------------------


def fetch_ticker_identifiers(session: Any) -> list[dict[str, Any]]:
    """ticker 種別の Identifier ノードと紐付く Entity を取得する。

    Parameters
    ----------
    session : Any
        Neo4j セッション。

    Returns
    -------
    list[dict[str, Any]]
        各要素に ``identifier_id``, ``value``, ``entity_key`` を含むリスト。
    """
    cypher = (
        "MATCH (e:Entity)-[:HAS_IDENTIFIER]->(id:Identifier) "
        "WHERE id.type = 'ticker' OR id.scheme = 'exchange_ticker' "
        "RETURN id.identifier_id AS identifier_id, "
        "       id.value AS value, "
        "       id.scheme AS scheme, "
        "       e.entity_key AS entity_key"
    )
    result = session.run(cypher)
    records = [
        {
            "identifier_id": r["identifier_id"],
            "value": r["value"],
            "scheme": r["scheme"],
            "entity_key": r["entity_key"],
        }
        for r in result
    ]
    logger.info("Found %d ticker-type Identifier nodes", len(records))
    return records


def migrate_identifiers_to_ticker(
    session: Any,
    identifiers: list[dict[str, Any]],
    dry_run: bool = False,
) -> tuple[int, int, int]:
    """Identifier(ticker) ノードを Ticker ノードに統合する。

    既存の HAS_IDENTIFIER→Identifier リレーションを HAS_TICKER→Ticker に移行する。
    Ticker ノードは MERGE で冪等作成。Identifier ノードは削除しない（安全なため）。

    Parameters
    ----------
    session : Any
        Neo4j セッション。
    identifiers : list[dict[str, Any]]
        fetch_ticker_identifiers の戻り値。
    dry_run : bool
        True の場合、DB への書き込みをスキップ。

    Returns
    -------
    tuple[int, int, int]
        ``(migrated, skipped, failed)`` のタプル。
    """
    migrated = 0
    skipped = 0
    failed = 0

    for ident in identifiers:
        identifier_id = ident["identifier_id"]
        value = ident.get("value") or ""
        entity_key = ident["entity_key"]
        scheme = ident.get("scheme") or "exchange_ticker"

        if not value.strip():
            skipped += 1
            logger.warning(
                "Identifier has empty value, skipping: identifier_id=%s",
                identifier_id,
            )
            continue

        ticker_id = f"ticker_{value.strip().lower().replace(' ', '_')}"

        if dry_run:
            logger.debug(
                "[dry-run] Would migrate Identifier→Ticker: identifier_id=%s value=%s ticker_id=%s",
                identifier_id,
                value,
                ticker_id,
            )
            migrated += 1
            continue

        try:
            # Ticker ノード MERGE + HAS_TICKER リレーション MERGE
            cypher = (
                "MATCH (e:Entity {entity_key: $entity_key}) "
                "MERGE (t:Ticker {ticker_id: $ticker_id}) "
                "  ON CREATE SET t.value = $value, t.type = 'ticker', t.scheme = $scheme "
                "MERGE (e)-[:HAS_TICKER]->(t) "
                "RETURN t.ticker_id AS tid"
            )
            result = session.run(
                cypher,
                entity_key=entity_key,
                ticker_id=ticker_id,
                value=value.strip(),
                scheme=scheme,
            )
            record = result.single()
            if record:
                migrated += 1
                logger.debug(
                    "Migrated Identifier to Ticker: identifier_id=%s ticker_id=%s",
                    identifier_id,
                    ticker_id,
                )
            else:
                skipped += 1
                logger.warning(
                    "Entity not found: entity_key=%s (skipping Identifier migration)",
                    entity_key,
                )
        except Exception:
            failed += 1
            logger.exception(
                "Failed to migrate Identifier: identifier_id=%s entity_key=%s",
                identifier_id,
                entity_key,
            )

    return migrated, skipped, failed


# ---------------------------------------------------------------------------
# Dry-run Summary
# ---------------------------------------------------------------------------


def run_dry_run_summary(session: Any) -> None:
    """dry-run 時のサマリーを出力する。"""
    # Phase 1: Ticker
    ticker_entities = fetch_entities_with_ticker(session)
    ticker_nodes, ticker_rels, _ = create_ticker_nodes(
        session, ticker_entities, dry_run=True
    )

    # Phase 2: Country
    country_entities = fetch_entities_with_country(session)
    # dry_run では nodes_created = rels_created = len(entities) (正常系)
    country_nodes = len(country_entities)
    country_rels = len(country_entities)
    # 正規化できないものを除外して概算
    unknown_countries = [
        e for e in country_entities if normalize_country(e["country"]) is None
    ]

    # Phase 3: Sector
    sectors = fetch_all_sectors(session)
    sector_ops = build_sector_normalization_ops(sectors)
    needs_rename = [
        op for op in sector_ops if op["raw_name"] != op["canonical_name"]
    ]

    # Phase 4: Industry
    industry_node_count = count_industry_nodes(session)
    industry_rel_count = count_industry_relationships(session)

    # Phase 5: Identifier
    ticker_identifiers = fetch_ticker_identifiers(session)

    print("\n=== dry-run サマリー ===")
    print(f"\n[Phase 1] Ticker ノード作成:")
    print(f"  ticker プロパティ保持 Entity: {len(ticker_entities):,} 件")
    print(f"  作成予定 Ticker ノード       : {ticker_nodes:,} 件（MERGE冪等）")
    print(f"  作成予定 HAS_TICKER          : {ticker_rels:,} 件（MERGE冪等）")

    print(f"\n[Phase 2] Country ノード作成:")
    print(f"  country プロパティ保持 Entity: {len(country_entities):,} 件")
    print(f"  作成予定 Country ノード      : {country_nodes:,} 件（MERGE冪等）")
    print(f"  作成予定 IN_COUNTRY          : {country_rels:,} 件（MERGE冪等）")
    if unknown_countries:
        print(
            f"  ⚠️ COUNTRY_NORMALIZATION 未定義: {len(unknown_countries):,} 件（生値で登録）"
        )
        for e in unknown_countries[:5]:
            print(f"    entity_key={e['entity_key']} country={e['country']}")

    print(f"\n[Phase 3] Sector 正規化:")
    print(f"  既存 Sector ノード数         : {len(sectors):,} 件")
    print(f"  GICS正規化対象               : {len(sector_ops):,} 件")
    print(f"  名称変更が必要               : {len(needs_rename):,} 件")
    if needs_rename:
        for op in needs_rename[:5]:
            print(
                f"    sector_id={op['sector_id']} '{op['raw_name']}' → '{op['canonical_name']}'"
            )

    print(f"\n[Phase 4] Industry 確認:")
    print(f"  Industry ノード数            : {industry_node_count:,} 件")
    print(f"  IN_INDUSTRY リレーション数   : {industry_rel_count:,} 件")

    print(f"\n[Phase 5] Identifier → Ticker 統合:")
    print(f"  ticker種別 Identifier        : {len(ticker_identifiers):,} 件")
    print(f"  統合予定                     : {len(ticker_identifiers):,} 件（MERGE冪等）")

    print("\n  ※ --dry-run のため DB への書き込みは行いません")


# ---------------------------------------------------------------------------
# Main Phases Runner
# ---------------------------------------------------------------------------


def run_phase_ticker(session: Any, dry_run: bool) -> MigrationStats:
    """Phase 1: Ticker ノード作成を実行する。"""
    stats = MigrationStats()
    entities = fetch_entities_with_ticker(session)
    nodes, rels, failed = create_ticker_nodes(session, entities, dry_run=dry_run)
    stats.ticker_nodes_created = nodes
    stats.ticker_rels_created = rels
    stats.ticker_failed = failed
    return stats


def run_phase_country(session: Any, dry_run: bool) -> MigrationStats:
    """Phase 2: Country ノード作成を実行する。"""
    stats = MigrationStats()
    entities = fetch_entities_with_country(session)
    nodes, rels, skipped, failed = create_country_nodes(
        session, entities, dry_run=dry_run
    )
    stats.country_nodes_created = nodes
    stats.country_rels_created = rels
    stats.country_skipped = skipped
    stats.country_failed = failed
    return stats


def run_phase_sector(session: Any, dry_run: bool) -> MigrationStats:
    """Phase 3: Sector 正規化を実行する。"""
    stats = MigrationStats()
    sectors = fetch_all_sectors(session)
    ops = build_sector_normalization_ops(sectors)
    stats.sector_skipped = len(sectors) - len(ops)
    normalized, failed = apply_sector_normalization(session, ops, dry_run=dry_run)
    stats.sector_normalized = normalized
    stats.sector_failed = failed
    return stats


def run_phase_industry(session: Any, _dry_run: bool) -> MigrationStats:
    """Phase 4: Industry 確認（読み取り専用）。"""
    stats = MigrationStats()
    stats.industry_rels_confirmed = count_industry_relationships(session)
    logger.info(
        "Industry phase: %d nodes, %d IN_INDUSTRY relationships confirmed",
        count_industry_nodes(session),
        stats.industry_rels_confirmed,
    )
    return stats


def run_phase_identifier(session: Any, dry_run: bool) -> MigrationStats:
    """Phase 5: Identifier → Ticker 統合を実行する。"""
    stats = MigrationStats()
    identifiers = fetch_ticker_identifiers(session)
    migrated, skipped, failed = migrate_identifiers_to_ticker(
        session, identifiers, dry_run=dry_run
    )
    stats.identifier_migrated = migrated
    stats.identifier_skipped = skipped
    stats.identifier_failed = failed
    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


_PHASE_RUNNERS = {
    "ticker": run_phase_ticker,
    "country": run_phase_country,
    "sector": run_phase_sector,
    "industry": run_phase_industry,
    "identifier": run_phase_identifier,
}
_ALL_PHASES = ["ticker", "country", "sector", "industry", "identifier"]


def main() -> None:
    """エンティティプロパティのノード分離移行スクリプトのエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description=(
            "Entity プロパティ（ticker/country）をノード分離し、"
            "Sector 正規化・Identifier 統合を行う移行スクリプト"
        ),
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.environ.get("NEO4J_URI", _DEFAULT_NEO4J_URI),
        help=f"Neo4j 接続 URI (デフォルト: {_DEFAULT_NEO4J_URI})",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.environ.get("NEO4J_USER", _DEFAULT_NEO4J_USER),
        help="Neo4j ユーザー名 (デフォルト: neo4j)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更対象件数のみ表示し、DB への書き込みは行わない",
    )
    parser.add_argument(
        "--phase",
        choices=[*_ALL_PHASES, "all"],
        default="all",
        help="実行するフェーズ（ticker/country/sector/industry/identifier/all）",
    )
    args = parser.parse_args()

    neo4j_password = os.environ.get("NEO4J_PASSWORD")
    if not neo4j_password:
        parser.error(
            "Neo4j password is required. Set NEO4J_PASSWORD environment variable."
        )

    logger.info("Connecting to Neo4j: %s (user: %s)", args.neo4j_uri, args.neo4j_user)
    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, neo4j_password),
    )

    try:
        driver.verify_connectivity()
        logger.info("Connected to Neo4j")

        with driver.session() as session:
            if args.dry_run and args.phase == "all":
                run_dry_run_summary(session)
                return

            phases = _ALL_PHASES if args.phase == "all" else [args.phase]
            total_stats = MigrationStats()

            for phase_name in phases:
                logger.info("=== Running Phase: %s ===", phase_name)
                runner = _PHASE_RUNNERS[phase_name]
                stats = runner(session, args.dry_run)

                # 統計を集計
                for attr in vars(stats):
                    current = getattr(total_stats, attr, 0)
                    setattr(total_stats, attr, current + getattr(stats, attr, 0))

            # 最終サマリー出力
            prefix = "[dry-run] " if args.dry_run else ""
            logger.info(
                "%sMigration complete. "
                "Ticker: nodes=%d rels=%d failed=%d | "
                "Country: nodes=%d rels=%d skipped=%d failed=%d | "
                "Sector: normalized=%d skipped=%d failed=%d | "
                "Industry: confirmed=%d | "
                "Identifier: migrated=%d skipped=%d failed=%d",
                prefix,
                total_stats.ticker_nodes_created,
                total_stats.ticker_rels_created,
                total_stats.ticker_failed,
                total_stats.country_nodes_created,
                total_stats.country_rels_created,
                total_stats.country_skipped,
                total_stats.country_failed,
                total_stats.sector_normalized,
                total_stats.sector_skipped,
                total_stats.sector_failed,
                total_stats.industry_rels_confirmed,
                total_stats.identifier_migrated,
                total_stats.identifier_skipped,
                total_stats.identifier_failed,
            )

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
