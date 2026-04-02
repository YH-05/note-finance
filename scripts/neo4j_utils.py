"""Neo4j 共有ユーティリティ。

複数スクリプトで使用する Neo4j 接続ヘルパーを集約する。

Enterprise multi-database 対応:
  全インスタンスが bolt://localhost:7687 に統合され、
  database パラメータで note/research/creator/quants を分離する。
"""

from __future__ import annotations

import os
import sys
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

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

# Enterprise 共通デフォルト
DEFAULT_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")

# インスタンス名 → database名 のマッピング
INSTANCE_DB_MAP: dict[str, str] = {
    "note": os.environ.get("NEO4J_NOTE_DB", "note"),
    "research": os.environ.get("NEO4J_RESEARCH_DB", "research"),
    "creator": os.environ.get("NEO4J_CREATOR_DB", "creator"),
    "quants": os.environ.get("NEO4J_QUANTS_DB", "quants"),
}


def resolve_database(instance: str | None = None) -> str | None:
    """インスタンス名から database 名を解決する。

    Parameters
    ----------
    instance : str | None
        インスタンス名（note/research/creator/quants）。
        None の場合は None を返す（デフォルトDB使用）。
    """
    if instance is None:
        return None
    return INSTANCE_DB_MAP.get(instance, instance)


def create_driver(
    uri: str = DEFAULT_URI,
    user: str = "neo4j",
    password: str | None = None,
) -> Any:
    """Neo4j ドライバーを作成し接続確認を行う。

    Parameters
    ----------
    uri : str
        Neo4j 接続 URI。デフォルトは ``bolt://localhost:7687``。
    user : str
        Neo4j ユーザー名。
    password : str | None
        Neo4j パスワード。``None`` の場合は ``NEO4J_PASSWORD`` 環境変数を参照する。
        環境変数も未設定の場合は ``ValueError`` を送出する。

    Returns
    -------
    Any
        接続確認済みの Neo4j ドライバー。

    Raises
    ------
    ValueError
        パスワードが指定されず ``NEO4J_PASSWORD`` も未設定の場合。
    """
    if password is None:
        password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        msg = (
            "Neo4j password is required. "
            "Set NEO4J_PASSWORD environment variable or pass --neo4j-password."
        )
        raise ValueError(msg)

    logger.info("Connecting to Neo4j: %s", uri)
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    logger.info("Neo4j connection verified")
    return driver
