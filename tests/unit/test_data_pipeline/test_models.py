"""Unit tests for data_pipeline.registry.models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_pipeline.registry.models import (
    CollectionMethodDef,
    CollectionMethodRegistry,
    ConfigRef,
    DataSource,
    SourceRegistry,
    ValidationIssue,
)


class TestCollectionMethodDef:
    """CollectionMethodDef のテスト."""

    def test_正常系_必須フィールドのみで生成できる(self) -> None:
        method = CollectionMethodDef(method_id="rss", name="RSS Feed")
        assert method.method_id == "rss"
        assert method.name == "RSS Feed"
        assert method.description == ""
        assert method.required_config == []
        assert method.default_schedule == "daily"

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        method = CollectionMethodDef(
            method_id="scraping",
            name="Web Scraping",
            description="スクレイピング",
            required_config=["listing_url"],
            optional_config=["article_selector"],
            default_schedule="weekly",
        )
        assert method.method_id == "scraping"
        assert method.required_config == ["listing_url"]
        assert method.optional_config == ["article_selector"]
        assert method.default_schedule == "weekly"


class TestCollectionMethodRegistry:
    """CollectionMethodRegistry のテスト."""

    def test_正常系_メソッド存在チェック(self) -> None:
        registry = CollectionMethodRegistry(
            version="1.0",
            methods={
                "rss": CollectionMethodDef(method_id="rss", name="RSS"),
                "api": CollectionMethodDef(method_id="api", name="API"),
            },
        )
        assert registry.has_method("rss") is True
        assert registry.has_method("api") is True
        assert registry.has_method("unknown") is False

    def test_正常系_メソッドID一覧(self) -> None:
        registry = CollectionMethodRegistry(
            version="1.0",
            methods={
                "rss": CollectionMethodDef(method_id="rss", name="RSS"),
                "api": CollectionMethodDef(method_id="api", name="API"),
            },
        )
        assert set(registry.method_ids()) == {"rss", "api"}

    def test_エッジケース_空のメソッドレジストリ(self) -> None:
        registry = CollectionMethodRegistry(version="1.0", methods={})
        assert registry.method_ids() == []
        assert registry.has_method("rss") is False


class TestConfigRef:
    """ConfigRef のテスト."""

    def test_正常系_ファイルのみ指定(self) -> None:
        ref = ConfigRef(file="rss-presets.json")
        assert ref.file == "rss-presets.json"
        assert ref.key is None
        assert ref.item_count is None

    def test_正常系_全フィールド指定(self) -> None:
        ref = ConfigRef(file="yfinance_tickers.json", key="Stock Indices", item_count=150)
        assert ref.file == "yfinance_tickers.json"
        assert ref.key == "Stock Indices"
        assert ref.item_count == 150


class TestDataSource:
    """DataSource のテスト."""

    def test_正常系_最小フィールドで生成できる(self) -> None:
        source = DataSource(
            source_id="test",
            name="Test Source",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
        )
        assert source.source_id == "test"
        assert source.enabled is True
        assert source.schedule == "daily"
        assert source.neo4j_connected is True
        assert source.tags == []

    def test_正常系_全フィールド指定で生成できる(self) -> None:
        source = DataSource(
            source_id="cnbc",
            name="CNBC",
            name_ja="CNBC",
            collection_method="rss",
            authority_level=4,
            target_instance="research",
            enabled=True,
            schedule="daily",
            config_ref=ConfigRef(file="rss-presets.json", item_count=21),
            emit_command="finance-news-workflow",
            tags=["us_market", "news"],
            url="https://www.cnbc.com",
            neo4j_connected=True,
            notes="テスト用",
        )
        assert source.source_id == "cnbc"
        assert source.config_ref is not None
        assert source.config_ref.item_count == 21

    def test_異常系_authority_levelが範囲外でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            DataSource(
                source_id="test",
                name="Test",
                collection_method="rss",
                authority_level=0,
                target_instance="research",
            )

    def test_異常系_authority_levelが6でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            DataSource(
                source_id="test",
                name="Test",
                collection_method="rss",
                authority_level=6,
                target_instance="research",
            )

    def test_異常系_target_instanceが不正値でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            DataSource(
                source_id="test",
                name="Test",
                collection_method="rss",
                authority_level=3,
                target_instance="invalid",  # type: ignore[arg-type]
            )

    def test_異常系_scheduleが不正値でValidationError(self) -> None:
        with pytest.raises(ValidationError):
            DataSource(
                source_id="test",
                name="Test",
                collection_method="rss",
                authority_level=3,
                target_instance="research",
                schedule="hourly",
            )

    @pytest.mark.parametrize(
        "schedule",
        ["daily", "weekly", "on_demand", "manual"],
    )
    def test_パラメトライズ_有効なschedule値(self, schedule: str) -> None:
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            schedule=schedule,
        )
        assert source.schedule == schedule

    @pytest.mark.parametrize(
        "instance",
        ["research", "creator", "note"],
    )
    def test_パラメトライズ_有効なtarget_instance値(self, instance: str) -> None:
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance=instance,  # type: ignore[arg-type]
        )
        assert source.target_instance == instance


class TestSourceRegistry:
    """SourceRegistry のテスト."""

    @pytest.fixture
    def registry(self) -> SourceRegistry:
        """テスト用レジストリ."""
        return SourceRegistry(
            version="1.0",
            updated_at="2026-03-24T00:00:00+09:00",
            sources=[
                DataSource(
                    source_id="cnbc",
                    name="CNBC",
                    collection_method="rss",
                    authority_level=4,
                    target_instance="research",
                    tags=["us_market", "news"],
                    neo4j_connected=True,
                ),
                DataSource(
                    source_id="yfinance",
                    name="Yahoo Finance",
                    collection_method="api",
                    authority_level=3,
                    target_instance="research",
                    tags=["quantitative"],
                    neo4j_connected=False,
                ),
                DataSource(
                    source_id="experience-db",
                    name="Experience DB",
                    collection_method="rss",
                    authority_level=2,
                    target_instance="creator",
                    enabled=False,
                    tags=["experience"],
                    neo4j_connected=False,
                ),
            ],
        )

    def test_正常系_source_idで検索できる(self, registry: SourceRegistry) -> None:
        source = registry.get_source("cnbc")
        assert source is not None
        assert source.name == "CNBC"

    def test_正常系_存在しないsource_idでNone(self, registry: SourceRegistry) -> None:
        assert registry.get_source("nonexistent") is None

    def test_正常系_収集方法でフィルタできる(self, registry: SourceRegistry) -> None:
        rss_sources = registry.filter_by_method("rss")
        assert len(rss_sources) == 2
        assert all(s.collection_method == "rss" for s in rss_sources)

    def test_正常系_インスタンスでフィルタできる(self, registry: SourceRegistry) -> None:
        research = registry.filter_by_instance("research")
        assert len(research) == 2

        creator = registry.filter_by_instance("creator")
        assert len(creator) == 1
        assert creator[0].source_id == "experience-db"

    def test_正常系_タグでフィルタできる(self, registry: SourceRegistry) -> None:
        us_market = registry.filter_by_tag("us_market")
        assert len(us_market) == 1
        assert us_market[0].source_id == "cnbc"

    def test_正常系_有効なソースのみ返す(self, registry: SourceRegistry) -> None:
        enabled = registry.get_enabled()
        assert len(enabled) == 2
        assert all(s.enabled for s in enabled)

    def test_正常系_Neo4j未接続ソース一覧(self, registry: SourceRegistry) -> None:
        disconnected = registry.get_disconnected()
        assert len(disconnected) == 2
        assert {s.source_id for s in disconnected} == {"yfinance", "experience-db"}

    def test_正常系_source_idsプロパティ(self, registry: SourceRegistry) -> None:
        assert registry.source_ids == ["cnbc", "yfinance", "experience-db"]

    def test_エッジケース_空のレジストリ(self) -> None:
        registry = SourceRegistry(version="1.0", updated_at="", sources=[])
        assert registry.source_ids == []
        assert registry.get_enabled() == []
        assert registry.get_disconnected() == []
        assert registry.filter_by_method("rss") == []


class TestValidationIssue:
    """ValidationIssue のテスト."""

    def test_正常系_エラーレベル(self) -> None:
        issue = ValidationIssue(
            level="error",
            source_id="test",
            message="Duplicate source_id",
        )
        assert issue.level == "error"
        assert issue.source_id == "test"

    def test_正常系_グローバル問題(self) -> None:
        issue = ValidationIssue(
            level="warning",
            message="File not found",
        )
        assert issue.source_id is None
