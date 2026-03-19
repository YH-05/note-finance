"""academic CLI エントリポイント.

``python -m academic fetch --arxiv-id 2303.09406`` で実行可能。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_OUTPUT_DIR = Path(".tmp/academic")
DEFAULT_OUTPUT_FILE = "papers.json"
BACKFILL_OUTPUT_DIR = Path(".tmp/graph-queue/academic-fetch")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m academic",
        description="arXiv 論文メタデータ取得 CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="サブコマンド")

    fetch_parser = subparsers.add_parser("fetch", help="arXiv 論文メタデータを取得")
    id_group = fetch_parser.add_mutually_exclusive_group(required=True)
    id_group.add_argument("--arxiv-id", type=str, help="単一の arXiv ID")
    id_group.add_argument("--arxiv-ids", type=str, nargs="+", help="複数の arXiv ID")
    fetch_parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
    )

    backfill_parser = subparsers.add_parser(
        "backfill", help="既存論文の著者・引用バックフィル"
    )
    backfill_parser.add_argument("--ids-file", type=str, required=True)
    backfill_parser.add_argument("--existing-ids", type=str, nargs="*", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "fetch":
        return _handle_fetch(args)
    if args.command == "backfill":
        return _handle_backfill(args)

    return 0


def _handle_fetch(args: argparse.Namespace) -> int:
    from .fetcher import PaperFetcher
    from .fetcher import paper_metadata_to_dict as _pm_to_dict

    arxiv_ids: list[str] = []
    if args.arxiv_id:
        arxiv_ids = [args.arxiv_id]
    elif args.arxiv_ids:
        arxiv_ids = args.arxiv_ids

    if not arxiv_ids:
        print("Error: No arXiv IDs specified", file=sys.stderr)
        return 1

    logger.info("Fetching papers", arxiv_ids=arxiv_ids, count=len(arxiv_ids))

    try:
        with PaperFetcher() as fetcher:
            if len(arxiv_ids) == 1:
                papers = [fetcher.fetch_paper(arxiv_ids[0])]
            else:
                papers = fetcher.fetch_papers_batch(arxiv_ids)
    except Exception as exc:
        logger.error("Failed to fetch papers", error=str(exc), exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_data = {"papers": [_pm_to_dict(p) for p in papers]}

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / DEFAULT_OUTPUT_FILE

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    logger.info("Papers saved", count=len(papers), output_path=str(output_path))
    print(str(output_path))
    return 0


def _read_arxiv_ids(file_path: str) -> list[str]:
    ids: list[str] = []
    with Path(file_path).open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            ids.append(stripped)
    return ids


def _handle_backfill(args: argparse.Namespace) -> int:
    from .fetcher import PaperFetcher
    from .fetcher import paper_metadata_to_dict as _pm_to_dict
    from .mapper import map_academic_papers

    try:
        arxiv_ids = _read_arxiv_ids(args.ids_file)
    except FileNotFoundError:
        print(f"Error: IDs file not found: {args.ids_file}", file=sys.stderr)
        return 1

    if not arxiv_ids:
        print(f"Error: No valid arXiv IDs in {args.ids_file}", file=sys.stderr)
        return 1

    logger.info("Backfill started", ids_file=args.ids_file, count=len(arxiv_ids))

    try:
        with PaperFetcher() as fetcher:
            papers = fetcher.fetch_papers_batch(arxiv_ids)
    except Exception as exc:
        logger.error("Failed to fetch papers", error=str(exc), exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    paper_dicts = [_pm_to_dict(p) for p in papers]
    existing_ids: list[str] = args.existing_ids or []
    graph_queue = map_academic_papers(
        {"papers": paper_dicts, "existing_source_ids": existing_ids}
    )

    output_dir = BACKFILL_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    queue_id = graph_queue.get("queue_id", "gq-unknown")
    output_path = output_dir / f"{queue_id}.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(graph_queue, f, ensure_ascii=False, indent=2)

    logger.info(
        "Backfill completed",
        output_path=str(output_path),
        source_count=len(graph_queue.get("sources", [])),
        author_count=len(graph_queue.get("authors", [])),
    )
    print(str(output_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
