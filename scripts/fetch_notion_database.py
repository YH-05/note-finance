#!/usr/bin/env python3
"""Notion Database → RawStore フェッチスクリプト.

メインNotionデータベース（2d18b707-7dce-801e-bc9d-ff46f91e4d42）からページを取得し、
ブロック本文を抽出してRawStoreに保存する。

保存後は `data_pipeline ingest` コマンドで Neo4j に投入する。

Usage
-----
::

    # 全件取得（RawStore保存のみ）
    uv run python scripts/fetch_notion_database.py

    # タグ絞り込み
    uv run python scripts/fetch_notion_database.py --tag ai_sns
    uv run python scripts/fetch_notion_database.py --tag side_business

    # 取得 + 投入まで
    uv run python scripts/fetch_notion_database.py --tag side_business --ingest --target creator
    uv run python scripts/fetch_notion_database.py --tag finance --ingest --target research

    # 保存後に個別投入
    uv run python -m data_pipeline ingest --source notion-db --target creator --genre career
    uv run python -m data_pipeline ingest --source notion-db-finance --target research

"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

DATABASE_ID = "2d18b707-7dce-801e-bc9d-ff46f91e4d42"
NOTION_VERSION = "2022-06-28"
API_BASE = "https://api.notion.com/v1"

# タグ → source_id サフィックスのマッピング
# タグ指定なしの場合は "notion-db"、タグ指定時は "notion-db-{tag}"
_DEFAULT_SOURCE_ID = "notion-db"

# タグ → 推奨ターゲット（--ingest 省略時の参考情報として表示）
TAG_DEFAULT_TARGET: dict[str, str] = {
    "finance": "research",
    "quants": "research",
    "python": "research",
    "ai_database": "research",
    "ai_rag": "research",
    "ai_sns": "creator",
    "ai_agent": "creator",
    "ai_coding": "creator",
    "ai_writing": "creator",
    "side_business": "creator",
    "knowledge_management": "creator",
    "study": "creator",
    "note_summary": "creator",
    "scrapbook": "creator",
}

# ---------------------------------------------------------------------------
# Notion API クライアント
# ---------------------------------------------------------------------------


class NotionClient:
    """Notion REST API の薄いラッパー."""

    def __init__(self, api_key: str) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )

    def query_database(
        self,
        database_id: str,
        tag_filter: str | None = None,
        since_date: str | None = None,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """データベースの全ページを取得する（ページネーション対応）.

        Parameters
        ----------
        database_id : str
            NotionデータベースID。
        tag_filter : str | None
            multi_select タグで絞り込む場合に指定。
        since_date : str | None
            この日付以降のアイテムのみ取得（YYYY-MM-DD形式）。
            Notionの "Created time" プロパティでフィルタリングする。
        page_size : int
            1リクエストあたりの取得件数（最大100）。

        Returns
        -------
        list[dict]
            ページオブジェクトのリスト。
        """
        url = f"{API_BASE}/databases/{database_id}/query"
        body: dict[str, Any] = {"page_size": page_size}

        # フィルタ条件を構築
        conditions: list[dict] = []
        if tag_filter:
            conditions.append(
                {"property": "tags", "multi_select": {"contains": tag_filter}}
            )
        if since_date:
            conditions.append(
                {
                    "property": "Created time",
                    "created_time": {"after": f"{since_date}T00:00:00+00:00"},
                }
            )

        if len(conditions) == 1:
            body["filter"] = conditions[0]
        elif len(conditions) > 1:
            body["filter"] = {"and": conditions}

        pages: list[dict] = []
        start_cursor: str | None = None

        while True:
            if start_cursor:
                body["start_cursor"] = start_cursor

            resp = self.session.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

            pages.extend(data.get("results", []))

            if data.get("has_more"):
                start_cursor = data.get("next_cursor")
            else:
                break

            time.sleep(0.3)  # レート制限回避

        return pages

    def get_block_children(self, block_id: str) -> list[dict[str, Any]]:
        """ブロックの子ブロックを全件取得する（ページネーション対応）.

        Parameters
        ----------
        block_id : str
            ページIDまたはブロックID。

        Returns
        -------
        list[dict]
            ブロックオブジェクトのリスト。
        """
        url = f"{API_BASE}/blocks/{block_id}/children"
        blocks: list[dict] = []
        start_cursor: str | None = None

        while True:
            params: dict[str, Any] = {"page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor

            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            blocks.extend(data.get("results", []))

            if data.get("has_more"):
                start_cursor = data.get("next_cursor")
            else:
                break

            time.sleep(0.2)

        return blocks


# ---------------------------------------------------------------------------
# ブロック → プレーンテキスト変換
# ---------------------------------------------------------------------------

_RICH_TEXT_BLOCK_TYPES = {
    "paragraph",
    "heading_1",
    "heading_2",
    "heading_3",
    "bulleted_list_item",
    "numbered_list_item",
    "quote",
    "callout",
    "toggle",
}

_HEADING_PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
    "quote": "> ",
}


def _extract_rich_text(rich_text_list: list[dict]) -> str:
    """rich_text 配列からプレーンテキストを連結して返す."""
    return "".join(rt.get("plain_text", "") for rt in rich_text_list)


def blocks_to_text(blocks: list[dict], *, depth: int = 0) -> str:
    """ブロックリストをプレーンテキストに変換する.

    Parameters
    ----------
    blocks : list[dict]
        Notion ブロックオブジェクトのリスト。
    depth : int
        ネスト深度（インデント用）。

    Returns
    -------
    str
        結合されたプレーンテキスト。
    """
    lines: list[str] = []
    indent = "  " * depth

    for block in blocks:
        block_type = block.get("type", "")
        content = block.get(block_type, {})

        if block_type in _RICH_TEXT_BLOCK_TYPES:
            rich_text = content.get("rich_text", [])
            text = _extract_rich_text(rich_text).strip()
            if text:
                prefix = _HEADING_PREFIX.get(block_type, "")
                if block_type == "bulleted_list_item":
                    prefix = "- "
                elif block_type == "numbered_list_item":
                    prefix = "1. "
                lines.append(f"{indent}{prefix}{text}")

        elif block_type == "code":
            rich_text = content.get("rich_text", [])
            text = _extract_rich_text(rich_text).strip()
            lang = content.get("language", "")
            if text:
                lines.append(f"```{lang}\n{text}\n```")

        elif block_type == "divider":
            lines.append("---")

        elif block_type == "image":
            # 画像はキャプションのみ抽出
            caption = _extract_rich_text(content.get("caption", [])).strip()
            if caption:
                lines.append(f"[画像: {caption}]")

        elif block_type == "table_of_contents":
            pass  # スキップ

        # その他（embed, video, file 等）はスキップ

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ページメタデータ抽出
# ---------------------------------------------------------------------------


def extract_page_meta(page: dict) -> dict[str, Any]:
    """Notion ページオブジェクトからメタデータを抽出する.

    Returns
    -------
    dict with keys: page_id, title, url, tags, created_time
    """
    props = page.get("properties", {})

    # タイトル
    title_list = props.get("Name", {}).get("title", [])
    title = _extract_rich_text(title_list).strip()

    # 元記事URL
    source_url = props.get("URL", {}).get("url") or ""

    # タグ
    tags = [t["name"] for t in props.get("tags", {}).get("multi_select", [])]

    # 作成時刻
    created_time_str = props.get("Created time", {}).get("created_time", "")
    created_time: datetime | None = None
    if created_time_str:
        try:
            created_time = datetime.fromisoformat(
                created_time_str.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    return {
        "page_id": page["id"],
        "title": title,
        "url": source_url or f"https://www.notion.so/{page['id'].replace('-', '')}",
        "tags": tags,
        "created_time": created_time,
        "notion_url": page.get("url", ""),
    }


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------


def fetch_and_save(
    *,
    api_key: str,
    tag_filter: str | None,
    since_date: str | None,
    source_id: str,
    dry_run: bool,
    max_pages: int | None,
) -> dict[str, int]:
    """Notion DB からフェッチして RawStore に保存する.

    Returns
    -------
    dict with keys: total, saved, skipped_duplicate, skipped_empty, errors
    """
    from data_pipeline.storage.raw_store import RawStore

    client = NotionClient(api_key)
    store = RawStore()

    logger.info(
        "Querying Notion Database (tag=%s, since=%s)...",
        tag_filter or "all",
        since_date or "none",
    )
    pages = client.query_database(
        DATABASE_ID, tag_filter=tag_filter, since_date=since_date
    )

    if max_pages:
        pages = pages[:max_pages]

    logger.info("Found %d pages", len(pages))

    stats = {"total": len(pages), "saved": 0, "skipped_duplicate": 0, "skipped_empty": 0, "errors": 0}

    for i, page in enumerate(pages, 1):
        meta = extract_page_meta(page)
        logger.debug("[%d/%d] %s", i, len(pages), meta["title"][:60])

        if dry_run:
            print(f"  [dry-run] {meta['title'][:80]}")
            continue

        # ブロック取得
        try:
            blocks = client.get_block_children(meta["page_id"])
        except requests.HTTPError as e:
            logger.warning("Failed to fetch blocks for %s: %s", meta["page_id"], e)
            stats["errors"] += 1
            continue

        raw_text = blocks_to_text(blocks)

        if not raw_text.strip():
            logger.debug("Empty content: %s", meta["title"][:60])
            stats["skipped_empty"] += 1
            continue

        outcome = store.save_text(
            source_id=source_id,
            url=meta["url"],
            title=meta["title"],
            raw_text=raw_text,
            collection_method="notion-db",
            published_at=meta["created_time"],
            language="ja",
            metadata={
                "tags": meta["tags"],
                "notion_url": meta["notion_url"],
                "page_id": meta["page_id"],
            },
        )

        if outcome == "saved":
            stats["saved"] += 1
        elif outcome == "duplicate":
            stats["skipped_duplicate"] += 1
        elif outcome == "empty":
            stats["skipped_empty"] += 1

        if i % 10 == 0:
            logger.info("Progress: %d/%d (saved=%d)", i, len(pages), stats["saved"])

        time.sleep(0.2)  # レート制限回避

    return stats


def main() -> int:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(
        description="Notion Database → RawStore フェッチ",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  uv run python scripts/fetch_notion_database.py
  uv run python scripts/fetch_notion_database.py --tag ai_sns
  uv run python scripts/fetch_notion_database.py --tag side_business --ingest --target creator
  uv run python scripts/fetch_notion_database.py --tag finance --ingest --target research --genre finance
        """,
    )
    parser.add_argument(
        "--tag",
        help="タグで絞り込み（例: ai_sns, side_business, finance）",
    )
    parser.add_argument(
        "--since",
        help="この日付以降のアイテムのみ取得（YYYY-MM-DD形式）。"
        "例: 2026-03-20（直近7日なら呼び出し側で計算して渡す）",
    )
    parser.add_argument(
        "--source-id",
        help="RawStore source_id（デフォルト: notion-db または notion-db-{tag}）",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="RawStore保存後に data_pipeline ingest を実行",
    )
    parser.add_argument(
        "--target",
        choices=["creator", "research"],
        default=None,
        help="投入先 Neo4j（--ingest 時に必須）",
    )
    parser.add_argument(
        "--genre",
        default="career",
        help="creator向けジャンル（デフォルト: career）",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="最大取得ページ数（デフォルト: 無制限）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="RawStore保存をスキップ（タイトル一覧のみ表示）",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="詳細ログ",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # APIキー確認
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        logger.error("NOTION_API_KEY が設定されていません。.env を確認してください。")
        return 1

    # --ingest 時は --target が必須
    if args.ingest and not args.target:
        # タグから推測
        if args.tag and args.tag in TAG_DEFAULT_TARGET:
            args.target = TAG_DEFAULT_TARGET[args.tag]
            logger.info("--target を自動設定: %s（タグ: %s）", args.target, args.tag)
        else:
            logger.error("--ingest 時は --target creator または --target research を指定してください")
            return 1

    # source_id を決定
    source_id = args.source_id
    if not source_id:
        source_id = f"notion-db-{args.tag}" if args.tag else _DEFAULT_SOURCE_ID

    print(f"\n{'=' * 60}")
    print(f"Notion Database → RawStore")
    print(f"  Database : {DATABASE_ID}")
    print(f"  Tag      : {args.tag or '（全件）'}")
    if args.since:
        print(f"  Since    : {args.since} 以降")
    print(f"  Source ID: {source_id}")
    if args.ingest:
        print(f"  Target   : {args.target}")
        print(f"  Genre    : {args.genre}")
    if args.dry_run:
        print("  [DRY RUN] RawStore保存はスキップ")
    print(f"{'=' * 60}\n")

    # フェッチ & 保存
    stats = fetch_and_save(
        api_key=api_key,
        tag_filter=args.tag,
        since_date=args.since,
        source_id=source_id,
        dry_run=args.dry_run,
        max_pages=args.max_pages,
    )

    print(f"\n{'=' * 60}")
    print(f"RawStore 保存結果")
    print(f"  取得     : {stats['total']} 件")
    print(f"  保存     : {stats['saved']} 件")
    print(f"  重複スキップ: {stats['skipped_duplicate']} 件")
    print(f"  空スキップ : {stats['skipped_empty']} 件")
    print(f"  エラー   : {stats['errors']} 件")
    print(f"{'=' * 60}")

    if args.dry_run:
        return 0

    if stats["saved"] == 0 and not args.ingest:
        print("\n新規保存なし。投入をスキップします。")
        return 0

    # --ingest オプション
    if args.ingest:
        print(f"\ndata_pipeline ingest を実行 ({source_id} → {args.target})...")
        cmd = [
            "uv", "run", "python", "-m", "data_pipeline",
            "ingest",
            "--source", source_id,
            "--target", args.target,
            "--genre", args.genre,
        ]
        print(f"  $ {' '.join(cmd)}\n")
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            logger.error("ingest が失敗しました (exit code %d)", result.returncode)
            return result.returncode
    else:
        print(f"\n次のステップ（Neo4j投入）:")
        print(f"  uv run python -m data_pipeline ingest --source {source_id} --target creator --genre career")
        print(f"  uv run python -m data_pipeline ingest --source {source_id} --target research")

    return 0


if __name__ == "__main__":
    sys.exit(main())
