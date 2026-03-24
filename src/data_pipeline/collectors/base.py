"""共通プロトコルと CollectedItem 定義.

全コレクターが実装すべきインターフェースと、
Layer 2（原文保存）への入力となる中間データモデルを定義する。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from data_pipeline.registry.models import DataSource


# ---------------------------------------------------------------------------
# CollectedItem: 収集結果の統一フォーマット
# ---------------------------------------------------------------------------


class CollectedItem(BaseModel):
    """収集されたアイテムの統一フォーマット.

    全コレクターはこの形式でデータを返す。
    Layer 2（原文保存）への入力となる。
    """

    source_id: str = Field(description="source_registry の source_id")
    url: str = Field(description="原文のURL")
    title: str = Field(description="タイトル")
    raw_text: str = Field(description="原文テキスト（本文）")
    published_at: datetime | None = Field(
        default=None,
        description="公開日時 (UTC)",
    )
    author: str | None = Field(default=None, description="著者")
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
        description="収集日時 (UTC)",
    )
    collection_method: str = Field(description="使用した収集方法")
    content_type: str = Field(
        default="article",
        description="コンテンツ種別 (article/report/data_point/paper/post)",
    )
    language: str | None = Field(default=None, description="言語コード (en/ja等)")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="収集方法固有のメタデータ",
    )


# ---------------------------------------------------------------------------
# CollectionResult: 収集バッチの結果
# ---------------------------------------------------------------------------


class CollectionResult(BaseModel):
    """1回の収集バッチの結果."""

    source_id: str = Field(description="対象ソースID")
    items: list[CollectedItem] = Field(
        default_factory=list,
        description="収集されたアイテム",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="収集中に発生したエラーメッセージ",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc),
    )
    finished_at: datetime | None = Field(default=None)

    @property
    def success_count(self) -> int:
        """成功件数."""
        return len(self.items)

    @property
    def error_count(self) -> int:
        """エラー件数."""
        return len(self.errors)

    @property
    def is_success(self) -> bool:
        """エラーなしで完了したか."""
        return len(self.errors) == 0

    def finish(self) -> None:
        """収集完了を記録する."""
        self.finished_at = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# BaseCollector: コレクターの基底クラス
# ---------------------------------------------------------------------------


class BaseCollector(ABC):
    """全コレクターの基底クラス.

    各収集方法（RSS, API, スクレイピング等）はこのクラスを継承し、
    collect() メソッドを実装する。

    Examples
    --------
    >>> class RssCollector(BaseCollector):
    ...     def collect(self, source: DataSource) -> CollectionResult:
    ...         # feedparser で収集
    ...         ...
    """

    @abstractmethod
    def collect(self, source: DataSource) -> CollectionResult:
        """データソースからアイテムを収集する.

        Parameters
        ----------
        source : DataSource
            収集対象のデータソース定義。

        Returns
        -------
        CollectionResult
            収集結果（アイテム + エラー情報）。
        """
        ...

    def collect_many(self, sources: list[DataSource]) -> list[CollectionResult]:
        """複数のデータソースから順次収集する.

        Parameters
        ----------
        sources : list[DataSource]
            収集対象のデータソース一覧。

        Returns
        -------
        list[CollectionResult]
            各ソースの収集結果。
        """
        results = []
        for source in sources:
            if not source.enabled:
                continue
            result = self.collect(source)
            results.append(result)
        return results
