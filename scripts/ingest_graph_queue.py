#!/usr/bin/env python3
"""NAS の graph-queue ファイルを research-neo4j に一括投入するスクリプト.

Mac Mini でスクレイピング（--skip-neo4j）→ NAS に graph-queue 保存
→ このスクリプトでメインマシンから Neo4j に投入、という2段構成で使用する。

処理済みファイルは processed/ サブディレクトリに移動する（MERGE ベースで冪等性あり）。

Usage
-----
::

    # 未処理ファイルを全投入（デフォルト: NAS の graph-queue ディレクトリ）
    uv run python scripts/ingest_graph_queue.py

    # ディレクトリを明示指定
    uv run python scripts/ingest_graph_queue.py \\
        --queue-dir /Volumes/personal_folder/graph-queue

    # 投入せず対象ファイルと件数だけ確認
    uv run python scripts/ingest_graph_queue.py --dry-run

    # 特定サブディレクトリのみ（デフォルト: finance-news-workflow）
    uv run python scripts/ingest_graph_queue.py --subdir finance-news-workflow

Notes
-----
- ``GRAPH_QUEUE_DIR`` 環境変数でデフォルトディレクトリを上書き可能
- ``NEO4J_RESEARCH_URI`` / ``NEO4J_RESEARCH_PASSWORD`` で接続先を変更可能
- 失敗したファイルは元の場所に残り、次回実行で再試行される
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from data_pipeline.neo4j_loader import ingest_to_neo4j, load_graph_queue

logger = logging.getLogger(__name__)

_DEFAULT_QUEUE_DIR = Path(
    os.environ.get("GRAPH_QUEUE_DIR", "/Volumes/personal_folder/graph-queue")
)
_DEFAULT_SUBDIR = "finance-news-workflow"
_PROCESSED_SUBDIR = "processed"


def _find_pending_files(queue_dir: Path, subdir: str) -> list[Path]:
    """未処理の graph-queue JSON ファイルを返す（processed/ は除外）.

    Parameters
    ----------
    queue_dir : Path
        graph-queue ベースディレクトリ。
    subdir : str
        対象サブディレクトリ名（例: "finance-news-workflow"）。

    Returns
    -------
    list[Path]
        未処理ファイルのリスト（ファイル名昇順）。
    """
    target = queue_dir / subdir
    if not target.exists():
        logger.info("Queue directory does not exist: %s", target)
        return []

    processed_dir = target / _PROCESSED_SUBDIR
    files = sorted(
        f
        for f in target.glob("*.json")
        if f.is_file() and f.resolve() != processed_dir.resolve()
    )
    logger.info("Found %d pending file(s) in %s", len(files), target)
    return files


def _mark_processed(queue_file: Path) -> None:
    """処理済みファイルを processed/ サブディレクトリに移動する.

    Parameters
    ----------
    queue_file : Path
        処理が完了した queue ファイルのパス。
    """
    processed_dir = queue_file.parent / _PROCESSED_SUBDIR
    processed_dir.mkdir(exist_ok=True)
    dest = processed_dir / queue_file.name
    shutil.move(str(queue_file), dest)
    logger.debug("Moved to processed: %s", dest)


def process_queue(
    queue_dir: Path,
    subdir: str = _DEFAULT_SUBDIR,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """未処理の graph-queue ファイルを全件 Neo4j に投入する.

    Parameters
    ----------
    queue_dir : Path
        graph-queue ベースディレクトリ。
    subdir : str
        対象サブディレクトリ名。
    dry_run : bool
        True の場合は Neo4j に書き込まず件数確認のみ行う。

    Returns
    -------
    dict[str, int]
        {"found": N, "ingested": N, "failed": N}
    """
    files = _find_pending_files(queue_dir, subdir)

    if not files:
        return {"found": 0, "ingested": 0, "failed": 0}

    ingested = 0
    failed = 0

    for queue_file in files:
        logger.info("Processing: %s", queue_file.name)
        try:
            queue_data = load_graph_queue(queue_file)
            result = ingest_to_neo4j(queue_data, dry_run=dry_run)
            logger.info(
                "Ingested %s: nodes=%d, relations=%d",
                queue_file.name,
                result.get("nodes", 0),
                result.get("relations", 0),
            )
            if not dry_run:
                _mark_processed(queue_file)
            ingested += 1
        except Exception as exc:
            logger.error(
                "Failed to ingest %s: %s",
                queue_file.name,
                exc,
                exc_info=True,
            )
            failed += 1

    return {"found": len(files), "ingested": ingested, "failed": failed}


def _parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する."""
    parser = argparse.ArgumentParser(
        description="NAS の graph-queue ファイルを research-neo4j に投入する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/ingest_graph_queue.py
  uv run python scripts/ingest_graph_queue.py --dry-run
  uv run python scripts/ingest_graph_queue.py --queue-dir /Volumes/personal_folder/graph-queue
        """,
    )
    parser.add_argument(
        "--queue-dir",
        type=Path,
        default=_DEFAULT_QUEUE_DIR,
        metavar="DIR",
        help=f"graph-queue ベースディレクトリ (default: {_DEFAULT_QUEUE_DIR})",
    )
    parser.add_argument(
        "--subdir",
        type=str,
        default=_DEFAULT_SUBDIR,
        metavar="NAME",
        help=f"処理対象サブディレクトリ (default: {_DEFAULT_SUBDIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Neo4j に書き込まず対象ファイルと件数のみ表示する",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル (default: INFO)",
    )
    return parser.parse_args()


def main() -> int:
    """メインエントリポイント.

    Returns
    -------
    int
        終了コード: 0=成功, 1=一部失敗あり
    """
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    if args.dry_run:
        logger.info("DRY RUN: Neo4j への書き込みは行いません")

    if not args.queue_dir.exists():
        logger.error("Queue directory not found: %s (NAS マウントを確認してください)", args.queue_dir)
        return 1

    summary = process_queue(args.queue_dir, args.subdir, dry_run=args.dry_run)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}ingest_graph_queue 完了")
    print(f"  発見:  {summary['found']} 件")
    print(f"  投入:  {summary['ingested']} 件")
    print(f"  失敗:  {summary['failed']} 件")

    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
