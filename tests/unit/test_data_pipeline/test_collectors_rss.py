"""Unit tests for data_pipeline.collectors.rss."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from data_pipeline.collectors.rss import (
    RssCollector,
    _extract_text,
    _fetch_full_text,
    _parse_datetime,
    _should_skip_full_text,
)
from data_pipeline.registry.models import ConfigRef, DataSource


def _mock_requests_and_feedparser(mock_feed):
    """requests.get + feedparser.parse を同時にモックするコンテキストマネージャ."""
    mock_response = type(
        "Response",
        (),
        {
            "content": b"<rss></rss>",
            "status_code": 200,
            "raise_for_status": lambda self: None,
        },
    )()
    return (
        patch("data_pipeline.collectors.rss.requests.get", return_value=mock_response),
        patch("data_pipeline.collectors.rss.feedparser.parse", return_value=mock_feed),
    )


class TestParseDateTime:
    """_parse_datetime のテスト."""

    def test_正常系_RFC2822形式をパースできる(self) -> None:
        dt = _parse_datetime("Mon, 24 Mar 2026 10:00:00 +0900")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 24

    def test_正常系_ISO8601形式をパースできる(self) -> None:
        dt = _parse_datetime("2026-03-24T10:00:00+09:00")
        assert dt is not None
        assert dt.year == 2026

    def test_正常系_Noneを渡すとNone(self) -> None:
        assert _parse_datetime(None) is None

    def test_正常系_空文字列でNone(self) -> None:
        assert _parse_datetime("") is None

    def test_エッジケース_不正な文字列でNone(self) -> None:
        assert _parse_datetime("not-a-date") is None


class TestExtractText:
    """_extract_text のテスト."""

    def test_正常系_contentフィールドから抽出(self) -> None:
        entry = {"content": [{"value": "Full article text"}]}
        assert _extract_text(entry) == "Full article text"

    def test_正常系_summaryにフォールバック(self) -> None:
        entry = {"summary": "Article summary"}
        assert _extract_text(entry) == "Article summary"

    def test_正常系_descriptionにフォールバック(self) -> None:
        entry = {"description": "Article description"}
        assert _extract_text(entry) == "Article description"

    def test_正常系_contentが優先される(self) -> None:
        entry = {
            "content": [{"value": "Full text"}],
            "summary": "Summary",
        }
        assert _extract_text(entry) == "Full text"

    def test_エッジケース_空のエントリで空文字列(self) -> None:
        assert _extract_text({}) == ""

    def test_エッジケース_content空リストでsummaryにフォールバック(self) -> None:
        entry = {"content": [], "summary": "Summary"}
        assert _extract_text(entry) == "Summary"


class TestShouldSkipFullText:
    """_should_skip_full_text のテスト."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.boj.or.jp/report.pdf",
            "https://example.com/data.xlsx",
            "https://example.com/archive.zip",
            "https://example.com/doc.docx",
        ],
    )
    def test_正常系_バイナリ拡張子はスキップ(self, url: str) -> None:
        assert _should_skip_full_text(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.fsa.go.jp/news/article.html",
            "https://www.jetro.go.jp/biznews/2026/03/abc.html",
            "https://example.com/article",
        ],
    )
    def test_正常系_HTMLページはスキップしない(self, url: str) -> None:
        assert _should_skip_full_text(url) is False


class TestFetchFullText:
    """_fetch_full_text のテスト."""

    def test_正常系_PDFはNoneを返す(self) -> None:
        result = _fetch_full_text("https://example.com/report.pdf")
        assert result is None

    def test_正常系_trafilaturaが呼ばれる(self) -> None:
        with (
            patch(
                "data_pipeline.collectors.rss.trafilatura.fetch_url",
                return_value="<html><body>Hello</body></html>",
            ),
            patch(
                "data_pipeline.collectors.rss.trafilatura.extract", return_value="Hello"
            ),
        ):
            result = _fetch_full_text("https://example.com/article")
            assert result == "Hello"

    def test_正常系_fetch_url失敗でNone(self) -> None:
        with patch(
            "data_pipeline.collectors.rss.trafilatura.fetch_url", return_value=None
        ):
            result = _fetch_full_text("https://example.com/article")
            assert result is None


class TestRssCollector:
    """RssCollector のテスト."""

    @pytest.fixture
    def config_dir_with_presets(self, tmp_path: Path) -> Path:
        """プリセットファイル付きの設定ディレクトリ."""
        presets = {
            "version": "1.0",
            "presets": [
                {
                    "url": "https://example.com/feed.xml",
                    "title": "Example Feed",
                    "category": "test",
                    "fetch_interval": "daily",
                    "enabled": True,
                },
                {
                    "url": "https://example.com/disabled.xml",
                    "title": "Disabled Feed",
                    "category": "test",
                    "fetch_interval": "daily",
                    "enabled": False,
                },
            ],
        }
        (tmp_path / "test-presets.json").write_text(
            json.dumps(presets, ensure_ascii=False),
        )
        return tmp_path

    def test_正常系_config_refからフィードURLを解決できる(
        self,
        config_dir_with_presets: Path,
    ) -> None:
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            config_ref=ConfigRef(file="test-presets.json"),
        )
        collector = RssCollector(config_dir=config_dir_with_presets)
        urls = collector._resolve_feed_urls(source)

        # enabled=True のフィードのみ
        assert len(urls) == 1
        assert urls[0]["url"] == "https://example.com/feed.xml"

    def test_正常系_urlフィールドからフォールバック解決(self, tmp_path: Path) -> None:
        source = DataSource(
            source_id="test",
            name="Test Source",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            url="https://example.com/rss",
        )
        collector = RssCollector(config_dir=tmp_path)
        urls = collector._resolve_feed_urls(source)
        assert len(urls) == 1
        assert urls[0]["url"] == "https://example.com/rss"

    def test_正常系_フィードURL解決不可でエラー(self, tmp_path: Path) -> None:
        source = DataSource(
            source_id="no-feed",
            name="No Feed",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
        )
        collector = RssCollector(config_dir=tmp_path)
        result = collector.collect(source)
        assert result.error_count >= 1
        assert "No feed URLs" in result.errors[0]

    def test_正常系_言語推定_jpタグ(self, tmp_path: Path) -> None:
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            tags=["jp_market"],
        )
        collector = RssCollector(config_dir=tmp_path)
        lang = collector._detect_language(source, "https://example.com")
        assert lang == "ja"

    def test_正常系_言語推定_usタグ(self, tmp_path: Path) -> None:
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            tags=["us_market"],
        )
        collector = RssCollector(config_dir=tmp_path)
        lang = collector._detect_language(source, "https://example.com")
        assert lang == "en"

    def test_正常系_言語推定_jpドメイン(self, tmp_path: Path) -> None:
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
        )
        collector = RssCollector(config_dir=tmp_path)
        lang = collector._detect_language(source, "https://www.fsa.go.jp/news")
        assert lang == "ja"

    def test_正常系_feedparser結果をCollectedItemに変換(
        self,
        tmp_path: Path,
    ) -> None:
        """feedparser の結果をモックして変換テスト."""
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            url="https://example.com/feed.xml",
        )

        mock_feed = type(
            "Feed",
            (),
            {
                "bozo": False,
                "entries": [
                    {
                        "link": "https://example.com/article/1",
                        "title": "Test Article",
                        "summary": "This is a test article.",
                        "published": "Mon, 24 Mar 2026 10:00:00 +0000",
                        "author": "Test Author",
                        "tags": [{"term": "finance"}],
                        "id": "article-1",
                    },
                ],
            },
        )()

        collector = RssCollector(config_dir=tmp_path)
        mock_req, mock_fp = _mock_requests_and_feedparser(mock_feed)
        with mock_req, mock_fp:
            result = collector.collect(source)

        assert result.success_count == 1
        item = result.items[0]
        assert item.source_id == "test"
        assert item.url == "https://example.com/article/1"
        assert item.title == "Test Article"
        assert item.raw_text == "This is a test article."
        assert item.author == "Test Author"
        assert item.collection_method == "rss"
        assert item.metadata["feed_title"] == "Test"
        assert "finance" in item.metadata["tags"]

    def test_正常系_fetch_if_emptyで空テキストの本文を取得(
        self,
        tmp_path: Path,
    ) -> None:
        """raw_text が空のアイテムに対して本文取得が行われる."""
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            url="https://example.com/feed.xml",
        )

        # summary が空のエントリ
        mock_feed = type(
            "Feed",
            (),
            {
                "bozo": False,
                "entries": [
                    {
                        "link": "https://example.com/article/1",
                        "title": "Article with no summary",
                        "summary": "",
                        "published": "Mon, 24 Mar 2026 10:00:00 +0000",
                    },
                ],
            },
        )()

        collector = RssCollector(
            config_dir=tmp_path,
            fetch_if_empty=True,
            request_delay=0,
        )

        mock_req, mock_fp = _mock_requests_and_feedparser(mock_feed)
        with (
            mock_req,
            mock_fp,
            patch(
                "data_pipeline.collectors.rss._fetch_full_text",
                return_value="Full article text from trafilatura",
            ) as mock_fetch,
        ):
            result = collector.collect(source)

        assert result.success_count == 1
        item = result.items[0]
        assert item.raw_text == "Full article text from trafilatura"
        assert item.metadata["full_text_fetched"] is True
        mock_fetch.assert_called_once_with("https://example.com/article/1")

    def test_正常系_fetch_if_emptyでテキスト有りはスキップ(
        self,
        tmp_path: Path,
    ) -> None:
        """raw_text がある場合は本文取得しない."""
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            url="https://example.com/feed.xml",
        )

        mock_feed = type(
            "Feed",
            (),
            {
                "bozo": False,
                "entries": [
                    {
                        "link": "https://example.com/article/1",
                        "title": "Article with summary",
                        "summary": "This is the summary text.",
                        "published": "Mon, 24 Mar 2026 10:00:00 +0000",
                    },
                ],
            },
        )()

        collector = RssCollector(
            config_dir=tmp_path,
            fetch_if_empty=True,
            request_delay=0,
        )

        mock_req, mock_fp = _mock_requests_and_feedparser(mock_feed)
        with (
            mock_req,
            mock_fp,
            patch("data_pipeline.collectors.rss._fetch_full_text") as mock_fetch,
        ):
            result = collector.collect(source)

        # テキストがあるので _fetch_full_text は呼ばれない
        mock_fetch.assert_not_called()
        assert result.items[0].raw_text == "This is the summary text."

    def test_正常系_fetch_full_textで全アイテム本文取得(
        self,
        tmp_path: Path,
    ) -> None:
        """fetch_full_text=True なら全アイテムで本文取得."""
        source = DataSource(
            source_id="test",
            name="Test",
            collection_method="rss",
            authority_level=3,
            target_instance="research",
            url="https://example.com/feed.xml",
        )

        mock_feed = type(
            "Feed",
            (),
            {
                "bozo": False,
                "entries": [
                    {
                        "link": "https://example.com/article/1",
                        "title": "Article with summary",
                        "summary": "RSS summary.",
                        "published": "Mon, 24 Mar 2026 10:00:00 +0000",
                    },
                ],
            },
        )()

        collector = RssCollector(
            config_dir=tmp_path,
            fetch_full_text=True,
            request_delay=0,
        )

        mock_req, mock_fp = _mock_requests_and_feedparser(mock_feed)
        with (
            mock_req,
            mock_fp,
            patch(
                "data_pipeline.collectors.rss._fetch_full_text",
                return_value="Full text overwrites RSS summary",
            ),
        ):
            result = collector.collect(source)

        item = result.items[0]
        assert item.raw_text == "Full text overwrites RSS summary"
        assert item.metadata["full_text_fetched"] is True


class TestRssCollectorIntegration:
    """実際のフィードを使った統合テスト."""

    @pytest.fixture
    def real_collector(self) -> RssCollector | None:
        """実設定ファイルを使うコレクター."""
        config_dir = Path(__file__).parents[3] / "data" / "config"
        if not (config_dir / "source_registry.json").exists():
            pytest.skip("Real config files not available")
        return RssCollector(config_dir=config_dir, max_items_per_feed=3)

    def test_正常系_JP_RSSフィードから収集できる(
        self,
        real_collector: RssCollector,
    ) -> None:
        from data_pipeline.registry import RegistryLoader

        config_dir = Path(__file__).parents[3] / "data" / "config"
        loader = RegistryLoader(config_dir=config_dir)
        registry = loader.load_source_registry()
        source = registry.get_source("jp-finance")
        assert source is not None

        result = real_collector.collect(source)
        # 少なくとも一部のフィードからアイテムが取得できること
        assert result.success_count > 0
        # 全アイテムが正しいsource_idを持つこと
        assert all(item.source_id == "jp-finance" for item in result.items)
        # 全アイテムがURLを持つこと
        assert all(item.url for item in result.items)
