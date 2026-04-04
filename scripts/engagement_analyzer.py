"""エンゲージメント分析 CLI.

Usage
-----
uv run python scripts/engagement_analyzer.py --account career_sister matrix
uv run python scripts/engagement_analyzer.py --account career_sister report
uv run python scripts/engagement_analyzer.py --account career_sister recommend
uv run python scripts/engagement_analyzer.py --account career_sister apply --dry-run
uv run python scripts/engagement_analyzer.py --account career_sister trend
uv run python scripts/engagement_analyzer.py --account career_sister compare
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from creator.analytics import (
    EngagementAnalyzer,
    InsightsStore,
    WeightRecommender,
)
from utils_core.logging.config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_posting_state(account: str) -> dict:
    path = PROJECT_ROOT / "creator" / account / "posting_state.json"
    if not path.exists():
        print(f"❌ {path} が見つかりません。", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _posting_state_path(account: str) -> Path:
    return PROJECT_ROOT / "creator" / account / "posting_state.json"


# ---------------------------------------------------------------------------
# matrix: マトリクス構築
# ---------------------------------------------------------------------------


def cmd_matrix(store: InsightsStore) -> None:
    """エンゲージメントマトリクスを構築・保存する."""
    analyzer = EngagementAnalyzer(store)
    matrix = analyzer.build_matrix()

    if matrix.get("total_posts_analyzed", 0) == 0:
        print("❌ インサイトデータがありません。先に insights_collector.py を実行してください。")
        return

    store.save_engagement_matrix(matrix)
    print(f"✅ マトリクス構築完了（{matrix['total_posts_analyzed']} 投稿分析）")
    print(f"   保存先: {store.base_dir / 'engagement_matrix.json'}")


# ---------------------------------------------------------------------------
# report: レポート表示
# ---------------------------------------------------------------------------


def cmd_report(store: InsightsStore) -> None:
    """エンゲージメントレポートを表示する."""
    matrix = store.load_engagement_matrix()
    if not matrix:
        print("❌ マトリクスが未構築です。先に `matrix` コマンドを実行してください。")
        return

    total = matrix.get("total_posts_analyzed", 0)
    print(f"\n{'=' * 60}")
    print(f"📊 エンゲージメントレポート（{total} 投稿分析）")
    print(f"{'=' * 60}")

    # テーマ別
    print(f"\n■ テーマ別パフォーマンス")
    print(f"{'テーマ':<12} {'投稿数':>6} {'平均views':>10} {'平均ER':>8} {'いいね':>6} {'返信':>6}")
    print("-" * 60)
    for key, val in sorted(
        matrix.get("by_theme", {}).items(),
        key=lambda x: x[1].get("avg_engagement_rate", 0),
        reverse=True,
    ):
        print(
            f"{key:<12} {val['posts']:>6} {val['avg_views']:>10} "
            f"{val['avg_engagement_rate']:>7.2%} {val.get('total_likes', 0):>6} "
            f"{val.get('total_replies', 0):>6}"
        )

    # 型別
    print(f"\n■ 型別パフォーマンス")
    print(f"{'型':<12} {'投稿数':>6} {'平均views':>10} {'平均ER':>8}")
    print("-" * 44)
    for key, val in sorted(
        matrix.get("by_type", {}).items(),
        key=lambda x: x[1].get("avg_engagement_rate", 0),
        reverse=True,
    ):
        print(
            f"{key:<12} {val['posts']:>6} {val['avg_views']:>10} "
            f"{val['avg_engagement_rate']:>7.2%}"
        )

    # スロット別
    print(f"\n■ スロット別パフォーマンス")
    print(f"{'スロット':<12} {'投稿数':>6} {'平均views':>10} {'平均ER':>8}")
    print("-" * 44)
    for key, val in sorted(
        matrix.get("by_slot", {}).items(),
        key=lambda x: x[1].get("avg_engagement_rate", 0),
        reverse=True,
    ):
        print(
            f"{key:<12} {val['posts']:>6} {val['avg_views']:>10} "
            f"{val['avg_engagement_rate']:>7.2%}"
        )

    # Top / Bottom 組み合わせ
    top = matrix.get("top_combinations", [])
    if top:
        print(f"\n■ 高エンゲージメント組み合わせ Top5")
        for i, combo in enumerate(top[:5], 1):
            print(
                f"  {i}. {combo['combo']} "
                f"(ER={combo['avg_engagement_rate']:.2%}, "
                f"{combo['posts']}投稿)"
            )

    bottom = matrix.get("bottom_combinations", [])
    if bottom:
        print(f"\n■ 低エンゲージメント組み合わせ Bottom5")
        for i, combo in enumerate(bottom[:5], 1):
            print(
                f"  {i}. {combo['combo']} "
                f"(ER={combo['avg_engagement_rate']:.2%}, "
                f"{combo['posts']}投稿)"
            )

    print()


# ---------------------------------------------------------------------------
# recommend: 重み調整推奨
# ---------------------------------------------------------------------------


def cmd_recommend(store: InsightsStore, account: str) -> None:
    """テーマ重みの調整推奨を表示する."""
    matrix = store.load_engagement_matrix()
    if not matrix:
        print("❌ マトリクスが未構築です。先に `matrix` コマンドを実行してください。")
        return

    state = _load_posting_state(account)
    recommender = WeightRecommender(matrix, state)
    recommendations = recommender.recommend()

    if not recommendations:
        print("📭 現時点で重み調整の推奨はありません（データ不足、または差分が小さい）。")
        return

    print(f"\n{'=' * 60}")
    print(f"🎯 テーマ重み調整推奨")
    print(f"{'=' * 60}")

    for rec in recommendations:
        direction = "↑" if rec["new_weight"] > rec["old_weight"] else "↓"
        print(
            f"\n  {rec['theme_id']} ({rec['theme_name']}): "
            f"{rec['old_weight']} → {rec['new_weight']} {direction}"
        )
        print(f"    理由: {rec['rationale']}")
        print(f"    分析投稿数: {rec['posts_analyzed']}")

    print(f"\n適用するには: uv run python scripts/engagement_analyzer.py "
          f"--account {account} apply")


# ---------------------------------------------------------------------------
# apply: 重み反映
# ---------------------------------------------------------------------------


def cmd_apply(store: InsightsStore, account: str, *, dry_run: bool = False) -> None:
    """推奨された重みを posting_state.json に反映する."""
    matrix = store.load_engagement_matrix()
    if not matrix:
        print("❌ マトリクスが未構築です。")
        return

    state = _load_posting_state(account)
    recommender = WeightRecommender(matrix, state)
    recommendations = recommender.recommend()

    if not recommendations:
        print("📭 適用する推奨がありません。")
        return

    if dry_run:
        print("[dry-run] 以下の変更を適用します（実際には書き込みません）:")
        for rec in recommendations:
            print(f"  {rec['theme_id']}: {rec['old_weight']} → {rec['new_weight']}")
        return

    path = _posting_state_path(account)
    result = recommender.apply(path)

    if result.get("applied"):
        changes = result["changes"]
        print(f"✅ {len(changes)} 件のテーマ重みを更新しました")
        for tid, change in changes.items():
            print(f"  {tid}: {change['old_weight']} → {change['new_weight']}")

        # 履歴に記録
        store.save_weight_history({
            "date": result["date"],
            "reason": "engagement_analysis",
            "posts_analyzed": matrix.get("total_posts_analyzed", 0),
            "changes": changes,
        })
    else:
        print(f"⚠️ 適用されませんでした: {result.get('reason')}")


# ---------------------------------------------------------------------------
# trend: トレンド表示
# ---------------------------------------------------------------------------


def cmd_trend(store: InsightsStore, window_days: int = 7) -> None:
    """エンゲージメントのトレンドを表示する."""
    analyzer = EngagementAnalyzer(store)
    trend = analyzer.trend_analysis(window_days=window_days)

    if trend.get("error"):
        print(f"❌ データがありません: {trend['error']}")
        return

    recent = trend["recent"]
    previous = trend["previous"]

    print(f"\n{'=' * 60}")
    print(f"📈 エンゲージメントトレンド（{window_days}日間比較）")
    print(f"{'=' * 60}")

    print(f"\n{'':>16} {'直近期間':>12} {'前期間':>12} {'変化':>10}")
    print("-" * 52)

    def _compare(label: str, key: str, fmt: str = "d") -> None:
        r_val = recent.get(key, 0)
        p_val = previous.get(key, 0)
        if fmt == "%":
            r_str = f"{r_val:.2%}"
            p_str = f"{p_val:.2%}"
            diff = r_val - p_val
            d_str = f"{diff:+.2%}" if p_val else "N/A"
        else:
            r_str = str(r_val)
            p_str = str(p_val)
            diff = r_val - p_val if p_val else 0
            d_str = f"{diff:+d}" if p_val else "N/A"
        print(f"{label:>16} {r_str:>12} {p_str:>12} {d_str:>10}")

    _compare("投稿数", "posts")
    _compare("平均views", "avg_views")
    _compare("平均ER", "avg_engagement_rate", "%")
    _compare("合計いいね", "total_likes")

    # フォロワー推移
    followers = store.load_followers()
    if len(followers) >= 2:
        latest = followers[-1]
        first = followers[0]
        growth = latest["count"] - first["count"]
        print(f"\n📊 フォロワー: {latest['count']} ({first['date']}から{growth:+d})")

    print()


# ---------------------------------------------------------------------------
# compare: Threads vs Instagram 比較
# ---------------------------------------------------------------------------


def cmd_compare(store: InsightsStore) -> None:
    """Threads と Instagram のパフォーマンスを比較する."""
    all_insights = store.list_post_insights()
    dual_posted = [
        i for i in all_insights
        if i.get("threads_insights") and i.get("instagram_insights")
    ]

    if not dual_posted:
        print("📭 Threads/Instagram 両方のインサイトがある投稿がありません。")
        print("   Instagram インサイトの収集は今後のアップデートで対応予定です。")
        return

    print(f"\n{'=' * 60}")
    print(f"📊 Threads vs Instagram 比較（{len(dual_posted)} 投稿）")
    print(f"{'=' * 60}")

    for item in dual_posted:
        t = item["threads_insights"]
        i = item["instagram_insights"]
        print(f"\n  {item['post_id']} ({item.get('theme', '?')} / {item.get('type', '?')})")
        print(f"    Threads:   views={t['views']} ER={t['engagement_rate']:.2%}")
        print(f"    Instagram: views={i.get('views', 'N/A')} ER={i.get('engagement_rate', 'N/A')}")


# ---------------------------------------------------------------------------
# CLI エントリポイント
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(description="エンゲージメント分析")
    parser.add_argument(
        "--account",
        default="career_sister",
        help="アカウント名 (default: career_sister)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # matrix
    subparsers.add_parser("matrix", help="エンゲージメントマトリクスを構築")

    # report
    subparsers.add_parser("report", help="エンゲージメントレポートを表示")

    # recommend
    subparsers.add_parser("recommend", help="テーマ重み調整を推奨")

    # apply
    p_apply = subparsers.add_parser("apply", help="推奨された重みを適用")
    p_apply.add_argument("--dry-run", action="store_true", help="変更を適用しない")

    # trend
    p_trend = subparsers.add_parser("trend", help="エンゲージメントトレンドを表示")
    p_trend.add_argument("--window", type=int, default=7, help="比較期間（日数）")

    # compare
    subparsers.add_parser("compare", help="Threads vs Instagram を比較")

    args = parser.parse_args()
    store = InsightsStore(args.account)

    if args.command == "matrix":
        cmd_matrix(store)
    elif args.command == "report":
        cmd_report(store)
    elif args.command == "recommend":
        cmd_recommend(store, args.account)
    elif args.command == "apply":
        cmd_apply(store, args.account, dry_run=args.dry_run)
    elif args.command == "trend":
        cmd_trend(store, window_days=args.window)
    elif args.command == "compare":
        cmd_compare(store)


if __name__ == "__main__":
    main()
