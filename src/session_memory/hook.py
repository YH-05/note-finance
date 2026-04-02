"""SessionEnd Hook エントリポイント.

Claude Code の SessionEnd イベントを受けて、会話トランスクリプトを
チャンク化し、SQLite + Neo4j に投入する。

処理フロー:
1. stdin JSON → HookInput パース
2. resolve_project() でプロジェクト判定 → 対象外スキップ
3. import_log で重複チェック → 既存ならスキップ
4. transcript.jsonl 読み込み → parse_transcript() でチャンク化
5. チャンク → embedding → SQLite 保存
6. Sonnet 抽出 → linker → Neo4j 投入（非同期、60秒タイムアウト）
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from session_memory._logging import get_logger
from session_memory.chunker import Chunk, parse_transcript, resolve_project
from session_memory.db import SessionMemoryDB

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path("data/cache/session_memory.db")
"""デフォルトの SQLite DB パス."""

_TARGET_PROJECTS: frozenset[str] = frozenset(
    os.environ.get("SESSION_MEMORY_TARGET_PROJECTS", "note-finance").split(",")
)
"""セッションメモリ投入対象のプロジェクト名（SESSION_MEMORY_TARGET_PROJECTS でカンマ区切り指定可）."""

_NEO4J_TIMEOUT_SECONDS = 60
"""Neo4j パイプラインのタイムアウト（秒）."""

_CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
"""Claude Code のプロジェクトディレクトリ."""


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HookInput:
    """SessionEnd Hook の入力データ.

    Parameters
    ----------
    session_id : str
        セッションID
    cwd : str
        作業ディレクトリ
    duration_ms : int
        セッション時間（ミリ秒）
    num_turns : int
        ターン数
    result : str
        セッション結果
    transcript_path : str | None
        transcript.jsonl のパス（None の場合は推定）
    """

    session_id: str
    cwd: str
    duration_ms: int = 0
    num_turns: int = 0
    result: str = ""
    transcript_path: str | None = None


# ---------------------------------------------------------------------------
# パース・判定関数
# ---------------------------------------------------------------------------


def parse_hook_input(raw: str) -> HookInput | None:
    """stdin JSON 文字列を HookInput にパースする.

    Parameters
    ----------
    raw : str
        stdin から読み取った JSON 文字列

    Returns
    -------
    HookInput | None
        パース成功時は HookInput、失敗時は None
    """
    if not raw or not raw.strip():
        logger.warning("Empty stdin input")
        return None

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse stdin JSON", raw_length=len(raw))
        return None

    if not isinstance(data, dict):
        logger.warning("stdin JSON is not a dict", type=type(data).__name__)
        return None

    session_id = data.get("session_id", "")
    if not session_id:
        logger.warning("session_id is missing from stdin JSON")
        return None

    return HookInput(
        session_id=session_id,
        cwd=data.get("cwd", ""),
        duration_ms=data.get("duration_ms", 0),
        num_turns=data.get("num_turns", 0),
        result=data.get("result", ""),
        transcript_path=data.get("transcript_path"),
    )


def is_target_project(project_name: str) -> bool:
    """プロジェクト名が投入対象かを判定する.

    Parameters
    ----------
    project_name : str
        解決済みプロジェクト名

    Returns
    -------
    bool
        対象プロジェクトの場合 True
    """
    if not project_name:
        return False
    return project_name in _TARGET_PROJECTS


def is_already_imported(db: SessionMemoryDB, session_id: str) -> bool:
    """セッションが既にインポート済みかを判定する.

    import_log テーブルを確認し、成功レコードが存在すれば True を返す。

    Parameters
    ----------
    db : SessionMemoryDB
        DB インスタンス
    session_id : str
        セッションID

    Returns
    -------
    bool
        インポート済みの場合 True
    """
    logs = db.get_import_logs(session_id)
    return any(log["status"] == "success" for log in logs)


def resolve_transcript_path(hook_input: HookInput) -> Path | None:
    """transcript.jsonl のパスを解決する.

    hook_input.transcript_path が指定されていればそれを使用し、
    未指定の場合は Claude Code の標準パスを推定する。

    Parameters
    ----------
    hook_input : HookInput
        Hook 入力データ

    Returns
    -------
    Path | None
        transcript.jsonl のパス。見つからない場合は None。
    """
    # 明示的に指定されている場合
    if hook_input.transcript_path:
        path = Path(hook_input.transcript_path)
        if path.exists():
            return path
        logger.warning(
            "Specified transcript_path does not exist",
            path=str(path),
        )

    # Claude Code 標準パスを推定
    # ~/.claude/projects/<project-key>/<session-id>.jsonl
    if not _CLAUDE_PROJECTS_DIR.exists():
        logger.debug("Claude projects directory not found")
        return None

    # プロジェクト境界チェック: cwd から解決したプロジェクト名に一致する
    # ディレクトリのみを検索対象とする
    project_name = resolve_project(hook_input.cwd)
    for project_dir in _CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        # プロジェクトディレクトリ名にプロジェクト名が含まれる場合のみ検索
        dir_name = project_dir.name
        if project_name and project_name.replace("/", "-") not in dir_name:
            continue
        candidate = project_dir / f"{hook_input.session_id}.jsonl"
        if candidate.exists():
            logger.debug(
                "Found transcript at Claude standard path",
                path=str(candidate),
            )
            return candidate

    logger.warning(
        "Could not find transcript.jsonl",
        session_id=hook_input.session_id,
    )
    return None


# ---------------------------------------------------------------------------
# SQLite 保存
# ---------------------------------------------------------------------------


def save_chunks_to_sqlite(
    db: SessionMemoryDB,
    chunks: list[Chunk],
) -> int:
    """チャンクリストを SQLite DB に保存する.

    Parameters
    ----------
    db : SessionMemoryDB
        DB インスタンス
    chunks : list[Chunk]
        保存するチャンクリスト

    Returns
    -------
    int
        保存したチャンク数
    """
    saved = 0
    for chunk in chunks:
        db.save_chunk(
            chunk_key=chunk.chunk_key,
            session_id=chunk.session_id,
            content=chunk.content,
            role=chunk.role,
        )
        saved += 1

    if saved > 0:
        logger.info("Chunks saved to SQLite", count=saved)

    return saved


# ---------------------------------------------------------------------------
# Neo4j パイプライン（非同期）
# ---------------------------------------------------------------------------


async def _run_neo4j_pipeline(  # noqa: PLR0911
    chunks: list[Chunk],
    session_id: str,
) -> dict[str, Any]:
    """Sonnet 抽出 + linker + Neo4j 投入の非同期パイプライン.

    Parameters
    ----------
    chunks : list[Chunk]
        チャンクリスト
    session_id : str
        セッションID

    Returns
    -------
    dict[str, Any]
        パイプライン結果
    """
    logger.info(
        "Starting Neo4j pipeline",
        session_id=session_id,
        chunk_count=len(chunks),
    )

    try:
        # Anthropic クライアント初期化
        from anthropic import AsyncAnthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning("ANTHROPIC_API_KEY is not set, skipping Neo4j pipeline")
            return {"status": "skipped", "reason": "ANTHROPIC_API_KEY not set"}
        client = AsyncAnthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic package not installed, skipping Neo4j pipeline")
        return {"status": "skipped", "reason": "anthropic not installed"}
    except Exception:
        logger.warning("Failed to initialize Anthropic client", exc_info=True)
        return {"status": "skipped", "reason": "anthropic client init failed"}

    # Sonnet 抽出
    try:
        from session_memory.extractor import extract_chunks_batch

        texts = [c.content for c in chunks]
        extractions = await extract_chunks_batch(texts, client=client)
        logger.info(
            "Sonnet extraction completed",
            extraction_count=len(extractions),
        )
    except Exception:
        logger.warning("Sonnet extraction failed", exc_info=True)
        return {"status": "partial", "reason": "extraction failed"}

    # Neo4j リンク投入
    try:
        # note-neo4j 接続（環境変数から取得、デフォルトはローカル開発用）
        from neo4j import GraphDatabase

        from session_memory.linker import LinkerConfig, NoteLinker

        neo4j_uri = os.environ.get(
            "NOTE_NEO4J_URI", os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        )
        neo4j_user = os.environ.get("NOTE_NEO4J_USER", "neo4j")
        neo4j_password = os.environ.get("NOTE_NEO4J_PASSWORD", "password")
        driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password),
        )
        linker = NoteLinker(driver=driver, config=LinkerConfig())

        # エンティティリンク
        total_linked = 0
        for extraction in extractions:
            for entity in extraction.entities:
                linker.link_entity(entity.name, entity.entity_type)
                total_linked += 1

        driver.close()

        logger.info(
            "Neo4j pipeline completed",
            linked_entities=total_linked,
        )
        return {
            "status": "success",
            "extractions": len(extractions),
            "linked_entities": total_linked,
        }

    except ImportError:
        logger.warning("neo4j package not installed, skipping linking")
        return {"status": "partial", "reason": "neo4j not installed"}
    except Exception:
        logger.warning("Neo4j pipeline failed", exc_info=True)
        return {"status": "partial", "reason": "neo4j pipeline failed"}


# ---------------------------------------------------------------------------
# メインフロー
# ---------------------------------------------------------------------------


async def run_session_end_hook(
    *,
    hook_input: HookInput,
    db_path: Path = _DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """SessionEnd Hook のメインフロー.

    Parameters
    ----------
    hook_input : HookInput
        パース済みの Hook 入力
    db_path : Path
        SQLite DB パス

    Returns
    -------
    dict[str, Any]
        実行結果の辞書
    """
    logger.info(
        "SessionEnd hook started",
        session_id=hook_input.session_id,
        cwd=hook_input.cwd,
        num_turns=hook_input.num_turns,
    )

    # Step 1: プロジェクト判定
    project = resolve_project(hook_input.cwd)
    if not is_target_project(project):
        logger.info(
            "Non-target project, skipping",
            project=project,
            cwd=hook_input.cwd,
        )
        return {
            "status": "skipped",
            "reason": f"Non-target project: {project}",
            "session_id": hook_input.session_id,
        }

    # Step 2: 重複チェック（DB接続は Step 5 まで再利用）
    with SessionMemoryDB(db_path) as db:
        if is_already_imported(db, hook_input.session_id):
            logger.info(
                "Session already imported, skipping",
                session_id=hook_input.session_id,
            )
            return {
                "status": "skipped",
                "reason": "Already imported (duplicate)",
                "session_id": hook_input.session_id,
            }

        # Step 3: transcript.jsonl 読み込み
        transcript_path = resolve_transcript_path(hook_input)
        if transcript_path is None:
            logger.warning(
                "Transcript not found, skipping",
                session_id=hook_input.session_id,
            )
            return {
                "status": "skipped",
                "reason": "Transcript file not found",
                "session_id": hook_input.session_id,
            }

        try:
            lines = transcript_path.read_text(encoding="utf-8").strip().splitlines()
        except Exception:
            logger.error(
                "Failed to read transcript",
                path=str(transcript_path),
                exc_info=True,
            )
            return {
                "status": "error",
                "reason": "Failed to read transcript",
                "session_id": hook_input.session_id,
            }

        # Step 4: チャンク化
        chunks = parse_transcript(lines)
        if not chunks:
            logger.info(
                "No chunks extracted from transcript",
                session_id=hook_input.session_id,
            )
            return {
                "status": "skipped",
                "reason": "No chunks in transcript",
                "session_id": hook_input.session_id,
                "chunks_saved": 0,
            }

        logger.info(
            "Chunks extracted",
            chunk_count=len(chunks),
            session_id=hook_input.session_id,
        )

        # Step 5: SQLite 保存
        saved_count = save_chunks_to_sqlite(db, chunks)
        db.log_import(
            session_id=hook_input.session_id,
            chunk_count=saved_count,
            status="success",
        )

    # Step 6: Neo4j パイプライン（非同期、タイムアウト付き）
    neo4j_result: dict[str, Any] = {"status": "skipped", "reason": "not attempted"}
    try:
        neo4j_result = await asyncio.wait_for(
            _run_neo4j_pipeline(chunks, hook_input.session_id),
            timeout=_NEO4J_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            "Neo4j pipeline timed out",
            timeout=_NEO4J_TIMEOUT_SECONDS,
        )
        neo4j_result = {"status": "timeout", "reason": "Neo4j pipeline timed out"}
    except Exception:
        logger.warning("Neo4j pipeline failed", exc_info=True)
        neo4j_result = {"status": "error", "reason": "Neo4j pipeline exception"}

    logger.info(
        "SessionEnd hook completed",
        session_id=hook_input.session_id,
        chunks_saved=saved_count,
        neo4j_status=neo4j_result.get("status"),
    )

    return {
        "status": "success",
        "session_id": hook_input.session_id,
        "project": project,
        "chunks_saved": saved_count,
        "neo4j": neo4j_result,
    }


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "HookInput",
    "is_already_imported",
    "is_target_project",
    "parse_hook_input",
    "resolve_transcript_path",
    "run_session_end_hook",
    "save_chunks_to_sqlite",
]
