"""Threads インサイト収集 CLI.

Usage
-----
uv run python scripts/insights_collector.py --account career_sister backfill
uv run python scripts/insights_collector.py --account career_sister collect
uv run python scripts/insights_collector.py --account career_sister followers
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from creator.analytics import InsightsStore
from creator.insights import ThreadsInsightsClient
from creator.poster import ThreadsConfig
from utils_core.logging.config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_posting_state(account: str) -> dict:
    """posting_state.json を読み込む."""
    path = PROJECT_ROOT / "creator" / account / "posting_state.json"
    if not path.exists():
        logger.error("posting_state_not_found", path=str(path))
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_posting_state(account: str, state: dict) -> None:
    """posting_state.json を書き込む."""
    path = PROJECT_ROOT / "creator" / account / "posting_state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# backfill: permalink → media_id 解決 + 全投稿インサイト取得
# ---------------------------------------------------------------------------


def cmd_backfill(
    client: ThreadsInsightsClient,
    store: InsightsStore,
    account: str,
    *,
    dry_run: bool = False,
    limit: int | None = None,
) -> None:
    """既存投稿の media_id を解決し、インサイトを一括取得する."""
    state = _load_posting_state(account)
    post_history = state.get("post_history", [])

    # permalink 一覧を収集
    permalinks = [
        p["threads_permalink"]
        for p in post_history
        if p.get("threads_permalink")
    ]
    if not permalinks:
        print("投稿履歴に permalink がありません。")
        return

    print(f"📊 {len(permalinks)} 件の permalink を media_id に解決中...")

    if dry_run:
        print("[dry-run] API 呼び出しをスキップ")
        for pl in permalinks[:5]:
            print(f"  → {pl}")
        if len(permalinks) > 5:
            print(f"  ... 他 {len(permalinks) - 5} 件")
        return

    # permalink → media_id マッピング構築
    mapping = client.resolve_media_ids(permalinks, max_fetch=200)
    print(f"✅ {len(mapping)}/{len(permalinks)} 件の media_id を解決")

    # posting_state.json に media_id を書き戻し
    updated_count = 0
    for post in post_history:
        pl = post.get("threads_permalink", "")
        if pl in mapping and "threads_media_id" not in post:
            post["threads_media_id"] = mapping[pl]
            updated_count += 1

    if updated_count > 0:
        _save_posting_state(account, state)
        print(f"✅ posting_state.json に {updated_count} 件の media_id を追記")

    # インサイト取得
    posts_to_fetch = [
        p for p in post_history
        if p.get("threads_media_id") and store.load_post_insights(p["post_id"]) is None
    ]
    if limit is not None:
        posts_to_fetch = posts_to_fetch[:limit]

    print(f"\n📈 {len(posts_to_fetch)} 件のインサイトを取得中...")

    for i, post in enumerate(posts_to_fetch):
        media_id = post["threads_media_id"]
        post_id = post["post_id"]
        try:
            insights = client.get_media_insights(media_id)
            data = {
                "post_id": post_id,
                "threads_media_id": media_id,
                "date": post.get("date"),
                "slot": post.get("slot"),
                "category": post.get("category"),
                "type": post.get("type"),
                "theme": post.get("theme"),
                "threads_permalink": post.get("threads_permalink"),
                "instagram_permalink": post.get("instagram_permalink"),
                "posted_at": post.get("posted_at"),
                "threads_insights": insights.to_dict(),
                "instagram_insights": None,
            }
            store.save_post_insights(post_id, data)
            er_pct = insights.engagement_rate * 100
            print(
                f"  [{i + 1}/{len(posts_to_fetch)}] {post_id} "
                f"views={insights.views} ER={er_pct:.1f}%"
            )
        except Exception as e:
            logger.error("insights_fetch_failed", post_id=post_id, error=str(e))
            print(f"  [{i + 1}/{len(posts_to_fetch)}] {post_id} ❌ {e}")

        # レート制限対策
        if i < len(posts_to_fetch) - 1:
            time.sleep(1)

    print(f"\n✅ backfill 完了")


# ---------------------------------------------------------------------------
# collect: 24h 経過した新投稿のインサイトを取得
# ---------------------------------------------------------------------------


def cmd_collect(
    client: ThreadsInsightsClient,
    store: InsightsStore,
    account: str,
    *,
    min_hours: float = 24.0,
    force: bool = False,
    limit: int | None = None,
) -> None:
    """投稿後 24h 以上経過した投稿のインサイトを取得する."""
    state = _load_posting_state(account)
    post_history = state.get("post_history", [])

    if force:
        # 全投稿（media_id あり）を対象
        needed = [p for p in post_history if p.get("threads_media_id")]
    else:
        needed = store.posts_needing_insights(post_history, min_hours=min_hours)

    # media_id がない投稿は permalink から解決を試みる
    no_media_id = [p for p in needed if not p.get("threads_media_id")]
    if no_media_id:
        permalinks = [p["threads_permalink"] for p in no_media_id if p.get("threads_permalink")]
        if permalinks:
            mapping = client.resolve_media_ids(permalinks)
            for post in no_media_id:
                pl = post.get("threads_permalink", "")
                if pl in mapping:
                    post["threads_media_id"] = mapping[pl]
            _save_posting_state(account, state)

    # media_id がある投稿のみ取得
    fetchable = [p for p in needed if p.get("threads_media_id")]
    if limit is not None:
        fetchable = fetchable[:limit]

    if not fetchable:
        print("📭 取得対象の投稿はありません。")
        return

    print(f"📈 {len(fetchable)} 件のインサイトを取得中...")

    for i, post in enumerate(fetchable):
        media_id = post["threads_media_id"]
        post_id = post["post_id"]
        try:
            insights = client.get_media_insights(media_id)
            data = {
                "post_id": post_id,
                "threads_media_id": media_id,
                "date": post.get("date"),
                "slot": post.get("slot"),
                "category": post.get("category"),
                "type": post.get("type"),
                "theme": post.get("theme"),
                "threads_permalink": post.get("threads_permalink"),
                "instagram_permalink": post.get("instagram_permalink"),
                "posted_at": post.get("posted_at"),
                "threads_insights": insights.to_dict(),
                "instagram_insights": None,
            }
            store.save_post_insights(post_id, data)
            er_pct = insights.engagement_rate * 100
            print(
                f"  [{i + 1}/{len(fetchable)}] {post_id} "
                f"views={insights.views} ER={er_pct:.1f}%"
            )
        except Exception as e:
            logger.error("insights_fetch_failed", post_id=post_id, error=str(e))
            print(f"  [{i + 1}/{len(fetchable)}] {post_id} ❌ {e}")

        if i < len(fetchable) - 1:
            time.sleep(1)

    print(f"\n✅ collect 完了")


# ---------------------------------------------------------------------------
# followers: フォロワー数を記録
# ---------------------------------------------------------------------------


def cmd_followers(
    client: ThreadsInsightsClient,
    store: InsightsStore,
) -> None:
    """現在のフォロワー数を取得・記録する."""
    print("📊 フォロワー数を取得中...")
    user_insights = client.get_user_insights()
    followers = user_insights.followers_count

    if followers is not None:
        store.save_follower_data(followers)
        print(f"✅ フォロワー数: {followers}")

        # 推移も表示
        history = store.load_followers()
        if len(history) >= 2:
            prev = history[-2]
            delta = followers - prev["count"]
            sign = "+" if delta >= 0 else ""
            print(f"   前回 ({prev['date']}): {prev['count']}（{sign}{delta}）")
    else:
        print("⚠️ フォロワー数を取得できませんでした。")


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(description="Threads インサイト収集")
    parser.add_argument(
        "--account",
        default="career_sister",
        help="アカウント名 (default: career_sister)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # backfill
    p_backfill = subparsers.add_parser("backfill", help="全投稿の media_id 解決 + インサイト取得")
    p_backfill.add_argument("--dry-run", action="store_true", help="API 呼び出しなしで確認")
    p_backfill.add_argument("--limit", type=int, help="取得する最大投稿数")

    # collect
    p_collect = subparsers.add_parser("collect", help="24h 経過した投稿のインサイト取得")
    p_collect.add_argument("--min-hours", type=float, default=24.0, help="最小経過時間（時間）")
    p_collect.add_argument("--force", action="store_true", help="既存インサイトも再取得")
    p_collect.add_argument("--limit", type=int, help="取得する最大投稿数")

    # followers
    subparsers.add_parser("followers", help="フォロワー数を取得・記録")

    args = parser.parse_args()

    config = ThreadsConfig.for_account(args.account)
    client = ThreadsInsightsClient(config)
    store = InsightsStore(args.account)

    if args.command == "backfill":
        cmd_backfill(
            client, store, args.account,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    elif args.command == "collect":
        cmd_collect(
            client, store, args.account,
            min_hours=args.min_hours,
            force=args.force,
            limit=args.limit,
        )
    elif args.command == "followers":
        cmd_followers(client, store)


if __name__ == "__main__":
    main()
