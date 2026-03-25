"""RSSコレクター: feedparser ベースのRSSフィード収集.

MCP不要。Python単独で日次バッチ実行可能。
source_registry の config_ref で参照されるプリセットファイルからフィードURLを解決し、
feedparser で記事を取得する。

RSSに本文が含まれないフィード（金融庁、JETRO等）は trafilatura で
リンク先から本文を自動取得する。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any

import feedparser
import requests
import trafilatura

from data_pipeline.collectors.base import (
    BaseCollector,
    CollectedItem,
    CollectionResult,
)

if TYPE_CHECKING:
    from pathlib import Path

    from data_pipeline.registry.models import DataSource

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# AIDEV-NOTE: feedparser の日時パース失敗時のフォールバック用
_FALLBACK_FORMATS = [
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%d %H:%M:%S",
    "%a, %d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S %Z",
]


def _parse_datetime(value: str | None) -> datetime | None:
    """日時文字列をパースする. 失敗時は None."""
    if not value:
        return None
    # RFC 2822 形式を試行
    try:
        return parsedate_to_datetime(value)
    except (ValueError, TypeError):
        pass
    # フォールバックフォーマット
    for fmt in _FALLBACK_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _extract_text(entry: dict[str, Any]) -> str:
    """feedparser エントリから本文テキストを抽出する."""
    # content フィールド（完全な本文）を優先
    if entry.get("content"):
        contents = entry["content"]
        if isinstance(contents, list) and contents:
            return contents[0].get("value", "")
    # summary（要約・抜粋）にフォールバック
    if "summary" in entry:
        return entry.get("summary", "")
    # description
    if "description" in entry:
        return entry.get("description", "")
    return ""


# AIDEV-NOTE: 本文取得をスキップする拡張子・パターン
_SKIP_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".xls",
    ".csv",
    ".zip",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
}


def _should_skip_full_text(url: str) -> bool:
    """URLが本文取得に適さないかを判定する（PDF等のバイナリ）."""
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in _SKIP_EXTENSIONS)


def _fetch_full_text(url: str) -> str | None:
    """trafilatura でURL先から本文テキストを取得する.

    Returns
    -------
    str | None
        取得したテキスト。失敗時は None。
    """
    if _should_skip_full_text(url):
        return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return None
        return trafilatura.extract(downloaded)
    except Exception:
        return None


def _load_feed_urls_from_preset(
    config_dir: Path,
    preset_file: str,
    source_id: str | None = None,
) -> list[dict[str, Any]]:
    """プリセットファイルからフィード情報をロードする.

    Parameters
    ----------
    config_dir : Path
        設定ディレクトリ。
    preset_file : str
        プリセットファイル名。
    source_id : str | None
        指定時、source_id が一致するフィードのみ返す。
    """
    path = config_dir / preset_file
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    presets = data.get("presets", [])
    feeds = [p for p in presets if p.get("enabled", True)]
    # source_id フィルタ（プリセットに source_id がある場合のみ適用）
    if source_id and any("source_id" in p for p in presets):
        feeds = [p for p in feeds if p.get("source_id") == source_id]
    return feeds


class RssCollector(BaseCollector):
    """feedparser ベースの RSS コレクター.

    Parameters
    ----------
    config_dir : Path
        data/config/ ディレクトリのパス。プリセットファイルの解決に使用。
    max_items_per_feed : int
        1フィードあたりの最大取得件数。
    fetch_full_text : bool
        True の場合、全アイテムでリンク先から本文を取得する。
    fetch_if_empty : bool
        True の場合、RSS に本文が含まれないアイテムのみリンク先から取得する。
        fetch_full_text=True の場合はこの設定は無視される。
    request_delay : float
        本文取得時のリクエスト間隔（秒）。サイトへの負荷を抑制する。
    feed_timeout : float
        1フィードあたりのHTTPタイムアウト（秒）。応答しないフィードをスキップする。

    Examples
    --------
    >>> from data_pipeline.registry import RegistryLoader
    >>> loader = RegistryLoader()
    >>> registry = loader.load_source_registry()
    >>> source = registry.get_source("jp-finance")
    >>> collector = RssCollector(config_dir=loader.config_dir, fetch_if_empty=True)
    >>> result = collector.collect(source)
    >>> print(f"collected {result.success_count} items")
    """

    def __init__(
        self,
        config_dir: Path,
        *,
        max_items_per_feed: int = 50,
        fetch_full_text: bool = False,
        fetch_if_empty: bool = True,
        request_delay: float = 1.0,
        feed_timeout: float = 10.0,
    ) -> None:
        self.config_dir = config_dir
        self.max_items_per_feed = max_items_per_feed
        self.fetch_full_text = fetch_full_text
        self.fetch_if_empty = fetch_if_empty
        self.request_delay = request_delay
        self.feed_timeout = feed_timeout

    def collect(self, source: DataSource) -> CollectionResult:
        """RSSフィードからアイテムを収集する.

        config_ref のプリセットファイルからフィードURLを解決し、
        各フィードを feedparser で取得する。
        """
        result = CollectionResult(source_id=source.source_id)

        # フィードURLを解決
        feed_urls = self._resolve_feed_urls(source)
        if not feed_urls:
            result.errors.append(
                f"No feed URLs resolved for source '{source.source_id}'",
            )
            result.finish()
            return result

        # 各フィードを取得
        for feed_info in feed_urls:
            url = feed_info["url"]
            feed_title = feed_info.get("title", url)
            try:
                items = self._fetch_feed(source, url, feed_title)
                result.items.extend(items)
            except Exception as e:
                result.errors.append(f"Failed to fetch '{feed_title}' ({url}): {e}")

        # 本文取得（fetch_full_text or fetch_if_empty）
        if self.fetch_full_text or self.fetch_if_empty:
            self._enrich_full_text(result)

        result.finish()
        return result

    def _resolve_feed_urls(self, source: DataSource) -> list[dict[str, Any]]:
        """DataSource からフィードURL一覧を解決する."""
        # config_ref がある場合はプリセットファイルから解決
        if source.config_ref is not None:
            feeds = _load_feed_urls_from_preset(
                self.config_dir,
                source.config_ref.file,
                source_id=source.source_id,
            )
            if feeds:
                return feeds

        # url フィールドがある場合は直接使用
        if source.url:
            return [{"url": source.url, "title": source.name}]

        return []

    def _fetch_feed(
        self,
        source: DataSource,
        url: str,
        feed_title: str,
    ) -> list[CollectedItem]:
        """1つのRSSフィードを取得してCollectedItemリストに変換する."""
        # AIDEV-NOTE: feedparser.parse(url) はHTTPタイムアウトを設定できないため、
        # requests で先にフィードXMLを取得し、feedparser にはテキストを渡す。
        try:
            resp = requests.get(
                url,
                timeout=self.feed_timeout,
                headers={"User-Agent": _USER_AGENT},
            )
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except requests.RequestException as e:
            msg = f"HTTP request failed: {e}"
            raise ValueError(msg) from e

        if parsed.bozo and not parsed.entries:
            msg = f"Feed parse error: {parsed.bozo_exception}"
            raise ValueError(msg)

        items: list[CollectedItem] = []
        for entry in parsed.entries[: self.max_items_per_feed]:
            entry_url = str(entry.get("link", ""))
            if not entry_url:
                continue

            raw_text = _extract_text(entry)
            title = str(entry.get("title", ""))
            published_raw = entry.get("published") or entry.get("updated")
            published_str = str(published_raw) if published_raw else None
            published_at = _parse_datetime(published_str)
            author_raw = entry.get("author")
            author = str(author_raw) if author_raw else None

            # 言語推定: URL or ソース設定から
            language = self._detect_language(source, entry_url)

            item = CollectedItem(
                source_id=source.source_id,
                url=entry_url,
                title=title,
                raw_text=raw_text,
                published_at=published_at,
                author=author,
                collection_method="rss",
                content_type="article",
                language=language,
                metadata={
                    "feed_url": url,
                    "feed_title": feed_title,
                    "entry_id": entry.get("id", entry_url),
                    "tags": [t.get("term", "") for t in (entry.get("tags") or [])],
                },
            )
            items.append(item)

        return items

    def _enrich_full_text(self, result: CollectionResult) -> None:
        """raw_text が空のアイテムに対してリンク先から本文を取得する."""
        fetched_count = 0
        for item in result.items:
            needs_fetch = self.fetch_full_text or (
                self.fetch_if_empty and not item.raw_text.strip()
            )
            if not needs_fetch:
                continue

            # レート制限
            if fetched_count > 0:
                time.sleep(self.request_delay)

            text = _fetch_full_text(item.url)
            if text:
                item.raw_text = text
                item.metadata["full_text_fetched"] = True
            else:
                item.metadata["full_text_fetched"] = False

            fetched_count += 1

    def _detect_language(self, source: DataSource, url: str) -> str | None:
        """ソースまたはURLからコンテンツの言語を推定する."""
        # タグベース
        if "jp_market" in source.tags or "jp_media" in source.tags:
            return "ja"
        if "us_market" in source.tags:
            return "en"
        # URLベース
        jp_domains = [
            ".go.jp",
            ".co.jp",
            ".or.jp",
            ".ne.jp",
            "toyokeizai.net",
            "jpx.co.jp",
        ]
        if any(d in url for d in jp_domains):
            return "ja"
        return None
