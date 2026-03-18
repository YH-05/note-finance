"""Main CLI entry point for nlm (NotebookLM browser automation).

Usage
-----
.. code-block:: bash

    nlm [--session-file PATH] [--headless/--no-headless] [--json] COMMAND
    nlm notebook list
    nlm chat ask NOTEBOOK_ID "質問テキスト"
"""

from __future__ import annotations

import click

from notebooklm.cli.audio_cmd import audio
from notebooklm.cli.chat_cmd import chat
from notebooklm.cli.note_cmd import note
from notebooklm.cli.notebook_cmd import notebook
from notebooklm.cli.session_cmd import session
from notebooklm.cli.source_cmd import source
from notebooklm.cli.studio_cmd import studio
from notebooklm.cli.workflow_cmd import workflow


@click.group()
@click.option(
    "--session-file",
    type=click.Path(),
    default=None,
    help="Session file path (default: .notebooklm-session.json)",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode (default: headless)",
)
@click.option(
    "--json",
    "json_output",
    is_flag=True,
    default=False,
    help="Output as JSON",
)
@click.pass_context
def cli(
    ctx: click.Context,
    session_file: str | None,
    headless: bool,
    json_output: bool,
) -> None:
    """nlm — NotebookLM ブラウザ自動化 CLI."""
    ctx.ensure_object(dict)
    ctx.obj["session_file"] = session_file
    ctx.obj["headless"] = headless
    ctx.obj["json_output"] = json_output


cli.add_command(notebook)
cli.add_command(source)
cli.add_command(chat)
cli.add_command(note)
cli.add_command(audio)
cli.add_command(studio)
cli.add_command(session)
cli.add_command(workflow)
