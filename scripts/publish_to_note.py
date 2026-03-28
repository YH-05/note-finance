#!/usr/bin/env python3
"""note.com 下書き投稿 CLI。

記事ディレクトリを指定して note.com に下書き投稿する。
Playwright を使ったブラウザ自動化で note.com エディタを操作する。

Usage
-----
通常実行::

    uv run python scripts/publish_to_note.py articles/asset_management/my-article

ドライラン（パースのみ）::

    uv run python scripts/publish_to_note.py articles/asset_management/my-article --dry-run

メタデータ更新なし::

    uv run python scripts/publish_to_note.py articles/asset_management/my-article --no-update-meta

ログインのみ（セッション保存）::

    uv run python scripts/publish_to_note.py --login-only

Creator モード（mitsuki note.com 投稿）::

    uv run python scripts/publish_to_note.py \\
      --creator-mode \\
      creator/mitsuki/drafts/week_2026-03-31/day_1_月
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import structlog

from note_publisher.browser_client import NoteBrowserClient
from note_publisher.config import load_config
from note_publisher.draft_publisher import DraftPublisher
from note_publisher.markdown_parser import parse_draft
from note_publisher.types import ArticleDraft, ContentBlock

logger = structlog.get_logger(__name__)


def parse_note_article_md(note_file: Path) -> tuple[str, str]:
    """Parse note_article.md and extract title and body.

    The first line starting with ``# `` is treated as the title.
    All remaining non-empty lines form the body.

    Parameters
    ----------
    note_file : Path
        Path to ``note_article.md``.

    Returns
    -------
    tuple[str, str]
        ``(title, body)`` where *title* is stripped of the ``# `` prefix
        and *body* is the Markdown text after the title line.

    Raises
    ------
    FileNotFoundError
        When ``note_file`` does not exist.
    ValueError
        When no ``# `` heading line is found in the file.
    """
    if not note_file.exists():
        error_msg = f"note_article.md が見つかりません: {note_file}"
        logger.error("note_article_not_found", path=str(note_file))
        raise FileNotFoundError(error_msg)

    content = note_file.read_text(encoding="utf-8")
    lines = content.split("\n")

    title: str | None = None
    title_index: int = -1
    for i, line in enumerate(lines):
        stripped = line.lstrip("#").strip()
        if line.startswith("#") and stripped:
            title = stripped
            title_index = i
            break

    if title is None:
        error_msg = f"タイトル行（# ...）が見つかりません: {note_file}"
        logger.error("note_article_title_not_found", path=str(note_file))
        raise ValueError(error_msg)

    body_lines = lines[title_index + 1 :]
    body = "\n".join(body_lines).strip()

    logger.debug(
        "note_article_parsed",
        title=title,
        body_length=len(body),
    )
    return title, body


def _strip_markdown_inline(text: str) -> str:
    """Remove inline markdown markers (**bold**, *italic*) from text.

    note.com's editor does not auto-convert markdown inline syntax,
    so these markers would appear literally if left in place.
    """
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    return text


def _build_article_draft_from_text(title: str, body: str) -> ArticleDraft:
    """Convert plain title + body text into an ArticleDraft.

    Each non-empty line of the body is wrapped in a paragraph block.
    Markdown heading lines (``##``, ``###``) are converted to heading blocks.

    Parameters
    ----------
    title : str
        Article title.
    body : str
        Markdown body text.

    Returns
    -------
    ArticleDraft
        An ArticleDraft ready for publishing via DraftPublisher.
    """
    blocks: list[ContentBlock] = []
    for line in body.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            blocks.append(
                ContentBlock(
                    block_type="heading",
                    content=stripped.lstrip("#").strip(),
                    level=3,
                )
            )
        elif stripped.startswith("## "):
            blocks.append(
                ContentBlock(
                    block_type="heading",
                    content=stripped.lstrip("#").strip(),
                    level=2,
                )
            )
        elif stripped.startswith("# "):
            blocks.append(
                ContentBlock(
                    block_type="heading",
                    content=stripped.lstrip("#").strip(),
                    level=1,
                )
            )
        elif stripped.startswith("- "):
            blocks.append(
                ContentBlock(
                    block_type="list_item",
                    content=_strip_markdown_inline(stripped[2:]),
                )
            )
        elif re.match(r"^\d+\. ", stripped):
            # 番号付きリスト: "1. text" → content="text"（番号はnote.comが自動付与）
            content = re.sub(r"^\d+\. ", "", stripped)
            blocks.append(
                ContentBlock(
                    block_type="numbered_list_item",
                    content=_strip_markdown_inline(content),
                )
            )
        elif stripped.startswith("> "):
            blocks.append(
                ContentBlock(
                    block_type="blockquote",
                    content=stripped[2:],
                )
            )
        elif stripped == "---":
            blocks.append(ContentBlock(block_type="separator", content=""))
        elif re.match(r"^#\S", stripped):
            # ハッシュタグ行: 前に2行の空行を挿入してから段落として追加
            blocks.append(ContentBlock(block_type="paragraph", content=""))
            blocks.append(ContentBlock(block_type="paragraph", content=""))
            blocks.append(ContentBlock(block_type="paragraph", content=stripped))
        else:
            blocks.append(ContentBlock(block_type="paragraph", content=_strip_markdown_inline(stripped)))

    # 目次ブロックを最初の見出しの直前に自動挿入する。
    # intro 段落の後・最初の ## 見出しの前に配置する（エディタに文字が入力済みの状態で
    # 挿入することで "+" ボタンが確実に現れる）。
    first_heading_idx = next(
        (i for i, b in enumerate(blocks) if b.block_type == "heading"),
        None,
    )
    if first_heading_idx is not None:
        blocks.insert(first_heading_idx, ContentBlock(block_type="toc", content=""))

    return ArticleDraft(title=title, body_blocks=blocks)


async def run_creator_mode_publish(
    article_dir: Path,
) -> tuple[int, str | None]:
    """Publish note_article.md from a creator day directory to note.com.

    Reads ``note_article.md`` from *article_dir*, builds an
    :class:`ArticleDraft` from the content, then uses
    :class:`~note_publisher.draft_publisher.DraftPublisher` to post it.

    Parameters
    ----------
    article_dir : Path
        Path to a creator day directory, e.g.
        ``creator/mitsuki/drafts/week_2026-03-31/day_1_月``.

    Returns
    -------
    tuple[int, str | None]
        ``(exit_code, draft_url)`` where *exit_code* is ``0`` on success
        and ``1`` on failure, and *draft_url* is the URL of the created
        draft (``None`` on failure).
    """
    logger.info("creator_mode_publish_started", article_dir=str(article_dir))

    note_file = article_dir / "note_article.md"
    try:
        title, body = parse_note_article_md(note_file)
    except (FileNotFoundError, ValueError) as exc:
        logger.error("creator_mode_parse_failed", error=str(exc))
        return 1, None

    draft = _build_article_draft_from_text(title, body)

    publisher = DraftPublisher()
    result = await publisher._execute_browser_publish(draft)

    if result.success:
        logger.info(
            "creator_mode_publish_success",
            draft_url=result.draft_url,
            article_dir=str(article_dir),
        )
        return 0, result.draft_url

    logger.error(
        "creator_mode_publish_failed",
        error=result.error_message,
        article_dir=str(article_dir),
    )
    return 1, None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Build and parse CLI arguments.

    Parameters
    ----------
    argv : list[str] | None
        Argument list to parse.  When ``None``, ``sys.argv[1:]`` is used.

    Returns
    -------
    argparse.Namespace
        Parsed arguments containing ``article_dir``, ``dry_run``,
        ``no_update_meta``, ``login_only``, and ``creator_mode``.
    """
    parser = argparse.ArgumentParser(
        description="note.com に記事を下書き投稿する",
    )
    parser.add_argument(
        "article_dir",
        type=Path,
        nargs="?",
        help="記事ディレクトリのパス",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Markdownパースのみ実行（ブラウザ操作なし）",
    )
    parser.add_argument(
        "--no-update-meta",
        action="store_true",
        help="メタデータファイルを更新しない",
    )
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="ログインしてセッションを保存するだけ",
    )
    parser.add_argument(
        "--creator-mode",
        action="store_true",
        help=(
            "creator モード: note_article.md を読み込んで note.com に直接投稿する。"
            " article_dir には creator/{account}/drafts/{week}/{day} を指定する。"
        ),
    )
    return parser.parse_args(argv)


async def run_login_only() -> int:
    """Launch the browser and wait for manual login.

    Persists the session state so that subsequent runs can skip login.

    Returns
    -------
    int
        Exit code (0 on success).
    """
    config = load_config()
    async with NoteBrowserClient(config) as client:
        await client.wait_for_manual_login(timeout_sec=300)
    logger.info("login_session_saved")
    return 0


async def run_publish(article_dir: Path, *, dry_run: bool, update_meta: bool) -> int:
    """Run the publish workflow.

    Parameters
    ----------
    article_dir : Path
        Path to the article directory.
    dry_run : bool
        If ``True``, only parse the Markdown (no browser operations).
    update_meta : bool
        If ``True``, update article metadata after publishing.

    Returns
    -------
    int
        Exit code (0 on success, 1 on failure).
    """
    publisher = DraftPublisher()

    if dry_run:
        draft = publisher.dry_run(article_dir)
        logger.info(
            "dry_run_result",
            title=draft.title,
            blocks=len(draft.body_blocks),
        )
        return 0

    result = await publisher.publish(article_dir, update_meta=update_meta)
    if result.success:
        logger.info("publish_success", draft_url=result.draft_url)
        if result.draft_url:
            print(result.draft_url)
        return 0

    logger.error("publish_failed", error=result.error_message)
    return 1


def main() -> None:
    """CLI entrypoint for note.com draft publishing."""
    args = parse_args()

    if args.login_only:
        code = asyncio.run(run_login_only())
        sys.exit(code)

    if args.article_dir is None:
        print(
            "エラー: article_dir は --login-only 以外では必須です",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.creator_mode:
        code, draft_url = asyncio.run(run_creator_mode_publish(args.article_dir))
        if code == 0 and draft_url:
            # Print draft_url to stdout so callers (e.g. auto_poster.py) can capture it
            print(draft_url)
        sys.exit(code)

    code = asyncio.run(
        run_publish(
            args.article_dir,
            dry_run=args.dry_run,
            update_meta=not args.no_update_meta,
        )
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
