"""Tests for report_scraper.core.scraper_registry module."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from report_scraper.core.base_scraper import BaseReportScraper
from report_scraper.core.scraper_registry import ScraperRegistry
from report_scraper.types import (
    CollectResult,
    ReportMetadata,
    ScrapedReport,
    SourceConfig,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubScraper(BaseReportScraper):
    """Minimal concrete scraper for testing."""

    def __init__(self, key: str = "stub_source") -> None:
        self._key = key

    @property
    def source_key(self) -> str:
        return self._key

    @property
    def source_config(self) -> SourceConfig:
        return SourceConfig(
            key=self._key,
            name="Stub Source",
            tier="sell_side",
            listing_url="https://stub.example.com",
            rendering="static",
        )

    async def fetch_listing(self) -> list[ReportMetadata]:
        return []

    async def extract_report(self, meta: ReportMetadata) -> ScrapedReport | None:
        return ScrapedReport(metadata=meta)


def _make_source_config(key: str = "test_source") -> SourceConfig:
    return SourceConfig(
        key=key,
        name="Test Source",
        tier="sell_side",
        listing_url=f"https://{key}.example.com",
        rendering="static",
    )


# ---------------------------------------------------------------------------
# Tests: Registration
# ---------------------------------------------------------------------------


class TestScraperRegistryRegister:
    """Tests for ScraperRegistry.register method."""

    def test_正常系_スクレイパーを登録できる(self) -> None:
        registry = ScraperRegistry()
        scraper = _StubScraper("source_a")
        registry.register(scraper)
        assert registry.get_scraper("source_a") is scraper

    def test_正常系_複数スクレイパーを登録できる(self) -> None:
        registry = ScraperRegistry()
        scraper_a = _StubScraper("source_a")
        scraper_b = _StubScraper("source_b")
        registry.register(scraper_a)
        registry.register(scraper_b)
        assert registry.get_scraper("source_a") is scraper_a
        assert registry.get_scraper("source_b") is scraper_b

    def test_正常系_同じキーで上書き登録できる(self) -> None:
        registry = ScraperRegistry()
        scraper_old = _StubScraper("source_a")
        scraper_new = _StubScraper("source_a")
        registry.register(scraper_old)
        registry.register(scraper_new)
        assert registry.get_scraper("source_a") is scraper_new


# ---------------------------------------------------------------------------
# Tests: get_scraper
# ---------------------------------------------------------------------------


class TestScraperRegistryGetScraper:
    """Tests for ScraperRegistry.get_scraper method."""

    def test_正常系_登録済みスクレイパーを取得できる(self) -> None:
        registry = ScraperRegistry()
        scraper = _StubScraper("source_a")
        registry.register(scraper)
        result = registry.get_scraper("source_a")
        assert result is scraper

    def test_異常系_未登録キーでKeyError(self) -> None:
        registry = ScraperRegistry()
        with pytest.raises(KeyError, match="unknown_source"):
            registry.get_scraper("unknown_source")


# ---------------------------------------------------------------------------
# Tests: list_sources
# ---------------------------------------------------------------------------


class TestScraperRegistryListSources:
    """Tests for ScraperRegistry.list_sources method."""

    def test_正常系_空のレジストリで空リスト(self) -> None:
        registry = ScraperRegistry()
        assert registry.list_sources() == []

    def test_正常系_登録済みソースキーのリストを取得(self) -> None:
        registry = ScraperRegistry()
        registry.register(_StubScraper("source_b"))
        registry.register(_StubScraper("source_a"))
        sources = registry.list_sources()
        assert sorted(sources) == ["source_a", "source_b"]


# ---------------------------------------------------------------------------
# Tests: register_from_configs
# ---------------------------------------------------------------------------


class TestScraperRegistryRegisterFromConfigs:
    """Tests for ScraperRegistry.register_from_configs method."""

    def test_正常系_設定リストからスクレイパーを自動登録(self) -> None:
        registry = ScraperRegistry()
        configs = [
            _make_source_config("src_a"),
            _make_source_config("src_b"),
        ]

        # Pre-register one scraper to verify it is NOT overwritten
        existing = _StubScraper("src_a")
        registry.register(existing)

        registered = registry.register_from_configs(configs)

        # src_a was already registered, so only src_b should be newly added
        # The existing scraper for src_a should be kept
        assert registry.get_scraper("src_a") is existing
        # src_b should get a new default scraper
        assert "src_b" in registry.list_sources()
        assert registered == 1  # Only src_b was newly registered

    def test_正常系_空の設定リストで何も登録しない(self) -> None:
        registry = ScraperRegistry()
        registered = registry.register_from_configs([])
        assert registered == 0
        assert registry.list_sources() == []
