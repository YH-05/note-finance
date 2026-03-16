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
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import structlog

from note_publisher.browser_client import NoteBrowserClient
from note_publisher.config import load_config
from note_publisher.draft_publisher import DraftPublisher

logger = structlog.get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Build and parse CLI arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments containing ``article_dir``, ``dry_run``,
        ``no_update_meta``, and ``login_only``.
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
    return parser.parse_args()


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
