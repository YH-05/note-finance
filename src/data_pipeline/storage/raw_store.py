"""原文テキストの永続化ストア.

CollectedItem を JSON ファイルとして保存し、
URL ベースの重複排除と日付ベースの検索を提供する。

ディレクトリ構造:
    {base_dir}/
    └── {source_id}/
        └── {YYYY-MM-DD}/
            └── {url_hash}.json

保存先のデフォルトは /Volumes/personal_folder/raw_texts。
マウントされていない場合はプロジェクト内 data/raw_texts にフォールバック。
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from data_pipeline.collectors.base import CollectedItem, CollectionResult

if TYPE_CHECKING:
    from datetime import datetime

# AIDEV-NOTE: RAW_STORE_DIR 環境変数で上書き可能。Mac Mini 等の別マシンでは
# launchd plist の EnvironmentVariables に NAS マウントパスを設定すること。
_DEFAULT_EXTERNAL_DIR = Path(os.environ.get("RAW_STORE_DIR", "/Volumes/personal_folder/raw_texts"))
_FALLBACK_DIR_NAME = "raw_texts"


def _url_hash(url: str) -> str:
    """URL から短いハッシュを生成する（重複排除のキー）."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _resolve_base_dir(base_dir: Path | None = None) -> Path:
    """保存先ディレクトリを解決する."""
    if base_dir is not None:
        return base_dir
    # 外付けSSD が利用可能ならそちらを使用
    if _DEFAULT_EXTERNAL_DIR.parent.exists():
        return _DEFAULT_EXTERNAL_DIR
    # フォールバック: プロジェクト内
    try:
        from data_paths import get_data_root

        return get_data_root() / _FALLBACK_DIR_NAME
    except ImportError:
        return Path("data") / _FALLBACK_DIR_NAME


class SaveResult(BaseModel):
    """保存バッチの結果."""

    source_id: str
    saved: int = Field(default=0, description="新規保存件数")
    skipped_duplicate: int = Field(default=0, description="重複スキップ件数")
    skipped_empty: int = Field(default=0, description="テキスト空でスキップ件数")
    errors: list[str] = Field(default_factory=list)
    saved_paths: list[str] = Field(
        default_factory=list,
        description="保存されたファイルパス",
    )


class RawStore:
    """原文テキストの永続化ストア.

    Parameters
    ----------
    base_dir : Path | None
        保存先ディレクトリ。None の場合はデフォルトを自動解決。
    skip_empty : bool
        True の場合、raw_text が空のアイテムは保存しない。

    Examples
    --------
    >>> store = RawStore()
    >>> result = store.save(collection_result)
    >>> print(f"saved {result.saved}, skipped {result.skipped_duplicate} duplicates")
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        skip_empty: bool = True,
    ) -> None:
        self.base_dir = _resolve_base_dir(base_dir)
        self.skip_empty = skip_empty

    def save(self, result: CollectionResult) -> SaveResult:
        """CollectionResult の全アイテムを保存する.

        Parameters
        ----------
        result : CollectionResult
            コレクターからの収集結果。

        Returns
        -------
        SaveResult
            保存結果（件数、スキップ数、エラー）。
        """
        save_result = SaveResult(source_id=result.source_id)

        for item in result.items:
            try:
                outcome = self.save_item(item)
                if outcome == "saved":
                    save_result.saved += 1
                elif outcome == "duplicate":
                    save_result.skipped_duplicate += 1
                elif outcome == "empty":
                    save_result.skipped_empty += 1
            except Exception as e:
                save_result.errors.append(f"Failed to save '{item.url}': {e}")

        return save_result

    def save_item(self, item: CollectedItem) -> str:
        """1アイテムを保存する.

        Returns
        -------
        str
            "saved", "duplicate", or "empty"
        """
        if self.skip_empty and not item.raw_text.strip():
            return "empty"

        file_path = self._item_path(item)

        if file_path.exists():
            return "duplicate"

        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = item.model_dump(mode="json")
        file_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return "saved"

    def save_text(
        self,
        *,
        source_id: str,
        url: str,
        title: str,
        raw_text: str,
        collection_method: str,
        published_at: datetime | None = None,
        author: str | None = None,
        content_type: str = "article",
        language: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """テキスト+メタデータを直接保存するヘルパー.

        CollectedItem を知らなくても保存できる簡易API。
        既存パイプラインから最小限の情報で呼び出せる。

        Returns
        -------
        str
            "saved", "duplicate", or "empty"

        Examples
        --------
        >>> store = RawStore()
        >>> store.save_text(
        ...     source_id="jp-finance",
        ...     url="https://www.fsa.go.jp/news/...",
        ...     title="金融庁ニュース",
        ...     raw_text="本文テキスト...",
        ...     collection_method="rss",
        ... )
        'saved'
        """
        item = CollectedItem(
            source_id=source_id,
            url=url,
            title=title,
            raw_text=raw_text,
            collection_method=collection_method,
            published_at=published_at,
            author=author,
            content_type=content_type,
            language=language,
            metadata=metadata or {},
        )
        return self.save_item(item)

    def save_many_texts(
        self,
        items: list[dict],
        *,
        source_id: str,
        collection_method: str,
    ) -> SaveResult:
        """dict のリストを一括保存するヘルパー.

        各 dict には最低限 url, title, raw_text が必要。
        既存パイプラインの出力をそのまま渡せる。

        Parameters
        ----------
        items : list[dict]
            保存するアイテムのリスト。各dictのキー:
            - url (必須)
            - title (必須)
            - raw_text (必須)
            - published_at, author, language, metadata (任意)
        source_id : str
            ソースID。
        collection_method : str
            収集方法。

        Returns
        -------
        SaveResult
            保存結果。
        """
        save_result = SaveResult(source_id=source_id)

        for item_dict in items:
            try:
                outcome = self.save_text(
                    source_id=source_id,
                    url=item_dict["url"],
                    title=item_dict.get("title", ""),
                    raw_text=item_dict.get(
                        "raw_text", item_dict.get("text", item_dict.get("content", ""))
                    ),
                    collection_method=collection_method,
                    published_at=item_dict.get("published_at"),
                    author=item_dict.get("author"),
                    language=item_dict.get("language"),
                    metadata=item_dict.get("metadata"),
                )
                if outcome == "saved":
                    save_result.saved += 1
                elif outcome == "duplicate":
                    save_result.skipped_duplicate += 1
                elif outcome == "empty":
                    save_result.skipped_empty += 1
            except Exception as e:
                save_result.errors.append(
                    f"Failed to save '{item_dict.get('url', '?')}': {e}",
                )

        return save_result

    def exists(self, url: str, source_id: str, date: str | None = None) -> bool:
        """URL が既に保存済みかチェックする.

        Parameters
        ----------
        url : str
            チェックするURL。
        source_id : str
            ソースID。
        date : str | None
            日付 (YYYY-MM-DD)。None の場合は全日付を検索。
        """
        h = _url_hash(url)
        source_dir = self.base_dir / source_id

        if date:
            return (source_dir / date / f"{h}.json").exists()

        # 全日付ディレクトリを検索
        if not source_dir.exists():
            return False
        return any(
            (d / f"{h}.json").exists() for d in source_dir.iterdir() if d.is_dir()
        )

    def load_items(
        self,
        source_id: str,
        date: str | None = None,
    ) -> list[CollectedItem]:
        """保存済みアイテムをロードする.

        Parameters
        ----------
        source_id : str
            ソースID。
        date : str | None
            日付 (YYYY-MM-DD)。None の場合は全日付。

        Returns
        -------
        list[CollectedItem]
            ロードされたアイテム。
        """
        source_dir = self.base_dir / source_id
        if not source_dir.exists():
            return []

        if date:
            date_dir = source_dir / date
            if not date_dir.exists():
                return []
            return self._load_from_dir(date_dir)

        # 全日付ディレクトリ
        items: list[CollectedItem] = []
        for date_dir in sorted(source_dir.iterdir()):
            if date_dir.is_dir():
                items.extend(self._load_from_dir(date_dir))
        return items

    def list_sources(self) -> list[str]:
        """保存済みソースID一覧を返す."""
        if not self.base_dir.exists():
            return []
        return sorted(d.name for d in self.base_dir.iterdir() if d.is_dir())

    def list_dates(self, source_id: str) -> list[str]:
        """source_id の保存済み日付一覧を返す."""
        source_dir = self.base_dir / source_id
        if not source_dir.exists():
            return []
        return sorted(d.name for d in source_dir.iterdir() if d.is_dir())

    def count(self, source_id: str, date: str | None = None) -> int:
        """保存済みアイテム数を返す."""
        source_dir = self.base_dir / source_id
        if not source_dir.exists():
            return 0

        if date:
            date_dir = source_dir / date
            if not date_dir.exists():
                return 0
            return sum(1 for f in date_dir.glob("*.json"))

        return sum(
            1 for d in source_dir.iterdir() if d.is_dir() for _ in d.glob("*.json")
        )

    def _item_path(self, item: CollectedItem) -> Path:
        """アイテムの保存先パスを計算する."""
        h = _url_hash(item.url)
        # 日付は collected_at から取得（UTCベース）
        date_str = item.collected_at.strftime("%Y-%m-%d")
        return self.base_dir / item.source_id / date_str / f"{h}.json"

    def _load_from_dir(self, directory: Path) -> list[CollectedItem]:
        """ディレクトリ内の全JSONをCollectedItemとしてロードする."""
        items: list[CollectedItem] = []
        for json_file in sorted(directory.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                items.append(CollectedItem(**data))
            except Exception:
                continue
        return items
