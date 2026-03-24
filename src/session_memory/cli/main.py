"""session_memory CLI main module.

Click サブコマンド群（save / search / bulk-import / stats）を実装し、
Rich Table/Console でリッチ出力を行う。

参照パターン: ``src/rss/cli/main.py``
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from session_memory.chunker import parse_transcript
from session_memory.db import SessionMemoryDB
from session_memory.types import ChunkRow

# ---------------------------------------------------------------------------
# ロガー
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    """Get logger with lazy initialization to avoid circular imports."""
    try:
        from session_memory._logging import get_logger

        return get_logger(__name__, module="cli")
    except ImportError:
        return logging.getLogger(__name__)


logger: Any = _get_logger()

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = Path("data/cache/session_memory.db")
"""デフォルトのDBファイルパス."""

# Rich Console
console = Console()

# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------


def _get_db_path(ctx: click.Context) -> Path:
    """コンテキストからDBパスを取得する.

    Parameters
    ----------
    ctx : click.Context
        Click コンテキスト

    Returns
    -------
    Path
        DBファイルパス
    """
    return ctx.obj.get("db_path", _DEFAULT_DB_PATH)


def _output_json(data: dict[str, Any] | list[dict[str, Any]]) -> None:
    """JSON 形式で出力する.

    Parameters
    ----------
    data : dict[str, Any] | list[dict[str, Any]]
        出力するデータ
    """
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def _truncate(text: str | None, max_length: int = 60) -> str:
    """テキストを指定長で切り詰める.

    Parameters
    ----------
    text : str | None
        切り詰め対象テキスト
    max_length : int, default=60
        最大文字数

    Returns
    -------
    str
        切り詰め後のテキスト
    """
    if text is None:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _configure_log_level(quiet: bool, verbose: bool) -> None:
    """CLI フラグに基づいてログレベルを設定する.

    Parameters
    ----------
    quiet : bool
        ログ出力を抑制
    verbose : bool
        DEBUG ログを有効化
    """
    if quiet:
        logging.getLogger("session_memory").setLevel(logging.CRITICAL)
    elif verbose:
        logging.getLogger("session_memory").setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# CLI グループ
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="memory-cli")
@click.option(
    "--db-path",
    type=click.Path(path_type=Path),
    default=_DEFAULT_DB_PATH,
    help="SQLite DB file path (default: data/cache/session_memory.db)",
)
@click.option("--quiet", "-q", is_flag=True, help="Suppress log output")
@click.option("--verbose", "-v", is_flag=True, help="Enable DEBUG log output")
@click.pass_context
def cli(ctx: click.Context, db_path: Path, quiet: bool, verbose: bool) -> None:
    """Session Memory CLI.

    Save, search, bulk-import, and view stats for session memory chunks.
    """
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path
    ctx.obj["quiet"] = quiet
    _configure_log_level(quiet, verbose)
    logger.debug("CLI started", db_path=str(db_path))


# ---------------------------------------------------------------------------
# save サブコマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--session-id", required=True, help="Session ID")
@click.option("--content", required=True, help="Chunk content text")
@click.option(
    "--role",
    type=click.Choice(["user", "assistant", "system"]),
    default="user",
    help="Speaker role (default: user)",
)
@click.option(
    "--chunk-key", default=None, help="Explicit chunk key (auto-generated if omitted)"
)
@click.option("--token-count", type=int, default=None, help="Token count")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def save(
    ctx: click.Context,
    session_id: str,
    content: str,
    role: str,
    chunk_key: str | None,
    token_count: int | None,
    json_output: bool,
) -> None:
    """Save a chunk to session memory."""
    db_path = _get_db_path(ctx)

    # chunk_key の自動生成
    if chunk_key is None:
        chunk_key = f"{session_id}::{uuid.uuid4().hex[:8]}"

    logger.info(
        "Saving chunk",
        chunk_key=chunk_key,
        session_id=session_id,
        role=role,
    )

    with SessionMemoryDB(db_path) as db:
        db.save_chunk(
            chunk_key=chunk_key,
            session_id=session_id,
            content=content,
            role=role,
            token_count=token_count,
        )

    if json_output:
        _output_json(
            {
                "status": "saved",
                "chunk_key": chunk_key,
                "session_id": session_id,
                "role": role,
                "content_length": len(content),
            }
        )
    else:
        console.print("[green]Chunk saved successfully[/green]")
        console.print(f"  Chunk Key:  {chunk_key}")
        console.print(f"  Session:    {session_id}")
        console.print(f"  Role:       {role}")
        console.print(f"  Length:     {len(content)} chars")

    logger.info("Chunk saved", chunk_key=chunk_key)


# ---------------------------------------------------------------------------
# search サブコマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--query", "-q", required=True, help="Search query text")
@click.option(
    "--mode",
    type=click.Choice(["fts", "vector", "hybrid"]),
    default="fts",
    help="Search mode (default: fts)",
)
@click.option("--limit", type=int, default=10, help="Maximum results (default: 10)")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    mode: str,
    limit: int,
    json_output: bool,
) -> None:
    """Search chunks by FTS full-text search."""
    db_path = _get_db_path(ctx)
    logger.info("Searching", query=query, mode=mode, limit=limit)

    with SessionMemoryDB(db_path) as db:
        if mode != "fts":
            # vector / hybrid は将来実装
            # AIDEV-NOTE: ベクトル検索は embedder 統合後に実装予定
            console.print(
                f"[yellow]Search mode '{mode}' is not yet implemented. "
                f"Using FTS fallback.[/yellow]"
            )
        results = db.search_fts(query, limit)

    if json_output:
        _output_json([_chunk_row_to_dict(r) for r in results])
    else:
        if not results:
            console.print(f"[yellow]No results found for '{query}'[/yellow]")
            return

        table = Table(title=f"Search Results for '{query}'")
        table.add_column("Chunk Key", style="cyan", max_width=20)
        table.add_column("Session", style="green", max_width=15)
        table.add_column("Role")
        table.add_column("Content", max_width=50)
        table.add_column("Created")

        for row in results:
            table.add_row(
                _truncate(row.chunk_key, 20),
                _truncate(row.session_id, 15),
                row.role,
                _truncate(row.content, 50),
                _truncate(row.created_at, 19) if row.created_at else "-",
            )

        console.print(table)
        console.print(f"\nFound {len(results)} results")

    logger.info("Search completed", query=query, count=len(results))


def _search_fts(
    conn: Any,
    query: str,
    limit: int,
) -> list[ChunkRow]:
    """FTS5 全文検索を実行する.

    Parameters
    ----------
    conn : Any
        SQLite 接続
    query : str
        検索クエリ
    limit : int
        最大結果数

    Returns
    -------
    list[ChunkRow]
        検索結果のチャンクリスト
    """
    # FTS5 クエリ: chunks_fts テーブルの rowid と chunks テーブルを結合
    # AIDEV-NOTE: chunks_fts は content カラムのみをインデックスしている
    try:
        cursor = conn.execute(
            """
            SELECT c.chunk_key, c.session_id, c.content, c.role,
                   c.token_count, c.created_at
            FROM chunks_fts AS fts
            JOIN chunks AS c ON fts.rowid = c.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY fts.rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = cursor.fetchall()
    except Exception:
        # FTS テーブルにデータがない場合は LIKE フォールバック
        logger.debug("FTS search failed, falling back to LIKE", query=query)
        cursor = conn.execute(
            """
            SELECT chunk_key, session_id, content, role,
                   token_count, created_at
            FROM chunks
            WHERE content LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        rows = cursor.fetchall()

    return [
        ChunkRow(
            chunk_key=row["chunk_key"],
            session_id=row["session_id"],
            content=row["content"],
            role=row["role"],
            token_count=row["token_count"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def _chunk_row_to_dict(row: ChunkRow) -> dict[str, Any]:
    """ChunkRow を辞書に変換する.

    Parameters
    ----------
    row : ChunkRow
        チャンク行

    Returns
    -------
    dict[str, Any]
        辞書表現
    """
    return {
        "chunk_key": row.chunk_key,
        "session_id": row.session_id,
        "content": row.content,
        "role": row.role,
        "token_count": row.token_count,
        "created_at": row.created_at,
    }


# ---------------------------------------------------------------------------
# bulk-import サブコマンド
# ---------------------------------------------------------------------------


@cli.command(name="bulk-import")
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def bulk_import(
    ctx: click.Context,
    file_path: Path,
    json_output: bool,
) -> None:
    """Bulk-import chunks from a transcript JSONL file.

    FILE_PATH is the path to a transcript.jsonl file.
    """
    db_path = _get_db_path(ctx)
    logger.info("Bulk importing", file_path=str(file_path))

    # JSONL ファイル読み込み
    try:
        lines = file_path.read_text(encoding="utf-8").strip().splitlines()
    except Exception as e:
        logger.error("Failed to read file", error=str(e))
        console.print(f"[red]Error: Failed to read file: {e}[/red]")
        sys.exit(1)

    # parse_transcript でチャンク化
    chunks = parse_transcript(lines)

    # DB に保存
    imported_count = 0
    with SessionMemoryDB(db_path) as db:
        for chunk in chunks:
            db.save_chunk(
                chunk_key=chunk.chunk_key,
                session_id=chunk.session_id,
                content=chunk.content,
                role=chunk.role,
            )
            imported_count += 1

        # インポートログ記録
        if chunks:
            session_id = chunks[0].session_id
            db.log_import(
                session_id=session_id,
                chunk_count=imported_count,
                status="success",
            )

    if json_output:
        _output_json(
            {
                "status": "success",
                "file": str(file_path),
                "chunks_imported": imported_count,
                "session_id": chunks[0].session_id if chunks else None,
            }
        )
    elif imported_count == 0:
        console.print("[yellow]No chunks found in the file[/yellow]")
    else:
        console.print("[green]Bulk import completed[/green]")
        console.print(f"  File:     {file_path}")
        console.print(f"  Chunks:   {imported_count}")
        if chunks:
            console.print(f"  Session:  {chunks[0].session_id}")

    logger.info(
        "Bulk import completed",
        file_path=str(file_path),
        chunks_imported=imported_count,
    )


# ---------------------------------------------------------------------------
# bulk-import-all サブコマンド
# ---------------------------------------------------------------------------


@cli.command(name="bulk-import-all")
@click.option(
    "--projects-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Claude projects directory (default: ~/.claude/projects/)",
)
@click.option(
    "--progress",
    is_flag=True,
    help="Show Rich progress bar",
)
@click.option(
    "--parallel",
    type=int,
    default=1,
    help="Number of parallel workers (default: 1)",
)
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def bulk_import_all(
    ctx: click.Context,
    projects_dir: Path | None,
    progress: bool,
    parallel: int,
    json_output: bool,
) -> None:
    """Bulk-import all sessions from ~/.claude/projects/.

    Walk all project directories under ~/.claude/projects/,
    discover transcript.jsonl files, and import them.
    Already-imported sessions are skipped (resume support).
    """
    from session_memory.cli.bulk_import import run_bulk_import_all

    db_path = _get_db_path(ctx)

    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"

    logger.info(
        "Bulk import all starting",
        projects_dir=str(projects_dir),
        parallel=parallel,
        progress=progress,
    )

    summary = run_bulk_import_all(
        db_path=db_path,
        projects_dir=projects_dir,
        parallel=parallel,
        progress=progress,
    )

    if json_output:
        _output_json(summary)
    else:
        console.print("[bold]Bulk Import All - Summary[/bold]")
        console.print(f"  Discovered:  {summary['total_discovered']} sessions")
        console.print(f"  Imported:    {summary['imported']} sessions")
        console.print(f"  Skipped:     {summary['skipped']} (already imported)")
        console.print(f"  Errors:      {summary['errors']}")
        console.print(f"  Total chunks: {summary['total_chunks']}")

        if summary.get("projects"):
            console.print()
            table = Table(title="Projects")
            table.add_column("Project", style="cyan", max_width=40)
            table.add_column("Imported", justify="right")
            table.add_column("Chunks", justify="right")
            table.add_column("Errors", justify="right")

            for proj_name, proj_data in summary["projects"].items():
                table.add_row(
                    _truncate(proj_name, 40),
                    str(proj_data["imported"]),
                    str(proj_data["chunks"]),
                    str(proj_data["errors"]),
                )

            console.print(table)

    logger.info("Bulk import all command completed")


# ---------------------------------------------------------------------------
# stats サブコマンド
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.pass_context
def stats(
    ctx: click.Context,
    json_output: bool,
) -> None:
    """Show session memory statistics."""
    db_path = _get_db_path(ctx)
    logger.info("Showing stats")

    with SessionMemoryDB(db_path) as db:
        stats_data = db.get_session_stats()

    total_chunks = stats_data["total_chunks"]
    total_sessions = stats_data["total_sessions"]
    sessions_data = stats_data["sessions"]
    import_count = stats_data["import_count"]
    extraction_count = stats_data["extraction_count"]

    if json_output:
        _output_json(
            {
                "total_chunks": total_chunks,
                "total_sessions": total_sessions,
                "total_imports": import_count,
                "total_extractions": extraction_count,
                "sessions": sessions_data,
            }
        )
    else:
        console.print("[bold]Session Memory Statistics[/bold]")
        console.print(f"  Total chunks:      {total_chunks}")
        console.print(f"  Total sessions:    {total_sessions}")
        console.print(f"  Import logs:       {import_count}")
        console.print(f"  Extraction logs:   {extraction_count}")

        if sessions_data:
            console.print()
            table = Table(title="Sessions")
            table.add_column("Session ID", style="cyan", max_width=20)
            table.add_column("Chunks", justify="right")
            table.add_column("First Chunk")
            table.add_column("Last Chunk")

            for row in sessions_data:
                table.add_row(
                    _truncate(row["session_id"], 20),
                    str(row["chunk_count"]),
                    _truncate(row["first_chunk"], 19) if row["first_chunk"] else "-",
                    _truncate(row["last_chunk"], 19) if row["last_chunk"] else "-",
                )

            console.print(table)

    logger.info(
        "Stats displayed", total_chunks=total_chunks, total_sessions=total_sessions
    )


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------


__all__ = ["cli"]


if __name__ == "__main__":
    cli()
