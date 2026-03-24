"""~/.claude/projects/ 全走査バルクインポート.

全 Claude Code プロジェクトディレクトリを走査し、
未インポートのセッション transcript.jsonl を一括取り込みする。

主な機能:
- ``discover_sessions()`` でプロジェクト別にセッションを発見
- ``filter_already_imported()`` で import_log による中断再開
- ``import_single_session()`` で単一セッションをインポート
- ``--progress`` で Rich 進捗バー表示
- ``--parallel N`` で並列インポート（デフォルト: 1）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from session_memory._logging import get_logger
from session_memory.chunker import parse_transcript
from session_memory.db import SessionMemoryDB

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_PROJECTS_DIR = Path.home() / ".claude" / "projects"
"""デフォルトの Claude Code プロジェクトディレクトリ."""

# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionInfo:
    """発見されたセッションの情報.

    Parameters
    ----------
    session_id : str
        セッションID（ファイル名から拡張子を除いたもの）
    transcript_path : Path
        transcript.jsonl のフルパス
    project_dir_name : str
        所属するプロジェクトディレクトリ名
    """

    session_id: str
    transcript_path: Path
    project_dir_name: str


@dataclass(frozen=True)
class ImportResult:
    """単一セッションのインポート結果.

    Parameters
    ----------
    session_id : str
        セッションID
    status : str
        結果ステータス（"success" / "skipped" / "error"）
    chunk_count : int
        インポートしたチャンク数
    error_message : str
        エラーメッセージ（エラー時のみ）
    project_dir_name : str
        所属するプロジェクトディレクトリ名
    """

    session_id: str
    status: str
    chunk_count: int = 0
    error_message: str = ""
    project_dir_name: str = ""


# ---------------------------------------------------------------------------
# 公開関数
# ---------------------------------------------------------------------------


def discover_sessions(projects_dir: Path) -> list[SessionInfo]:
    """プロジェクトディレクトリ配下の全セッション transcript を発見する.

    Parameters
    ----------
    projects_dir : Path
        Claude Code プロジェクトディレクトリ（~/.claude/projects/）

    Returns
    -------
    list[SessionInfo]
        発見されたセッション情報のリスト
    """
    if not projects_dir.exists() or not projects_dir.is_dir():
        logger.debug(
            "Projects directory not found",
            path=str(projects_dir),
        )
        return []

    sessions: list[SessionInfo] = []

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue

        for jsonl_file in sorted(project_dir.iterdir()):
            if not jsonl_file.is_file():
                continue
            if jsonl_file.suffix != ".jsonl":
                continue

            session_id = jsonl_file.stem
            sessions.append(
                SessionInfo(
                    session_id=session_id,
                    transcript_path=jsonl_file,
                    project_dir_name=project_dir.name,
                )
            )

    logger.info(
        "Sessions discovered",
        total=len(sessions),
        projects_dir=str(projects_dir),
    )
    return sessions


def filter_already_imported(
    db: SessionMemoryDB,
    sessions: list[SessionInfo],
) -> list[SessionInfo]:
    """import_log に存在するセッションをフィルタする.

    Parameters
    ----------
    db : SessionMemoryDB
        DB インスタンス（オープン済み）
    sessions : list[SessionInfo]
        チェック対象のセッションリスト

    Returns
    -------
    list[SessionInfo]
        未インポートのセッションのみ
    """
    filtered: list[SessionInfo] = []
    for session in sessions:
        logs = db.get_import_logs(session.session_id)
        if any(log["status"] == "success" for log in logs):
            logger.debug(
                "Session already imported, skipping",
                session_id=session.session_id,
            )
            continue
        filtered.append(session)

    logger.info(
        "Filtered already imported sessions",
        total=len(sessions),
        remaining=len(filtered),
        skipped=len(sessions) - len(filtered),
    )
    return filtered


def import_single_session(
    db: SessionMemoryDB,
    session: SessionInfo,
) -> ImportResult:
    """単一セッションをインポートする.

    transcript.jsonl を読み込み、チャンク化して DB に保存し、
    import_log を記録する。

    Parameters
    ----------
    db : SessionMemoryDB
        DB インスタンス（オープン済み）
    session : SessionInfo
        インポート対象のセッション情報

    Returns
    -------
    ImportResult
        インポート結果
    """
    logger.info(
        "Importing session",
        session_id=session.session_id,
        project=session.project_dir_name,
    )

    # transcript.jsonl 読み込み
    try:
        lines = session.transcript_path.read_text(encoding="utf-8").strip().splitlines()
    except Exception as e:
        logger.error(
            "Failed to read transcript",
            session_id=session.session_id,
            error=str(e),
        )
        return ImportResult(
            session_id=session.session_id,
            status="error",
            error_message=f"Failed to read file: {e}",
            project_dir_name=session.project_dir_name,
        )

    # チャンク化
    chunks = parse_transcript(lines)
    if not chunks:
        logger.debug(
            "No chunks extracted",
            session_id=session.session_id,
        )
        db.log_import(
            session_id=session.session_id,
            chunk_count=0,
            status="success",
        )
        return ImportResult(
            session_id=session.session_id,
            status="success",
            chunk_count=0,
            project_dir_name=session.project_dir_name,
        )

    # DB に保存
    saved = 0
    for chunk in chunks:
        db.save_chunk(
            chunk_key=chunk.chunk_key,
            session_id=chunk.session_id,
            content=chunk.content,
            role=chunk.role,
        )
        saved += 1

    # import_log 記録
    db.log_import(
        session_id=session.session_id,
        chunk_count=saved,
        status="success",
    )

    # コミット（中断再開のため各セッション毎にコミット）
    conn = db._require_conn()
    conn.commit()

    logger.info(
        "Session imported",
        session_id=session.session_id,
        chunk_count=saved,
    )
    return ImportResult(
        session_id=session.session_id,
        status="success",
        chunk_count=saved,
        project_dir_name=session.project_dir_name,
    )


def run_bulk_import_all(
    *,
    db_path: Path,
    projects_dir: Path,
    parallel: int = 1,
    progress: bool = False,
) -> dict[str, Any]:
    """全プロジェクトの全セッションをバルクインポートする.

    Parameters
    ----------
    db_path : Path
        SQLite DB パス
    projects_dir : Path
        Claude Code プロジェクトディレクトリ
    parallel : int
        並列数（現在は逐次実行、将来対応）
    progress : bool
        Rich 進捗バー表示の有無

    Returns
    -------
    dict[str, Any]
        インポート結果のサマリー
    """
    logger.info(
        "Bulk import all started",
        projects_dir=str(projects_dir),
        parallel=parallel,
        progress=progress,
    )

    # Phase 1: セッション発見
    all_sessions = discover_sessions(projects_dir)
    if not all_sessions:
        logger.info("No sessions found")
        return {
            "status": "success",
            "total_discovered": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "total_chunks": 0,
            "projects": {},
            "results": [],
        }

    # Phase 2: 重複フィルタ
    with SessionMemoryDB(db_path) as db:
        pending = filter_already_imported(db, all_sessions)

    skipped_count = len(all_sessions) - len(pending)

    if not pending:
        logger.info(
            "All sessions already imported",
            total=len(all_sessions),
        )
        return {
            "status": "success",
            "total_discovered": len(all_sessions),
            "imported": 0,
            "skipped": skipped_count,
            "errors": 0,
            "total_chunks": 0,
            "projects": {},
            "results": [],
        }

    # Phase 3: インポート実行
    results: list[ImportResult] = []
    total_chunks = 0

    if progress:
        try:
            from rich.progress import Progress

            with Progress() as rich_progress:
                task = rich_progress.add_task(
                    "Importing sessions...",
                    total=len(pending),
                )
                with SessionMemoryDB(db_path) as db:
                    for session in pending:
                        result = import_single_session(db, session)
                        results.append(result)
                        total_chunks += result.chunk_count
                        rich_progress.advance(task)
        except ImportError:
            # Rich 未インストール時はフォールバック
            logger.debug("Rich not available, falling back to plain progress")
            with SessionMemoryDB(db_path) as db:
                for session in pending:
                    result = import_single_session(db, session)
                    results.append(result)
                    total_chunks += result.chunk_count
    else:
        with SessionMemoryDB(db_path) as db:
            for session in pending:
                result = import_single_session(db, session)
                results.append(result)
                total_chunks += result.chunk_count

    # Phase 4: 結果集計
    imported_count = sum(1 for r in results if r.status == "success")
    error_count = sum(1 for r in results if r.status == "error")

    # プロジェクト別集計
    projects_summary: dict[str, dict[str, int]] = {}
    for r in results:
        if r.project_dir_name not in projects_summary:
            projects_summary[r.project_dir_name] = {
                "imported": 0,
                "chunks": 0,
                "errors": 0,
            }
        if r.status == "success":
            projects_summary[r.project_dir_name]["imported"] += 1
            projects_summary[r.project_dir_name]["chunks"] += r.chunk_count
        elif r.status == "error":
            projects_summary[r.project_dir_name]["errors"] += 1

    summary = {
        "status": "success",
        "total_discovered": len(all_sessions),
        "imported": imported_count,
        "skipped": skipped_count,
        "errors": error_count,
        "total_chunks": total_chunks,
        "projects": projects_summary,
        "results": [
            {
                "session_id": r.session_id,
                "status": r.status,
                "chunk_count": r.chunk_count,
                "project": r.project_dir_name,
                "error": r.error_message or None,
            }
            for r in results
        ],
    }

    logger.info(
        "Bulk import all completed",
        total_discovered=len(all_sessions),
        imported=imported_count,
        skipped=skipped_count,
        errors=error_count,
        total_chunks=total_chunks,
    )
    return summary


__all__ = [
    "ImportResult",
    "SessionInfo",
    "discover_sessions",
    "filter_already_imported",
    "import_single_session",
    "run_bulk_import_all",
]
