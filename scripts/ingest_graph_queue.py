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


_VERIFICATION_ERROR_THRESHOLD = 0.10  # 10% 以上の差異で ERROR 判定


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


def _verify_ingestion(
    result: dict,
    queue_file: Path,
) -> bool:
    """投入結果を検証し、差異があれば警告/エラーを出力する.

    Parameters
    ----------
    result : dict
        ingest_to_neo4j() の戻り値。``rel_verification`` キーに
        ``{section: (expected, created)}`` を含む。
    queue_file : Path
        検証対象の graph-queue ファイル（ログ出力用）。

    Returns
    -------
    bool
        True: 検証 OK または WARNING（processed に移動可）。
        False: ERROR（差異率 >= 10%、processed に移動すべきでない）。
    """
    rel_verification = result.get("rel_verification", {})
    if not rel_verification:
        return True

    has_error = False
    for section, (expected, created) in rel_verification.items():
        if expected == 0:
            continue
        # created は「新規作成数」。MERGE 既存マッチ分を含まないため、
        # created < expected は正常（冪等 MERGE の期待動作）。
        # ただし MATCH 失敗（ノード不在）でも created=0 になるため、
        # 「全件が新規投入のはずなのに created=0」を検出する。
        # → expected > 0 かつ created == 0 の場合のみ警告対象とする。
        if created == 0 and expected > 0:
            discrepancy_rate = 1.0  # 100% 欠落
        else:
            # 正常: 一部 MERGE 既存 + 一部新規作成
            continue

        if discrepancy_rate >= _VERIFICATION_ERROR_THRESHOLD:
            logger.error(
                "VERIFICATION ERROR [%s] %s: expected=%d, created=%d (%.0f%% missing) — "
                "file will NOT be moved to processed",
                queue_file.name,
                section,
                expected,
                created,
                discrepancy_rate * 100,
            )
            has_error = True

    return not has_error


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
                verified = _verify_ingestion(result, queue_file)
                if verified:
                    _mark_processed(queue_file)
                else:
                    logger.warning(
                        "Skipping move to processed due to verification errors: %s",
                        queue_file.name,
                    )
                    failed += 1
                    continue
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


def process_single_file(
    queue_file: Path,
    *,
    dry_run: bool = False,
    keep: bool = False,
) -> dict[str, int]:
    """単一の graph-queue JSON ファイルを Neo4j に投入する.

    Parameters
    ----------
    queue_file : Path
        投入する graph-queue JSON ファイルのパス。
    dry_run : bool
        True の場合は Neo4j に書き込まず件数確認のみ行う。
    keep : bool
        True の場合は処理済みファイルを移動せずそのまま残す。

    Returns
    -------
    dict[str, int]
        {"found": 1, "ingested": 0|1, "failed": 0|1}
    """
    if not queue_file.exists():
        logger.error("File not found: %s", queue_file)
        return {"found": 0, "ingested": 0, "failed": 0}

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
            verified = _verify_ingestion(result, queue_file)
            if not verified:
                logger.warning(
                    "Verification errors detected: %s (file kept in place)",
                    queue_file.name,
                )
                return {"found": 1, "ingested": 0, "failed": 1}
            if not keep:
                _mark_processed(queue_file)
        return {"found": 1, "ingested": 1, "failed": 0}
    except Exception as exc:
        logger.error("Failed to ingest %s: %s", queue_file.name, exc, exc_info=True)
        return {"found": 1, "ingested": 0, "failed": 1}


def _parse_args() -> argparse.Namespace:
    """コマンドライン引数を解析する."""
    parser = argparse.ArgumentParser(
        description="graph-queue ファイルを research-neo4j に投入する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # NAS の未処理ファイルを全投入
  uv run python scripts/ingest_graph_queue.py

  # ローカルの web-research キューを全投入
  uv run python scripts/ingest_graph_queue.py --queue-dir .tmp/graph-queue --subdir web-research

  # 特定ファイルのみ投入
  uv run python scripts/ingest_graph_queue.py --file .tmp/graph-queue/web-research/gq-xxx.json

  # ドライラン
  uv run python scripts/ingest_graph_queue.py --dry-run
        """,
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        metavar="PATH",
        help="特定の graph-queue JSON ファイルを投入（--queue-dir/--subdir と排他）",
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
        "--keep",
        action="store_true",
        default=False,
        help="処理済みファイルを移動せず保持する",
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

    if args.file:
        # --file モード: 単一ファイル投入
        summary = process_single_file(
            args.file,
            dry_run=args.dry_run,
            keep=args.keep,
        )
    else:
        # ディレクトリモード: 未処理ファイル一括投入
        if not args.queue_dir.exists():
            logger.error(
                "Queue directory not found: %s (NAS マウントを確認してください)",
                args.queue_dir,
            )
            return 1
        summary = process_queue(args.queue_dir, args.subdir, dry_run=args.dry_run)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}ingest_graph_queue 完了")
    print(f"  発見:  {summary['found']} 件")
    print(f"  投入:  {summary['ingested']} 件")
    print(f"  失敗:  {summary['failed']} 件")

    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
