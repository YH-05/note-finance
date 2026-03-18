"""Note subcommands for the nlm CLI."""

from __future__ import annotations

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


@click.group()
def note() -> None:
    """メモの管理（一覧・作成・取得・削除）。"""


@note.command("list")
@click.argument("notebook_id")
@click.pass_context
@run_async
async def list_cmd(ctx: click.Context, notebook_id: str) -> None:
    """ノートブック内のメモ一覧を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.note import NoteService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NoteService(manager)
        notes = await service.list_notes(notebook_id)

        if ctx.obj.get("json_output"):
            output_json(notes)
        else:
            if not notes:
                output_success("メモはありません。")
                return
            for i, n in enumerate(notes):
                click.echo(f"  [{i}] {n.title}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@note.command("create")
@click.argument("notebook_id")
@click.option("--title", "-t", default=None, help="メモのタイトル")
@click.option("--content", "-c", required=True, help="メモの内容")
@click.pass_context
@run_async
async def create_cmd(
    ctx: click.Context, notebook_id: str, title: str | None, content: str
) -> None:
    """新しいメモを作成する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.note import NoteService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NoteService(manager)
        n = await service.create_note(notebook_id, content, title)

        if ctx.obj.get("json_output"):
            output_json(n)
        else:
            output_success(f"作成完了: {n.title} ({n.note_id})")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@note.command("get")
@click.argument("notebook_id")
@click.argument("note_index", type=int)
@click.pass_context
@run_async
async def get_cmd(ctx: click.Context, notebook_id: str, note_index: int) -> None:
    """メモの内容を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.note import NoteService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NoteService(manager)
        n = await service.get_note(notebook_id, note_index)

        if ctx.obj.get("json_output"):
            output_json(n)
        else:
            click.echo(f"# {n.title}\n")
            click.echo(n.content)
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@note.command("delete")
@click.argument("notebook_id")
@click.argument("note_index", type=int)
@click.option("--yes", "-y", is_flag=True, help="確認をスキップ")
@click.pass_context
@run_async
async def delete_cmd(
    ctx: click.Context, notebook_id: str, note_index: int, yes: bool
) -> None:
    """メモを削除する。"""
    if not yes:
        click.confirm(f"メモ #{note_index} を削除しますか？", abort=True)

    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.note import NoteService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NoteService(manager)
        await service.delete_note(notebook_id, note_index)
        output_success(f"削除完了: メモ #{note_index}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
