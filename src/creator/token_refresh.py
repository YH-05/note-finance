"""Threads / Instagram トークン自動リフレッシュ.

両APIとも60日有効のLong-lived tokenを使用。
30-50日ごとにリフレッシュすることで期限切れを防ぐ。

使い方:
    # 手動実行
    uv run python -m src.creator.token_refresh

    # cron（毎週日曜3時に実行）
    0 3 * * 0 cd /Users/yukihata/Desktop/note-finance && uv run python -m src.creator.token_refresh
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

THREADS_BASE = "https://graph.threads.net"
INSTAGRAM_BASE = "https://graph.instagram.com"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def refresh_threads_token(current_token: str) -> dict:
    """Threads の Long-lived token をリフレッシュ.

    Returns
    -------
    dict
        {"access_token": "...", "token_type": "bearer", "expires_in": 5184000}
    """
    resp = httpx.get(
        f"{THREADS_BASE}/refresh_access_token",
        params={
            "grant_type": "th_refresh_token",
            "access_token": current_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_instagram_token(current_token: str) -> dict:
    """Instagram の Long-lived token をリフレッシュ.

    Returns
    -------
    dict
        {"access_token": "...", "token_type": "bearer", "expires_in": 5184000}
    """
    resp = httpx.get(
        f"{INSTAGRAM_BASE}/refresh_access_token",
        params={
            "grant_type": "ig_refresh_token",
            "access_token": current_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_env_var(env_path: Path, key: str, new_value: str) -> None:
    """`.env` ファイル内の変数を更新."""
    content = env_path.read_text()
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)

    if pattern.search(content):
        content = pattern.sub(f"{key}={new_value}", content)
    else:
        content += f"\n{key}={new_value}\n"

    env_path.write_text(content)


def run_refresh() -> None:
    """両プラットフォームのトークンをリフレッシュし .env を更新."""
    now = datetime.now(tz=timezone.utc).isoformat()
    print(f"[{now}] Token refresh started")

    # Threads
    threads_token = os.getenv("THREADS_ACCESS_TOKEN", "")
    if threads_token:
        try:
            result = refresh_threads_token(threads_token)
            new_token = result["access_token"]
            expires_in = result.get("expires_in", 0)
            update_env_var(ENV_PATH, "THREADS_ACCESS_TOKEN", new_token)
            print(f"  Threads: refreshed (expires_in={expires_in}s = {expires_in // 86400}d)")
        except httpx.HTTPStatusError as e:
            error_body = e.response.json() if e.response.content else {}
            print(f"  Threads: FAILED - {error_body}")
        except Exception as e:
            print(f"  Threads: FAILED - {e}")
    else:
        print("  Threads: skipped (no token)")

    # Instagram
    ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if ig_token:
        try:
            result = refresh_instagram_token(ig_token)
            new_token = result["access_token"]
            expires_in = result.get("expires_in", 0)
            update_env_var(ENV_PATH, "INSTAGRAM_ACCESS_TOKEN", new_token)
            print(f"  Instagram: refreshed (expires_in={expires_in}s = {expires_in // 86400}d)")
        except httpx.HTTPStatusError as e:
            error_body = e.response.json() if e.response.content else {}
            print(f"  Instagram: FAILED - {error_body}")
        except Exception as e:
            print(f"  Instagram: FAILED - {e}")
    else:
        print("  Instagram: skipped (no token)")

    print("  Done.")


if __name__ == "__main__":
    run_refresh()
