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

    # note.com クリエイター操作
    uv run python -m data_pipeline note-com scrape {username}
    uv run python -m data_pipeline note-com monitor
    uv run python -m data_pipeline note-com add {username}
    uv run python -m data_pipeline note-com list
    uv run python -m data_pipeline note-com remove {username}

    # RawStore → Neo4j 投入
    uv run python -m data_pipeline ingest --source note-com-{user} --target creator

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


def _cmd_ingest(args: argparse.Namespace) -> int:
    """ingest サブコマンド: RawStore → Neo4j 投入."""
    from data_pipeline.pipeline import run_ingest_from_rawstore

    result = run_ingest_from_rawstore(
        source_id=args.source,
        target=args.target,
        date=args.date,
        genre=args.genre,
        link_entities=args.link_entities,
        dry_run=args.dry_run,
    )

    print(f"\n{'='*50}")
    print(f"Ingest: {args.source} → {args.target}")
    print(f"Items loaded: {result.items_collected}")
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


def _cmd_note_com(args: argparse.Namespace) -> int:
    """note-com サブコマンド: note.com クリエイター操作."""
    from pathlib import Path

    config_path = Path("data/config/note-com-creators.json")

    if args.note_com_command == "scrape":
        return _note_com_scrape(args, config_path)
    elif args.note_com_command == "monitor":
        return _note_com_monitor(config_path)
    elif args.note_com_command == "add":
        return _note_com_add(args, config_path)
    elif args.note_com_command == "list":
        return _note_com_list(config_path)
    elif args.note_com_command == "remove":
        return _note_com_remove(args, config_path)
    return 1


def _note_com_scrape(args: argparse.Namespace, config_path: Path) -> int:
    """note-com scrape: 一括スクレイピング."""
    import asyncio
    from pathlib import Path

    from data_pipeline.collectors.note_com_browser import NoteComBrowser
    from data_pipeline.storage.raw_store import RawStore

    username = args.username
    max_articles = args.max_articles
    source_id = f"note-com-{username}"

    print(f"Scraping note.com/{username} (max: {max_articles} articles)...")

    async def _scrape() -> int:
        store = RawStore()
        saved = 0
        skipped_paid = 0
        skipped_dup = 0

        async with NoteComBrowser(headless=True) as browser:
            urls = await browser.list_article_urls(username, max_pages=10)
            urls = urls[:max_articles]
            print(f"Found {len(urls)} article URLs")

            for i, url in enumerate(urls, 1):
                article = await browser.scrape_article(url)
                if article is None:
                    skipped_paid += 1
                    continue

                result = store.save_text(
                    source_id=source_id,
                    url=article.url,
                    title=article.title,
                    raw_text=article.body_text,
                    collection_method="note-com",
                    published_at=article.published_at,
                    author=article.author,
                    language="ja",
                    metadata={
                        "hashtags": article.hashtags,
                        "like_count": article.like_count,
                    },
                )
                if result == "saved":
                    saved += 1
                elif result == "duplicate":
                    skipped_dup += 1

                if i % 5 == 0:
                    print(f"  Progress: {i}/{len(urls)}")

        print(f"\n{'='*50}")
        print(f"Scrape complete: note.com/{username}")
        print(f"  Saved: {saved}")
        print(f"  Skipped (paid): {skipped_paid}")
        print(f"  Skipped (duplicate): {skipped_dup}")
        print(f"{'='*50}")
        return saved

    saved_count = asyncio.run(_scrape())

    # RSSモニター追加の質問
    if saved_count > 0:
        try:
            answer = input(f"\nRSSモニターに {username} を追加しますか？ [y/N]: ").strip().lower()
            if answer == "y":
                from pathlib import Path

                _note_com_add_to_config(
                    config_path,
                    username=username,
                    genre=getattr(args, "genre", "career"),
                )
                print(f"✓ {username} をRSSモニターに追加しました")
        except (EOFError, KeyboardInterrupt):
            pass

    return 0


def _note_com_monitor(config_path: Path) -> int:
    """note-com monitor: RSSモニタリング."""
    from data_pipeline.collectors.note_com_rss import NoteComRssMonitor

    monitor = NoteComRssMonitor(config_path=config_path)
    result = monitor.monitor()

    print(f"\n{'='*50}")
    print("RSS Monitor complete")
    print(f"  Creators checked: {result.creators_checked}")
    print(f"  New articles found: {result.new_articles_found}")
    print(f"  Articles saved: {result.articles_saved}")
    print(f"  Skipped (paid): {result.articles_skipped_paid}")
    print(f"  Skipped (duplicate): {result.articles_skipped_duplicate}")
    print(f"  Errors: {len(result.errors)}")
    print(f"{'='*50}")

    return 0 if not result.errors else 1


def _note_com_add(args: argparse.Namespace, config_path: Path) -> int:
    """note-com add: クリエイター追加."""
    _note_com_add_to_config(
        config_path,
        username=args.username,
        genre=getattr(args, "genre", "career"),
    )
    print(f"✓ {args.username} を追加しました（genre: {getattr(args, 'genre', 'career')}）")
    return 0


def _note_com_add_to_config(
    config_path: Path,
    *,
    username: str,
    genre: str = "career",
) -> None:
    """config にクリエイターを追加する."""
    import json
    from datetime import datetime, timezone

    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)

    # 重複チェック
    existing = [c["username"] for c in config.get("creators", [])]
    if username in existing:
        print(f"  {username} は既に登録済みです")
        return

    config.setdefault("creators", []).append({
        "username": username,
        "display_name": username,
        "genres": [genre],
        "target_instance": "creator",
        "rss_enabled": True,
        "enabled": True,
        "added_at": datetime.now(tz=timezone.utc).isoformat(),
    })

    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _note_com_list(config_path: Path) -> int:
    """note-com list: クリエイター一覧."""
    import json

    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)

    creators = config.get("creators", [])
    if not creators:
        print("登録済みクリエイターはありません")
        return 0

    print(f"{'Username':<25} {'Genre':<15} {'RSS':<6} {'Enabled':<8}")
    print("-" * 60)
    for c in creators:
        genres = ", ".join(c.get("genres", []))
        rss = "✓" if c.get("rss_enabled") else "-"
        enabled = "✓" if c.get("enabled", True) else "-"
        print(f"{c['username']:<25} {genres:<15} {rss:<6} {enabled:<8}")

    return 0


def _note_com_remove(args: argparse.Namespace, config_path: Path) -> int:
    """note-com remove: クリエイター削除."""
    import json

    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)

    original_count = len(config.get("creators", []))
    config["creators"] = [
        c for c in config.get("creators", [])
        if c["username"] != args.username
    ]

    if len(config["creators"]) == original_count:
        print(f"  {args.username} は登録されていません")
        return 1

    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✓ {args.username} を削除しました")
    return 0


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

    # ingest サブコマンド
    ingest_parser = subparsers.add_parser("ingest", help="RawStore → Neo4j 投入")
    ingest_parser.add_argument(
        "--source", required=True,
        help="RawStore の source_id (例: note-com-yukihata)",
    )
    ingest_parser.add_argument(
        "--target", required=True, choices=["research", "creator"],
        help="投入先",
    )
    ingest_parser.add_argument(
        "--date",
        help="日付フィルタ (YYYY-MM-DD)",
    )
    ingest_parser.add_argument(
        "--genre", default="career",
        help="creator target のジャンル (default: career)",
    )
    ingest_parser.add_argument(
        "--link-entities", action="store_true",
        help="Entity Linkerを実行",
    )
    ingest_parser.add_argument(
        "--dry-run", action="store_true",
        help="Neo4j投入をスキップ",
    )

    # note-com サブコマンド
    note_com_parser = subparsers.add_parser("note-com", help="note.com クリエイター操作")
    note_com_sub = note_com_parser.add_subparsers(
        dest="note_com_command", required=True,
    )

    # note-com scrape
    scrape_parser = note_com_sub.add_parser("scrape", help="クリエイターの記事を一括取得")
    scrape_parser.add_argument("username", help="note.com ユーザー名")
    scrape_parser.add_argument(
        "--max-articles", type=int, default=50,
        help="最大記事数 (default: 50)",
    )
    scrape_parser.add_argument(
        "--genre", default="career",
        help="ジャンル (default: career)",
    )

    # note-com monitor
    note_com_sub.add_parser("monitor", help="RSSモニタリング実行")

    # note-com add
    add_parser = note_com_sub.add_parser("add", help="クリエイターを追加")
    add_parser.add_argument("username", help="note.com ユーザー名")
    add_parser.add_argument(
        "--genre", default="career",
        help="ジャンル (default: career)",
    )

    # note-com list
    note_com_sub.add_parser("list", help="登録クリエイター一覧")

    # note-com remove
    remove_parser = note_com_sub.add_parser("remove", help="クリエイターを削除")
    remove_parser.add_argument("username", help="note.com ユーザー名")

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
    elif args.command == "ingest":
        return _cmd_ingest(args)
    elif args.command == "note-com":
        return _cmd_note_com(args)
    elif args.command == "registry":
        return _cmd_registry(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
