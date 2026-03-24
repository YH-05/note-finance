"""Unit tests for data_pipeline.integrations.bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from data_pipeline.integrations.bridge import (
    save_news_scraper_results,
    save_pdf_chunks,
    save_pdf_report,
    save_raw_texts,
    save_reddit_posts,
    save_rss_mcp_items,
    save_web_research_results,
    set_store,
)
from data_pipeline.storage.raw_store import RawStore


@pytest.fixture(autouse=True)
def _use_tmp_store(tmp_path: Path) -> None:
    """全テストで一時ディレクトリのストアを使用."""
    set_store(RawStore(base_dir=tmp_path))


class TestSaveNewsScraperResults:
    """save_news_scraper_results のテスト."""

    def test_正常系_dict形式の記事を保存(self) -> None:
        articles = [
            {
                "url": "https://www.cnbc.com/article/1",
                "title": "Market Update",
                "content": "S&P 500 reached new highs.",
                "published": "2026-03-24T10:00:00+00:00",
                "source": "cnbc",
                "category": "markets",
                "author": "Reporter",
                "tags": ["stocks"],
            },
            {
                "url": "https://www.cnbc.com/article/2",
                "title": "Fed Meeting",
                "summary": "Fed held rates steady.",
                "source": "cnbc",
            },
        ]
        result = save_news_scraper_results(articles, source_id="cnbc")
        assert result.saved == 2
        assert result.skipped_empty == 0

    def test_正常系_テキスト空はスキップ(self) -> None:
        articles = [
            {"url": "https://a.com", "title": "No text"},
        ]
        result = save_news_scraper_results(articles, source_id="test")
        assert result.skipped_empty == 1


class TestSaveReportScraperResults:
    """save_report_scraper_results のテスト."""

    def test_正常系_レポートを保存(self) -> None:
        from data_pipeline.integrations.bridge import save_report_scraper_results

        reports = [
            {
                "metadata": {
                    "url": "https://goldman.com/report/1",
                    "title": "Q1 Outlook",
                    "published": "2026-03-01",
                    "source_key": "goldman_sachs",
                    "author": "Analyst",
                    "tags": ("macro", "equity"),
                },
                "content": {
                    "text": "Our Q1 outlook suggests...",
                    "method": "trafilatura",
                    "length": 5000,
                },
            },
        ]
        result = save_report_scraper_results(reports, source_id="report-scraper")
        assert result.saved == 1


class TestSavePdfChunks:
    """save_pdf_chunks のテスト."""

    def test_正常系_チャンクを保存(self) -> None:
        chunks = [
            {"content": "Executive summary text.", "chunk_index": 0, "section_title": "Summary"},
            {"content": "Market analysis text.", "chunk_index": 1, "section_title": "Analysis"},
        ]
        result = save_pdf_chunks(
            chunks,
            source_id="pdf-sellside",
            pdf_url="https://example.com/report.pdf",
            pdf_title="Q1 Report",
        )
        assert result.saved == 2


class TestSavePdfReport:
    """save_pdf_report のテスト."""

    def test_正常系_全文を保存(self) -> None:
        result = save_pdf_report(
            "Full report markdown text...",
            source_id="pdf-earnings",
            pdf_url="https://example.com/earnings.pdf",
            pdf_title="AAPL Q1 2026",
        )
        assert result.saved == 1

    def test_正常系_重複は排除(self) -> None:
        save_pdf_report(
            "Text",
            source_id="test",
            pdf_url="https://a.com/dup.pdf",
            pdf_title="Dup",
        )
        result = save_pdf_report(
            "Text",
            source_id="test",
            pdf_url="https://a.com/dup.pdf",
            pdf_title="Dup",
        )
        assert result.skipped_duplicate == 1


class TestSaveRssMcpItems:
    """save_rss_mcp_items のテスト."""

    def test_正常系_RSS_MCPアイテムを保存(self) -> None:
        items = [
            {
                "item_id": "abc",
                "title": "News Item",
                "link": "https://example.com/news/1",
                "summary": "Summary text.",
                "published": "2026-03-24T10:00:00+00:00",
            },
        ]
        result = save_rss_mcp_items(items, source_id="cnbc")
        assert result.saved == 1


class TestSaveWebResearchResults:
    """save_web_research_results のテスト."""

    def test_正常系_検索結果を保存(self) -> None:
        findings = [
            {
                "url": "https://example.com/article",
                "title": "Research Finding",
                "content": "Detailed analysis of market trends.",
                "query": "S&P 500",
                "provider": "tavily",
            },
        ]
        result = save_web_research_results(findings, source_id="tavily")
        assert result.saved == 1


class TestSaveRedditPosts:
    """save_reddit_posts のテスト."""

    def test_正常系_Reddit投稿を保存(self) -> None:
        posts = [
            {
                "title": "What do you think about NVDA?",
                "url": "https://reddit.com/r/investing/abc",
                "selftext": "I've been looking at NVDA...",
                "author": "investor123",
                "subreddit": "investing",
                "score": 42,
            },
        ]
        result = save_reddit_posts(posts)
        assert result.saved == 1


class TestSaveRawTexts:
    """save_raw_texts 汎用ブリッジのテスト."""

    def test_正常系_任意テキストを保存(self) -> None:
        items = [
            {"url": "https://a.com", "title": "A", "raw_text": "Text A"},
            {"url": "https://b.com", "title": "B", "content": "Text B"},
        ]
        result = save_raw_texts(items, source_id="custom", collection_method="manual")
        assert result.saved == 2


class TestBridgeIntegration:
    """複数ブリッジの統合テスト."""

    def test_正常系_複数ソースの保存が共存(self, tmp_path: Path) -> None:
        store = RawStore(base_dir=tmp_path)
        set_store(store)

        # RSS
        save_rss_mcp_items(
            [{"link": "https://rss.com/1", "title": "RSS", "summary": "RSS text"}],
            source_id="cnbc",
        )
        # Web検索
        save_web_research_results(
            [{"url": "https://web.com/1", "title": "Web", "content": "Web text"}],
            source_id="tavily",
        )
        # Reddit
        save_reddit_posts(
            [{"url": "https://reddit.com/1", "title": "Reddit", "selftext": "Reddit text"}],
        )

        assert set(store.list_sources()) == {"cnbc", "tavily", "reddit"}
        assert store.count("cnbc") == 1
        assert store.count("tavily") == 1
        assert store.count("reddit") == 1
