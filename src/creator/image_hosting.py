"""画像ホスティングモジュール（Cloudflare R2）.

Instagram/Threads の投稿には公開URLの画像が必要。
ローカル画像を R2 にアップロードし、公開URLを返す。

セットアップ:
    1. Cloudflare アカウント作成 (https://dash.cloudflare.com/)
    2. R2 → Create Bucket → "creator-media"
    3. R2 → Bucket Settings → Public Access を有効化
    4. R2 → Manage R2 API Tokens → Create API Token (Object Read & Write)
    5. .env に以下を設定:
        R2_ACCOUNT_ID=...
        R2_ACCESS_KEY_ID=...
        R2_SECRET_ACCESS_KEY=...
        R2_BUCKET_NAME=creator-media
        R2_PUBLIC_URL=https://pub-xxxx.r2.dev
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import boto3
from dotenv import load_dotenv

load_dotenv()


class R2ImageHost:
    """Cloudflare R2 画像ホスティング."""

    def __init__(self) -> None:
        self.account_id = os.getenv("R2_ACCOUNT_ID", "")
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "creator-media")
        self.public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{self.account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY", ""),
            region_name="auto",
        )

    @property
    def is_configured(self) -> bool:
        """R2 が設定済みか."""
        return bool(self.account_id and self.public_url)

    def upload(self, local_path: str | Path, *, prefix: str = "images") -> str:
        """ローカル画像を R2 にアップロードし、公開URLを返す.

        Parameters
        ----------
        local_path
            アップロードするローカルファイルパス
        prefix
            R2 上のフォルダプレフィックス

        Returns
        -------
        str
            公開URL
        """
        path = Path(local_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # content-hash でファイル名を生成（重複アップロード防止）
        file_hash = hashlib.md5(path.read_bytes()).hexdigest()[:12]
        ext = path.suffix.lower()
        key = f"{prefix}/{file_hash}{ext}"

        content_type = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(ext, "application/octet-stream")

        self._client.upload_file(
            str(path),
            self.bucket_name,
            key,
            ExtraArgs={"ContentType": content_type},
        )

        return f"{self.public_url}/{key}"

    def upload_batch(
        self, local_paths: list[str | Path], *, prefix: str = "images"
    ) -> list[str]:
        """複数画像を一括アップロード."""
        return [self.upload(p, prefix=prefix) for p in local_paths]

    def delete(self, key: str) -> None:
        """R2 上のオブジェクトを削除."""
        self._client.delete_object(Bucket=self.bucket_name, Key=key)

    def list_objects(self, prefix: str = "") -> list[dict]:
        """R2 上のオブジェクト一覧."""
        resp = self._client.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
        return resp.get("Contents", [])
