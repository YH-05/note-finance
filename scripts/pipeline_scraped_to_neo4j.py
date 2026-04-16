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
NEO4J_RESEARCH_URI = os.environ.get(
    "NEO4J_RESEARCH_URI",
    os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
)


# ---------------------------------------------------------------------------
# Pre-checks
# ---------------------------------------------------------------------------


def _check_neo4j_available(uri: str) -> bool:
    """research-neo4j に Bolt 接続できるか確認する。

    Parameters
    ----------
    uri : str
        Neo4j の Bolt URI (例 ``bolt://localhost:7688``)。

    Returns
    -------
    bool
        接続可能なら True。
    """
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or 7687
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError as exc:
        logger.warning(
            "research-neo4j unreachable", uri=uri, host=host, port=port, error=str(exc)
        )
        return False


def _check_nas_mounted(scraped_base: str) -> bool:
    """NAS scraped ベースディレクトリがマウントされているか確認する。

    Parameters
    ----------
    scraped_base : str
        NAS 上の scraped ルートパス。

    Returns
    -------
    bool
        ディレクトリが存在すれば True。
    """
    if not Path(scraped_base).is_dir():
        logger.error("NAS scraped directory not accessible", path=scraped_base)
        return False
    return True


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
    result = subprocess.run(cmd, capture_output=True, text=True)

    # dedup ログは常にパススルー（ユーザーに件数サマリを見せる）
    if result.stdout:
        sys.stdout.write(result.stdout)
        sys.stdout.flush()
    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()

    if result.returncode != 0:
        logger.error("Stage 2 failed", returncode=result.returncode)
        sys.exit(result.returncode)

    # dry-run は常に Stage 3/4 をスキップ（dedup_scraped.py は出力パスを書かない）
    if dry_run:
        logger.info("Stage 2: dry-run complete, skipping Stage 3/4")
        return None

    # 本実行時は stdout 最終非空行が出力ファイルパス（新規記事あり時のみ）
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


_INGEST_SUMMARY_RE = re.compile(
    r"投入ノード:\s*(\d+).*?投入リレーション:\s*(\d+)",
    re.DOTALL,
)


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
    result = subprocess.run(cmd, capture_output=True, text=True)

    # ingest_graph_queue のサマリをパススルーしつつ node/rel 数を抽出
    if result.stdout:
        sys.stdout.write(result.stdout)
        sys.stdout.flush()
    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()

    if result.returncode != 0:
        logger.error("Stage 4 failed", returncode=result.returncode)
        sys.exit(result.returncode)

    match = _INGEST_SUMMARY_RE.search(result.stdout or "")
    if match:
        nodes, relations = int(match.group(1)), int(match.group(2))
        logger.info("Stage 4: complete", nodes=nodes, relations=relations)
    else:
        logger.info("Stage 4: complete (summary not parsed)")


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
    parser.add_argument(
        "--skip-precheck",
        action="store_true",
        default=False,
        help="NAS/Neo4j 接続確認をスキップ",
    )
    parser.add_argument(
        "--neo4j-uri",
        default=NEO4J_RESEARCH_URI,
        help=f"research-neo4j Bolt URI (default: {NEO4J_RESEARCH_URI})",
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

    # Stage 1: pre-checks（NAS マウント / Neo4j 接続）
    if not args.skip_precheck:
        if not _check_nas_mounted(args.scraped_base):
            logger.error(
                "NAS not mounted. Mount /Volumes/personal_folder and retry, "
                "or pass --skip-precheck to override.",
            )
            return 2
        if not args.dry_run and not _check_neo4j_available(args.neo4j_uri):
            logger.error(
                "research-neo4j is unreachable. Start the Neo4j container "
                "(bolt://localhost:7688) and retry, or pass --skip-precheck / --dry-run.",
            )
            return 2

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
