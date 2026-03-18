"""Audio subcommands for the nlm CLI."""

from __future__ import annotations

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


@click.group()
def audio() -> None:
    """オーディオ概要の生成。"""


@audio.command("generate")
@click.argument("notebook_id")
@click.option("--prompt", "-p", default=None, help="カスタマイズプロンプト")
@click.pass_context
@run_async
async def generate_cmd(
    ctx: click.Context, notebook_id: str, prompt: str | None
) -> None:
    """Audio Overview（ポッドキャスト風オーディオ）を生成する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.audio import AudioService

    click.echo("Audio Overview を生成中... (最大10分)")

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = AudioService(manager)
        result = await service.generate_audio_overview(notebook_id, prompt)

        if ctx.obj.get("json_output"):
            output_json(result)
        else:
            output_success(
                f"生成完了: {result.status} ({result.generation_time_seconds:.1f}秒)"
            )
            if result.audio_url:
                click.echo(f"Audio URL: {result.audio_url}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
