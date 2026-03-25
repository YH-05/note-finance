"""note.com Playwright-based collector.

NoteComBrowser を使い、note-com-creators.json に登録されたクリエイターの
公開記事を収集する。有料記事は自動的にスキップされる。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from data_pipeline.collectors.base import (
    BaseCollector,
    CollectedItem,
    CollectionResult,
)
from data_pipeline.collectors.note_com_browser import NoteArticle, NoteComBrowser

if TYPE_CHECKING:
    from pathlib import Path

    from data_pipeline.registry.models import DataSource

logger = logging.getLogger(__name__)

# AIDEV-NOTE: source_id のプレフィックス。"note-com-{username}" 形式で
# 個別クリエイターを識別する。
_SOURCE_ID_PREFIX = "note-com"


class NoteComCollector(BaseCollector):
    """note.com Playwright-based collector.

    note-com-creators.json からクリエイター一覧を取得し、
    NoteComBrowser で各クリエイターの記事を収集する。

    Parameters
    ----------
    config_dir : Path
        data/config/ ディレクトリのパス。
    max_articles : int
        1クリエイターあたりの最大記事数。
    request_delay : float
        リクエスト間隔（秒）。
    headless : bool
        ヘッドレスモードで実行するか。
    """

    def __init__(
        self,
        config_dir: Path,
        *,
        max_articles: int = 50,
        request_delay: float = 2.0,
        headless: bool = True,
    ) -> None:
        self.config_dir = config_dir
        self.max_articles = max_articles
        self.request_delay = request_delay
        self.headless = headless

    def collect(self, source: DataSource) -> CollectionResult:
        """同期インターフェース。内部で asyncio.run() を呼ぶ。

        Parameters
        ----------
        source : DataSource
            収集対象のデータソース定義。

        Returns
        -------
        CollectionResult
            収集結果（アイテム + エラー情報）。
        """
        return asyncio.run(self._collect_async(source))

    async def _collect_async(self, source: DataSource) -> CollectionResult:
        """非同期メインロジック。

        Parameters
        ----------
        source : DataSource
            収集対象のデータソース定義。

        Returns
        -------
        CollectionResult
            収集結果（アイテム + エラー情報）。
        """
        result = CollectionResult(source_id=source.source_id)

        creators = self._load_creators(source)
        if not creators:
            result.errors.append(
                f"No enabled creators found for source '{source.source_id}'",
            )
            result.finish()
            return result

        logger.info(
            "note_com_collection_starting source_id=%s creator_count=%d max_articles=%d",
            source.source_id,
            len(creators),
            self.max_articles,
        )

        async with NoteComBrowser(
            headless=self.headless,
            request_delay=self.request_delay,
        ) as browser:
            for creator in creators:
                username: str = creator["username"]
                source_id = (
                    source.source_id
                    if source.source_id != _SOURCE_ID_PREFIX
                    else f"{_SOURCE_ID_PREFIX}-{username}"
                )

                try:
                    items = await self._collect_creator(
                        browser=browser,
                        username=username,
                        source_id=source_id,
                    )
                    result.items.extend(items)
                    logger.info(
                        "creator_collection_completed username=%s article_count=%d",
                        username,
                        len(items),
                    )
                except Exception as exc:
                    error_msg = f"Failed to collect from creator '{username}': {exc}"
                    result.errors.append(error_msg)
                    logger.error(
                        "creator_collection_failed username=%s error=%s",
                        username,
                        str(exc),
                        exc_info=True,
                    )

        result.finish()
        logger.info(
            "note_com_collection_finished source_id=%s total_items=%d total_errors=%d",
            source.source_id,
            result.success_count,
            result.error_count,
        )
        return result

    async def _collect_creator(
        self,
        *,
        browser: NoteComBrowser,
        username: str,
        source_id: str,
    ) -> list[CollectedItem]:
        """1クリエイターの記事を収集する。

        Parameters
        ----------
        browser : NoteComBrowser
            起動済みブラウザインスタンス。
        username : str
            note.com のユーザー名。
        source_id : str
            CollectedItem に付与する source_id。

        Returns
        -------
        list[CollectedItem]
            収集された記事のリスト。
        """
        # max_pages を max_articles から概算（1ページ約10記事想定）
        max_pages = max(1, (self.max_articles + 9) // 10)

        urls = await browser.list_article_urls(username, max_pages=max_pages)
        urls = urls[: self.max_articles]

        logger.info(
            "scraping_creator_articles username=%s url_count=%d",
            username,
            len(urls),
        )

        items: list[CollectedItem] = []
        for url in urls:
            article = await browser.scrape_article(url)
            if article is None:
                # 有料記事またはスクレイプ失敗 — スキップ
                logger.debug("article_skipped url=%s username=%s", url, username)
                continue

            item = self._article_to_collected_item(article, source_id)
            items.append(item)

        return items

    def _load_creators(self, source: DataSource) -> list[dict]:
        """note-com-creators.json からクリエイター一覧を取得する。

        source.config_ref.file から設定ファイルを読み込み、
        enabled=true のクリエイターを返す。
        source_id でフィルタも可能にする（source.source_id が
        "note-com-{username}" 形式の場合）。

        Parameters
        ----------
        source : DataSource
            データソース定義。config_ref.file で設定ファイルを参照する。

        Returns
        -------
        list[dict]
            有効なクリエイター情報のリスト。
        """
        # 設定ファイルパスの解決
        if source.config_ref is not None:
            config_path = self.config_dir / source.config_ref.file
        else:
            config_path = self.config_dir / "note-com-creators.json"

        if not config_path.exists():
            logger.warning(
                "creators_config_not_found path=%s",
                str(config_path),
            )
            return []

        try:
            with config_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error(
                "creators_config_load_failed path=%s error=%s",
                str(config_path),
                str(exc),
            )
            return []

        creators: list[dict] = data.get("creators", [])

        # enabled フィルタ
        enabled_creators = [c for c in creators if c.get("enabled", True)]

        # source_id が "note-com-{username}" 形式の場合、特定クリエイターのみ
        if (
            source.source_id.startswith(f"{_SOURCE_ID_PREFIX}-")
            and source.source_id != _SOURCE_ID_PREFIX
        ):
            target_username = source.source_id[len(f"{_SOURCE_ID_PREFIX}-") :]
            enabled_creators = [
                c for c in enabled_creators if c.get("username") == target_username
            ]

        logger.debug(
            "creators_loaded config_path=%s total=%d enabled=%d",
            str(config_path),
            len(creators),
            len(enabled_creators),
        )
        return enabled_creators

    @staticmethod
    def _article_to_collected_item(
        article: NoteArticle,
        source_id: str,
    ) -> CollectedItem:
        """NoteArticle を CollectedItem に変換する。

        Parameters
        ----------
        article : NoteArticle
            スクレイプ済みの note.com 記事データ。
        source_id : str
            CollectedItem に付与する source_id。

        Returns
        -------
        CollectedItem
            統一フォーマットに変換された記事データ。
        """
        return CollectedItem(
            source_id=source_id,
            url=article.url,
            title=article.title,
            raw_text=article.body_text,
            published_at=article.published_at,
            author=article.author,
            collection_method="note-com",
            content_type="article",
            language="ja",
            metadata={
                "hashtags": article.hashtags,
                "like_count": article.like_count,
            },
        )


__all__ = ["NoteComCollector"]
