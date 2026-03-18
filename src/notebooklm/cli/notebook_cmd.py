"""Notebook subcommands for the nlm CLI."""

from __future__ import annotations

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


@click.group()
def notebook() -> None:
    """ノートブックの管理（一覧・作成・要約・削除）。"""


@notebook.command("list")
@click.pass_context
@run_async
async def list_cmd(ctx: click.Context) -> None:
    """ノートブック一覧を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.notebook import NotebookService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NotebookService(manager)
        notebooks = await service.list_notebooks()

        if ctx.obj.get("json_output"):
            output_json(notebooks)
        else:
            if not notebooks:
                output_success("ノートブックはありません。")
                return
            for nb in notebooks:
                updated = nb.updated_at.isoformat() if nb.updated_at else "N/A"
                click.echo(
                    f"  {nb.notebook_id}  {nb.title}  "
                    f"(sources: {nb.source_count}, updated: {updated})"
                )
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@notebook.command("create")
@click.argument("title")
@click.pass_context
@run_async
async def create_cmd(ctx: click.Context, title: str) -> None:
    """新しいノートブックを作成する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.notebook import NotebookService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NotebookService(manager)
        nb = await service.create_notebook(title)

        if ctx.obj.get("json_output"):
            output_json(nb)
        else:
            output_success(f"作成完了: {nb.notebook_id} ({nb.title})")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@notebook.command("summary")
@click.argument("notebook_id")
@click.pass_context
@run_async
async def summary_cmd(ctx: click.Context, notebook_id: str) -> None:
    """ノートブックのサマリーを取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.notebook import NotebookService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NotebookService(manager)
        summary = await service.get_notebook_summary(notebook_id)

        if ctx.obj.get("json_output"):
            output_json(summary)
        else:
            click.echo(summary.summary_text)
            if summary.suggested_questions:
                click.echo("\n推奨質問:")
                for q in summary.suggested_questions:
                    click.echo(f"  - {q}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@notebook.command("delete")
@click.argument("notebook_id")
@click.option("--yes", "-y", is_flag=True, help="確認をスキップ")
@click.pass_context
@run_async
async def delete_cmd(ctx: click.Context, notebook_id: str, yes: bool) -> None:
    """ノートブックを削除する。"""
    if not yes:
        click.confirm(f"ノートブック {notebook_id} を削除しますか？", abort=True)

    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.notebook import NotebookService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = NotebookService(manager)
        success = await service.delete_notebook(notebook_id)

        if ctx.obj.get("json_output"):
            output_json({"deleted": success, "notebook_id": notebook_id})
        elif success:
            output_success(f"削除完了: {notebook_id}")
        else:
            output_error(f"削除に失敗しました: {notebook_id}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
