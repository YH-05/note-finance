"""Tests for report_scraper.config.loader module."""

from __future__ import annotations

from pathlib import Path

import pytest

from report_scraper.config.loader import load_config
from report_scraper.exceptions import ConfigError
from report_scraper.types import ReportScraperConfig


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_正常系_有効なYAMLからReportScraperConfigを生成(
        self, tmp_path: Path
    ) -> None:
        """Valid YAML with global and sources produces a ReportScraperConfig."""
        yaml_content = """\
global:
  output_dir: "data/scraped/reports"
  max_reports_per_source: 10
  dedup_days: 14

sources:
  - key: "test_source"
    name: "Test Research"
    tier: "sell_side"
    listing_url: "https://example.com/research"
    rendering: "static"
    tags: ["macro"]
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert isinstance(config, ReportScraperConfig)
        assert config.global_config.max_reports_per_source == 10
        assert config.global_config.dedup_days == 14
        assert len(config.sources) == 1
        assert config.sources[0].key == "test_source"
        assert config.sources[0].tier == "sell_side"
        assert config.sources[0].tags == ["macro"]

    def test_正常系_複数ソースを含むYAMLを正しくパース(self, tmp_path: Path) -> None:
        """YAML with multiple sources parses all sources correctly."""
        yaml_content = """\
global:
  max_reports_per_source: 20

sources:
  - key: "source_a"
    name: "Source A"
    tier: "buy_side"
    listing_url: "https://a.example.com"
    rendering: "rss"
  - key: "source_b"
    name: "Source B"
    tier: "sell_side"
    listing_url: "https://b.example.com"
    rendering: "playwright"
    pdf_selector: "a.pdf-link"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert len(config.sources) == 2
        assert config.sources[0].key == "source_a"
        assert config.sources[0].rendering == "rss"
        assert config.sources[1].key == "source_b"
        assert config.sources[1].pdf_selector == "a.pdf-link"

    def test_正常系_globalセクション省略時にデフォルト値を使用(
        self, tmp_path: Path
    ) -> None:
        """When global section is omitted, default GlobalConfig values are used."""
        yaml_content = """\
sources:
  - key: "minimal"
    name: "Minimal Source"
    tier: "aggregator"
    listing_url: "https://example.com"
    rendering: "static"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)

        assert config.global_config.max_reports_per_source == 20
        assert config.global_config.dedup_days == 30
        assert config.global_config.output_dir == Path("data/scraped/reports")

    def test_異常系_ファイルが存在しない場合にConfigError(self) -> None:
        """Non-existent file raises ConfigError."""
        with pytest.raises(ConfigError, match="not found"):
            load_config(Path("/nonexistent/path/config.yaml"))

    def test_異常系_ディレクトリパスを指定した場合にConfigError(
        self, tmp_path: Path
    ) -> None:
        """Directory path (not a file) raises ConfigError."""
        with pytest.raises(ConfigError, match="not a file"):
            load_config(tmp_path)

    def test_異常系_不正なYAML構文でConfigError(self, tmp_path: Path) -> None:
        """Invalid YAML syntax raises ConfigError."""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("key: [invalid yaml", encoding="utf-8")

        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(config_file)

    def test_異常系_YAMLルートがマッピングでない場合にConfigError(
        self, tmp_path: Path
    ) -> None:
        """YAML root that is not a mapping raises ConfigError."""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ConfigError, match="mapping"):
            load_config(config_file)

    def test_異常系_必須フィールド欠落でConfigError(self, tmp_path: Path) -> None:
        """Missing required fields in source raises ConfigError."""
        yaml_content = """\
sources:
  - key: "incomplete"
    name: "Incomplete Source"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_異常系_sourcesが空リストでConfigError(self, tmp_path: Path) -> None:
        """Empty sources list raises ConfigError."""
        yaml_content = """\
sources: []
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_異常系_sourcesキーが欠落でConfigError(self, tmp_path: Path) -> None:
        """Missing sources key raises ConfigError."""
        yaml_content = """\
global:
  max_reports_per_source: 10
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_異常系_不正なtier値でConfigError(self, tmp_path: Path) -> None:
        """Invalid tier value raises ConfigError."""
        yaml_content = """\
sources:
  - key: "bad_tier"
    name: "Bad Tier"
    tier: "invalid_tier"
    listing_url: "https://example.com"
    rendering: "static"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_異常系_不正なrendering値でConfigError(self, tmp_path: Path) -> None:
        """Invalid rendering value raises ConfigError."""
        yaml_content = """\
sources:
  - key: "bad_rendering"
    name: "Bad Rendering"
    tier: "sell_side"
    listing_url: "https://example.com"
    rendering: "unknown_renderer"
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        with pytest.raises(ConfigError, match="validation failed"):
            load_config(config_file)

    def test_正常系_実際の設定ファイルをロードできる(self) -> None:
        """The actual report-scraper-config.yaml loads successfully."""
        config_path = Path("data/config/report-scraper-config.yaml")
        if not config_path.exists():
            pytest.skip("Actual config file not present")

        config = load_config(config_path)

        assert len(config.sources) >= 1
        assert config.global_config.max_reports_per_source > 0


class TestBaseReportScraperABC:
    """Tests for BaseReportScraper abstract base class."""

    def test_異常系_抽象メソッド未実装でTypeError(self) -> None:
        """Subclass without abstract methods raises TypeError on instantiation."""
        from report_scraper.core.base_scraper import BaseReportScraper

        class IncompleteScraper(BaseReportScraper):
            pass

        with pytest.raises(TypeError):
            IncompleteScraper()  # type: ignore[abstract]

    def test_正常系_全抽象メソッド実装でインスタンス化可能(self) -> None:
        """Subclass implementing all abstract methods can be instantiated."""
        from report_scraper.core.base_scraper import BaseReportScraper
        from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

        class CompleteScraper(BaseReportScraper):
            @property
            def source_key(self) -> str:
                return "test"

            @property
            def source_config(self) -> SourceConfig:
                return SourceConfig(
                    key="test",
                    name="Test",
                    tier="sell_side",
                    listing_url="https://example.com",
                    rendering="static",
                )

            async def fetch_listing(self) -> list[ReportMetadata]:
                return []

            async def extract_report(
                self, meta: ReportMetadata
            ) -> ScrapedReport | None:
                return None

        scraper = CompleteScraper()
        assert scraper.source_key == "test"
        assert scraper.source_config.key == "test"

    @pytest.mark.asyncio
    async def test_正常系_collect_latestがCollectResultを返す(self) -> None:
        """collect_latest returns a CollectResult with empty reports."""
        from report_scraper.core.base_scraper import BaseReportScraper
        from report_scraper.types import (
            CollectResult,
            ReportMetadata,
            ScrapedReport,
            SourceConfig,
        )

        class EmptyScraper(BaseReportScraper):
            @property
            def source_key(self) -> str:
                return "empty"

            @property
            def source_config(self) -> SourceConfig:
                return SourceConfig(
                    key="empty",
                    name="Empty",
                    tier="aggregator",
                    listing_url="https://example.com",
                    rendering="rss",
                )

            async def fetch_listing(self) -> list[ReportMetadata]:
                return []

            async def extract_report(
                self, meta: ReportMetadata
            ) -> ScrapedReport | None:
                return None

        scraper = EmptyScraper()
        result = await scraper.collect_latest()

        assert isinstance(result, CollectResult)
        assert result.source_key == "empty"
        assert result.reports == ()
        assert result.errors == ()
        assert result.duration >= 0

    @pytest.mark.asyncio
    async def test_正常系_collect_latestがレポートを収集(self) -> None:
        """collect_latest collects reports from fetch_listing + extract_report."""
        from datetime import datetime, timezone

        from report_scraper.core.base_scraper import BaseReportScraper
        from report_scraper.types import (
            CollectResult,
            ReportMetadata,
            ScrapedReport,
            SourceConfig,
        )

        class WorkingScraper(BaseReportScraper):
            @property
            def source_key(self) -> str:
                return "working"

            @property
            def source_config(self) -> SourceConfig:
                return SourceConfig(
                    key="working",
                    name="Working",
                    tier="sell_side",
                    listing_url="https://example.com",
                    rendering="static",
                )

            async def fetch_listing(self) -> list[ReportMetadata]:
                return [
                    ReportMetadata(
                        url="https://example.com/report1",
                        title="Report 1",
                        published=datetime(2026, 3, 1, tzinfo=timezone.utc),
                        source_key="working",
                    ),
                    ReportMetadata(
                        url="https://example.com/report2",
                        title="Report 2",
                        published=datetime(2026, 3, 2, tzinfo=timezone.utc),
                        source_key="working",
                    ),
                ]

            async def extract_report(
                self, meta: ReportMetadata
            ) -> ScrapedReport | None:
                return ScrapedReport(metadata=meta)

        scraper = WorkingScraper()
        result = await scraper.collect_latest(max_reports=5)

        assert isinstance(result, CollectResult)
        assert len(result.reports) == 2
        assert result.reports[0].metadata.title == "Report 1"
        assert result.errors == ()

    @pytest.mark.asyncio
    async def test_正常系_collect_latestがmax_reportsで制限(self) -> None:
        """collect_latest truncates listing to max_reports."""
        from datetime import datetime, timezone

        from report_scraper.core.base_scraper import BaseReportScraper
        from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

        class ManyScraper(BaseReportScraper):
            @property
            def source_key(self) -> str:
                return "many"

            @property
            def source_config(self) -> SourceConfig:
                return SourceConfig(
                    key="many",
                    name="Many",
                    tier="sell_side",
                    listing_url="https://example.com",
                    rendering="static",
                )

            async def fetch_listing(self) -> list[ReportMetadata]:
                return [
                    ReportMetadata(
                        url=f"https://example.com/report{i}",
                        title=f"Report {i}",
                        published=datetime(2026, 3, i + 1, tzinfo=timezone.utc),
                        source_key="many",
                    )
                    for i in range(10)
                ]

            async def extract_report(
                self, meta: ReportMetadata
            ) -> ScrapedReport | None:
                return ScrapedReport(metadata=meta)

        scraper = ManyScraper()
        result = await scraper.collect_latest(max_reports=3)

        assert len(result.reports) == 3

    @pytest.mark.asyncio
    async def test_異常系_fetch_listing失敗時にエラーをCollectResultに含む(
        self,
    ) -> None:
        """When fetch_listing raises, collect_latest returns error in CollectResult."""
        from report_scraper.core.base_scraper import BaseReportScraper
        from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

        class FailingScraper(BaseReportScraper):
            @property
            def source_key(self) -> str:
                return "failing"

            @property
            def source_config(self) -> SourceConfig:
                return SourceConfig(
                    key="failing",
                    name="Failing",
                    tier="sell_side",
                    listing_url="https://example.com",
                    rendering="static",
                )

            async def fetch_listing(self) -> list[ReportMetadata]:
                msg = "Connection refused"
                raise ConnectionError(msg)

            async def extract_report(
                self, meta: ReportMetadata
            ) -> ScrapedReport | None:
                return None

        scraper = FailingScraper()
        result = await scraper.collect_latest()

        assert result.reports == ()
        assert len(result.errors) == 1
        assert "Connection refused" in result.errors[0]

    @pytest.mark.asyncio
    async def test_異常系_extract_report失敗時にエラーをCollectResultに含む(
        self,
    ) -> None:
        """When extract_report raises for some reports, errors are captured."""
        from datetime import datetime, timezone

        from report_scraper.core.base_scraper import BaseReportScraper
        from report_scraper.types import ReportMetadata, ScrapedReport, SourceConfig

        class PartialFailScraper(BaseReportScraper):
            @property
            def source_key(self) -> str:
                return "partial"

            @property
            def source_config(self) -> SourceConfig:
                return SourceConfig(
                    key="partial",
                    name="Partial",
                    tier="sell_side",
                    listing_url="https://example.com",
                    rendering="static",
                )

            async def fetch_listing(self) -> list[ReportMetadata]:
                return [
                    ReportMetadata(
                        url="https://example.com/ok",
                        title="OK Report",
                        published=datetime(2026, 3, 1, tzinfo=timezone.utc),
                        source_key="partial",
                    ),
                    ReportMetadata(
                        url="https://example.com/fail",
                        title="Fail Report",
                        published=datetime(2026, 3, 2, tzinfo=timezone.utc),
                        source_key="partial",
                    ),
                ]

            async def extract_report(
                self, meta: ReportMetadata
            ) -> ScrapedReport | None:
                if "fail" in meta.url:
                    msg = "Extraction timeout"
                    raise TimeoutError(msg)
                return ScrapedReport(metadata=meta)

        scraper = PartialFailScraper()
        result = await scraper.collect_latest()

        assert len(result.reports) == 1
        assert result.reports[0].metadata.title == "OK Report"
        assert len(result.errors) == 1
        assert "Extraction timeout" in result.errors[0]
