"""Unit tests for data_pipeline.storage.adapters."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from data_pipeline.collectors.base import CollectedItem
from data_pipeline.storage.adapters import (
    convert_many,
    from_pdf_chunk,
    from_pdf_report,
    from_reddit_post,
    from_rss_mcp_item,
    from_web_research,
)


class TestFromRssMcpItem:
    """from_rss_mcp_item のテスト."""

    def test_正常系_全フィールドあり(self) -> None:
        item = {
            "item_id": "abc-123",
            "title": "Test Article",
            "link": "https://example.com/article",
            "published": "2026-03-24T10:00:00+00:00",
            "summary": "Article summary",
            "content": "Full content",
            "author": "John",
            "fetched_at": "2026-03-24T12:00:00+00:00",
        }
        result = from_rss_mcp_item(item, "cnbc")

        assert isinstance(result, CollectedItem)
        assert result.source_id == "cnbc"
        assert result.url == "https://example.com/article"
        assert result.title == "Test Article"
        assert result.raw_text == "Full content"  # content優先
        assert result.author == "John"
        assert result.collection_method == "rss"

    def test_正常系_contentなしでsummaryフォールバック(self) -> None:
        item = {
            "title": "Test",
            "link": "https://example.com",
            "summary": "Summary text",
        }
        result = from_rss_mcp_item(item, "test")
        assert result.raw_text == "Summary text"

    def test_正常系_published日時パース(self) -> None:
        item = {
            "title": "Test",
            "link": "https://example.com",
            "published": "2026-03-24T10:00:00+09:00",
        }
        result = from_rss_mcp_item(item, "test")
        assert result.published_at is not None
        assert result.published_at.year == 2026

    def test_エッジケース_最小フィールド(self) -> None:
        item = {"link": "https://example.com"}
        result = from_rss_mcp_item(item, "test")
        assert result.url == "https://example.com"
        assert result.title == ""
        assert result.raw_text == ""


class TestFromPdfChunk:
    """from_pdf_chunk のテスト."""

    def test_正常系_チャンクを変換(self) -> None:
        chunk = {
            "text": "This is page 1 content.",
            "chunk_index": 0,
            "page_range": "1-3",
            "section": "Executive Summary",
        }
        result = from_pdf_chunk(
            chunk,
            "pdf-sellside",
            pdf_url="https://example.com/report.pdf",
            pdf_title="Q1 2026 Report",
        )

        assert result.source_id == "pdf-sellside"
        assert result.url == "https://example.com/report.pdf#chunk-0"
        assert result.title == "Q1 2026 Report"
        assert result.metadata["pdf_url"] == "https://example.com/report.pdf"
        assert result.raw_text == "This is page 1 content."
        assert result.collection_method == "pdf"
        assert result.content_type == "report"
        assert result.metadata["chunk_index"] == 0

    def test_正常系_contentキーフォールバック(self) -> None:
        chunk = {"content": "Alternative key"}
        result = from_pdf_chunk(chunk, "test")
        assert result.raw_text == "Alternative key"


class TestFromPdfReport:
    """from_pdf_report のテスト."""

    def test_正常系_全文を変換(self) -> None:
        result = from_pdf_report(
            "Full report text here...",
            source_id="pdf-earnings",
            pdf_url="https://example.com/earnings.pdf",
            pdf_title="Earnings Report",
        )
        assert result.raw_text == "Full report text here..."
        assert result.content_type == "report"
        assert result.collection_method == "pdf"


class TestFromWebResearch:
    """from_web_research のテスト."""

    def test_正常系_Tavily結果を変換(self) -> None:
        finding = {
            "url": "https://example.com/article",
            "title": "Research Finding",
            "content": "Detailed content from web search.",
            "query": "S&P 500 outlook",
            "provider": "tavily",
            "score": 0.95,
        }
        result = from_web_research(finding, "tavily")

        assert result.url == "https://example.com/article"
        assert result.raw_text == "Detailed content from web search."
        assert result.collection_method == "web_search"
        assert result.metadata["search_query"] == "S&P 500 outlook"
        assert result.metadata["score"] == 0.95

    def test_正常系_source_urlキーフォールバック(self) -> None:
        finding = {
            "source_url": "https://example.com",
            "title": "Test",
            "summary": "Summary text",
        }
        result = from_web_research(finding, "gemini-search")
        assert result.url == "https://example.com"
        assert result.raw_text == "Summary text"


class TestFromRedditPost:
    """from_reddit_post のテスト."""

    def test_正常系_Reddit投稿を変換(self) -> None:
        post = {
            "title": "What do you think about NVDA?",
            "url": "https://reddit.com/r/investing/abc",
            "selftext": "I've been looking at NVDA...",
            "author": "investor123",
            "subreddit": "investing",
            "score": 42,
            "num_comments": 15,
        }
        result = from_reddit_post(post)

        assert result.source_id == "reddit"
        assert result.title == "What do you think about NVDA?"
        assert result.raw_text == "I've been looking at NVDA..."
        assert result.collection_method == "api"
        assert result.content_type == "post"
        assert result.metadata["subreddit"] == "investing"

    def test_正常系_bodyキーフォールバック(self) -> None:
        post = {
            "title": "Comment",
            "permalink": "/r/stocks/xyz",
            "body": "Comment text",
        }
        result = from_reddit_post(post, source_id="reddit")
        assert result.url == "/r/stocks/xyz"
        assert result.raw_text == "Comment text"


class TestConvertMany:
    """convert_many のテスト."""

    def test_正常系_リスト一括変換(self) -> None:
        items = [
            {"link": "https://a.com", "title": "A", "summary": "Text A"},
            {"link": "https://b.com", "title": "B", "summary": "Text B"},
        ]
        results = convert_many(items, from_rss_mcp_item, "test")
        assert len(results) == 2
        assert results[0].url == "https://a.com"
        assert results[1].url == "https://b.com"

    def test_正常系_変換失敗はスキップ(self) -> None:
        def bad_converter(item, source_id):
            if item.get("bad"):
                raise ValueError("bad item")
            return from_rss_mcp_item(item, source_id)

        items = [
            {"link": "https://a.com", "title": "A"},
            {"bad": True},
            {"link": "https://c.com", "title": "C"},
        ]
        results = convert_many(items, bad_converter, "test")
        assert len(results) == 2

    def test_エッジケース_空リスト(self) -> None:
        results = convert_many([], from_rss_mcp_item, "test")
        assert results == []
