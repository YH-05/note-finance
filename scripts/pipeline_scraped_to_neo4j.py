#!/usr/bin/env python3
"""Stage 2→3→4 オーケストレーター: scraped JSON → Neo4j 投入パイプライン。

NAS に蓄積された RSS スクレイピング JSON を重複排除し、
graph-queue を生成して research-neo4j に投入する 3 段バッチ処理。

Stages
------
Stage 2: dedup_scraped.py          重複排除 + processed/ 移動 + レジストリ更新
Stage 3: emit_research_queue.py    graph-queue JSON 生成
Stage 4: ingest_graph_queue.py     research-neo4j 投入

Usage
-----
::

    # 通常実行（1日1回 launchd から）
    uv run python scripts/pipeline_scraped_to_neo4j.py

    # 特定ソースのみ
    uv run python scripts/pipeline_scraped_to_neo4j.py --sources cnbc jetro

    # NAS パスを上書き
    uv run python scripts/pipeline_scraped_to_neo4j.py --scraped-base /path/to/scraped

    # dry-run（Stage 2 のみ preview、Stage 3/4 は実行しない）
    uv run python scripts/pipeline_scraped_to_neo4j.py --dry-run

Notes
-----
- Stage 2 の出力パスは stdout 最終行から取得する
- Stage 3 の出力パスは stdout の "Queue file: {path}" 行から取得する
- 新規記事が 0 件の場合は Stage 3/4 をスキップして正常終了
- ``NAS_SCRAPED_BASE`` 環境変数で NAS パスをデフォルト上書き可能
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from news_scraper._logging import get_logger

logger = get_logger(__name__, module="pipeline_scraped_to_neo4j")

SCRIPT_DIR = Path(__file__).resolve().parent
NAS_SCRAPED_BASE = os.environ.get(
    "NAS_SCRAPED_BASE", "/Volumes/personal_folder/scraped"
)


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------


def _run_stage2_dedup(
    scraped_base: str,
    sources: list[str],
    dry_run: bool,
    log_level: str,
) -> Path | None:
    """Stage 2: dedup_scraped.py を実行し、出力ファイルパスを返す。

    Parameters
    ----------
    scraped_base : str
        NAS scraped ベースディレクトリ。
    sources : list[str]
        処理対象ソース名リスト。
    dry_run : bool
        True の場合 dedup を dry-run で実行し None を返す。
    log_level : str
        ログレベル文字列。

    Returns
    -------
    Path | None
        dedup 出力 .tmp ファイルパス。新規記事なし or dry-run の場合は None。
    """
    cmd = [
        "uv",
        "run",
        "python",
        str(SCRIPT_DIR / "dedup_scraped.py"),
        "--scraped-base",
        scraped_base,
        "--log-level",
        log_level,
    ]
    if sources:
        cmd += ["--sources"] + sources
    if dry_run:
        cmd.append("--dry-run")

    logger.info("Stage 2: dedup_scraped starting", dry_run=dry_run)
    result = subprocess.run(
        cmd, capture_output=False, text=True, stdout=subprocess.PIPE
    )

    if result.returncode != 0:
        logger.error("Stage 2 failed", returncode=result.returncode)
        sys.exit(result.returncode)

    # stdout 最終行が出力ファイルパス（新規記事あり時のみ）
    stdout_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    if not stdout_lines:
        logger.info("Stage 2: no new articles, stopping pipeline")
        return None

    output_path = Path(stdout_lines[-1])
    if not output_path.exists():
        logger.info("Stage 2: no new articles, stopping pipeline")
        return None

    logger.info("Stage 2: complete", output=str(output_path))
    return output_path


def _run_stage3_emit(dedup_output: Path) -> Path | None:
    """Stage 3: emit_research_queue.py を実行し、queue ファイルパスを返す。

    Parameters
    ----------
    dedup_output : Path
        Stage 2 の出力 .tmp ファイルパス。

    Returns
    -------
    Path | None
        graph-queue JSON ファイルパス。失敗時は None。
    """
    cmd = [
        "uv",
        "run",
        "python",
        str(SCRIPT_DIR / "emit_research_queue.py"),
        "--command",
        "finance-news-workflow",
        "--input",
        str(dedup_output),
    ]

    logger.info("Stage 3: emit_research_queue starting", input=str(dedup_output))
    result = subprocess.run(
        cmd, capture_output=False, text=True, stdout=subprocess.PIPE
    )

    if result.returncode != 0:
        logger.error("Stage 3 failed", returncode=result.returncode)
        sys.exit(result.returncode)

    # "Queue file: {path}" 行を探す
    for line in result.stdout.splitlines():
        m = re.match(r"Queue file:\s*(.+)", line.strip())
        if m:
            queue_path = Path(m.group(1).strip())
            logger.info("Stage 3: complete", output=str(queue_path))
            return queue_path

    logger.error("Stage 3: could not find queue file path in stdout")
    sys.exit(1)


def _run_stage4_ingest(queue_file: Path, log_level: str) -> None:
    """Stage 4: ingest_graph_queue.py を実行して Neo4j に投入する。

    Parameters
    ----------
    queue_file : Path
        graph-queue JSON ファイルパス。
    log_level : str
        ログレベル文字列。
    """
    cmd = [
        "uv",
        "run",
        "python",
        str(SCRIPT_DIR / "ingest_graph_queue.py"),
        "--file",
        str(queue_file),
        "--log-level",
        log_level,
    ]

    logger.info("Stage 4: ingest_graph_queue starting", input=str(queue_file))
    result = subprocess.run(cmd, capture_output=False, text=True)

    if result.returncode != 0:
        logger.error("Stage 4 failed", returncode=result.returncode)
        sys.exit(result.returncode)

    logger.info("Stage 4: complete")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="scraped JSON → Neo4j 投入パイプライン (Stage 2→3→4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python scripts/pipeline_scraped_to_neo4j.py
  uv run python scripts/pipeline_scraped_to_neo4j.py --dry-run
  uv run python scripts/pipeline_scraped_to_neo4j.py --sources cnbc jetro
        """,
    )
    parser.add_argument(
        "--scraped-base",
        default=NAS_SCRAPED_BASE,
        help=f"NAS scraped ベースディレクトリ (default: {NAS_SCRAPED_BASE})",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=[],
        metavar="SOURCE",
        help="処理対象ソース（省略時は全ソース）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Stage 2 を dry-run で実行し Stage 3/4 をスキップ",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="ログレベル (default: INFO)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    started_at = datetime.now(timezone.utc)
    logger.info(
        "pipeline_scraped_to_neo4j starting",
        scraped_base=args.scraped_base,
        sources=args.sources or "all",
        dry_run=args.dry_run,
    )

    # Stage 2: dedup
    dedup_output = _run_stage2_dedup(
        scraped_base=args.scraped_base,
        sources=args.sources,
        dry_run=args.dry_run,
        log_level=args.log_level,
    )
    if dedup_output is None:
        logger.info("Pipeline complete (no new articles or dry-run)")
        return 0

    # Stage 3: emit graph-queue
    queue_file = _run_stage3_emit(dedup_output)
    if queue_file is None:
        return 1

    # Stage 4: ingest to Neo4j
    _run_stage4_ingest(queue_file, log_level=args.log_level)

    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    logger.info(
        "Pipeline complete",
        dedup_output=str(dedup_output),
        queue_file=str(queue_file),
        elapsed_sec=round(elapsed, 1),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
