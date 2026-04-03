#!/usr/bin/env python3
"""ABOUT/MENTIONS リレーションを RELATES_TO にリネームする移行スクリプト。

Wave 5 移行スクリプト。以下のフェーズを順次実行する:

1. **移行前件数取得**: ABOUT / MENTIONS / RELATES_TO の現在件数を記録する。
2. **ABOUT → RELATES_TO リネーム**: apoc.refactor.rename.type を 1,000 件バッチで実行。
3. **MENTIONS → RELATES_TO リネーム**: apoc.refactor.rename.type を 1,000 件バッチで実行。
4. **移行後検証**: ABOUT 0 件 / MENTIONS 0 件 / RELATES_TO 件数が移行前合計と一致することを確認。

Usage
-----
::

    # 対象件数確認（DB への書き込みなし）
    uv run python scripts/migrate_relations_to_relates_to.py --dry-run

    # 本番実行（全フェーズ）
    uv run python scripts/migrate_relations_to_relates_to.py

    # 特定フェーズのみ実行
    uv run python scripts/migrate_relations_to_relates_to.py --phase pre_count
    uv run python scripts/migrate_relations_to_relates_to.py --phase migrate_about
    uv run python scripts/migrate_relations_to_relates_to.py --phase migrate_mentions
    uv run python scripts/migrate_relations_to_relates_to.py --phase verify

    # バッチサイズを変更（デフォルト: 1,000）
    uv run python scripts/migrate_relations_to_relates_to.py --batch-size 500

    # 接続先を指定
    uv run python scripts/migrate_relations_to_relates_to.py --neo4j-uri bolt://localhost:7688

設計方針
--------
- 冪等実行可能: 移行済みのリレーションは ABOUT/MENTIONS に存在しないため再実行しても安全
- --dry-run フラグで書き込みをスキップして件数のみ確認
- 大量データ対応: 1,000 件単位バッチで apoc.refactor.rename.type を実行
- neo4j-write-rules.md 例外適用: 本スクリプトは移行専用（ユーザー明示承認済み）
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field

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

_DEFAULT_NEO4J_URI = "bolt://localhost:7687"
_DEFAULT_NEO4J_USER = "neo4j"
_DEFAULT_BATCH_SIZE = 1_000
"""バッチサイズ。apoc.refactor.rename.type の 1 回あたり処理件数。"""


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------


@dataclass
class MigrationCounts:
    """移行前後のリレーション件数スナップショット。"""

    about: int = 0
    """ABOUT リレーション件数。"""

    mentions: int = 0
    """MENTIONS リレーション件数。"""

    relates_to: int = 0
    """RELATES_TO リレーション件数。"""

    @property
    def total_source(self) -> int:
        """移行元合計 (ABOUT + MENTIONS)。"""
        return self.about + self.mentions


@dataclass
class MigrationStats:
    """Wave 5 リレーション移行の統計情報。"""

    pre: MigrationCounts = field(default_factory=MigrationCounts)
    """移行前カウント。"""

    post: MigrationCounts = field(default_factory=MigrationCounts)
    """移行後カウント。"""

    about_migrated: int = 0
    """ABOUT → RELATES_TO に変換したバッチ合計件数。"""

    mentions_migrated: int = 0
    """MENTIONS → RELATES_TO に変換したバッチ合計件数。"""

    verified: bool = False
    """検証結果（True = OK）。"""

    failed: int = 0
    """失敗件数。"""


# ---------------------------------------------------------------------------
# Phase 1: 移行前件数取得
# ---------------------------------------------------------------------------


def fetch_relation_counts(session: object) -> MigrationCounts:
    """ABOUT / MENTIONS / RELATES_TO の件数を取得する。

    Parameters
    ----------
    session : object
        Neo4j セッション。

    Returns
    -------
    MigrationCounts
        各リレーション種別の件数。
    """
    counts = MigrationCounts()

    cypher_about = "MATCH ()-[r:ABOUT]->() RETURN count(r) AS cnt"
    record = session.run(cypher_about).single()  # type: ignore[union-attr]
    counts.about = record["cnt"] if record else 0

    cypher_mentions = "MATCH ()-[r:MENTIONS]->() RETURN count(r) AS cnt"
    record = session.run(cypher_mentions).single()  # type: ignore[union-attr]
    counts.mentions = record["cnt"] if record else 0

    cypher_relates = "MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS cnt"
    record = session.run(cypher_relates).single()  # type: ignore[union-attr]
    counts.relates_to = record["cnt"] if record else 0

    logger.info(
        "Relation counts: ABOUT=%d MENTIONS=%d RELATES_TO=%d",
        counts.about,
        counts.mentions,
        counts.relates_to,
    )
    return counts


# ---------------------------------------------------------------------------
# Phase 2: ABOUT → RELATES_TO バッチリネーム
# ---------------------------------------------------------------------------


def migrate_about_to_relates_to(
    session: object,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> int:
    """ABOUT リレーションを RELATES_TO にバッチリネームする。

    apoc.refactor.rename.type を使用して ``batch_size`` 件単位でリネームを繰り返す。
    全件処理が完了すると ``ABOUT`` リレーションが 0 件になる。

    Parameters
    ----------
    session : object
        Neo4j セッション。
    batch_size : int
        1 回あたりの処理件数（デフォルト: 1,000）。
    dry_run : bool
        True の場合、実際の書き込みをスキップして 0 を返す。

    Returns
    -------
    int
        変換済みリレーション合計件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug("[dry-run] Would migrate ABOUT → RELATES_TO (batch_size=%d)", batch_size)
        return 0

    total_migrated = 0
    # AIDEV-NOTE: apoc.refactor.rename.type は ABOUT を RELATES_TO にリネームする。
    # batchSize 引数で一度に処理する件数を制御してメモリ圧迫を防ぐ。
    cypher = (
        "CALL apoc.refactor.rename.type('ABOUT', 'RELATES_TO', [], {batchSize: $batch_size}) "
        "YIELD total "
        "RETURN total"
    )
    try:
        result = session.run(cypher, batch_size=batch_size)  # type: ignore[union-attr]
        record = result.single()
        migrated = record["total"] if record else 0
        total_migrated += migrated
        logger.info("Migrated ABOUT → RELATES_TO: total=%d", migrated)
    except Exception:
        logger.exception("Failed to migrate ABOUT → RELATES_TO")

    return total_migrated


# ---------------------------------------------------------------------------
# Phase 3: MENTIONS → RELATES_TO バッチリネーム
# ---------------------------------------------------------------------------


def migrate_mentions_to_relates_to(
    session: object,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> int:
    """MENTIONS リレーションを RELATES_TO にバッチリネームする。

    apoc.refactor.rename.type を使用して ``batch_size`` 件単位でリネームを繰り返す。
    全件処理が完了すると ``MENTIONS`` リレーションが 0 件になる。

    Parameters
    ----------
    session : object
        Neo4j セッション。
    batch_size : int
        1 回あたりの処理件数（デフォルト: 1,000）。
    dry_run : bool
        True の場合、実際の書き込みをスキップして 0 を返す。

    Returns
    -------
    int
        変換済みリレーション合計件数（dry_run=True の場合は 0）。
    """
    if dry_run:
        logger.debug("[dry-run] Would migrate MENTIONS → RELATES_TO (batch_size=%d)", batch_size)
        return 0

    total_migrated = 0
    # AIDEV-NOTE: apoc.refactor.rename.type は MENTIONS を RELATES_TO にリネームする。
    # batchSize 引数で一度に処理する件数を制御してメモリ圧迫を防ぐ。
    cypher = (
        "CALL apoc.refactor.rename.type('MENTIONS', 'RELATES_TO', [], {batchSize: $batch_size}) "
        "YIELD total "
        "RETURN total"
    )
    try:
        result = session.run(cypher, batch_size=batch_size)  # type: ignore[union-attr]
        record = result.single()
        migrated = record["total"] if record else 0
        total_migrated += migrated
        logger.info("Migrated MENTIONS → RELATES_TO: total=%d", migrated)
    except Exception:
        logger.exception("Failed to migrate MENTIONS → RELATES_TO")

    return total_migrated


# ---------------------------------------------------------------------------
# Phase 4: 移行後検証
# ---------------------------------------------------------------------------


def verify_migration(
    session: object,
    pre_counts: MigrationCounts,
) -> bool:
    """移行後のリレーション件数を検証する。

    以下の条件を全て満たす場合に True を返す:

    - ABOUT リレーションが 0 件
    - MENTIONS リレーションが 0 件
    - RELATES_TO 件数が移行前合計 (ABOUT + MENTIONS + 既存 RELATES_TO) と一致

    Parameters
    ----------
    session : object
        Neo4j セッション。
    pre_counts : MigrationCounts
        移行前のリレーション件数（Phase 1 の取得結果）。

    Returns
    -------
    bool
        True = 検証 OK。
    """
    post = fetch_relation_counts(session)

    expected_relates_to = pre_counts.about + pre_counts.mentions + pre_counts.relates_to

    ok = True

    if post.about != 0:
        logger.error("Verification FAILED: ABOUT count is %d (expected 0)", post.about)
        ok = False
    else:
        logger.info("Verification OK: ABOUT = 0")

    if post.mentions != 0:
        logger.error("Verification FAILED: MENTIONS count is %d (expected 0)", post.mentions)
        ok = False
    else:
        logger.info("Verification OK: MENTIONS = 0")

    if post.relates_to != expected_relates_to:
        logger.error(
            "Verification FAILED: RELATES_TO count=%d (expected %d = %d + %d + %d)",
            post.relates_to,
            expected_relates_to,
            pre_counts.about,
            pre_counts.mentions,
            pre_counts.relates_to,
        )
        ok = False
    else:
        logger.info(
            "Verification OK: RELATES_TO=%d matches expected=%d",
            post.relates_to,
            expected_relates_to,
        )

    return ok


# ---------------------------------------------------------------------------
# Dry-run サマリー
# ---------------------------------------------------------------------------


def run_dry_run_summary(session: object) -> None:
    """dry-run サマリーを標準出力に表示する。

    Parameters
    ----------
    session : object
        Neo4j セッション（読み取り専用クエリのみ実行）。
    """
    counts = fetch_relation_counts(session)

    print("\n=== Wave 5 dry-run サマリー ===")
    print(f"  Phase 2: ABOUT → RELATES_TO 移行対象     : {counts.about:,} 件")
    print(f"  Phase 3: MENTIONS → RELATES_TO 移行対象  : {counts.mentions:,} 件")
    print(f"  移行前 RELATES_TO 件数                   : {counts.relates_to:,} 件")
    print(f"  移行後 RELATES_TO 期待件数               : {counts.total_source + counts.relates_to:,} 件")
    print("  ※ --dry-run のため DB への書き込みは行いません")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Wave 5 ABOUT/MENTIONS → RELATES_TO リネームスクリプトのエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description=(
            "Wave 5: ABOUT/MENTIONS リレーションを RELATES_TO にリネームする移行スクリプト"
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
        choices=["pre_count", "migrate_about", "migrate_mentions", "verify"],
        default=None,
        help="特定フェーズのみ実行（デフォルト: 全フェーズ）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=_DEFAULT_BATCH_SIZE,
        help=f"1 回あたりの処理件数 (デフォルト: {_DEFAULT_BATCH_SIZE})",
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
            if args.dry_run:
                run_dry_run_summary(session)
                return

            stats = MigrationStats()
            run_all = args.phase is None

            # Phase 1: 移行前件数取得
            if run_all or args.phase == "pre_count":
                stats.pre = fetch_relation_counts(session)
                logger.info(
                    "Phase 1 complete: ABOUT=%d MENTIONS=%d RELATES_TO=%d",
                    stats.pre.about,
                    stats.pre.mentions,
                    stats.pre.relates_to,
                )

            # Phase 2: ABOUT → RELATES_TO
            if run_all or args.phase == "migrate_about":
                stats.about_migrated = migrate_about_to_relates_to(
                    session, batch_size=args.batch_size
                )
                logger.info(
                    "Phase 2 complete: about_migrated=%d", stats.about_migrated
                )

            # Phase 3: MENTIONS → RELATES_TO
            if run_all or args.phase == "migrate_mentions":
                stats.mentions_migrated = migrate_mentions_to_relates_to(
                    session, batch_size=args.batch_size
                )
                logger.info(
                    "Phase 3 complete: mentions_migrated=%d", stats.mentions_migrated
                )

            # Phase 4: 移行後検証
            if run_all or args.phase == "verify":
                # verify には pre_counts が必要。単体実行時は現時点で再取得
                if not run_all:
                    # verify 単体実行の場合は現在の件数を基に期待値を計算できないため
                    # 移行後の状態のみ確認する（ABOUT=0, MENTIONS=0 のみ検証）
                    post = fetch_relation_counts(session)
                    stats.post = post
                    stats.verified = post.about == 0 and post.mentions == 0
                    if stats.verified:
                        logger.info(
                            "Phase 4 (verify-only): ABOUT=0 OK, MENTIONS=0 OK, "
                            "RELATES_TO=%d",
                            post.relates_to,
                        )
                    else:
                        logger.error(
                            "Phase 4 (verify-only) FAILED: ABOUT=%d MENTIONS=%d",
                            post.about,
                            post.mentions,
                        )
                else:
                    stats.verified = verify_migration(session, stats.pre)
                    stats.post = fetch_relation_counts(session)
                    logger.info("Phase 4 complete: verified=%s", stats.verified)

            logger.info(
                "Wave 5 migration complete: "
                "about_migrated=%d mentions_migrated=%d verified=%s "
                "post_ABOUT=%d post_MENTIONS=%d post_RELATES_TO=%d",
                stats.about_migrated,
                stats.mentions_migrated,
                stats.verified,
                stats.post.about,
                stats.post.mentions,
                stats.post.relates_to,
            )

            if run_all and not stats.verified:
                logger.error("Migration verification FAILED. Please check the logs above.")
                sys.exit(1)

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
