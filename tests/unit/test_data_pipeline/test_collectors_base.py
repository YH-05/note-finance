"""Unit tests for data_pipeline.collectors.base."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_pipeline.collectors.base import (
    BaseCollector,
    CollectedItem,
    CollectionResult,
)
from data_pipeline.registry.models import DataSource


class TestCollectedItem:
    """CollectedItem のテスト."""

    def test_正常系_最小フィールドで生成できる(self) -> None:
        item = CollectedItem(
            source_id="test",
            url="https://example.com/article/1",
            title="Test Article",
            raw_text="This is the content.",
            collection_method="rss",
        )
        assert item.source_id == "test"
        assert item.url == "https://example.com/article/1"
        assert item.content_type == "article"
        assert item.language is None
        assert item.metadata == {}
        assert item.collected_at is not None

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        now = datetime.now(tz=timezone.utc)
        item = CollectedItem(
            source_id="cnbc",
            url="https://www.cnbc.com/article/1",
            title="S&P 500 hits record",
            raw_text="The S&P 500 index reached...",
            published_at=now,
            author="John Doe",
            collected_at=now,
            collection_method="rss",
            content_type="article",
            language="en",
            metadata={"feed_url": "https://www.cnbc.com/rss"},
        )
        assert item.author == "John Doe"
        assert item.language == "en"
        assert item.metadata["feed_url"] == "https://www.cnbc.com/rss"

    def test_正常系_collected_atがデフォルトで設定される(self) -> None:
        item = CollectedItem(
            source_id="test",
            url="https://example.com",
            title="Test",
            raw_text="content",
            collection_method="rss",
        )
        assert item.collected_at.tzinfo is not None


class TestCollectionResult:
    """CollectionResult のテスト."""

    def test_正常系_空の結果を生成できる(self) -> None:
        result = CollectionResult(source_id="test")
        assert result.success_count == 0
        assert result.error_count == 0
        assert result.is_success is True

    def test_正常系_アイテムを追加できる(self) -> None:
        result = CollectionResult(source_id="test")
        result.items.append(
            CollectedItem(
                source_id="test",
                url="https://example.com",
                title="Test",
                raw_text="content",
                collection_method="rss",
            ),
        )
        assert result.success_count == 1
        assert result.is_success is True

    def test_正常系_エラーがあるとis_successがFalse(self) -> None:
        result = CollectionResult(source_id="test")
        result.errors.append("Some error")
        assert result.is_success is False
        assert result.error_count == 1

    def test_正常系_finishで完了時刻が記録される(self) -> None:
        result = CollectionResult(source_id="test")
        assert result.finished_at is None
        result.finish()
        assert result.finished_at is not None


class TestBaseCollector:
    """BaseCollector のテスト."""

    def test_正常系_collect_manyでdisabledソースがスキップされる(self) -> None:
        class DummyCollector(BaseCollector):
            def collect(self, source: DataSource) -> CollectionResult:
                result = CollectionResult(source_id=source.source_id)
                result.items.append(
                    CollectedItem(
                        source_id=source.source_id,
                        url="https://example.com",
                        title="Test",
                        raw_text="content",
                        collection_method="rss",
                    ),
                )
                result.finish()
                return result

        collector = DummyCollector()
        sources = [
            DataSource(
                source_id="enabled",
                name="Enabled",
                collection_method="rss",
                authority_level=3,
                target_instance="research",
                enabled=True,
            ),
            DataSource(
                source_id="disabled",
                name="Disabled",
                collection_method="rss",
                authority_level=3,
                target_instance="research",
                enabled=False,
            ),
        ]
        results = collector.collect_many(sources)
        assert len(results) == 1
        assert results[0].source_id == "enabled"
