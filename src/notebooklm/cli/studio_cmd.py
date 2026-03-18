"""Studio subcommands for the nlm CLI."""

from __future__ import annotations

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


@click.group()
def studio() -> None:
    """Studio コンテンツの生成（レポート・スライド・インフォグラフィック・データテーブル）。"""


@studio.command("generate")
@click.argument("notebook_id")
@click.option(
    "--type",
    "-t",
    "content_type",
    type=click.Choice(["report", "infographic", "slides", "data_table"]),
    default="report",
    help="コンテンツタイプ (default: report)",
)
@click.option(
    "--format",
    "-f",
    "report_format",
    type=click.Choice(["custom", "briefing_doc", "study_guide", "blog_post"]),
    default=None,
    help="レポートフォーマット（report タイプ時のみ）",
)
@click.pass_context
@run_async
async def generate_cmd(
    ctx: click.Context,
    notebook_id: str,
    content_type: str,
    report_format: str | None,
) -> None:
    """Studio コンテンツを生成する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.studio import StudioService

    click.echo(f"Studio コンテンツを生成中... (type={content_type})")

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = StudioService(manager)

        kwargs: dict = {"notebook_id": notebook_id, "content_type": content_type}
        if report_format and content_type == "report":
            kwargs["report_format"] = report_format

        result = await service.generate_content(**kwargs)

        if ctx.obj.get("json_output"):
            output_json(result)
        else:
            output_success(
                f"生成完了: {result.content_type} — {result.title} "
                f"({result.generation_time_seconds:.1f}秒)"
            )
            if result.text_content:
                click.echo(f"\n{result.text_content}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
