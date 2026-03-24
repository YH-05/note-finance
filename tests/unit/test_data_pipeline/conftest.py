"""Fixtures for data_pipeline registry tests."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_config_dir() -> Iterator[Path]:
    """一時設定ディレクトリを作成する."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_collection_methods() -> dict:
    """テスト用の収集方法定義."""
    return {
        "version": "1.0",
        "methods": {
            "rss": {
                "method_id": "rss",
                "name": "RSS Feed",
                "description": "RSSフィードから取得",
                "required_config": ["url"],
                "optional_config": ["category"],
                "default_schedule": "daily",
            },
            "api": {
                "method_id": "api",
                "name": "API",
                "description": "APIから取得",
                "required_config": [],
                "optional_config": ["api_endpoint"],
                "default_schedule": "daily",
            },
            "scraping": {
                "method_id": "scraping",
                "name": "Web Scraping",
                "description": "スクレイピング",
                "required_config": ["listing_url"],
                "optional_config": [],
                "default_schedule": "weekly",
            },
        },
    }


@pytest.fixture
def sample_source_registry() -> dict:
    """テスト用のソースレジストリ."""
    return {
        "version": "1.0",
        "updated_at": "2026-03-24T00:00:00+09:00",
        "sources": [
            {
                "source_id": "cnbc",
                "name": "CNBC",
                "name_ja": "CNBC",
                "collection_method": "rss",
                "authority_level": 4,
                "target_instance": "research",
                "enabled": True,
                "schedule": "daily",
                "config_ref": {"file": "rss-presets.json", "item_count": 21},
                "emit_command": "finance-news-workflow",
                "tags": ["us_market", "news"],
                "neo4j_connected": True,
            },
            {
                "source_id": "yfinance",
                "name": "Yahoo Finance",
                "collection_method": "api",
                "authority_level": 3,
                "target_instance": "research",
                "enabled": True,
                "schedule": "daily",
                "config_ref": {"file": "yfinance_tickers.json", "item_count": 150},
                "tags": ["quantitative", "market_data"],
                "neo4j_connected": False,
                "notes": "Neo4j未接続",
            },
            {
                "source_id": "experience-db",
                "name": "Experience DB",
                "collection_method": "rss",
                "authority_level": 2,
                "target_instance": "creator",
                "enabled": True,
                "schedule": "weekly",
                "tags": ["experience"],
                "neo4j_connected": False,
            },
            {
                "source_id": "industry-research",
                "name": "Industry Research",
                "collection_method": "scraping",
                "authority_level": 4,
                "target_instance": "research",
                "enabled": False,
                "schedule": "weekly",
                "tags": ["sector"],
                "neo4j_connected": False,
            },
        ],
    }


@pytest.fixture
def populated_config_dir(
    temp_config_dir: Path,
    sample_collection_methods: dict,
    sample_source_registry: dict,
) -> Path:
    """設定ファイルが配置された一時ディレクトリを返す."""
    methods_path = temp_config_dir / "collection_methods.json"
    methods_path.write_text(json.dumps(sample_collection_methods, ensure_ascii=False))

    registry_path = temp_config_dir / "source_registry.json"
    registry_path.write_text(json.dumps(sample_source_registry, ensure_ascii=False))

    # config_ref で参照される既存設定ファイルのダミー
    (temp_config_dir / "rss-presets.json").write_text("{}")
    (temp_config_dir / "yfinance_tickers.json").write_text("{}")

    return temp_config_dir
