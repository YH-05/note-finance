"""Session management subcommands for the nlm CLI."""

from __future__ import annotations

from pathlib import Path

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success
from notebooklm.constants import DEFAULT_SESSION_FILE


@click.group()
def session() -> None:
    """セッション管理（ステータス確認・クリア）。"""


@session.command("status")
@click.pass_context
@run_async
async def status_cmd(ctx: click.Context) -> None:
    """セッションの状態を確認する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager

    session_file = ctx.obj.get("session_file") or DEFAULT_SESSION_FILE
    session_path = Path(session_file)

    info: dict = {
        "session_file": str(session_path),
        "exists": session_path.exists(),
        "valid": False,
    }

    if session_path.exists():
        manager = NotebookLMBrowserManager(
            session_file=session_file,
            headless=True,
        )
        try:
            await manager._ensure_browser()
            info["valid"] = await manager.is_session_valid()
        except Exception as e:
            info["error"] = str(e)
        finally:
            await manager.close()

    if ctx.obj.get("json_output"):
        output_json(info)
    else:
        click.echo(f"Session file: {info['session_file']}")
        click.echo(f"Exists: {info['exists']}")
        click.echo(f"Valid: {info['valid']}")
        if "error" in info:
            click.echo(f"Error: {info['error']}")


@session.command("clear")
@click.option("--yes", "-y", is_flag=True, help="確認をスキップ")
@click.pass_context
def clear_cmd(ctx: click.Context, yes: bool) -> None:
    """セッションファイルを削除する。"""
    session_file = ctx.obj.get("session_file") or DEFAULT_SESSION_FILE
    session_path = Path(session_file)

    if not session_path.exists():
        output_success("セッションファイルは存在しません。")
        return

    if not yes:
        click.confirm(f"{session_path} を削除しますか？", abort=True)

    session_path.unlink()
    output_success(f"セッションファイルを削除しました: {session_path}")
