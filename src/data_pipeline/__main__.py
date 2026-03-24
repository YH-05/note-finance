"""日次バッチ CLI エントリポイント.

Usage
-----
::

    # 全RSSソースを収集→原文保存（Layer 0-2のみ）
    uv run python -m data_pipeline collect

    # RSS + スクレイピング
    uv run python -m data_pipeline collect --method rss --method scraping

    # 特定ソースのみ
    uv run python -m data_pipeline collect --source jp-finance --source jp-trade

    # Neo4j投入まで（LLM抽出なし）
    uv run python -m data_pipeline collect --ingest

    # dry-run
    uv run python -m data_pipeline collect --dry-run

    # creator-neo4j向け
    uv run python -m data_pipeline collect --target creator --source wealth-blogs-scrape

    # レジストリ情報
    uv run python -m data_pipeline registry
    uv run python -m data_pipeline registry --validate
"""

from __future__ import annotations

import argparse
import logging
import sys


def _cmd_collect(args: argparse.Namespace) -> int:
    """collect サブコマンド."""
    from data_pipeline.pipeline import run_pipeline

    methods = args.method or ["rss"]
    source_ids = args.source or None

    result = run_pipeline(
        target=args.target,
        source_ids=source_ids,
        method=methods if len(methods) > 1 else methods[0],
        extract=False,  # CLIではLLM抽出なし（Claude Code外なので）
        max_items_per_feed=args.max_items,
        ingest_neo4j=args.ingest,
        dry_run=args.dry_run,
        genre=args.genre,
        link_entities=args.link_entities,
    )

    print(f"\n{'='*50}")
    print(f"Target: {result.target}")
    print(f"Sources: {result.sources_processed}")
    print(f"Collected: {result.items_collected}")
    print(f"Saved: {result.items_saved}")
    print(f"Facts: {result.facts_total}")
    if result.tips_total:
        print(f"Tips: {result.tips_total}")
    if result.stories_total:
        print(f"Stories: {result.stories_total}")
    if result.graph_queue_path:
        print(f"Graph queue: {result.graph_queue_path}")
    if result.neo4j_nodes:
        print(f"Neo4j: {result.neo4j_nodes} nodes, {result.neo4j_relations} relations")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.is_success}")
    print(f"{'='*50}")

    return 0 if result.is_success else 1


def _cmd_registry(args: argparse.Namespace) -> int:
    """registry サブコマンド."""
    from data_pipeline.registry import RegistryLoader

    loader = RegistryLoader()

    if args.validate:
        issues = loader.validate()
        if not issues:
            print("No issues found.")
            return 0
        for issue in issues:
            print(f"[{issue.level.upper()}] {issue.source_id or 'global'}: {issue.message}")
        errors = [i for i in issues if i.level == "error"]
        return 1 if errors else 0

    import json

    summary = loader.summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    """CLI メインエントリポイント."""
    parser = argparse.ArgumentParser(
        prog="data_pipeline",
        description="データ収集・保存・構造化パイプライン",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログ出力",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # collect サブコマンド
    collect_parser = subparsers.add_parser("collect", help="データ収集・保存")
    collect_parser.add_argument(
        "--target", default="research", choices=["research", "creator"],
        help="投入先 (default: research)",
    )
    collect_parser.add_argument(
        "--method", action="append",
        help="収集方法 (rss, scraping)。複数指定可",
    )
    collect_parser.add_argument(
        "--source", action="append",
        help="ソースID指定。複数指定可",
    )
    collect_parser.add_argument(
        "--max-items", type=int, default=10,
        help="1フィード/サイトあたりの最大取得数 (default: 10)",
    )
    collect_parser.add_argument(
        "--ingest", action="store_true",
        help="Neo4j投入まで実行",
    )
    collect_parser.add_argument(
        "--dry-run", action="store_true",
        help="Neo4j投入をスキップ（カウントのみ）",
    )
    collect_parser.add_argument(
        "--genre", default="career",
        help="creator target のジャンル (default: career)",
    )
    collect_parser.add_argument(
        "--link-entities", action="store_true",
        help="Entity Linkerを実行",
    )

    # registry サブコマンド
    registry_parser = subparsers.add_parser("registry", help="ソースレジストリ情報")
    registry_parser.add_argument(
        "--validate", action="store_true",
        help="整合性チェック",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "collect":
        return _cmd_collect(args)
    elif args.command == "registry":
        return _cmd_registry(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
