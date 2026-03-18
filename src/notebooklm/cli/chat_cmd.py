"""Chat subcommands for the nlm CLI (most critical feature).

Includes single-question chat and batch processing with the proven
3-question-per-batch + page-reload pattern.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import click

from notebooklm.cli._async import run_async
from notebooklm.cli._output import output_error, output_json, output_success


def _save_batch_results(output_dir: str, summary: dict, results: list[dict]) -> None:
    """Save batch results to JSON and Markdown files."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")

    json_path = out_path / f"batch_results_{ts}.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    md_path = out_path / f"batch_results_{ts}.md"
    md_lines = [f"# Batch Q&A — {ts}\n"]
    for r in results:
        md_lines.append(f"## Q{r['index'] + 1}: {r['question']}\n")
        md_lines.append(f"{r['answer']}\n")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    click.echo(f"結果保存: {json_path}")
    click.echo(f"Markdown: {md_path}")


@click.group()
def chat() -> None:
    """チャット操作（質問・バッチ・履歴・設定）。"""


@chat.command("ask")
@click.argument("notebook_id")
@click.argument("question")
@click.pass_context
@run_async
async def ask_cmd(ctx: click.Context, notebook_id: str, question: str) -> None:
    """単一の質問を送信し、回答を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = ChatService(manager)
        response = await service.chat(notebook_id, question)

        if ctx.obj.get("json_output"):
            output_json(response)
        else:
            click.echo(f"Q: {response.question}\n")
            click.echo(f"A: {response.answer}")
            if response.citations:
                click.echo(f"\nCitations: {', '.join(response.citations)}")
            if response.suggested_followups:
                click.echo("\nFollow-ups:")
                for fu in response.suggested_followups:
                    click.echo(f"  - {fu}")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@chat.command("batch")
@click.argument("notebook_id")
@click.option(
    "--file",
    "-f",
    "questions_file",
    required=True,
    type=click.Path(exists=True),
    help="質問ファイル（1行1質問）",
)
@click.option(
    "--batch-size",
    default=3,
    type=int,
    help="バッチごとの質問数（リロード間隔、default: 3）",
)
@click.option(
    "--output-dir",
    "-o",
    default=None,
    type=click.Path(),
    help="結果の出力先ディレクトリ",
)
@click.pass_context
@run_async
async def batch_cmd(
    ctx: click.Context,
    notebook_id: str,
    questions_file: str,
    batch_size: int,
    output_dir: str | None,
) -> None:
    """ファイルから質問を読み込み、バッチ処理で回答を収集する。

    3問バッチ + ページリロードの実証済みパターンで処理。
    """
    from notebooklm._logging import get_logger
    from notebooklm.browser.helpers import navigate_to_notebook
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService

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

    click.echo(f"質問数: {len(questions)}, バッチサイズ: {batch_size}")

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    results: list[dict] = []
    errors: list[dict] = []

    try:
        await manager._ensure_browser()
        service = ChatService(manager)

        for i, question in enumerate(questions):
            batch_num = i // batch_size
            pos_in_batch = i % batch_size

            if pos_in_batch == 0 and i > 0:
                click.echo(f"  [バッチ {batch_num}] ページリロード中...")
                logger.info(
                    "Batch reload",
                    batch_num=batch_num,
                    completed=i,
                    total=len(questions),
                )

            click.echo(f"  [{i + 1}/{len(questions)}] {question[:60]}...")

            try:
                response = await service.chat(notebook_id, question)
                results.append(
                    {
                        "index": i,
                        "question": response.question,
                        "answer": response.answer,
                        "citations": response.citations,
                    }
                )
            except Exception as e:
                logger.error("Batch question failed", index=i, error=str(e))
                errors.append({"index": i, "question": question, "error": str(e)})

        # Output results
        summary = {
            "notebook_id": notebook_id,
            "total": len(questions),
            "succeeded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

        if ctx.obj.get("json_output"):
            output_json(summary)
        else:
            click.echo(
                f"\n完了: {len(results)}/{len(questions)} 成功 ({len(errors)} 失敗)"
            )

        if output_dir:
            _save_batch_results(output_dir, summary, results)

    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@chat.command("history")
@click.argument("notebook_id")
@click.pass_context
@run_async
async def history_cmd(ctx: click.Context, notebook_id: str) -> None:
    """チャット履歴を取得する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = ChatService(manager)
        history = await service.get_chat_history(notebook_id)

        if ctx.obj.get("json_output"):
            output_json(history)
        else:
            click.echo(f"メッセージ数: {history.total_messages}")
            for msg in history.messages:
                click.echo(f"\nQ: {msg.question}")
                click.echo(f"A: {msg.answer[:200]}...")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@chat.command("clear")
@click.argument("notebook_id")
@click.option("--yes", "-y", is_flag=True, help="確認をスキップ")
@click.pass_context
@run_async
async def clear_cmd(ctx: click.Context, notebook_id: str, yes: bool) -> None:
    """チャット履歴をクリアする。"""
    if not yes:
        click.confirm("チャット履歴をクリアしますか？", abort=True)

    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = ChatService(manager)
        await service.clear_chat_history(notebook_id)
        output_success("チャット履歴をクリアしました。")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@chat.command("configure")
@click.argument("notebook_id")
@click.option("--prompt", "-p", required=True, help="システムプロンプト")
@click.pass_context
@run_async
async def configure_cmd(ctx: click.Context, notebook_id: str, prompt: str) -> None:
    """チャットのシステムプロンプトを設定する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = ChatService(manager)
        await service.configure_chat(notebook_id, prompt)
        output_success("システムプロンプトを設定しました。")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()


@chat.command("save-to-note")
@click.argument("notebook_id")
@click.argument("question")
@click.pass_context
@run_async
async def save_to_note_cmd(ctx: click.Context, notebook_id: str, question: str) -> None:
    """質問を送信し、回答をノートに保存する。"""
    from notebooklm.browser.manager import NotebookLMBrowserManager
    from notebooklm.services.chat import ChatService

    manager = NotebookLMBrowserManager(
        session_file=ctx.obj.get("session_file"),
        headless=ctx.obj.get("headless", True),
    )
    try:
        await manager._ensure_browser()
        service = ChatService(manager)
        await service.save_response_to_note(notebook_id, question)
        output_success("回答をノートに保存しました。")
    except Exception as e:
        output_error(str(e))
    finally:
        await manager.close()
