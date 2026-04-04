"""インサイトデータのストレージと分析モジュール.

収集したインサイトの JSON 保存・読み込み、
テーマ×型×スロットの3次元エンゲージメントマトリクス構築、
重み調整推奨を提供する。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from utils_core.logging.config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# InsightsStore — JSON ストレージ
# ---------------------------------------------------------------------------


class InsightsStore:
    """インサイトデータの永続化を管理する.

    Parameters
    ----------
    account : str
        アカウント名（career_sister / mitsuki）。
    """

    def __init__(self, account: str) -> None:
        self.account = account
        self.base_dir = PROJECT_ROOT / "creator" / account / "analytics"
        self.insights_dir = self.base_dir / "insights"
        self.user_insights_dir = self.base_dir / "user_insights"

    def _ensure_dirs(self) -> None:
        self.insights_dir.mkdir(parents=True, exist_ok=True)
        self.user_insights_dir.mkdir(parents=True, exist_ok=True)

    def save_post_insights(self, post_id: str, data: dict) -> Path:
        """投稿インサイトを JSON ファイルに保存する."""
        self._ensure_dirs()
        path = self.insights_dir / f"{post_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("post_insights_saved", post_id=post_id, path=str(path))
        return path

    def load_post_insights(self, post_id: str) -> dict | None:
        """投稿インサイトを読み込む。未取得なら None を返す."""
        path = self.insights_dir / f"{post_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_post_insights(self) -> list[dict]:
        """全投稿インサイトを読み込む."""
        if not self.insights_dir.exists():
            return []
        results = []
        for p in sorted(self.insights_dir.glob("*.json")):
            results.append(json.loads(p.read_text(encoding="utf-8")))
        return results

    def save_user_insights(self, date_str: str, data: dict) -> Path:
        """ユーザー集計インサイトを保存する."""
        self._ensure_dirs()
        path = self.user_insights_dir / f"{date_str}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("user_insights_saved", date=date_str, path=str(path))
        return path

    def save_engagement_matrix(self, matrix: dict) -> Path:
        """エンゲージメントマトリクスを保存する."""
        self._ensure_dirs()
        path = self.base_dir / "engagement_matrix.json"
        path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("engagement_matrix_saved", path=str(path))
        return path

    def load_engagement_matrix(self) -> dict | None:
        """エンゲージメントマトリクスを読み込む."""
        path = self.base_dir / "engagement_matrix.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_follower_data(self, count: int) -> None:
        """フォロワー数をタイムシリーズに追記する."""
        self._ensure_dirs()
        path = self.base_dir / "followers.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {"data_points": []}

        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        points = data["data_points"]

        # 同日上書き
        existing = next((p for p in points if p["date"] == today), None)
        if existing:
            existing["count"] = count
        else:
            prev_count = points[-1]["count"] if points else None
            delta = count - prev_count if prev_count is not None else None
            points.append({"date": today, "count": count, "delta": delta})

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("follower_data_saved", date=today, count=count)

    def load_followers(self) -> list[dict]:
        """フォロワー推移データを読み込む."""
        path = self.base_dir / "followers.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("data_points", [])

    def save_weight_history(self, entry: dict) -> None:
        """重み調整履歴を追記する."""
        self._ensure_dirs()
        path = self.base_dir / "weight_history.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {"adjustments": []}
        data["adjustments"].append(entry)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("weight_history_saved", date=entry.get("date"))

    def posts_needing_insights(
        self, post_history: list[dict], min_hours: float = 24.0
    ) -> list[dict]:
        """インサイト未取得の投稿を抽出する.

        Parameters
        ----------
        post_history : list[dict]
            posting_state.json の post_history。
        min_hours : float
            投稿後の最小経過時間（時間）。

        Returns
        -------
        list[dict]
            インサイト取得が必要な投稿リスト。
        """
        now = datetime.now(tz=timezone.utc)
        needed = []
        for post in post_history:
            post_id = post.get("post_id", "")
            posted_at = post.get("posted_at")
            if not posted_at or not post.get("threads_permalink"):
                continue
            # 既にインサイト取得済みならスキップ
            if self.load_post_insights(post_id) is not None:
                continue
            # 経過時間チェック
            try:
                post_time = datetime.fromisoformat(posted_at)
                if post_time.tzinfo is None:
                    post_time = post_time.replace(tzinfo=timezone.utc)
                hours_elapsed = (now - post_time).total_seconds() / 3600
                if hours_elapsed >= min_hours:
                    needed.append(post)
            except (ValueError, TypeError):
                logger.warning("invalid_posted_at", post_id=post_id, posted_at=posted_at)
        return needed


# ---------------------------------------------------------------------------
# EngagementAnalyzer — 3次元マトリクス構築
# ---------------------------------------------------------------------------


class EngagementAnalyzer:
    """テーマ×型×スロットのエンゲージメントマトリクスを構築する.

    Parameters
    ----------
    store : InsightsStore
        インサイトストレージ。
    """

    def __init__(self, store: InsightsStore) -> None:
        self.store = store

    def build_matrix(self) -> dict:
        """全投稿インサイトからマトリクスを構築する."""
        all_insights = self.store.list_post_insights()
        if not all_insights:
            logger.warning("no_insights_data")
            return {"total_posts_analyzed": 0}

        # threads_insights が存在する投稿のみ
        valid = [
            i for i in all_insights
            if i.get("threads_insights") and i["threads_insights"].get("views", 0) > 0
        ]

        by_theme: dict[str, list[dict]] = {}
        by_type: dict[str, list[dict]] = {}
        by_slot: dict[str, list[dict]] = {}
        cross_theme_type: dict[str, list[dict]] = {}
        cross_theme_slot: dict[str, list[dict]] = {}
        cross_type_slot: dict[str, list[dict]] = {}

        for item in valid:
            ins = item["threads_insights"]
            theme = item.get("theme", "unknown")
            post_type = item.get("type", "unknown")
            slot = item.get("slot", "unknown")

            by_theme.setdefault(theme, []).append(ins)
            by_type.setdefault(post_type, []).append(ins)
            by_slot.setdefault(slot, []).append(ins)
            cross_theme_type.setdefault(f"{theme}_{post_type}", []).append(ins)
            cross_theme_slot.setdefault(f"{theme}_{slot}", []).append(ins)
            cross_type_slot.setdefault(f"{post_type}_{slot}", []).append(ins)

        now = datetime.now(tz=timezone.utc).isoformat()

        matrix = {
            "generated_at": now,
            "total_posts_analyzed": len(valid),
            "by_theme": self._aggregate(by_theme),
            "by_type": self._aggregate(by_type),
            "by_slot": self._aggregate(by_slot),
            "cross_dimensional": {
                "theme_x_type": self._aggregate(cross_theme_type),
                "theme_x_slot": self._aggregate(cross_theme_slot),
                "type_x_slot": self._aggregate(cross_type_slot),
            },
            "top_combinations": [],
            "bottom_combinations": [],
        }

        # Top / Bottom 組み合わせ（最低2投稿以上）
        all_combos = []
        for prefix, bucket in [
            ("theme_x_type", cross_theme_type),
            ("theme_x_slot", cross_theme_slot),
            ("type_x_slot", cross_type_slot),
        ]:
            for key, items in bucket.items():
                if len(items) >= 2:
                    avg_er = mean(i["engagement_rate"] for i in items)
                    all_combos.append({
                        "combo": key,
                        "dimension": prefix,
                        "avg_engagement_rate": round(avg_er, 4),
                        "posts": len(items),
                    })

        all_combos.sort(key=lambda x: x["avg_engagement_rate"], reverse=True)
        matrix["top_combinations"] = all_combos[:5]
        matrix["bottom_combinations"] = all_combos[-5:] if len(all_combos) >= 5 else all_combos

        logger.info(
            "engagement_matrix_built",
            total_posts=len(valid),
            themes=len(by_theme),
            types=len(by_type),
        )
        return matrix

    def trend_analysis(self, window_days: int = 7) -> dict:
        """直近期間 vs 前期間のエンゲージメント推移を算出する."""
        all_insights = self.store.list_post_insights()
        valid = [
            i for i in all_insights
            if i.get("threads_insights") and i.get("date")
        ]
        if not valid:
            return {"error": "no_data"}

        now = datetime.now(tz=timezone.utc)
        recent = []
        previous = []

        for item in valid:
            try:
                post_date = datetime.fromisoformat(item["date"] + "T00:00:00+00:00")
                days_ago = (now - post_date).days
                if days_ago <= window_days:
                    recent.append(item["threads_insights"])
                elif days_ago <= window_days * 2:
                    previous.append(item["threads_insights"])
            except (ValueError, TypeError):
                continue

        return {
            "window_days": window_days,
            "recent": self._period_summary(recent),
            "previous": self._period_summary(previous),
        }

    @staticmethod
    def _aggregate(bucket: dict[str, list[dict]]) -> dict:
        """バケット内のメトリクスを集計する."""
        result = {}
        for key, items in bucket.items():
            views_list = [i["views"] for i in items]
            er_list = [i["engagement_rate"] for i in items]
            result[key] = {
                "posts": len(items),
                "avg_views": round(mean(views_list)) if views_list else 0,
                "avg_engagement_rate": round(mean(er_list), 4) if er_list else 0.0,
                "total_likes": sum(i.get("likes", 0) for i in items),
                "total_replies": sum(i.get("replies", 0) for i in items),
            }
        return result

    @staticmethod
    def _period_summary(items: list[dict]) -> dict:
        """期間内メトリクスのサマリを算出する."""
        if not items:
            return {"posts": 0, "avg_views": 0, "avg_engagement_rate": 0.0}
        return {
            "posts": len(items),
            "avg_views": round(mean(i["views"] for i in items)),
            "avg_engagement_rate": round(
                mean(i["engagement_rate"] for i in items), 4
            ),
            "total_likes": sum(i.get("likes", 0) for i in items),
        }


# ---------------------------------------------------------------------------
# WeightRecommender — 重み調整推奨
# ---------------------------------------------------------------------------


class WeightRecommender:
    """エンゲージメントマトリクスからテーマ重みの調整を推奨する.

    Parameters
    ----------
    matrix : dict
        EngagementAnalyzer.build_matrix() の出力。
    posting_state : dict
        posting_state.json の内容。
    """

    MIN_POSTS = 3  # 推奨に必要な最低投稿数
    WEIGHT_STEP = 0.2
    WEIGHT_MIN = 0.3
    WEIGHT_MAX = 2.0

    def __init__(self, matrix: dict, posting_state: dict) -> None:
        self.matrix = matrix
        self.posting_state = posting_state

    def recommend(self) -> list[dict]:
        """テーマ重み調整の推奨リストを生成する."""
        by_theme = self.matrix.get("by_theme", {})
        if not by_theme:
            return []

        # 全テーマの平均エンゲージメント率
        all_rates = [
            v["avg_engagement_rate"]
            for v in by_theme.values()
            if v.get("posts", 0) >= self.MIN_POSTS
        ]
        if not all_rates:
            logger.warning("insufficient_data_for_recommendations", min_posts=self.MIN_POSTS)
            return []

        global_mean = mean(all_rates)
        themes_map = {t["id"]: t for t in self.posting_state.get("themes", [])}

        recommendations = []
        for theme_id, stats in by_theme.items():
            if stats["posts"] < self.MIN_POSTS:
                continue
            if theme_id not in themes_map:
                continue

            current_weight = themes_map[theme_id]["weight"]
            er = stats["avg_engagement_rate"]
            diff = er - global_mean

            if diff > 0.005:
                new_weight = min(current_weight + self.WEIGHT_STEP, self.WEIGHT_MAX)
                rationale = f"平均ER {er:.4f} > 全体平均 {global_mean:.4f}（+{diff:.4f}）"
            elif diff < -0.005:
                new_weight = max(current_weight - self.WEIGHT_STEP, self.WEIGHT_MIN)
                rationale = f"平均ER {er:.4f} < 全体平均 {global_mean:.4f}（{diff:.4f}）"
            else:
                continue

            if new_weight == current_weight:
                continue

            recommendations.append({
                "theme_id": theme_id,
                "theme_name": themes_map[theme_id]["name"],
                "old_weight": current_weight,
                "new_weight": round(new_weight, 1),
                "rationale": rationale,
                "posts_analyzed": stats["posts"],
                "avg_engagement_rate": er,
            })

        logger.info("weight_recommendations_generated", count=len(recommendations))
        return recommendations

    def apply(self, state_path: Path) -> dict:
        """推奨された重みを posting_state.json に反映する.

        Parameters
        ----------
        state_path : Path
            posting_state.json のパス。

        Returns
        -------
        dict
            適用した変更内容。
        """
        recommendations = self.recommend()
        if not recommendations:
            return {"applied": False, "reason": "no_recommendations"}

        state = json.loads(state_path.read_text(encoding="utf-8"))
        changes = {}

        for rec in recommendations:
            for theme in state.get("themes", []):
                if theme["id"] == rec["theme_id"]:
                    theme["weight"] = rec["new_weight"]
                    changes[rec["theme_id"]] = {
                        "old_weight": rec["old_weight"],
                        "new_weight": rec["new_weight"],
                        "rationale": rec["rationale"],
                    }
                    break

        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info("weights_applied", changes=len(changes))
        return {
            "applied": True,
            "changes": changes,
            "date": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        }
