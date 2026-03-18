"""Source subcommands for the nlm CLI."""

from __future__ import annotations

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


@click.group()
def source() -> None:
    """ソースの管理（追加・一覧・詳細・削除・リサーチ）。"""


@source.command("list")
@click.argument("notebook_id")
@click.pass_context
@run_async
async def list_cmd(ctx: click.Context, notebook_id: str) -> None:
    """ノートブック内のソース一覧を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        sources = await service.list_sources(notebook_id)

        if ctx.obj.get("json_output"):
            output_json(sources)
        else:
            if not sources:
                output_success("ソースはありません。")
                return
            for i, src in enumerate(sources):
                click.echo(f"  [{i}] {src.title} ({src.source_type})")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("add-text")
@click.argument("notebook_id")
@click.option("--title", "-t", required=True, help="ソースのタイトル")
@click.option("--content", "-c", required=True, help="テキストコンテンツ")
@click.pass_context
@run_async
async def add_text_cmd(
    ctx: click.Context, notebook_id: str, title: str, content: str
) -> None:
    """テキストソースを追加する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        src = await service.add_text_source(notebook_id, content, title)

        if ctx.obj.get("json_output"):
            output_json(src)
        else:
            output_success(f"追加完了: {src.title} ({src.source_type})")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("add-url")
@click.argument("notebook_id")
@click.option("--url", "-u", required=True, help="ソースURL")
@click.pass_context
@run_async
async def add_url_cmd(ctx: click.Context, notebook_id: str, url: str) -> None:
    """URLソースを追加する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        src = await service.add_url_source(notebook_id, url)

        if ctx.obj.get("json_output"):
            output_json(src)
        else:
            output_success(f"追加完了: {src.title} ({src.source_type})")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("add-file")
@click.argument("notebook_id")
@click.option(
    "--file",
    "-f",
    "file_path",
    required=True,
    type=click.Path(exists=True),
    help="アップロードするファイル",
)
@click.pass_context
@run_async
async def add_file_cmd(ctx: click.Context, notebook_id: str, file_path: str) -> None:
    """ファイルソースをアップロードする。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        src = await service.add_file_source(notebook_id, file_path)

        if ctx.obj.get("json_output"):
            output_json(src)
        else:
            output_success(f"追加完了: {src.title} ({src.source_type})")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("details")
@click.argument("notebook_id")
@click.argument("source_index", type=int)
@click.pass_context
@run_async
async def details_cmd(ctx: click.Context, notebook_id: str, source_index: int) -> None:
    """ソースの詳細情報を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        detail = await service.get_source_details(notebook_id, source_index)

        if ctx.obj.get("json_output"):
            output_json(detail)
        else:
            click.echo(f"Title: {detail.title}")
            click.echo(f"Type: {detail.source_type}")
            if detail.source_url:
                click.echo(f"URL: {detail.source_url}")
            if detail.content_summary:
                click.echo(f"Summary: {detail.content_summary}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("delete")
@click.argument("notebook_id")
@click.argument("source_index", type=int)
@click.option("--yes", "-y", is_flag=True, help="確認をスキップ")
@click.pass_context
@run_async
async def delete_cmd(
    ctx: click.Context, notebook_id: str, source_index: int, yes: bool
) -> None:
    """ソースを削除する。"""
    if not yes:
        click.confirm(f"ソース #{source_index} を削除しますか？", abort=True)

    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        await service.delete_source(notebook_id, source_index)
        output_success(f"削除完了: ソース #{source_index}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("rename")
@click.argument("notebook_id")
@click.argument("source_index", type=int)
@click.option("--name", "-n", required=True, help="新しい名前")
@click.pass_context
@run_async
async def rename_cmd(
    ctx: click.Context, notebook_id: str, source_index: int, name: str
) -> None:
    """ソースの名前を変更する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        await service.rename_source(notebook_id, source_index, name)
        output_success(f"名前変更完了: ソース #{source_index} → {name}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@source.command("research")
@click.argument("notebook_id")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["fast", "deep"]),
    default="fast",
    help="リサーチモード (default: fast)",
)
@click.option(
    "--query", "-q", default=None, help="検索クエリ（省略時はノートブック内容ベース）"
)
@click.pass_context
@run_async
async def research_cmd(
    ctx: click.Context, notebook_id: str, mode: str, query: str | None
) -> None:
    """Webリサーチを実行する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.source import SourceService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = SourceService(manager)
        result = await service.web_research(notebook_id, query=query, mode=mode)

        if ctx.obj.get("json_output"):
            output_json(result)
        else:
            output_success(f"リサーチ完了 (mode={mode})")
            if hasattr(result, "model_dump"):
                for k, v in result.model_dump().items():
                    click.echo(f"  {k}: {v}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
