"""Threads / Instagram インサイト取得モジュール.

投稿単位のエンゲージメントメトリクス（views, likes, replies, reposts, quotes）を
Threads Insights API から取得する。
permalink → media_id の解決もサポートする。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from creator.poster import (
    THREADS_BASE,
    ThreadsConfig,
)
from utils_core.logging.config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------


@dataclass
class MediaInsights:
    """投稿単位のインサイトメトリクス."""

    views: int
    likes: int
    replies: int
    reposts: int
    quotes: int
    engagement_rate: float
    fetched_at: str

    def to_dict(self) -> dict:
        """辞書に変換する."""
        return {
            "views": self.views,
            "likes": self.likes,
            "replies": self.replies,
            "reposts": self.reposts,
            "quotes": self.quotes,
            "engagement_rate": self.engagement_rate,
            "fetched_at": self.fetched_at,
        }


@dataclass
class UserInsights:
    """ユーザーレベルの集計インサイト."""

    views: int
    likes: int
    replies: int
    reposts: int
    quotes: int
    followers_count: int | None
    fetched_at: str

    def to_dict(self) -> dict:
        """辞書に変換する."""
        return {
            "views": self.views,
            "likes": self.likes,
            "replies": self.replies,
            "reposts": self.reposts,
            "quotes": self.quotes,
            "followers_count": self.followers_count,
            "fetched_at": self.fetched_at,
        }


@dataclass
class ThreadInfo:
    """Threads API から取得した投稿情報."""

    media_id: str
    permalink: str
    timestamp: str | None = None


# ---------------------------------------------------------------------------
# Threads Insights Client
# ---------------------------------------------------------------------------


class ThreadsInsightsClient:
    """Threads Insights API クライアント.

    Parameters
    ----------
    config : ThreadsConfig
        Threads API 認証設定。
    """

    MEDIA_METRICS = "views,likes,replies,reposts,quotes"
    USER_METRICS = "views,likes,replies,reposts,quotes,followers_count"

    def __init__(self, config: ThreadsConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=30)

    def get_media_insights(self, media_id: str) -> MediaInsights:
        """投稿のインサイトメトリクスを取得する.

        Parameters
        ----------
        media_id : str
            Threads メディア ID。

        Returns
        -------
        MediaInsights
            取得したメトリクス。
        """
        resp = self._client.get(
            f"{THREADS_BASE}/{media_id}/insights",
            params={
                "metric": self.MEDIA_METRICS,
                "access_token": self.config.access_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        metrics = self._parse_insights_response(data)
        views = metrics.get("views", 0)
        likes = metrics.get("likes", 0)
        replies = metrics.get("replies", 0)
        reposts = metrics.get("reposts", 0)
        quotes = metrics.get("quotes", 0)

        engagement = likes + replies + reposts + quotes
        engagement_rate = engagement / views if views > 0 else 0.0

        now = datetime.now(tz=timezone.utc).isoformat()

        logger.info(
            "media_insights_fetched",
            media_id=media_id,
            views=views,
            likes=likes,
            replies=replies,
            engagement_rate=round(engagement_rate, 4),
        )

        return MediaInsights(
            views=views,
            likes=likes,
            replies=replies,
            reposts=reposts,
            quotes=quotes,
            engagement_rate=round(engagement_rate, 4),
            fetched_at=now,
        )

    def get_user_insights(
        self,
        since: int | None = None,
        until: int | None = None,
    ) -> UserInsights:
        """ユーザーレベルの集計インサイトを取得する.

        Parameters
        ----------
        since : int | None
            開始 Unix タイムスタンプ。
        until : int | None
            終了 Unix タイムスタンプ。

        Returns
        -------
        UserInsights
            取得した集計メトリクス。
        """
        params: dict[str, str | int] = {
            "metric": self.USER_METRICS,
            "access_token": self.config.access_token,
        }
        if since is not None:
            params["since"] = since
        if until is not None:
            params["until"] = until

        resp = self._client.get(
            f"{THREADS_BASE}/{self.config.user_id}/threads_insights",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

        metrics = self._parse_insights_response(data)
        now = datetime.now(tz=timezone.utc).isoformat()

        logger.info(
            "user_insights_fetched",
            views=metrics.get("views", 0),
            followers_count=metrics.get("followers_count"),
        )

        return UserInsights(
            views=metrics.get("views", 0),
            likes=metrics.get("likes", 0),
            replies=metrics.get("replies", 0),
            reposts=metrics.get("reposts", 0),
            quotes=metrics.get("quotes", 0),
            followers_count=metrics.get("followers_count"),
            fetched_at=now,
        )

    def list_user_threads(self, limit: int = 100) -> list[ThreadInfo]:
        """ユーザーの投稿一覧を取得する（ページネーション対応）.

        Parameters
        ----------
        limit : int
            取得する最大投稿数。

        Returns
        -------
        list[ThreadInfo]
            投稿情報のリスト。
        """
        threads: list[ThreadInfo] = []
        url = f"{THREADS_BASE}/{self.config.user_id}/threads"
        params: dict[str, str | int] = {
            "fields": "id,permalink,timestamp",
            "limit": min(limit, 100),
            "access_token": self.config.access_token,
        }

        while len(threads) < limit:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("data", []):
                threads.append(
                    ThreadInfo(
                        media_id=item["id"],
                        permalink=item.get("permalink", ""),
                        timestamp=item.get("timestamp"),
                    )
                )
                if len(threads) >= limit:
                    break

            # ページネーション
            paging = data.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break
            url = next_url
            params = {}  # next_url にパラメータが含まれる

        logger.info("user_threads_listed", count=len(threads))
        return threads

    def resolve_media_ids(
        self, permalinks: list[str], max_fetch: int = 200
    ) -> dict[str, str]:
        """permalink → media_id のマッピングを構築する.

        Parameters
        ----------
        permalinks : list[str]
            解決したい permalink のリスト。
        max_fetch : int
            API から取得する最大投稿数。

        Returns
        -------
        dict[str, str]
            permalink → media_id のマッピング。
        """
        threads = self.list_user_threads(limit=max_fetch)
        permalink_set = set(permalinks)
        mapping: dict[str, str] = {}

        for t in threads:
            if t.permalink in permalink_set:
                mapping[t.permalink] = t.media_id

        resolved = len(mapping)
        unresolved = len(permalink_set) - resolved
        logger.info(
            "media_ids_resolved",
            resolved=resolved,
            unresolved=unresolved,
            total_fetched=len(threads),
        )
        return mapping

    @staticmethod
    def _parse_insights_response(data: dict) -> dict[str, int]:
        """Insights API レスポンスからメトリクス辞書を構築する."""
        metrics: dict[str, int] = {}
        for item in data.get("data", []):
            name = item.get("name", "")
            values = item.get("values", [])
            if values:
                metrics[name] = values[0].get("value", 0)
            else:
                total = item.get("total_value", {}).get("value", 0)
                metrics[name] = total
        return metrics
