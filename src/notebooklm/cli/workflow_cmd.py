"""Workflow subcommands for the nlm CLI (composite operations)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


def _save_research_results(
    output_dir: str,
    summary: dict,
    chat_results: list[dict],
    studio_result: dict | None,
) -> None:
    """Save research workflow results to JSON and Markdown files."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

    json_path = out_path / f"research_{ts}.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    md_lines = [f"# Research Workflow — {ts}\n"]
    for r in chat_results:
        md_lines.append(f"## Q{r['index'] + 1}: {r['question']}\n")
        md_lines.append(f"{r['answer']}\n")
    if studio_result and studio_result.get("text_content"):
        md_lines.append("\n---\n## Studio Content\n")
        md_lines.append(studio_result["text_content"])

    md_path = out_path / f"research_{ts}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    click.echo(f"\n結果保存: {json_path}")


@click.group()
def workflow() -> None:
    """ワークフロー（複合操作）。"""


@workflow.command("research")
@click.argument("notebook_id")
@click.option(
    "--questions-file",
    "-q",
    required=True,
    type=click.Path(exists=True),
    help="質問ファイル（1行1質問）",
)
@click.option(
    "--batch-size",
    default=3,
    type=int,
    help="バッチごとの質問数（default: 3）",
)
@click.option(
    "--output-dir",
    "-o",
    default=None,
    type=click.Path(),
    help="結果の出力先ディレクトリ",
)
@click.option(
    "--content-type",
    "-t",
    type=click.Choice(["report", "infographic", "slides", "data_table"]),
    default=None,
    help="チャット後に生成するStudioコンテンツ（省略時はチャットのみ）",
)
@click.pass_context
@run_async
async def research_cmd(
    ctx: click.Context,
    notebook_id: str,
    questions_file: str,
    batch_size: int,
    output_dir: str | None,
    content_type: str | None,
) -> None:
    """リサーチワークフロー: 質問バッチ → (オプション) Studio コンテンツ生成。"""
    from notebooklm._logging import get_logger
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService
    from notebooklm.services.studio import StudioService

    logger = get_logger(__name__)

    questions_path = Path(questions_file)
    questions = [
        line.strip()
        for line in questions_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not questions:
        output_error("質問ファイルに有効な質問がありません。")
        return

    click.echo(f"リサーチワークフロー開始: {len(questions)} 質問")

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )

    chat_results: list[dict] = []
    chat_errors: list[dict] = []
    studio_result = None

    try:
        await manager._ensure_browser()
        chat_svc = ChatService(manager)

        # Phase 1: Batch chat
        click.echo("\n[Phase 1] チャット質問を送信中...")
        for i, question in enumerate(questions):
            pos_in_batch = i % batch_size

            if pos_in_batch == 0 and i > 0:
                click.echo(f"  バッチリロード ({i}/{len(questions)})...")

            click.echo(f"  [{i + 1}/{len(questions)}] {question[:60]}...")

            try:
                response = await chat_svc.chat(notebook_id, question)
                chat_results.append(
                    {
                        "index": i,
                        "question": response.question,
                        "answer": response.answer,
                        "citations": response.citations,
                    }
                )
            except Exception as e:
                logger.error("Question failed", index=i, error=str(e))
                chat_errors.append({"index": i, "question": question, "error": str(e)})

        click.echo(f"  チャット完了: {len(chat_results)}/{len(questions)} 成功")

        # Phase 2: Studio content (optional)
        if content_type:
            click.echo(f"\n[Phase 2] Studio コンテンツ生成 (type={content_type})...")
            studio_svc = StudioService(manager)
            try:
                result = await studio_svc.generate_content(notebook_id, content_type)
                studio_result = result.model_dump(mode="json")
                click.echo(f"  生成完了: {result.title}")
            except Exception as e:
                logger.error("Studio generation failed", error=str(e))
                click.echo(f"  Studio 生成失敗: {e}")

        # Summary
        summary = {
            "notebook_id": notebook_id,
            "workflow": "research",
            "chat": {
                "total": len(questions),
                "succeeded": len(chat_results),
                "failed": len(chat_errors),
                "results": chat_results,
                "errors": chat_errors,
            },
            "studio": studio_result,
        }

        if ctx.obj.get("json_output"):
            output_json(summary)

        if output_dir:
            _save_research_results(output_dir, summary, chat_results, studio_result)

    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
