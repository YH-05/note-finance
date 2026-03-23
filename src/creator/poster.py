"""Threads / Instagram 投稿モジュール.

Container → Publish の2ステップモデルで両APIに対応。
画像投稿には公開URLが必要（image_hosting.py と連携）。
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Literal

import httpx
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------
THREADS_BASE = "https://graph.threads.net/v1.0"
INSTAGRAM_BASE = "https://graph.instagram.com/v24.0"

CONTAINER_POLL_INTERVAL = 5  # 秒
CONTAINER_POLL_MAX = 30  # 最大待機回数


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------
@dataclass
class PostResult:
    """投稿結果."""

    platform: Literal["threads", "instagram"]
    media_id: str
    permalink: str | None = None
    timestamp: str | None = None
    error: str | None = None


@dataclass
class ThreadsConfig:
    """Threads API 設定."""

    access_token: str = field(
        default_factory=lambda: os.getenv("THREADS_ACCESS_TOKEN", "")
    )
    user_id: str = field(default_factory=lambda: os.getenv("THREADS_USER_ID", ""))


@dataclass
class InstagramConfig:
    """Instagram API 設定."""

    access_token: str = field(
        default_factory=lambda: os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    )
    user_id: str = field(default_factory=lambda: os.getenv("INSTAGRAM_USER_ID", ""))


# ---------------------------------------------------------------------------
# Threads Poster
# ---------------------------------------------------------------------------
class ThreadsPoster:
    """Threads API 投稿クライアント."""

    def __init__(self, config: ThreadsConfig | None = None) -> None:
        self.config = config or ThreadsConfig()
        self._client = httpx.Client(timeout=30)

    def post_text(self, text: str) -> PostResult:
        """テキスト投稿."""
        container_id = self._create_container(media_type="TEXT", text=text)
        time.sleep(5)
        return self._publish(container_id)

    def post_image(self, text: str, image_url: str) -> PostResult:
        """画像付き投稿."""
        container_id = self._create_container(
            media_type="IMAGE", text=text, image_url=image_url
        )
        self._wait_for_container(container_id)
        return self._publish(container_id)

    def post_carousel(self, text: str, image_urls: list[str]) -> PostResult:
        """カルーセル投稿（複数画像）."""
        # Step 1: 子コンテナ作成
        child_ids = []
        for url in image_urls:
            resp = self._client.post(
                f"{THREADS_BASE}/{self.config.user_id}/threads",
                data={
                    "media_type": "IMAGE",
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": self.config.access_token,
                },
            )
            resp.raise_for_status()
            child_ids.append(resp.json()["id"])

        # Step 2: 親コンテナ作成
        resp = self._client.post(
            f"{THREADS_BASE}/{self.config.user_id}/threads",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "text": text,
                "access_token": self.config.access_token,
            },
        )
        resp.raise_for_status()
        carousel_id = resp.json()["id"]

        self._wait_for_container(carousel_id)
        return self._publish(carousel_id)

    def _create_container(
        self,
        *,
        media_type: str,
        text: str,
        image_url: str | None = None,
    ) -> str:
        data: dict[str, str] = {
            "media_type": media_type,
            "text": text,
            "access_token": self.config.access_token,
        }
        if image_url:
            data["image_url"] = image_url

        resp = self._client.post(
            f"{THREADS_BASE}/{self.config.user_id}/threads", data=data
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _wait_for_container(self, container_id: str) -> None:
        for _ in range(CONTAINER_POLL_MAX):
            time.sleep(CONTAINER_POLL_INTERVAL)
            resp = self._client.get(
                f"{THREADS_BASE}/{container_id}",
                params={
                    "fields": "status",
                    "access_token": self.config.access_token,
                },
            )
            status = resp.json().get("status")
            if status == "FINISHED":
                return
            if status == "ERROR":
                msg = resp.json().get("error_message", "Unknown error")
                raise RuntimeError(f"Threads container failed: {msg}")
        raise TimeoutError(f"Container {container_id} did not finish in time")

    def _publish(self, container_id: str) -> PostResult:
        resp = self._client.post(
            f"{THREADS_BASE}/{self.config.user_id}/threads_publish",
            data={
                "creation_id": container_id,
                "access_token": self.config.access_token,
            },
        )
        resp.raise_for_status()
        media_id = resp.json()["id"]

        # permalink 取得
        detail = self._client.get(
            f"{THREADS_BASE}/{media_id}",
            params={
                "fields": "id,permalink,timestamp",
                "access_token": self.config.access_token,
            },
        ).json()

        return PostResult(
            platform="threads",
            media_id=media_id,
            permalink=detail.get("permalink"),
            timestamp=detail.get("timestamp"),
        )

    def get_rate_limit(self) -> dict:
        """レート制限の使用状況を取得."""
        resp = self._client.get(
            f"{THREADS_BASE}/{self.config.user_id}/threads_publishing_limit",
            params={
                "fields": "quota_usage,config",
                "access_token": self.config.access_token,
            },
        )
        return resp.json()


# ---------------------------------------------------------------------------
# Instagram Poster
# ---------------------------------------------------------------------------
class InstagramPoster:
    """Instagram Graph API 投稿クライアント."""

    def __init__(self, config: InstagramConfig | None = None) -> None:
        self.config = config or InstagramConfig()
        self._client = httpx.Client(timeout=60)

    def post_image(self, caption: str, image_url: str) -> PostResult:
        """単一画像投稿."""
        container_id = self._create_container(image_url=image_url, caption=caption)
        self._wait_for_container(container_id)
        return self._publish(container_id)

    def post_carousel(self, caption: str, image_urls: list[str]) -> PostResult:
        """カルーセル投稿（2〜10枚）."""
        if len(image_urls) < 2:
            raise ValueError("Carousel requires at least 2 images")
        if len(image_urls) > 10:
            raise ValueError("Carousel supports max 10 images")

        # Step 1: 子コンテナ作成
        child_ids = []
        for url in image_urls:
            resp = self._client.post(
                f"{INSTAGRAM_BASE}/{self.config.user_id}/media",
                data={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": self.config.access_token,
                },
            )
            resp.raise_for_status()
            child_ids.append(resp.json()["id"])

        # Step 2: 全子コンテナの FINISHED 待ち
        for cid in child_ids:
            self._wait_for_container(cid)

        # Step 3: 親コンテナ作成
        resp = self._client.post(
            f"{INSTAGRAM_BASE}/{self.config.user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": self.config.access_token,
            },
        )
        resp.raise_for_status()
        carousel_id = resp.json()["id"]

        # Step 4: 親コンテナ FINISHED 待ち
        self._wait_for_container(carousel_id)

        # Step 5: Publish
        return self._publish(carousel_id)

    def _create_container(
        self,
        *,
        image_url: str,
        caption: str,
    ) -> str:
        resp = self._client.post(
            f"{INSTAGRAM_BASE}/{self.config.user_id}/media",
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.config.access_token,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def _wait_for_container(self, container_id: str) -> None:
        for _ in range(CONTAINER_POLL_MAX):
            time.sleep(CONTAINER_POLL_INTERVAL)
            resp = self._client.get(
                f"{INSTAGRAM_BASE}/{container_id}",
                params={
                    "fields": "status_code",
                    "access_token": self.config.access_token,
                },
            )
            status = resp.json().get("status_code")
            if status == "FINISHED":
                return
            if status == "ERROR":
                msg = resp.json().get("error_message", "Unknown error")
                raise RuntimeError(f"Instagram container failed: {msg}")
        raise TimeoutError(f"Container {container_id} did not finish in time")

    def _publish(self, container_id: str) -> PostResult:
        resp = self._client.post(
            f"{INSTAGRAM_BASE}/{self.config.user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.config.access_token,
            },
        )
        resp.raise_for_status()
        media_id = resp.json()["id"]

        # permalink 取得
        detail = self._client.get(
            f"{INSTAGRAM_BASE}/{media_id}",
            params={
                "fields": "id,permalink,timestamp,caption",
                "access_token": self.config.access_token,
            },
        ).json()

        return PostResult(
            platform="instagram",
            media_id=media_id,
            permalink=detail.get("permalink"),
            timestamp=detail.get("timestamp"),
        )

    def get_rate_limit(self) -> dict:
        """レート制限の使用状況を取得."""
        resp = self._client.get(
            f"{INSTAGRAM_BASE}/{self.config.user_id}/content_publishing_limit",
            params={
                "fields": "quota_usage,config",
                "access_token": self.config.access_token,
            },
        )
        return resp.json()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SNS投稿CLI")
    parser.add_argument("platform", choices=["threads", "instagram"])
    parser.add_argument("--text", required=True, help="投稿テキスト")
    parser.add_argument("--image-url", help="画像URL（Instagram必須）")
    parser.add_argument("--image-urls", nargs="+", help="カルーセル用複数画像URL")
    args = parser.parse_args()

    if args.platform == "threads":
        poster = ThreadsPoster()
        if args.image_urls:
            result = poster.post_carousel(args.text, args.image_urls)
        elif args.image_url:
            result = poster.post_image(args.text, args.image_url)
        else:
            result = poster.post_text(args.text)
    else:
        poster = InstagramPoster()
        if args.image_urls:
            result = poster.post_carousel(args.text, args.image_urls)
        elif args.image_url:
            result = poster.post_image(args.text, args.image_url)
        else:
            parser.error("Instagram requires --image-url or --image-urls")

    print(f"Platform: {result.platform}")
    print(f"Media ID: {result.media_id}")
    print(f"Permalink: {result.permalink}")
    print(f"Timestamp: {result.timestamp}")
