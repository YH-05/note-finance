"""Tests for scripts/emit_graph_queue.py.

graph-queue 生成スクリプトの単体テスト。
6コマンドのマッピングロジック、ID生成、CLI引数パース、自動クリーンアップを検証。
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from emit_graph_queue import (
    COMMANDS,
    THEME_TO_CATEGORY,
    cleanup_old_files,
    generate_claim_id,
    generate_entity_id,
    generate_queue_id,
    generate_source_id,
    generate_topic_id,
    main,
    map_ai_research,
    map_asset_management,
    map_finance_full,
    map_finance_news,
    map_market_report,
    map_reddit_topics,
    parse_args,
    resolve_category,
    run,
)
from freezegun import freeze_time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FROZEN_TIME = "2026-03-07T12:00:00+00:00"
"""Fixed time for deterministic tests."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _news_batch(
    *,
    theme_key: str = "index",
    articles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """finance-news-workflow 形式のバッチデータを生成。"""
    if articles is None:
        articles = [
            {
                "url": "https://www.cnbc.com/2026/03/07/sp500-hits-record.html",
                "title": "S&P 500 hits record high",
                "summary": "The S&P 500 index reached an all-time high on Friday.",
                "feed_source": "CNBC - Markets",
                "published": "2026-03-07T10:00:00+00:00",
            }
        ]
    return {
        "session_id": "news-20260307-120000",
        "batch_label": theme_key,
        "articles": articles,
    }


def _ai_research_batch(
    companies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """ai-research-collect 形式のバッチデータを生成。"""
    if companies is None:
        companies = [
            {
                "company_name": "NVIDIA",
                "ticker": "NVDA",
                "url": "https://example.com/nvidia-ai-report",
                "title": "NVIDIA AI Revenue Surges",
                "summary": "NVIDIA reported record AI revenue.",
                "published": "2026-03-07T08:00:00+00:00",
            }
        ]
    return {
        "session_id": "ai-research-20260307-120000",
        "companies": companies,
    }


def _market_report_data() -> dict[str, Any]:
    """generate-market-report 形式のデータを生成。"""
    return {
        "session_id": "market-report-20260307",
        "report_date": "2026-03-07",
        "sections": [
            {
                "title": "Weekly Market Summary",
                "content": "Markets rallied this week.",
                "sources": [
                    {
                        "url": "https://example.com/market-recap",
                        "title": "Market Recap",
                        "published": "2026-03-07T09:00:00+00:00",
                    }
                ],
            }
        ],
    }


def _asset_management_batch() -> dict[str, Any]:
    """asset-management 形式のバッチデータを生成。"""
    return {
        "session_id": "asset-mgmt-20260307-120000",
        "themes": {
            "nisa": {
                "articles": [
                    {
                        "url": "https://example.com/nisa-update",
                        "title": "NISA制度の改正",
                        "summary": "新NISA制度が開始",
                        "feed_source": "FSA",
                        "published": "2026-03-07T06:00:00+00:00",
                    }
                ],
                "name_ja": "NISA制度",
            }
        },
    }


def _reddit_topics_batch() -> dict[str, Any]:
    """reddit-finance-topics 形式のバッチデータを生成。"""
    return {
        "session_id": "reddit-topics-20260307",
        "topics": [
            {
                "name": "Dividend ETFs vs Growth ETFs",
                "url": "https://reddit.com/r/investing/comments/abc123",
                "title": "Dividend ETFs vs Growth ETFs debate",
                "summary": "Community discusses merits of dividend vs growth.",
                "subreddit": "r/investing",
                "published": "2026-03-06T18:00:00+00:00",
                "score": 245,
            }
        ],
    }


def _finance_full_data() -> dict[str, Any]:
    """finance-full 形式のデータを生成。"""
    return {
        "session_id": "finance-full-20260307",
        "sources": [
            {
                "url": "https://example.com/source1",
                "title": "Primary Source",
                "published": "2026-03-07T10:00:00+00:00",
            }
        ],
        "claims": [
            {
                "content": "S&P 500 rose 2% this week.",
                "source_url": "https://example.com/source1",
                "category": "stock",
            }
        ],
    }


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """parse_args 関数のテスト。"""

    def test_正常系_最小限の引数(self) -> None:
        args = parse_args(
            ["--command", "finance-news-workflow", "--input", "data.json"]
        )
        assert args.command == "finance-news-workflow"
        assert args.input == "data.json"
        assert args.cleanup is False

    def test_正常系_cleanupオプション(self) -> None:
        args = parse_args(
            ["--command", "finance-news-workflow", "--input", "data.json", "--cleanup"]
        )
        assert args.cleanup is True

    def test_正常系_全6コマンドが指定できる(self) -> None:
        for cmd in COMMANDS:
            args = parse_args(["--command", cmd, "--input", "dummy"])
            assert args.command == cmd

    def test_異常系_commandが未指定でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--input", "data.json"])

    def test_異常系_inputが未指定でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--command", "finance-news-workflow"])

    def test_異常系_不正なコマンド名でエラー(self) -> None:
        with pytest.raises(SystemExit):
            parse_args(["--command", "invalid-command", "--input", "data.json"])


# ---------------------------------------------------------------------------
# ID Generation
# ---------------------------------------------------------------------------


class TestGenerateSourceId:
    """generate_source_id 関数のテスト。"""

    def test_正常系_同じURLで同じIDを生成(self) -> None:
        url = "https://example.com/article/1"
        id1 = generate_source_id(url)
        id2 = generate_source_id(url)
        assert id1 == id2

    def test_正常系_異なるURLで異なるIDを生成(self) -> None:
        id1 = generate_source_id("https://example.com/1")
        id2 = generate_source_id("https://example.com/2")
        assert id1 != id2

    def test_正常系_UUID形式で返る(self) -> None:
        result = generate_source_id("https://example.com/test")
        # uuid5 format: 8-4-4-4-12
        parts = result.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8


class TestGenerateTopicId:
    """generate_topic_id 関数のテスト。"""

    def test_正常系_同じ名前とカテゴリで同じIDを生成(self) -> None:
        id1 = generate_topic_id("S&P 500", "stock")
        id2 = generate_topic_id("S&P 500", "stock")
        assert id1 == id2

    def test_正常系_異なるカテゴリで異なるIDを生成(self) -> None:
        id1 = generate_topic_id("Interest Rates", "macro")
        id2 = generate_topic_id("Interest Rates", "finance")
        assert id1 != id2


class TestGenerateEntityId:
    """generate_entity_id 関数のテスト。"""

    def test_正常系_同じ名前とタイプで同じIDを生成(self) -> None:
        id1 = generate_entity_id("NVIDIA", "company")
        id2 = generate_entity_id("NVIDIA", "company")
        assert id1 == id2

    def test_正常系_異なるタイプで異なるIDを生成(self) -> None:
        id1 = generate_entity_id("NVIDIA", "company")
        id2 = generate_entity_id("NVIDIA", "ticker")
        assert id1 != id2


class TestGenerateClaimId:
    """generate_claim_id 関数のテスト。"""

    def test_正常系_同じ内容で同じIDを生成(self) -> None:
        content = "S&P 500 rose 2% this week."
        id1 = generate_claim_id(content)
        id2 = generate_claim_id(content)
        assert id1 == id2

    def test_正常系_16文字のhex文字列を返す(self) -> None:
        result = generate_claim_id("test content")
        assert len(result) == 16
        # Should be valid hex
        int(result, 16)

    def test_正常系_異なる内容で異なるIDを生成(self) -> None:
        id1 = generate_claim_id("content A")
        id2 = generate_claim_id("content B")
        assert id1 != id2


class TestGenerateQueueId:
    """generate_queue_id 関数のテスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_gqプレフィックスで始まる(self) -> None:
        result = generate_queue_id()
        assert result.startswith("gq-")

    @freeze_time(FROZEN_TIME)
    def test_正常系_タイムスタンプを含む(self) -> None:
        result = generate_queue_id()
        # format: gq-{timestamp}-{hash4}
        parts = result.split("-")
        assert len(parts) == 3
        # timestamp part should be numeric
        assert parts[1].isdigit()

    @freeze_time(FROZEN_TIME)
    def test_正常系_hash4は4文字hex(self) -> None:
        result = generate_queue_id()
        parts = result.split("-")
        hash_part = parts[2]
        assert len(hash_part) == 4
        int(hash_part, 16)


# ---------------------------------------------------------------------------
# resolve_category
# ---------------------------------------------------------------------------


class TestResolveCategory:
    """resolve_category 関数のテスト。"""

    def test_正常系_indexはstockに変換(self) -> None:
        assert resolve_category("index") == "stock"

    def test_正常系_stockはstockに変換(self) -> None:
        assert resolve_category("stock") == "stock"

    def test_正常系_sectorはsectorに変換(self) -> None:
        assert resolve_category("sector") == "sector"

    def test_正常系_macro_cnbcはmacroに変換(self) -> None:
        assert resolve_category("macro_cnbc") == "macro"

    def test_正常系_macro_otherはmacroに変換(self) -> None:
        assert resolve_category("macro_other") == "macro"

    def test_正常系_ai_cnbcはaiに変換(self) -> None:
        assert resolve_category("ai_cnbc") == "ai"

    def test_正常系_ai_nasdaqはaiに変換(self) -> None:
        assert resolve_category("ai_nasdaq") == "ai"

    def test_正常系_ai_techはaiに変換(self) -> None:
        assert resolve_category("ai_tech") == "ai"

    def test_正常系_finance_cnbcはfinanceに変換(self) -> None:
        assert resolve_category("finance_cnbc") == "finance"

    def test_正常系_finance_nasdaqはfinanceに変換(self) -> None:
        assert resolve_category("finance_nasdaq") == "finance"

    def test_正常系_finance_otherはfinanceに変換(self) -> None:
        assert resolve_category("finance_other") == "finance"

    def test_エッジケース_未知のテーマはotherに変換(self) -> None:
        assert resolve_category("unknown_theme") == "other"


# ---------------------------------------------------------------------------
# map_finance_news
# ---------------------------------------------------------------------------


class TestMapFinanceNews:
    """map_finance_news 関数のテスト。"""

    def test_正常系_sourcesが生成される(self) -> None:
        batch = _news_batch()
        result = map_finance_news(batch)

        assert len(result["sources"]) == 1
        source = result["sources"][0]
        assert source["url"] == "https://www.cnbc.com/2026/03/07/sp500-hits-record.html"
        assert source["title"] == "S&P 500 hits record high"
        assert "source_id" in source

    def test_正常系_claimsが生成される(self) -> None:
        batch = _news_batch()
        result = map_finance_news(batch)

        assert len(result["claims"]) == 1
        claim = result["claims"][0]
        assert (
            claim["content"] == "The S&P 500 index reached an all-time high on Friday."
        )
        assert "claim_id" in claim

    def test_正常系_batch_labelが設定される(self) -> None:
        batch = _news_batch(theme_key="macro_cnbc")
        result = map_finance_news(batch)
        assert result["batch_label"] == "macro_cnbc"

    def test_正常系_session_idが設定される(self) -> None:
        batch = _news_batch()
        result = map_finance_news(batch)
        assert result["session_id"] == "news-20260307-120000"

    def test_正常系_source_idが決定論的(self) -> None:
        batch = _news_batch()
        r1 = map_finance_news(batch)
        r2 = map_finance_news(batch)
        assert r1["sources"][0]["source_id"] == r2["sources"][0]["source_id"]

    def test_正常系_claimのcategoryがテーマから解決される(self) -> None:
        batch = _news_batch(theme_key="macro_cnbc")
        result = map_finance_news(batch)
        assert result["claims"][0]["category"] == "macro"

    def test_正常系_summaryが空の記事ではclaimが生成されない(self) -> None:
        batch = _news_batch(
            articles=[
                {
                    "url": "https://example.com/no-summary",
                    "title": "No Summary Article",
                    "summary": "",
                    "feed_source": "Test",
                    "published": "2026-03-07T10:00:00+00:00",
                }
            ]
        )
        result = map_finance_news(batch)
        assert len(result["sources"]) == 1
        assert len(result["claims"]) == 0

    def test_エッジケース_空のarticlesで空結果(self) -> None:
        batch = _news_batch(articles=[])
        result = map_finance_news(batch)
        assert result["sources"] == []
        assert result["claims"] == []


# ---------------------------------------------------------------------------
# map_ai_research
# ---------------------------------------------------------------------------


class TestMapAiResearch:
    """map_ai_research 関数のテスト。"""

    def test_正常系_entitiesが生成される(self) -> None:
        batch = _ai_research_batch()
        result = map_ai_research(batch)

        assert len(result["entities"]) >= 1
        entity_names = [e["name"] for e in result["entities"]]
        assert "NVIDIA" in entity_names

    def test_正常系_sourcesが生成される(self) -> None:
        batch = _ai_research_batch()
        result = map_ai_research(batch)

        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com/nvidia-ai-report"

    def test_正常系_entity_idが決定論的(self) -> None:
        batch = _ai_research_batch()
        r1 = map_ai_research(batch)
        r2 = map_ai_research(batch)
        assert r1["entities"][0]["entity_id"] == r2["entities"][0]["entity_id"]

    def test_正常系_entity_typeがcompanyに設定される(self) -> None:
        batch = _ai_research_batch()
        result = map_ai_research(batch)

        assert len(result["entities"]) == 1
        assert result["entities"][0]["entity_type"] == "company"

    def test_正常系_tickerがentityに含まれる(self) -> None:
        batch = _ai_research_batch()
        result = map_ai_research(batch)

        assert result["entities"][0]["ticker"] == "NVDA"

    def test_正常系_batch_labelがaiに設定される(self) -> None:
        batch = _ai_research_batch()
        result = map_ai_research(batch)
        assert result["batch_label"] == "ai"

    def test_正常系_URLなしのcompanyではsourceが生成されない(self) -> None:
        batch = _ai_research_batch(
            companies=[
                {
                    "company_name": "TestCorp",
                    "ticker": "TST",
                    "url": "",
                    "title": "TestCorp Report",
                    "published": "2026-03-07T08:00:00+00:00",
                }
            ]
        )
        result = map_ai_research(batch)
        assert len(result["entities"]) == 1
        assert len(result["sources"]) == 0

    def test_エッジケース_空のcompaniesで空結果(self) -> None:
        batch = _ai_research_batch(companies=[])
        result = map_ai_research(batch)
        assert result["entities"] == []
        assert result["sources"] == []


# ---------------------------------------------------------------------------
# map_market_report
# ---------------------------------------------------------------------------


class TestMapMarketReport:
    """map_market_report 関数のテスト。"""

    def test_正常系_sourcesが統合される(self) -> None:
        data = _market_report_data()
        result = map_market_report(data)

        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com/market-recap"

    def test_正常系_claimsがsectionから生成される(self) -> None:
        data = _market_report_data()
        result = map_market_report(data)

        assert len(result["claims"]) == 1
        assert "Markets rallied" in result["claims"][0]["content"]

    def test_正常系_session_idが設定される(self) -> None:
        data = _market_report_data()
        result = map_market_report(data)
        assert result["session_id"] == "market-report-20260307"

    def test_正常系_batch_labelがmarket_reportに設定される(self) -> None:
        data = _market_report_data()
        result = map_market_report(data)
        assert result["batch_label"] == "market-report"

    def test_正常系_重複URLが除外される(self) -> None:
        data = {
            "session_id": "market-report-dedup",
            "sections": [
                {
                    "title": "Section A",
                    "content": "Content A",
                    "sources": [
                        {
                            "url": "https://example.com/same",
                            "title": "A",
                            "published": "",
                        },
                    ],
                },
                {
                    "title": "Section B",
                    "content": "Content B",
                    "sources": [
                        {
                            "url": "https://example.com/same",
                            "title": "A dup",
                            "published": "",
                        },
                    ],
                },
            ],
        }
        result = map_market_report(data)
        assert len(result["sources"]) == 1

    def test_正常系_claimのcategoryがmacroに設定される(self) -> None:
        data = _market_report_data()
        result = map_market_report(data)
        assert result["claims"][0]["category"] == "macro"


# ---------------------------------------------------------------------------
# map_asset_management
# ---------------------------------------------------------------------------


class TestMapAssetManagement:
    """map_asset_management 関数のテスト。"""

    def test_正常系_sourcesが生成される(self) -> None:
        batch = _asset_management_batch()
        result = map_asset_management(batch)

        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com/nisa-update"

    def test_正常系_topicsが生成される(self) -> None:
        batch = _asset_management_batch()
        result = map_asset_management(batch)

        assert len(result["topics"]) == 1
        assert result["topics"][0]["name"] == "NISA制度"

    def test_正常系_session_idが設定される(self) -> None:
        batch = _asset_management_batch()
        result = map_asset_management(batch)
        assert result["session_id"] == "asset-mgmt-20260307-120000"

    def test_正常系_batch_labelがasset_managementに設定される(self) -> None:
        batch = _asset_management_batch()
        result = map_asset_management(batch)
        assert result["batch_label"] == "asset-management"

    def test_正常系_topic_idが決定論的(self) -> None:
        batch = _asset_management_batch()
        r1 = map_asset_management(batch)
        r2 = map_asset_management(batch)
        assert r1["topics"][0]["topic_id"] == r2["topics"][0]["topic_id"]

    def test_正常系_topicのcategoryがasset_managementに設定される(self) -> None:
        batch = _asset_management_batch()
        result = map_asset_management(batch)
        assert result["topics"][0]["category"] == "asset-management"

    def test_エッジケース_URLなしのarticleではsourceが生成されない(self) -> None:
        batch = {
            "session_id": "test",
            "themes": {
                "nisa": {
                    "articles": [{"url": "", "title": "No URL article"}],
                    "name_ja": "NISA制度",
                }
            },
        }
        result = map_asset_management(batch)
        assert len(result["sources"]) == 0
        assert len(result["topics"]) == 1


# ---------------------------------------------------------------------------
# map_reddit_topics
# ---------------------------------------------------------------------------


class TestMapRedditTopics:
    """map_reddit_topics 関数のテスト。"""

    def test_正常系_sourcesが生成される(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)

        assert len(result["sources"]) == 1
        assert "reddit.com" in result["sources"][0]["url"]

    def test_正常系_topicsが生成される(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)

        assert len(result["topics"]) == 1
        assert result["topics"][0]["name"] == "Dividend ETFs vs Growth ETFs"

    def test_正常系_session_idが設定される(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)
        assert result["session_id"] == "reddit-topics-20260307"

    def test_正常系_batch_labelがredditに設定される(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)
        assert result["batch_label"] == "reddit"

    def test_正常系_sourceにscoreが含まれる(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)
        assert result["sources"][0]["score"] == 245

    def test_正常系_sourceにsubredditが含まれる(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)
        assert result["sources"][0]["subreddit"] == "r/investing"

    def test_正常系_topicのcategoryがredditに設定される(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)
        assert result["topics"][0]["category"] == "reddit"

    def test_エッジケース_URLなしのtopicではsourceが生成されない(self) -> None:
        batch = {
            "session_id": "test",
            "topics": [
                {
                    "name": "No URL Topic",
                    "url": "",
                    "title": "Test",
                    "subreddit": "r/test",
                }
            ],
        }
        result = map_reddit_topics(batch)
        assert len(result["topics"]) == 1
        assert len(result["sources"]) == 0


# ---------------------------------------------------------------------------
# map_finance_full
# ---------------------------------------------------------------------------


class TestMapFinanceFull:
    """map_finance_full 関数のテスト。"""

    def test_正常系_sourcesが変換される(self) -> None:
        data = _finance_full_data()
        result = map_finance_full(data)

        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com/source1"

    def test_正常系_claimsが変換される(self) -> None:
        data = _finance_full_data()
        result = map_finance_full(data)

        assert len(result["claims"]) == 1
        assert "S&P 500 rose 2%" in result["claims"][0]["content"]

    def test_正常系_session_idが設定される(self) -> None:
        data = _finance_full_data()
        result = map_finance_full(data)
        assert result["session_id"] == "finance-full-20260307"

    def test_正常系_batch_labelがfinance_fullに設定される(self) -> None:
        data = _finance_full_data()
        result = map_finance_full(data)
        assert result["batch_label"] == "finance-full"

    def test_正常系_claimにsource_urlが含まれる(self) -> None:
        data = _finance_full_data()
        result = map_finance_full(data)
        assert result["claims"][0]["source_url"] == "https://example.com/source1"

    def test_正常系_claimにcategoryが含まれる(self) -> None:
        data = _finance_full_data()
        result = map_finance_full(data)
        assert result["claims"][0]["category"] == "stock"

    def test_正常系_source_idが決定論的(self) -> None:
        data = _finance_full_data()
        r1 = map_finance_full(data)
        r2 = map_finance_full(data)
        assert r1["sources"][0]["source_id"] == r2["sources"][0]["source_id"]

    def test_正常系_claim_idが決定論的(self) -> None:
        data = _finance_full_data()
        r1 = map_finance_full(data)
        r2 = map_finance_full(data)
        assert r1["claims"][0]["claim_id"] == r2["claims"][0]["claim_id"]


# ---------------------------------------------------------------------------
# cleanup_old_files
# ---------------------------------------------------------------------------


class TestCleanupOldFiles:
    """cleanup_old_files 関数のテスト。"""

    def test_正常系_7日以上前のファイルを削除(self, tmp_path: Path) -> None:
        # Create an old file (set mtime to 8 days ago)
        old_file = tmp_path / "old-queue.json"
        old_file.write_text("{}", encoding="utf-8")
        old_mtime = time.time() - (8 * 24 * 3600)
        os.utime(old_file, (old_mtime, old_mtime))

        # Create a recent file
        new_file = tmp_path / "new-queue.json"
        new_file.write_text("{}", encoding="utf-8")

        deleted = cleanup_old_files(tmp_path, max_age_days=7)

        assert not old_file.exists()
        assert new_file.exists()
        assert deleted == 1

    def test_正常系_7日未満のファイルは保持(self, tmp_path: Path) -> None:
        recent_file = tmp_path / "recent.json"
        recent_file.write_text("{}", encoding="utf-8")

        deleted = cleanup_old_files(tmp_path, max_age_days=7)

        assert recent_file.exists()
        assert deleted == 0

    def test_エッジケース_存在しないディレクトリで0を返す(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        deleted = cleanup_old_files(nonexistent, max_age_days=7)
        assert deleted == 0

    def test_エッジケース_空ディレクトリで0を返す(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        deleted = cleanup_old_files(empty_dir, max_age_days=7)
        assert deleted == 0


# ---------------------------------------------------------------------------
# run (integration)
# ---------------------------------------------------------------------------


class TestRun:
    """run 関数の統合テスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_finance_news_workflowでキューファイルが生成される(
        self, tmp_path: Path
    ) -> None:
        # Prepare input file
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps(_news_batch(), ensure_ascii=False),
            encoding="utf-8",
        )

        output_dir = tmp_path / "output"

        exit_code = run(
            command="finance-news-workflow",
            input_path=input_file,
            output_base=output_dir,
            cleanup=False,
        )

        assert exit_code == 0
        # Check output file was created
        output_files = list(output_dir.glob("finance-news-workflow/*.json"))
        assert len(output_files) == 1

        # Verify schema
        data = json.loads(output_files[0].read_text(encoding="utf-8"))
        assert data["schema_version"] == "1.0"
        assert data["command_source"] == "finance-news-workflow"
        assert "queue_id" in data
        assert "created_at" in data
        assert "sources" in data

    @freeze_time(FROZEN_TIME)
    def test_正常系_ai_research_collectでキューファイルが生成される(
        self, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps(_ai_research_batch(), ensure_ascii=False),
            encoding="utf-8",
        )

        output_dir = tmp_path / "output"

        exit_code = run(
            command="ai-research-collect",
            input_path=input_file,
            output_base=output_dir,
            cleanup=False,
        )

        assert exit_code == 0
        output_files = list(output_dir.glob("ai-research-collect/*.json"))
        assert len(output_files) == 1

        data = json.loads(output_files[0].read_text(encoding="utf-8"))
        assert data["command_source"] == "ai-research-collect"
        assert len(data["entities"]) >= 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_cleanupオプションで古いファイルが削除される(
        self, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps(_news_batch(), ensure_ascii=False),
            encoding="utf-8",
        )

        output_dir = tmp_path / "output"
        cmd_dir = output_dir / "finance-news-workflow"
        cmd_dir.mkdir(parents=True)

        # Create old file
        old_file = cmd_dir / "old.json"
        old_file.write_text("{}", encoding="utf-8")
        old_mtime = time.time() - (8 * 24 * 3600)
        os.utime(old_file, (old_mtime, old_mtime))

        exit_code = run(
            command="finance-news-workflow",
            input_path=input_file,
            output_base=output_dir,
            cleanup=True,
        )

        assert exit_code == 0
        assert not old_file.exists()

    def test_異常系_存在しない入力ファイルでexit1(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.json"
        output_dir = tmp_path / "output"

        exit_code = run(
            command="finance-news-workflow",
            input_path=nonexistent,
            output_base=output_dir,
            cleanup=False,
        )

        assert exit_code == 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_出力JSONがgraph_queue標準フォーマットに準拠(
        self, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps(_news_batch(), ensure_ascii=False),
            encoding="utf-8",
        )

        output_dir = tmp_path / "output"

        run(
            command="finance-news-workflow",
            input_path=input_file,
            output_base=output_dir,
            cleanup=False,
        )

        output_files = list(output_dir.glob("finance-news-workflow/*.json"))
        data = json.loads(output_files[0].read_text(encoding="utf-8"))

        # Verify all required top-level keys
        required_keys = {
            "schema_version",
            "queue_id",
            "created_at",
            "command_source",
            "session_id",
            "batch_label",
            "sources",
            "topics",
            "claims",
            "entities",
            "relations",
        }
        assert required_keys.issubset(set(data.keys()))

    @freeze_time(FROZEN_TIME)
    def test_正常系_全6コマンドでキューファイルが生成される(
        self, tmp_path: Path
    ) -> None:
        """全コマンドのマッピングが実装されていることを確認。"""
        test_data = {
            "finance-news-workflow": _news_batch(),
            "ai-research-collect": _ai_research_batch(),
            "generate-market-report": _market_report_data(),
            "asset-management": _asset_management_batch(),
            "reddit-finance-topics": _reddit_topics_batch(),
            "finance-full": _finance_full_data(),
        }

        for cmd, data in test_data.items():
            input_file = tmp_path / f"{cmd}-input.json"
            input_file.write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )
            output_dir = tmp_path / f"{cmd}-output"

            exit_code = run(
                command=cmd,
                input_path=input_file,
                output_base=output_dir,
                cleanup=False,
            )

            assert exit_code == 0, f"Command {cmd} failed"
            output_files = list(output_dir.glob(f"{cmd}/*.json"))
            assert len(output_files) == 1, f"Expected 1 output file for {cmd}"


# ---------------------------------------------------------------------------
# main (CLI entry point)
# ---------------------------------------------------------------------------


class TestMain:
    """main 関数のテスト。"""

    def test_異常系_存在しない入力ファイルでSystemExit(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.json"
        exit_code = main(
            ["--command", "finance-news-workflow", "--input", str(nonexistent)]
        )
        assert exit_code == 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_有効な入力ファイルでexit0(self, tmp_path: Path) -> None:
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps(_news_batch(), ensure_ascii=False),
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"
        # main() uses DEFAULT_OUTPUT_BASE, so we use run() to specify output_base
        exit_code = run(
            command="finance-news-workflow",
            input_path=input_file,
            output_base=output_dir,
            cleanup=False,
        )
        assert exit_code == 0

    def test_異常系_不正なJSONファイルでexit1(self, tmp_path: Path) -> None:
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json{{{", encoding="utf-8")
        output_dir = tmp_path / "output"

        exit_code = run(
            command="finance-news-workflow",
            input_path=invalid_file,
            output_base=output_dir,
            cleanup=False,
        )
        assert exit_code == 1


# ---------------------------------------------------------------------------
# THEME_TO_CATEGORY mapping completeness
# ---------------------------------------------------------------------------


class TestThemeToCategoryMapping:
    """THEME_TO_CATEGORY 定数のテスト。"""

    def test_正常系_全テーマキーが定義されている(self) -> None:
        expected_keys = {
            "index",
            "stock",
            "sector",
            "macro_cnbc",
            "macro_other",
            "ai_cnbc",
            "ai_nasdaq",
            "ai_tech",
            "finance_cnbc",
            "finance_nasdaq",
            "finance_other",
        }
        assert expected_keys.issubset(set(THEME_TO_CATEGORY.keys()))

    def test_正常系_全カテゴリが有効な値(self) -> None:
        valid_categories = {"stock", "sector", "macro", "ai", "finance"}
        for category in THEME_TO_CATEGORY.values():
            assert category in valid_categories
