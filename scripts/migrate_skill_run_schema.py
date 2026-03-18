#!/usr/bin/env python3
"""SkillRun 制約・インデックスを research-neo4j に適用するワンショットマイグレーション。

research-neo4j (bolt://localhost:7688) に対して、Skill Observability 用の
制約とインデックスを冪等に適用する。DDL は docker/research-neo4j/init/
01-constraints-indexes.cypher の Skill Observability セクションと同一。

Usage
-----
::

    # 適用（デフォルト: bolt://localhost:7688）
    python scripts/migrate_skill_run_schema.py

    # 接続先を指定
    python scripts/migrate_skill_run_schema.py --neo4j-uri bolt://localhost:7688

    # dry-run（DDL を出力のみ）
    python scripts/migrate_skill_run_schema.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j driver not installed. Run: uv add neo4j")
    sys.exit(1)

try:
    from finance.utils.logging_config import get_logger

    logger = get_logger(__name__)
except ImportError:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL definitions (identical to 01-constraints-indexes.cypher Skill Observability)
# ---------------------------------------------------------------------------

SKILL_RUN_DDL: list[str] = [
    (
        "CREATE CONSTRAINT skill_run_id_unique IF NOT EXISTS "
        "FOR (sr:SkillRun) REQUIRE sr.skill_run_id IS UNIQUE"
    ),
    (
        "CREATE INDEX skill_run_skill_name IF NOT EXISTS "
        "FOR (sr:SkillRun) ON (sr.skill_name)"
    ),
    ("CREATE INDEX skill_run_status IF NOT EXISTS FOR (sr:SkillRun) ON (sr.status)"),
    (
        "CREATE INDEX skill_run_start_at IF NOT EXISTS "
        "FOR (sr:SkillRun) ON (sr.start_at)"
    ),
    (
        "CREATE INDEX skill_run_command_source IF NOT EXISTS "
        "FOR (sr:SkillRun) ON (sr.command_source)"
    ),
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def build_ddl_summary(ddl_list: list[str]) -> str:
    """DDL リストを人間可読なサマリー文字列に変換する。

    Parameters
    ----------
    ddl_list : list[str]
        実行する DDL ステートメントのリスト。

    Returns
    -------
    str
        改行区切りの DDL サマリー。空リストの場合は空文字列。
    """
    if not ddl_list:
        return ""
    return "\n".join(ddl_list)


def apply_ddl(session: Any, ddl_list: list[str]) -> dict[str, int]:
    """DDL ステートメントを Neo4j セッションで実行する。

    Parameters
    ----------
    session
        Neo4j セッション。
    ddl_list : list[str]
        実行する DDL ステートメントのリスト。

    Returns
    -------
    dict[str, int]
        ``{"applied": int, "failed": int}`` の統計情報。
    """
    stats: dict[str, int] = {"applied": 0, "failed": 0}

    for ddl in ddl_list:
        try:
            session.run(ddl)
            stats["applied"] += 1
            logger.info("Applied: %s", ddl)
        except Exception:
            stats["failed"] += 1
            logger.exception("Failed: %s", ddl)

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """SkillRun スキーママイグレーションのエントリーポイント。"""
    parser = argparse.ArgumentParser(
        description="Apply SkillRun constraints and indexes to research-neo4j",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=os.environ.get("NEO4J_URI", "bolt://localhost:7688"),
        help="Neo4j connection URI (default: bolt://localhost:7688)",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.environ.get("NEO4J_USER", "neo4j"),
        help="Neo4j username",
    )
    parser.add_argument(
        "--neo4j-password",
        default=os.environ.get("NEO4J_PASSWORD"),
        help="Neo4j password (required: set NEO4J_PASSWORD env var)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print DDL statements without executing",
    )
    args = parser.parse_args()

    # dry-run: DDL を出力して終了
    if args.dry_run:
        summary = build_ddl_summary(SKILL_RUN_DDL)
        logger.info("Dry-run mode: DDL statements to apply")
        print(summary)
        return

    if not args.neo4j_password:
        parser.error(
            "Neo4j password is required. "
            "Set NEO4J_PASSWORD environment variable or use --neo4j-password."
        )

    logger.info(
        "Connecting to Neo4j: %s (user: %s)",
        args.neo4j_uri,
        args.neo4j_user,
    )
    driver = GraphDatabase.driver(
        args.neo4j_uri,
        auth=(args.neo4j_user, args.neo4j_password),
    )

    try:
        driver.verify_connectivity()
        logger.info("Connected to Neo4j")

        with driver.session() as session:
            stats = apply_ddl(session, SKILL_RUN_DDL)

        logger.info(
            "Migration complete: %d applied, %d failed",
            stats["applied"],
            stats["failed"],
        )

        if stats["failed"] > 0:
            logger.error("Some DDL statements failed. Check logs for details.")
            sys.exit(1)

    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
