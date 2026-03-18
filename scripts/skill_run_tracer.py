#!/usr/bin/env python3
"""SkillRun ノードの CRUD を担う CLI ユーティリティ。

サブコマンド start / complete / feedback を提供し、Neo4j 上の
``Memory:SkillRun`` ノードを操作する。Neo4j 未起動時はグレースフル
デグラデーションにより合成 ID を返し、スキル実行をブロックしない。

Usage
-----
::

    # start: SkillRun ノード作成、skill_run_id を stdout に出力
    SRID=$(python scripts/skill_run_tracer.py start \\
        --skill-name test-skill --command-source manual)

    # complete: status/duration_ms 等を更新
    python scripts/skill_run_tracer.py complete \\
        --skill-run-id "$SRID" --status success

    # feedback: feedback_score 更新（INVOKED_SKILL リレーション作成オプション）
    python scripts/skill_run_tracer.py feedback \\
        --skill-run-id "$SRID" --score 0.8

    # feedback with invocation file
    python scripts/skill_run_tracer.py feedback \\
        --skill-run-id "$SRID" --score 0.8 \\
        --feedback-file invocations.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None  # type: ignore[assignment, misc]

try:
    from finance.utils.logging_config import get_logger
except ImportError:
    from session_utils import get_logger  # type: ignore[no-redef]

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NEO4J_URI = "bolt://localhost:7688"
DEFAULT_NEO4J_USER = "neo4j"
MAX_SUMMARY_LENGTH = 500


# ---------------------------------------------------------------------------
# Pure utility functions
# ---------------------------------------------------------------------------


def generate_skill_run_id(skill_name: str, session_id: str, start_at: str) -> str:
    """SHA-256 の先頭 32 文字から skill_run_id を生成する。

    Parameters
    ----------
    skill_name : str
        スキル名。
    session_id : str
        セッション ID。
    start_at : str
        開始時刻の ISO 8601 文字列。

    Returns
    -------
    str
        32 文字の hex ダイジェスト。
    """
    key = f"{skill_name}:{session_id}:{start_at}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def get_session_id() -> str:
    """環境変数 ``CLAUDE_SESSION_ID`` または UUID4 からセッション ID を取得する。

    Returns
    -------
    str
        セッション ID 文字列。
    """
    return os.environ.get("CLAUDE_SESSION_ID", str(uuid.uuid4()))


def truncate_summary(text: str | None, max_length: int = MAX_SUMMARY_LENGTH) -> str | None:
    """テキストを max_length 以下に切り詰める。

    Parameters
    ----------
    text : str | None
        入力テキスト。None の場合はそのまま返す。
    max_length : int
        最大文字数。デフォルト 500。

    Returns
    -------
    str | None
        切り詰めたテキスト、または None。
    """
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def compute_duration_ms(start_at: str, end_at: str) -> int | None:
    """start_at と end_at から実行時間をミリ秒で計算する。

    Parameters
    ----------
    start_at : str
        開始時刻の ISO 8601 文字列。
    end_at : str
        終了時刻の ISO 8601 文字列。

    Returns
    -------
    int | None
        ミリ秒単位の実行時間。パース失敗時は None。
    """
    try:
        start = datetime.fromisoformat(start_at)
        end = datetime.fromisoformat(end_at)
        delta = end - start
        return int(delta.total_seconds() * 1000)
    except (ValueError, TypeError) as exc:
        logger.warning("failed_to_compute_duration", error=str(exc))
        return None


# ---------------------------------------------------------------------------
# Cypher query builders (pure functions)
# ---------------------------------------------------------------------------


def build_start_cypher(
    *,
    skill_run_id: str,
    skill_name: str,
    session_id: str,
    start_at: str,
    command_source: str | None,
    input_summary: str | None,
) -> tuple[str, dict[str, Any]]:
    """start サブコマンド用の MERGE Cypher とパラメータを構築する。

    Parameters
    ----------
    skill_run_id : str
        一意の skill_run_id。
    skill_name : str
        スキル名。
    session_id : str
        セッション ID。
    start_at : str
        開始時刻 ISO 8601。
    command_source : str | None
        呼び出し元コマンド名。
    input_summary : str | None
        入力概要。

    Returns
    -------
    tuple[str, dict[str, Any]]
        Cypher クエリ文字列とパラメータ辞書。
    """
    query = """
    MERGE (sr:Memory:SkillRun {skill_run_id: $skill_run_id})
    ON CREATE SET
        sr.skill_name = $skill_name,
        sr.session_id = $session_id,
        sr.status = $status,
        sr.start_at = datetime($start_at),
        sr.command_source = $command_source,
        sr.input_summary = $input_summary
    ON MATCH SET
        sr.skill_name = $skill_name,
        sr.session_id = $session_id,
        sr.status = $status,
        sr.start_at = datetime($start_at),
        sr.command_source = $command_source,
        sr.input_summary = $input_summary
    """
    params: dict[str, Any] = {
        "skill_run_id": skill_run_id,
        "skill_name": skill_name,
        "session_id": session_id,
        "status": "running",
        "start_at": start_at,
        "command_source": command_source,
        "input_summary": truncate_summary(input_summary),
    }
    return query, params


def build_complete_cypher(
    *,
    skill_run_id: str,
    status: str,
    end_at: str,
    duration_ms: int | None,
    output_summary: str | None,
    error_message: str | None,
    error_type: str | None,
) -> tuple[str, dict[str, Any]]:
    """complete サブコマンド用の MATCH...SET Cypher とパラメータを構築する。

    Parameters
    ----------
    skill_run_id : str
        更新対象の skill_run_id。
    status : str
        完了ステータス（success / failure / partial / timeout）。
    end_at : str
        終了時刻 ISO 8601。
    duration_ms : int | None
        実行時間ミリ秒。
    output_summary : str | None
        出力概要。
    error_message : str | None
        エラーメッセージ。
    error_type : str | None
        エラー分類。

    Returns
    -------
    tuple[str, dict[str, Any]]
        Cypher クエリ文字列とパラメータ辞書。
    """
    query = """
    MATCH (sr:Memory:SkillRun {skill_run_id: $skill_run_id})
    SET sr.status = $status,
        sr.end_at = datetime($end_at),
        sr.duration_ms = $duration_ms,
        sr.output_summary = $output_summary,
        sr.error_message = $error_message,
        sr.error_type = $error_type
    """
    params: dict[str, Any] = {
        "skill_run_id": skill_run_id,
        "status": status,
        "end_at": end_at,
        "duration_ms": duration_ms,
        "output_summary": truncate_summary(output_summary),
        "error_message": truncate_summary(error_message),
        "error_type": error_type,
    }
    return query, params


def build_feedback_cypher(
    *,
    skill_run_id: str,
    feedback_score: float,
) -> tuple[str, dict[str, Any]]:
    """feedback サブコマンド用の MATCH...SET Cypher とパラメータを構築する。

    Parameters
    ----------
    skill_run_id : str
        更新対象の skill_run_id。
    feedback_score : float
        品質スコア 0.0 - 1.0。

    Returns
    -------
    tuple[str, dict[str, Any]]
        Cypher クエリ文字列とパラメータ辞書。
    """
    query = """
    MATCH (sr:Memory:SkillRun {skill_run_id: $skill_run_id})
    SET sr.feedback_score = $feedback_score
    """
    params: dict[str, Any] = {
        "skill_run_id": skill_run_id,
        "feedback_score": feedback_score,
    }
    return query, params


def build_invoked_skill_cypher(
    *,
    parent_id: str,
    child_id: str,
) -> tuple[str, dict[str, Any]]:
    """INVOKED_SKILL リレーション作成用の MERGE Cypher とパラメータを構築する。

    Parameters
    ----------
    parent_id : str
        親 SkillRun の skill_run_id。
    child_id : str
        子 SkillRun の skill_run_id。

    Returns
    -------
    tuple[str, dict[str, Any]]
        Cypher クエリ文字列とパラメータ辞書。
    """
    query = """
    MATCH (parent:Memory:SkillRun {skill_run_id: $parent_id})
    MATCH (child:Memory:SkillRun {skill_run_id: $child_id})
    MERGE (parent)-[:INVOKED_SKILL]->(child)
    """
    params: dict[str, Any] = {
        "parent_id": parent_id,
        "child_id": child_id,
    }
    return query, params


# ---------------------------------------------------------------------------
# Neo4j driver & execution (graceful degradation)
# ---------------------------------------------------------------------------


def create_neo4j_driver(
    *,
    uri: str,
    user: str,
    password: str | None,
) -> Any | None:
    """Neo4j ドライバを作成する。接続失敗時は None を返す。

    Parameters
    ----------
    uri : str
        Neo4j 接続 URI。
    user : str
        Neo4j ユーザー名。
    password : str | None
        Neo4j パスワード。None の場合は接続をスキップ。

    Returns
    -------
    Any | None
        Neo4j ドライバ、または接続不可時は None。
    """
    if GraphDatabase is None:
        logger.warning("neo4j_driver_not_installed", msg="neo4j package not available")
        return None

    if not password:
        logger.warning("neo4j_password_not_set", msg="NEO4J_PASSWORD not configured")
        return None

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        logger.info("neo4j_connected", uri=uri)
        return driver
    except Exception as exc:
        logger.warning("neo4j_connection_failed", uri=uri, error=str(exc))
        return None


def execute_cypher(
    driver: Any | None,
    query: str,
    params: dict[str, Any],
) -> bool:
    """Cypher クエリを実行する。ドライバが None または実行失敗時は False を返す。

    Parameters
    ----------
    driver : Any | None
        Neo4j ドライバ。None の場合は実行をスキップ。
    query : str
        Cypher クエリ文字列。
    params : dict[str, Any]
        パラメータ辞書。

    Returns
    -------
    bool
        実行成功時 True、失敗時 False。
    """
    if driver is None:
        logger.warning("cypher_skipped", msg="No Neo4j driver available")
        return False

    try:
        with driver.session() as session:
            session.run(query, **params)
        logger.debug("cypher_executed", query_prefix=query[:60])
        return True
    except Exception as exc:
        logger.warning("cypher_execution_failed", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Feedback file parsing
# ---------------------------------------------------------------------------


def parse_feedback_file(path: str) -> list[tuple[str, str]]:
    """フィードバックファイルから INVOKED_SKILL リレーション情報を読み取る。

    Parameters
    ----------
    path : str
        JSON ファイルパス。期待するフォーマット::

            {
                "invocations": [
                    {"parent_id": "...", "child_id": "..."},
                    ...
                ]
            }

    Returns
    -------
    list[tuple[str, str]]
        (parent_id, child_id) のタプルリスト。ファイル不存在や JSON 不正時は空リスト。
    """
    try:
        with Path(path).open(encoding="utf-8") as f:
            data = json.load(f)
        invocations = data.get("invocations", [])
        return [(inv["parent_id"], inv["child_id"]) for inv in invocations]
    except FileNotFoundError:
        logger.warning("feedback_file_not_found", path=path)
        return []
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("feedback_file_parse_error", path=path, error=str(exc))
        return []


# ---------------------------------------------------------------------------
# Driver lifecycle helper
# ---------------------------------------------------------------------------


def _get_neo4j_password() -> str | None:
    """環境変数 ``NEO4J_PASSWORD`` からパスワードを取得する。"""
    return os.environ.get("NEO4J_PASSWORD")


def _run_with_driver(
    args: argparse.Namespace,
    queries: list[tuple[str, dict[str, Any]]],
) -> list[bool]:
    """ドライバのライフサイクルを管理し、クエリリストを実行する。

    Parameters
    ----------
    args : argparse.Namespace
        CLI 引数（neo4j_uri, neo4j_user を含む）。
    queries : list[tuple[str, dict[str, Any]]]
        (Cypher, params) のリスト。

    Returns
    -------
    list[bool]
        各クエリの実行結果リスト。
    """
    driver = create_neo4j_driver(
        uri=args.neo4j_uri,
        user=args.neo4j_user,
        password=_get_neo4j_password(),
    )
    try:
        return [execute_cypher(driver, q, p) for q, p in queries]
    finally:
        if driver is not None:
            driver.close()


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------


def _cmd_start(args: argparse.Namespace) -> None:
    """start サブコマンド: SkillRun ノードを作成し skill_run_id を stdout に出力する。

    Neo4j 未起動時はグレースフルデグラデーションにより合成 ID を stdout に出力する。
    """
    session_id = get_session_id()
    start_at = datetime.now(timezone.utc).isoformat()
    skill_run_id = generate_skill_run_id(args.skill_name, session_id, start_at)

    logger.info(
        "skill_run_start",
        skill_run_id=skill_run_id,
        skill_name=args.skill_name,
        session_id=session_id,
    )

    query, params = build_start_cypher(
        skill_run_id=skill_run_id,
        skill_name=args.skill_name,
        session_id=session_id,
        start_at=start_at,
        command_source=args.command_source,
        input_summary=args.input_summary,
    )

    results = _run_with_driver(args, [(query, params)])
    if not results[0]:
        logger.warning(
            "skill_run_start_degraded",
            msg="Neo4j unavailable; returning synthetic ID",
            skill_run_id=skill_run_id,
        )

    # skill_run_id を stdout に出力（シェルスクリプトでキャプチャ可能）
    print(skill_run_id)


def _cmd_complete(args: argparse.Namespace) -> None:
    """complete サブコマンド: SkillRun の status/duration_ms/error 等を更新する。"""
    end_at = datetime.now(timezone.utc).isoformat()
    duration_ms = args.duration_ms

    logger.info(
        "skill_run_complete",
        skill_run_id=args.skill_run_id,
        status=args.status,
    )

    query, params = build_complete_cypher(
        skill_run_id=args.skill_run_id,
        status=args.status,
        end_at=end_at,
        duration_ms=duration_ms,
        output_summary=args.output_summary,
        error_message=args.error_message,
        error_type=args.error_type,
    )

    results = _run_with_driver(args, [(query, params)])
    if not results[0]:
        logger.warning(
            "skill_run_complete_degraded",
            msg="Neo4j unavailable; complete operation skipped",
            skill_run_id=args.skill_run_id,
        )


def _cmd_feedback(args: argparse.Namespace) -> None:
    """feedback サブコマンド: feedback_score を更新し、INVOKED_SKILL リレーションを作成する。"""
    logger.info(
        "skill_run_feedback",
        skill_run_id=args.skill_run_id,
        score=args.score,
    )

    # feedback_score 更新 + INVOKED_SKILL リレーション作成
    queries: list[tuple[str, dict[str, Any]]] = []

    fb_query, fb_params = build_feedback_cypher(
        skill_run_id=args.skill_run_id,
        feedback_score=args.score,
    )
    queries.append((fb_query, fb_params))

    # --feedback-file 指定時は INVOKED_SKILL リレーション一括追加
    if args.feedback_file:
        invocations = parse_feedback_file(args.feedback_file)
        for parent_id, child_id in invocations:
            rel_query, rel_params = build_invoked_skill_cypher(
                parent_id=parent_id,
                child_id=child_id,
            )
            queries.append((rel_query, rel_params))

    results = _run_with_driver(args, queries)

    if not results[0]:
        logger.warning(
            "skill_run_feedback_degraded",
            msg="Neo4j unavailable; feedback operation skipped",
            skill_run_id=args.skill_run_id,
        )

    # invocations のログ出力
    if args.feedback_file and len(results) > 1:
        invocations = parse_feedback_file(args.feedback_file)
        for i, (parent_id, child_id) in enumerate(invocations):
            if results[i + 1]:
                logger.info(
                    "invoked_skill_created",
                    parent_id=parent_id,
                    child_id=child_id,
                )


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """CLI パーサーを構築する。

    Returns
    -------
    argparse.ArgumentParser
        サブコマンド付きパーサー。
    """
    parser = argparse.ArgumentParser(
        description="SkillRun node CRUD utility for Neo4j",
    )

    # 共通引数（パスワードは環境変数 NEO4J_PASSWORD のみ受付）
    parser.add_argument(
        "--neo4j-uri",
        default=os.environ.get("NEO4J_URI", DEFAULT_NEO4J_URI),
        help=f"Neo4j connection URI (default: {DEFAULT_NEO4J_URI})",
    )
    parser.add_argument(
        "--neo4j-user",
        default=os.environ.get("NEO4J_USER", DEFAULT_NEO4J_USER),
        help=f"Neo4j username (default: {DEFAULT_NEO4J_USER})",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- start ---
    start_parser = subparsers.add_parser("start", help="Create a SkillRun node")
    start_parser.add_argument(
        "--skill-name",
        required=True,
        help="Skill name (from SKILL.md)",
    )
    start_parser.add_argument(
        "--command-source",
        default=None,
        help="Source command that triggered this skill",
    )
    start_parser.add_argument(
        "--input-summary",
        default=None,
        help="Input summary (max 500 chars)",
    )
    start_parser.set_defaults(func=_cmd_start)

    # --- complete ---
    complete_parser = subparsers.add_parser("complete", help="Update SkillRun status")
    complete_parser.add_argument(
        "--skill-run-id",
        required=True,
        help="skill_run_id to update",
    )
    complete_parser.add_argument(
        "--status",
        required=True,
        choices=["success", "failure", "partial", "timeout"],
        help="Completion status",
    )
    complete_parser.add_argument(
        "--duration-ms",
        type=int,
        default=None,
        help="Execution duration in milliseconds",
    )
    complete_parser.add_argument(
        "--output-summary",
        default=None,
        help="Output summary (max 500 chars)",
    )
    complete_parser.add_argument(
        "--error-message",
        default=None,
        help="Error message (for failure/timeout)",
    )
    complete_parser.add_argument(
        "--error-type",
        default=None,
        help="Error type classification",
    )
    complete_parser.set_defaults(func=_cmd_complete)

    # --- feedback ---
    feedback_parser = subparsers.add_parser("feedback", help="Update feedback score")
    feedback_parser.add_argument(
        "--skill-run-id",
        required=True,
        help="skill_run_id to update",
    )
    def _score_type(value: str) -> float:
        v = float(value)
        if not 0.0 <= v <= 1.0:
            msg = f"score must be between 0.0 and 1.0, got {v}"
            raise argparse.ArgumentTypeError(msg)
        return v

    feedback_parser.add_argument(
        "--score",
        type=_score_type,
        required=True,
        help="Quality score 0.0 - 1.0",
    )
    feedback_parser.add_argument(
        "--feedback-file",
        default=None,
        help="JSON file with INVOKED_SKILL invocations",
    )
    feedback_parser.set_defaults(func=_cmd_feedback)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI エントリーポイント。"""
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
