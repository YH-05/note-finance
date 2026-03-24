"""Unit tests for data_pipeline.registry.loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_pipeline.registry.loader import RegistryLoader
from data_pipeline.registry.models import (
    CollectionMethodRegistry,
    SourceRegistry,
)


class TestRegistryLoaderLoad:
    """RegistryLoader のロード機能テスト."""

    def test_正常系_収集方法定義をロードできる(self, populated_config_dir: Path) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        methods = loader.load_collection_methods()

        assert isinstance(methods, CollectionMethodRegistry)
        assert methods.version == "1.0"
        assert methods.has_method("rss")
        assert methods.has_method("api")
        assert methods.has_method("scraping")

    def test_正常系_ソースレジストリをロードできる(self, populated_config_dir: Path) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        registry = loader.load_source_registry()

        assert isinstance(registry, SourceRegistry)
        assert registry.version == "1.0"
        assert len(registry.sources) == 4

    def test_正常系_ソースのフィールドが正しくロードされる(
        self, populated_config_dir: Path,
    ) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        registry = loader.load_source_registry()

        cnbc = registry.get_source("cnbc")
        assert cnbc is not None
        assert cnbc.name == "CNBC"
        assert cnbc.collection_method == "rss"
        assert cnbc.authority_level == 4
        assert cnbc.target_instance == "research"
        assert cnbc.neo4j_connected is True
        assert cnbc.config_ref is not None
        assert cnbc.config_ref.file == "rss-presets.json"

    def test_異常系_収集方法ファイルが存在しない場合FileNotFoundError(
        self, temp_config_dir: Path,
    ) -> None:
        loader = RegistryLoader(config_dir=temp_config_dir)
        with pytest.raises(FileNotFoundError, match="collection_methods.json"):
            loader.load_collection_methods()

    def test_異常系_レジストリファイルが存在しない場合FileNotFoundError(
        self, temp_config_dir: Path,
    ) -> None:
        loader = RegistryLoader(config_dir=temp_config_dir)
        with pytest.raises(FileNotFoundError, match="source_registry.json"):
            loader.load_source_registry()


class TestRegistryLoaderValidate:
    """RegistryLoader のバリデーション機能テスト."""

    def test_正常系_正しい設定でエラーなし(self, populated_config_dir: Path) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        issues = loader.validate()

        errors = [i for i in issues if i.level == "error"]
        assert errors == []

    def test_正常系_Neo4j未接続ソースに警告が出る(
        self, populated_config_dir: Path,
    ) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        issues = loader.validate()

        warnings = [i for i in issues if i.level == "warning"]
        # yfinance と experience-db は enabled=True かつ neo4j_connected=False
        neo4j_warnings = [
            w for w in warnings if "not connected to Neo4j" in w.message
        ]
        assert len(neo4j_warnings) == 2
        warning_ids = {w.source_id for w in neo4j_warnings}
        assert "yfinance" in warning_ids
        assert "experience-db" in warning_ids

    def test_正常系_disabled_かつ_neo4j未接続は警告なし(
        self, populated_config_dir: Path,
    ) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        issues = loader.validate()

        # industry-research は enabled=False なので警告対象外
        warning_ids = {
            i.source_id
            for i in issues
            if i.level == "warning" and "not connected to Neo4j" in i.message
        }
        assert "industry-research" not in warning_ids

    def test_異常系_重複source_idでエラー(
        self,
        temp_config_dir: Path,
        sample_collection_methods: dict,
    ) -> None:
        # collection_methods.json を配置
        (temp_config_dir / "collection_methods.json").write_text(
            json.dumps(sample_collection_methods),
        )

        # 重複 source_id を含むレジストリ
        duplicate_registry = {
            "version": "1.0",
            "updated_at": "2026-03-24",
            "sources": [
                {
                    "source_id": "dup",
                    "name": "Source A",
                    "collection_method": "rss",
                    "authority_level": 3,
                    "target_instance": "research",
                },
                {
                    "source_id": "dup",
                    "name": "Source B",
                    "collection_method": "api",
                    "authority_level": 3,
                    "target_instance": "research",
                },
            ],
        }
        (temp_config_dir / "source_registry.json").write_text(
            json.dumps(duplicate_registry),
        )

        loader = RegistryLoader(config_dir=temp_config_dir)
        issues = loader.validate()

        errors = [i for i in issues if i.level == "error"]
        assert any("Duplicate source_id" in e.message for e in errors)

    def test_異常系_未定義のcollection_methodでエラー(
        self,
        temp_config_dir: Path,
        sample_collection_methods: dict,
    ) -> None:
        (temp_config_dir / "collection_methods.json").write_text(
            json.dumps(sample_collection_methods),
        )

        registry = {
            "version": "1.0",
            "updated_at": "2026-03-24",
            "sources": [
                {
                    "source_id": "test",
                    "name": "Test",
                    "collection_method": "unknown_method",
                    "authority_level": 3,
                    "target_instance": "research",
                },
            ],
        }
        (temp_config_dir / "source_registry.json").write_text(
            json.dumps(registry),
        )

        loader = RegistryLoader(config_dir=temp_config_dir)
        issues = loader.validate()

        errors = [i for i in issues if i.level == "error"]
        assert any("Unknown collection_method" in e.message for e in errors)

    def test_正常系_config_ref参照先が存在しない場合警告(
        self,
        temp_config_dir: Path,
        sample_collection_methods: dict,
    ) -> None:
        (temp_config_dir / "collection_methods.json").write_text(
            json.dumps(sample_collection_methods),
        )

        registry = {
            "version": "1.0",
            "updated_at": "2026-03-24",
            "sources": [
                {
                    "source_id": "test",
                    "name": "Test",
                    "collection_method": "rss",
                    "authority_level": 3,
                    "target_instance": "research",
                    "config_ref": {"file": "nonexistent.json"},
                },
            ],
        }
        (temp_config_dir / "source_registry.json").write_text(
            json.dumps(registry),
        )

        loader = RegistryLoader(config_dir=temp_config_dir)
        issues = loader.validate()

        warnings = [i for i in issues if i.level == "warning"]
        assert any("Config file not found" in w.message for w in warnings)

    def test_異常系_収集方法ファイルが壊れている場合エラー(
        self, temp_config_dir: Path,
    ) -> None:
        (temp_config_dir / "collection_methods.json").write_text("not json")
        (temp_config_dir / "source_registry.json").write_text("{}")

        loader = RegistryLoader(config_dir=temp_config_dir)
        issues = loader.validate()

        errors = [i for i in issues if i.level == "error"]
        assert len(errors) >= 1
        assert any("collection_methods.json" in e.message for e in errors)


class TestRegistryLoaderSummary:
    """RegistryLoader のサマリー機能テスト."""

    def test_正常系_サマリーを生成できる(self, populated_config_dir: Path) -> None:
        loader = RegistryLoader(config_dir=populated_config_dir)
        summary = loader.summary()

        assert summary["total_sources"] == 4
        assert summary["enabled"] == 3
        assert summary["disabled"] == 1
        assert summary["neo4j_connected"] == 1
        assert summary["neo4j_disconnected"] == 3
        assert summary["by_collection_method"]["rss"] == 2
        assert summary["by_collection_method"]["api"] == 1
        assert summary["by_collection_method"]["scraping"] == 1
        assert summary["by_target_instance"]["research"] == 3
        assert summary["by_target_instance"]["creator"] == 1
        assert "rss" in summary["defined_methods"]


class TestRegistryLoaderIntegration:
    """実際の設定ファイルを使った統合テスト."""

    @pytest.fixture
    def real_loader(self) -> RegistryLoader:
        """プロジェクトの実設定ファイルを使うローダー."""
        config_dir = Path(__file__).parents[3] / "data" / "config"
        if not (config_dir / "source_registry.json").exists():
            pytest.skip("Real config files not available")
        return RegistryLoader(config_dir=config_dir)

    def test_正常系_実設定ファイルのロードが成功する(
        self, real_loader: RegistryLoader,
    ) -> None:
        registry = real_loader.load_source_registry()
        assert len(registry.sources) >= 20

    def test_正常系_実設定ファイルのバリデーションにエラーがない(
        self, real_loader: RegistryLoader,
    ) -> None:
        issues = real_loader.validate()
        errors = [i for i in issues if i.level == "error"]
        assert errors == [], f"Validation errors: {[e.message for e in errors]}"

    def test_正常系_実設定ファイルのサマリーが妥当(
        self, real_loader: RegistryLoader,
    ) -> None:
        summary = real_loader.summary()
        assert summary["total_sources"] >= 20
        assert summary["enabled"] >= 15
        assert len(summary["defined_methods"]) >= 5
