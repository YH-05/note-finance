"""Tests for Advisor Perspectives scraper.

Tests cover:
- source_key and source_config properties
- feed_url attribute
- extract_report() metadata wrapping
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig


class TestAdvisorPerspectivesProperties:
    """Tests for AdvisorPerspectivesScraper properties."""

    def test_正常系_source_keyがadvisor_perspectivesを返す(self) -> None:
        from report_scraper.scrapers.advisor_perspectives import (
            AdvisorPerspectivesScraper,
        )

        scraper = AdvisorPerspectivesScraper()
        assert scraper.source_key == "advisor_perspectives"

    def test_正常系_source_configが正しい設定を返す(self) -> None:
        from report_scraper.scrapers.advisor_perspectives import (
            AdvisorPerspectivesScraper,
        )

        scraper = AdvisorPerspectivesScraper()
        config = scraper.source_config
        assert isinstance(config, SourceConfig)
        assert config.key == "advisor_perspectives"
        assert config.tier == "aggregator"
        assert config.rendering == "rss"

    def test_正常系_feed_urlが設定されている(self) -> None:
        from report_scraper.scrapers.advisor_perspectives import (
            AdvisorPerspectivesScraper,
        )

        scraper = AdvisorPerspectivesScraper()
        assert "advisorperspectives.com" in scraper.feed_url
        assert scraper.feed_url.endswith(".rss")

    def test_正常系_source_configのtagsにマクロが含まれる(self) -> None:
        from report_scraper.scrapers.advisor_perspectives import (
            AdvisorPerspectivesScraper,
        )

        scraper = AdvisorPerspectivesScraper()
        config = scraper.source_config
        assert "macro" in config.tags


class TestAdvisorPerspectivesExtractReport:
    """Tests for AdvisorPerspectivesScraper.extract_report."""

    @pytest.mark.asyncio
    async def test_正常系_メタデータをScrapedReportでラップして返す(self) -> None:
        from report_scraper.scrapers.advisor_perspectives import (
            AdvisorPerspectivesScraper,
        )

        scraper = AdvisorPerspectivesScraper()
        meta = ReportMetadata(
            url="https://www.advisorperspectives.com/commentaries/2026/03/01/test",
            title="Test Commentary",
            published=datetime(2026, 3, 1, tzinfo=timezone.utc),
            source_key="advisor_perspectives",
            author="Test Author",
        )

        result = await scraper.extract_report(meta)

        assert result is not None
        assert isinstance(result, ScrapedReport)
        assert result.metadata == meta
        assert result.content is None
