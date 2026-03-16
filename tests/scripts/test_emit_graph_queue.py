"""Tests for scripts/emit_graph_queue.py.

graph-queue 生成スクリプトの単体テスト。
9コマンドのマッピングロジック、ID生成、CLI引数パース、自動クリーンアップを検証。
wealth-scrape のディレクトリ入力（backfill）およびJSON入力（incremental）を含む。
topic-discovery の文字列ベースIDマッピングとno_search条件分岐を含む。
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
    TOPIC_DISCOVERY_CATEGORIES,
    _load_wealth_themes,
    _magnitude_from_score,
    _match_domain_to_theme,
    _parse_yaml_frontmatter,
    _scan_wealth_directory,
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
    map_topic_discovery,
    map_wealth_scrape,
    map_wealth_scrape_backfill,
    map_wealth_scrape_incremental,
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


def _wealth_scrape_backfill_data() -> dict[str, Any]:
    """wealth-scrape backfill 形式のデータを生成（ドメイン記事 + テーマ設定）。"""
    return {
        "session_id": "wealth-scrape-20260307-120000-000000",
        "timestamp": "2026-03-07T12:00:00+00:00",
        "mode": "backfill",
        "themes": {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "keywords_en": [
                    "index fund",
                    "ETF",
                    "passive investing",
                    "invest",
                ],
                "articles": [
                    {
                        "url": "https://ofdollarsanddata.com/why-you-should-invest/",
                        "title": "Why You Should Invest",
                        "summary": "Data-driven analysis of long-term investing benefits.",
                        "feed_source": "Of Dollars and Data",
                        "published": "2026-03-05T10:00:00+00:00",
                        "source_key": "ofdollarsanddata",
                        "domain": "ofdollarsanddata.com",
                    }
                ],
                "keywords_used": ["data-driven", "investing", "portfolio"],
            },
            "personal_finance": {
                "name_en": "Personal Finance",
                "keywords_en": [
                    "budgeting",
                    "save money",
                    "personal finance",
                ],
                "articles": [
                    {
                        "url": "https://moneycrashers.com/save-money-tips/",
                        "title": "50 Ways to Save Money",
                        "summary": "Practical tips for reducing expenses.",
                        "feed_source": "Money Crashers",
                        "published": "2026-03-04T08:00:00+00:00",
                        "source_key": "moneycrashers",
                        "domain": "moneycrashers.com",
                    }
                ],
                "keywords_used": ["savings", "budgeting", "personal finance"],
            },
        },
        "stats": {
            "total": 150,
            "filtered": 80,
            "matched": 25,
            "scraped": 20,
            "skipped": 5,
        },
    }


def _wealth_scrape_incremental_data() -> dict[str, Any]:
    """wealth-scrape incremental 形式（WealthScrapeSession）のデータを生成。"""
    return {
        "session_id": "wealth-scrape-20260307-120000-000000",
        "timestamp": "2026-03-07T12:00:00+00:00",
        "mode": "incremental",
        "themes": {
            "fire_wealth_building": {
                "name_en": "FIRE & Wealth Building",
                "keywords_en": [
                    "FIRE",
                    "financial independence",
                    "early retirement",
                    "wealth building",
                ],
                "articles": [
                    {
                        "url": "https://affordanything.com/financial-independence/",
                        "title": "The Path to Financial Independence",
                        "summary": "A comprehensive guide to achieving FIRE.",
                        "feed_source": "Afford Anything",
                        "published": "2026-03-07T07:00:00+00:00",
                        "source_key": "affordanything",
                        "domain": "affordanything.com",
                    }
                ],
                "keywords_used": ["FIRE", "financial independence", "wealth building"],
            },
        },
        "stats": {
            "total": 45,
            "filtered": 30,
            "matched": 10,
            "scraped": 0,
            "skipped": 0,
        },
    }


def _topic_discovery_data() -> dict[str, Any]:
    """topic-discovery（topic-suggestions セッション）形式のデータを生成。"""
    return {
        "session_id": "topic-suggestion-2026-03-07T1200",
        "generated_at": "2026-03-07T12:00:00+09:00",
        "parameters": {
            "category": None,
            "count": 5,
            "no_search": False,
        },
        "search_insights": {
            "queries_executed": 10,
            "trends": [
                {
                    "query": "S&P 500 weekly performance March 2026",
                    "source": "tavily",
                    "key_findings": [
                        "S&P 500 gained 1.5% on strong earnings",
                        "Tech sector led gains with AI stocks",
                    ],
                }
            ],
        },
        "content_gaps": {
            "category_distribution": {
                "market_report": 3,
                "stock_analysis": 2,
                "quant_analysis": 0,
            },
            "underserved_categories": ["quant_analysis", "asset_management"],
            "gap_topics": ["クオンツ分析の入門記事が不足"],
        },
        "suggestions": [
            {
                "rank": 1,
                "topic": "S&P 500 週次レビュー：AI銘柄が牽引する上昇相場",
                "category": "market_report",
                "suggested_symbols": ["^GSPC", "NVDA"],
                "suggested_period": "2026-03-03 to 2026-03-07",
                "scores": {
                    "timeliness": 9,
                    "information_availability": 8,
                    "reader_interest": 8,
                    "feasibility": 9,
                    "uniqueness": 7,
                    "total": 41,
                },
                "rationale": "AI銘柄の好決算でS&P 500が週間で上昇。タイムリーなレビュー記事。",
                "key_points": [
                    "NVIDIA好決算の影響",
                    "セクターローテーションの兆候",
                ],
                "target_audience": "intermediate",
                "estimated_word_count": 4000,
                "selected": None,
            }
        ],
        "category_balance": {"market_report": 3, "stock_analysis": 2},
        "recommendation": "quant_analysis カテゴリの記事を優先的に執筆すべき",
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

    def test_正常系_全コマンドが指定できる(self) -> None:
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

    def test_正常系_32文字のhex文字列を返す(self) -> None:
        result = generate_claim_id("test content")
        assert len(result) == 32
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
        # format: gq-{timestamp}-{rand8}
        parts = result.split("-")
        assert len(parts) == 3
        # timestamp part should be numeric
        assert parts[1].isdigit()

    @freeze_time(FROZEN_TIME)
    def test_正常系_rand8は8文字hex(self) -> None:
        result = generate_queue_id()
        parts = result.split("-")
        rand_part = parts[2]
        assert len(rand_part) == 8
        int(rand_part, 16)

    @freeze_time(FROZEN_TIME)
    def test_正常系_同一時刻でも異なるIDを生成(self) -> None:
        id1 = generate_queue_id()
        id2 = generate_queue_id()
        assert id1 != id2


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

    def test_正常系_groups形式でトピックが正しく抽出される(self) -> None:
        """groups ネスト形式のデータで topics が正しく生成されること。"""
        batch: dict[str, Any] = {
            "session_id": "reddit-topics-groups-20260307",
            "groups": {
                "investing": {
                    "topics": [
                        {
                            "name": "Dividend ETFs vs Growth ETFs",
                            "url": "https://reddit.com/r/investing/comments/abc123",
                            "title": "Dividend ETFs vs Growth ETFs debate",
                            "summary": "Community discusses merits of dividend vs growth.",
                            "subreddit": "r/investing",
                            "created_at": "2026-03-06T18:00:00+00:00",
                            "score": 245,
                        }
                    ],
                },
                "personalfinance": {
                    "topics": [
                        {
                            "name": "Emergency Fund Strategy",
                            "url": "https://reddit.com/r/personalfinance/comments/def456",
                            "title": "Best emergency fund strategy in 2026",
                            "summary": "Discussion on optimal emergency fund sizes.",
                            "subreddit": "r/personalfinance",
                            "created_at": "2026-03-06T20:00:00+00:00",
                            "score": 180,
                        }
                    ],
                },
            },
        }
        result = map_reddit_topics(batch)

        # 2グループからそれぞれ1トピックずつ、計2トピック
        assert len(result["topics"]) == 2
        topic_names = {t["name"] for t in result["topics"]}
        assert topic_names == {
            "Dividend ETFs vs Growth ETFs",
            "Emergency Fund Strategy",
        }

        # URLありの全トピックからsourceが生成される
        assert len(result["sources"]) == 2
        source_urls = {s["url"] for s in result["sources"]}
        assert "https://reddit.com/r/investing/comments/abc123" in source_urls
        assert "https://reddit.com/r/personalfinance/comments/def456" in source_urls

        # sourceにsubredditとscoreが含まれる
        for source in result["sources"]:
            assert "subreddit" in source
            assert "score" in source

        # 全topicのcategoryがredditに設定される
        for topic in result["topics"]:
            assert topic["category"] == "reddit"

        # session_idが保持される
        assert result["session_id"] == "reddit-topics-groups-20260307"
        assert result["batch_label"] == "reddit"

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
        assert data["schema_version"] == "2.0"
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
            "facts",
            "entities",
            "chunks",
            "financial_datapoints",
            "fiscal_periods",
            "relations",
        }
        assert required_keys.issubset(set(data.keys()))

    @freeze_time(FROZEN_TIME)
    def test_正常系_全コマンドでキューファイルが生成される(
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
            "wealth-scrape": _wealth_scrape_incremental_data(),
            "topic-discovery": _topic_discovery_data(),
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


# ---------------------------------------------------------------------------
# _parse_yaml_frontmatter
# ---------------------------------------------------------------------------


class TestParseYamlFrontmatter:
    """_parse_yaml_frontmatter 関数のテスト。"""

    def test_正常系_全フィールドを取得できる(self, tmp_path: Path) -> None:
        md_file = tmp_path / "article.md"
        md_file.write_text(
            "---\n"
            "url: 'https://example.com/article/1'\n"
            "title: 'S&P 500 hits record high'\n"
            "date: '2026-03-07'\n"
            "author: 'John Doe'\n"
            "domain: 'example.com'\n"
            "---\n"
            "\n"
            "# Article body here\n",
            encoding="utf-8",
        )
        result = _parse_yaml_frontmatter(md_file)
        assert result is not None
        assert result["url"] == "https://example.com/article/1"
        assert result["title"] == "S&P 500 hits record high"
        assert result["date"] == "2026-03-07"
        assert result["author"] == "John Doe"
        assert result["domain"] == "example.com"

    def test_正常系_引用符なしの値もパースできる(self, tmp_path: Path) -> None:
        md_file = tmp_path / "article.md"
        md_file.write_text(
            "---\n"
            "url: https://example.com/article/2\n"
            "title: Market Update\n"
            "date: 2026-03-07\n"
            "author: Jane\n"
            "domain: example.com\n"
            "---\n"
            "\n"
            "Body text.\n",
            encoding="utf-8",
        )
        result = _parse_yaml_frontmatter(md_file)
        assert result is not None
        assert result["url"] == "https://example.com/article/2"
        assert result["title"] == "Market Update"
        assert result["author"] == "Jane"

    def test_エッジケース_空フィールドを空文字として返す(self, tmp_path: Path) -> None:
        md_file = tmp_path / "article.md"
        md_file.write_text(
            "---\n"
            "url: 'https://example.com/article/3'\n"
            "title: 'Test Article'\n"
            "date: '2026-03-07'\n"
            "author: ''\n"
            "domain: 'example.com'\n"
            "---\n"
            "\n"
            "Body.\n",
            encoding="utf-8",
        )
        result = _parse_yaml_frontmatter(md_file)
        assert result is not None
        assert result["author"] == ""

    def test_異常系_frontmatter区切りなしでNoneを返す(self, tmp_path: Path) -> None:
        md_file = tmp_path / "no-frontmatter.md"
        md_file.write_text(
            "# Just a heading\n\nSome content without frontmatter.\n",
            encoding="utf-8",
        )
        result = _parse_yaml_frontmatter(md_file)
        assert result is None

    def test_異常系_存在しないファイルでNoneを返す(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.md"
        result = _parse_yaml_frontmatter(nonexistent)
        assert result is None

    def test_正常系_値なしのフィールドを空文字として返す(self, tmp_path: Path) -> None:
        md_file = tmp_path / "article.md"
        md_file.write_text(
            "---\n"
            "url: 'https://example.com/article/4'\n"
            "title: 'Test'\n"
            "date: '2026-03-07'\n"
            "author:\n"
            "domain: 'example.com'\n"
            "---\n"
            "\n"
            "Body.\n",
            encoding="utf-8",
        )
        result = _parse_yaml_frontmatter(md_file)
        assert result is not None
        assert result["author"] == ""


# ---------------------------------------------------------------------------
# Helpers: wealth directory structure
# ---------------------------------------------------------------------------


def _create_wealth_md(
    dir_path: Path,
    *,
    url: str = "https://example.com/article",
    title: str = "Test Article",
    published: str = "2026-03-07",
    source: str = "Example",
    domain: str = "example.com",
    body: str = "Article body text here.",
) -> Path:
    """Create a Markdown file with frontmatter in the given directory."""
    stripped = url.rstrip("/")
    slug = stripped.rsplit("/", maxsplit=1)[-1] or "article"
    md_file = dir_path / f"{slug}.md"
    md_file.write_text(
        f"---\n"
        f"url: '{url}'\n"
        f"title: '{title}'\n"
        f"published: '{published}'\n"
        f"source: '{source}'\n"
        f"domain: '{domain}'\n"
        f"---\n"
        f"\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return md_file


def _create_wealth_theme_config(tmp_path: Path) -> Path:
    """Create a minimal wealth-management-themes.json config file."""
    config_path = tmp_path / "wealth-management-themes.json"
    config_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "themes": {
                    "data_driven_investing": {
                        "name_en": "Data-Driven Investing",
                        "keywords_en": ["index fund", "ETF", "passive investing"],
                        "target_sources": ["ofdollarsanddata", "monevator"],
                    },
                    "personal_finance": {
                        "name_en": "Personal Finance",
                        "keywords_en": ["budgeting", "saving", "personal finance"],
                        "target_sources": ["moneycrashers", "kiplinger"],
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return config_path


def _create_wealth_directory(tmp_path: Path) -> Path:
    """Create a wealth-scrape directory with two domains and sample articles."""
    wealth_dir = tmp_path / "wealth"
    wealth_dir.mkdir()

    # Domain 1: ofdollarsanddata.com (matches data_driven_investing theme)
    domain1 = wealth_dir / "ofdollarsanddata.com"
    domain1.mkdir()
    _create_wealth_md(
        domain1,
        url="https://ofdollarsanddata.com/why-you-should-invest/",
        title="Why You Should Invest",
        published="2026-03-05T10:00:00+00:00",
        source="Of Dollars and Data",
        domain="ofdollarsanddata.com",
        body="Data-driven analysis of long-term investing benefits.",
    )
    _create_wealth_md(
        domain1,
        url="https://ofdollarsanddata.com/saving-vs-investing/",
        title="Saving vs Investing",
        published="2026-03-04T08:00:00+00:00",
        source="Of Dollars and Data",
        domain="ofdollarsanddata.com",
        body="Comparing savings accounts and investment returns.",
    )

    # Domain 2: moneycrashers.com (matches personal_finance theme)
    domain2 = wealth_dir / "moneycrashers.com"
    domain2.mkdir()
    _create_wealth_md(
        domain2,
        url="https://moneycrashers.com/save-money-tips/",
        title="50 Ways to Save Money",
        published="2026-03-04T08:00:00+00:00",
        source="Money Crashers",
        domain="moneycrashers.com",
        body="Practical tips for reducing expenses and building savings.",
    )

    return wealth_dir


# ---------------------------------------------------------------------------
# _load_wealth_themes
# ---------------------------------------------------------------------------


class TestLoadWealthThemes:
    """_load_wealth_themes 関数のテスト。"""

    def test_正常系_テーマ設定を読み込める(self, tmp_path: Path) -> None:
        config_path = _create_wealth_theme_config(tmp_path)
        themes = _load_wealth_themes(config_path)
        assert "data_driven_investing" in themes
        assert "personal_finance" in themes
        assert themes["data_driven_investing"]["name_en"] == "Data-Driven Investing"

    def test_異常系_存在しないファイルで空辞書(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent.json"
        themes = _load_wealth_themes(nonexistent)
        assert themes == {}

    def test_異常系_不正なJSONで空辞書(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not json", encoding="utf-8")
        themes = _load_wealth_themes(bad_file)
        assert themes == {}


# ---------------------------------------------------------------------------
# _match_domain_to_theme
# ---------------------------------------------------------------------------


class TestMatchDomainToTheme:
    """_match_domain_to_theme 関数のテスト。"""

    def test_正常系_ドメインがテーマにマッチする(self) -> None:
        themes = {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "target_sources": ["ofdollarsanddata", "monevator"],
            },
        }
        result = _match_domain_to_theme("ofdollarsanddata.com", themes)
        assert result is not None
        assert result == ("data_driven_investing", "Data-Driven Investing")

    def test_正常系_マッチしないドメインでNone(self) -> None:
        themes = {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "target_sources": ["ofdollarsanddata"],
            },
        }
        result = _match_domain_to_theme("unknowndomain.com", themes)
        assert result is None

    def test_エッジケース_空テーマでNone(self) -> None:
        result = _match_domain_to_theme("example.com", {})
        assert result is None


# ---------------------------------------------------------------------------
# _scan_wealth_directory
# ---------------------------------------------------------------------------


class TestScanWealthDirectory:
    """_scan_wealth_directory 関数のテスト。"""

    def test_正常系_ドメインごとにmapped_dictが返される(self, tmp_path: Path) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)

        results = _scan_wealth_directory(wealth_dir, theme_config_path=config_path)

        assert isinstance(results, list)
        assert len(results) == 2  # 2 domains

    def test_正常系_sourcesが各ドメインの記事を含む(self, tmp_path: Path) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)

        results = _scan_wealth_directory(wealth_dir, theme_config_path=config_path)

        # Find moneycrashers result (1 article)
        mc_result = [r for r in results if "moneycrashers" in r["batch_label"]]
        assert len(mc_result) == 1
        assert len(mc_result[0]["sources"]) == 1
        assert mc_result[0]["sources"][0]["url"] == (
            "https://moneycrashers.com/save-money-tips/"
        )

        # Find ofdollarsanddata result (2 articles)
        od_result = [r for r in results if "ofdollarsanddata" in r["batch_label"]]
        assert len(od_result) == 1
        assert len(od_result[0]["sources"]) == 2

    def test_正常系_topicsがテーママッチングで生成される(self, tmp_path: Path) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)

        results = _scan_wealth_directory(wealth_dir, theme_config_path=config_path)

        # ofdollarsanddata matches data_driven_investing
        od_result = [r for r in results if "ofdollarsanddata" in r["batch_label"]]
        assert len(od_result[0]["topics"]) == 1
        assert od_result[0]["topics"][0]["name"] == "Data-Driven Investing"
        assert od_result[0]["topics"][0]["category"] == "wealth"

    def test_正常系_chunksが本文テキストを含む(self, tmp_path: Path) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)

        results = _scan_wealth_directory(wealth_dir, theme_config_path=config_path)

        mc_result = [r for r in results if "moneycrashers" in r["batch_label"]]
        assert len(mc_result[0]["chunks"]) == 1
        assert "Practical tips" in mc_result[0]["chunks"][0]["content"]

    def test_正常系_session_idがドメイン名を含む(self, tmp_path: Path) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)

        results = _scan_wealth_directory(wealth_dir, theme_config_path=config_path)

        od_result = [r for r in results if "ofdollarsanddata" in r["batch_label"]]
        assert od_result[0]["session_id"] == "wealth-backfill-ofdollarsanddata.com"

    def test_異常系_存在しないディレクトリで空リスト(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "nonexistent"
        results = _scan_wealth_directory(nonexistent)
        assert results == []

    def test_エッジケース_空ディレクトリで空リスト(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        results = _scan_wealth_directory(empty_dir)
        assert results == []

    def test_エッジケース_frontmatterなしのファイルはスキップ(
        self, tmp_path: Path
    ) -> None:
        wealth_dir = tmp_path / "wealth"
        wealth_dir.mkdir()
        domain_dir = wealth_dir / "example.com"
        domain_dir.mkdir()

        # File without frontmatter
        no_fm = domain_dir / "no-frontmatter.md"
        no_fm.write_text("# Just a heading\nNo frontmatter here.\n", encoding="utf-8")

        results = _scan_wealth_directory(wealth_dir)
        assert results == []

    def test_エッジケース_URLなしのfrontmatterはスキップ(self, tmp_path: Path) -> None:
        wealth_dir = tmp_path / "wealth"
        wealth_dir.mkdir()
        domain_dir = wealth_dir / "example.com"
        domain_dir.mkdir()

        md_file = domain_dir / "no-url.md"
        md_file.write_text(
            "---\ntitle: 'No URL'\ndate: '2026-03-07'\n---\n\nBody.\n",
            encoding="utf-8",
        )

        results = _scan_wealth_directory(wealth_dir)
        assert results == []


# ---------------------------------------------------------------------------
# map_wealth_scrape
# ---------------------------------------------------------------------------


class TestMapWealthScrape:
    """map_wealth_scrape ディスパッチャー関数のテスト。"""

    def test_正常系_backfillモードでbackfill関数にディスパッチ(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape(data)
        # backfill produces entities (domain entities)
        assert len(result["entities"]) > 0

    def test_正常系_incrementalモードでincremental関数にディスパッチ(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape(data)
        # incremental produces claims
        assert len(result["claims"]) > 0

    def test_正常系_modeなしでincrementalにフォールバック(self) -> None:
        data = {
            "session_id": "test",
            "themes": {
                "test_theme": {
                    "name_en": "Test Theme",
                    "keywords_en": ["test"],
                    "articles": [
                        {
                            "url": "https://example.com/article",
                            "title": "Test Article about test topic",
                            "summary": "A test summary.",
                            "published": "2026-03-07T12:00:00+00:00",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape(data)
        # incremental mode produces claims
        assert len(result["claims"]) > 0

    def test_正常系_sourcesが生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape(data)

        assert len(result["sources"]) == 2
        urls = {s["url"] for s in result["sources"]}
        assert "https://ofdollarsanddata.com/why-you-should-invest/" in urls
        assert "https://moneycrashers.com/save-money-tips/" in urls

    def test_正常系_topicsが生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape(data)

        assert len(result["topics"]) == 2
        topic_names = {t["name"] for t in result["topics"]}
        assert "Data-Driven Investing" in topic_names
        assert "Personal Finance" in topic_names

    def test_正常系_session_idが設定される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape(data)
        assert result["session_id"] == "wealth-scrape-20260307-120000-000000"

    def test_正常系_batch_labelがwealth_scrapeに設定される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape(data)
        assert result["batch_label"] == "wealth-scrape"

    def test_正常系_incremental形式もマッピングできる(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape(data)

        assert len(result["sources"]) == 1
        assert len(result["topics"]) == 1
        assert result["topics"][0]["name"] == "FIRE & Wealth Building"

    def test_正常系_topic_idが決定論的(self) -> None:
        data = _wealth_scrape_backfill_data()
        r1 = map_wealth_scrape(data)
        r2 = map_wealth_scrape(data)
        assert r1["topics"][0]["topic_id"] == r2["topics"][0]["topic_id"]

    def test_エッジケース_URLなしのarticleではsourceが生成されない(self) -> None:
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "test_theme": {
                    "name_en": "Test Theme",
                    "keywords_en": ["test"],
                    "articles": [{"url": "", "title": "No URL article"}],
                }
            },
        }
        result = map_wealth_scrape(data)
        assert len(result["sources"]) == 0
        assert len(result["topics"]) == 1

    def test_エッジケース_空テーマで空結果(self) -> None:
        data = {"session_id": "test", "mode": "backfill", "themes": {}}
        result = map_wealth_scrape(data)
        assert len(result["sources"]) == 0
        assert len(result["topics"]) == 0


# ---------------------------------------------------------------------------
# map_wealth_scrape_backfill
# ---------------------------------------------------------------------------


class TestMapWealthScrapeBackfill:
    """map_wealth_scrape_backfill 関数のテスト。"""

    def test_正常系_sourceにsource_type_blogが設定される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for source in result["sources"]:
            assert source["source_type"] == "blog"

    def test_正常系_sourceにdomainが設定される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        domains = {s["domain"] for s in result["sources"]}
        assert "ofdollarsanddata.com" in domains
        assert "moneycrashers.com" in domains

    def test_正常系_source_idがgenerate_source_idで生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for source in result["sources"]:
            assert source["source_id"] == generate_source_id(source["url"])

    def test_正常系_topicのcategoryがwealth_managementに設定される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for topic in result["topics"]:
            assert topic["category"] == "wealth-management"

    def test_正常系_topic_idがgenerate_topic_idで生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for topic in result["topics"]:
            expected_id = generate_topic_id(topic["name"], "wealth-management")
            assert topic["topic_id"] == expected_id

    def test_正常系_domain_entityが生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        assert len(result["entities"]) == 2
        for entity in result["entities"]:
            assert entity["entity_type"] == "domain"

    def test_正常系_domain_entity_idがgenerate_entity_idで生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for entity in result["entities"]:
            expected_id = generate_entity_id(entity["name"], "domain")
            assert entity["entity_id"] == expected_id

    def test_正常系_キーワードマッチでtaggedリレーション生成(self) -> None:
        """タイトルにテーマキーワードが含まれる場合、taggedリレーションが生成される。"""
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "data_driven_investing": {
                    "name_en": "Data-Driven Investing",
                    "keywords_en": ["index fund", "ETF", "passive investing"],
                    "articles": [
                        {
                            "url": "https://example.com/etf-guide",
                            "title": "The Ultimate ETF Guide for Beginners",
                            "published": "2026-03-07T12:00:00+00:00",
                            "domain": "example.com",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape_backfill(data)
        tagged = result["relations"].get("tagged", [])
        assert len(tagged) == 1
        source_id = generate_source_id("https://example.com/etf-guide")
        topic_id = generate_topic_id("Data-Driven Investing", "wealth-management")
        assert tagged[0]["from_id"] == source_id
        assert tagged[0]["to_id"] == topic_id

    def test_正常系_キーワード大文字小文字区別なしでマッチ(self) -> None:
        """title.lower()とkeyword.lower()で比較されるため大文字小文字は区別しない。"""
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "dividend_income": {
                    "name_en": "Dividend Income",
                    "keywords_en": ["DIVIDEND"],
                    "articles": [
                        {
                            "url": "https://example.com/dividend",
                            "title": "Best dividend Stocks for 2026",
                            "published": "2026-03-07T12:00:00+00:00",
                            "domain": "example.com",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape_backfill(data)
        tagged = result["relations"].get("tagged", [])
        assert len(tagged) == 1

    def test_正常系_キーワードマッチなしでtaggedリレーションなし(self) -> None:
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "data_driven_investing": {
                    "name_en": "Data-Driven Investing",
                    "keywords_en": ["index fund", "ETF"],
                    "articles": [
                        {
                            "url": "https://example.com/unrelated",
                            "title": "Cooking Recipes for Beginners",
                            "published": "2026-03-07T12:00:00+00:00",
                            "domain": "example.com",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape_backfill(data)
        tagged = result["relations"].get("tagged", [])
        assert len(tagged) == 0

    def test_正常系_複数テーマのキーワードマッチで複数tagged生成(self) -> None:
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "data_driven_investing": {
                    "name_en": "Data-Driven Investing",
                    "keywords_en": ["ETF"],
                    "articles": [
                        {
                            "url": "https://example.com/etf",
                            "title": "ETF Investment Guide",
                            "published": "2026-03-07T12:00:00+00:00",
                            "domain": "example.com",
                        }
                    ],
                },
                "dividend_income": {
                    "name_en": "Dividend Income",
                    "keywords_en": ["dividend"],
                    "articles": [
                        {
                            "url": "https://example.com/dividend",
                            "title": "Top Dividend Stocks",
                            "published": "2026-03-07T12:00:00+00:00",
                            "domain": "example.com",
                        }
                    ],
                },
            },
        }
        result = map_wealth_scrape_backfill(data)
        tagged = result["relations"].get("tagged", [])
        assert len(tagged) == 2

    def test_正常系_batch_labelがwealth_scrapeに設定される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        assert result["batch_label"] == "wealth-scrape"

    def test_正常系_claimsは空(self) -> None:
        """backfill ではclaimsは生成しない。"""
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        assert len(result["claims"]) == 0

    def test_エッジケース_keywords_enが未設定でもtaggedは空(self) -> None:
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "test_theme": {
                    "name_en": "Test Theme",
                    "articles": [
                        {
                            "url": "https://example.com/article",
                            "title": "Some article",
                            "domain": "example.com",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape_backfill(data)
        tagged = result["relations"].get("tagged", [])
        assert len(tagged) == 0

    def test_エッジケース_domain重複でentity重複なし(self) -> None:
        """同じドメインの複数記事でも Entity は1つだけ生成される。"""
        data = {
            "session_id": "test",
            "mode": "backfill",
            "themes": {
                "test_theme": {
                    "name_en": "Test Theme",
                    "keywords_en": [],
                    "articles": [
                        {
                            "url": "https://example.com/a1",
                            "title": "Article 1",
                            "domain": "example.com",
                        },
                        {
                            "url": "https://example.com/a2",
                            "title": "Article 2",
                            "domain": "example.com",
                        },
                    ],
                }
            },
        }
        result = map_wealth_scrape_backfill(data)
        assert len(result["entities"]) == 1


# ---------------------------------------------------------------------------
# map_wealth_scrape_incremental
# ---------------------------------------------------------------------------


class TestMapWealthScrapeIncremental:
    """map_wealth_scrape_incremental 関数のテスト。"""

    def test_正常系_sourcesが生成される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        assert len(result["sources"]) == 1
        assert (
            result["sources"][0]["url"]
            == "https://affordanything.com/financial-independence/"
        )

    def test_正常系_topicsが生成される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        assert len(result["topics"]) == 1
        assert result["topics"][0]["name"] == "FIRE & Wealth Building"

    def test_正常系_topicのcategoryがwealth_managementに設定される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        for topic in result["topics"]:
            assert topic["category"] == "wealth-management"

    def test_正常系_claimsが生成される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        assert len(result["claims"]) == 1
        assert result["claims"][0]["content"] == (
            "A comprehensive guide to achieving FIRE."
        )

    def test_正常系_claim_idがgenerate_claim_idで生成される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        for claim in result["claims"]:
            assert claim["claim_id"] == generate_claim_id(claim["content"])

    def test_正常系_source_claimリレーションが生成される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        source_claims = result["relations"].get("source_claim", [])
        assert len(source_claims) == 1
        source_id = generate_source_id(
            "https://affordanything.com/financial-independence/"
        )
        assert source_claims[0]["from_id"] == source_id

    def test_正常系_taggedリレーションが生成される(self) -> None:
        """incremental ではキーワードマッチによる tagged リレーションが生成される。"""
        data = {
            "session_id": "test",
            "mode": "incremental",
            "themes": {
                "fire_wealth_building": {
                    "name_en": "FIRE & Wealth Building",
                    "keywords_en": ["FIRE", "financial independence"],
                    "articles": [
                        {
                            "url": "https://example.com/fire-guide",
                            "title": "Your Path to Financial Independence and FIRE",
                            "summary": "Guide to FIRE.",
                            "published": "2026-03-07T12:00:00+00:00",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape_incremental(data)
        tagged = result["relations"].get("tagged", [])
        assert len(tagged) >= 1

    def test_正常系_entitiesは空(self) -> None:
        """incremental ではドメインentitiesは生成しない。"""
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        assert len(result["entities"]) == 0

    def test_正常系_batch_labelがwealth_scrapeに設定される(self) -> None:
        data = _wealth_scrape_incremental_data()
        result = map_wealth_scrape_incremental(data)
        assert result["batch_label"] == "wealth-scrape"

    def test_正常系_summaryなしの記事ではclaimが生成されない(self) -> None:
        data = {
            "session_id": "test",
            "mode": "incremental",
            "themes": {
                "test_theme": {
                    "name_en": "Test Theme",
                    "keywords_en": [],
                    "articles": [
                        {
                            "url": "https://example.com/article",
                            "title": "Article without summary",
                            "summary": "",
                            "published": "2026-03-07T12:00:00+00:00",
                        }
                    ],
                }
            },
        }
        result = map_wealth_scrape_incremental(data)
        assert len(result["claims"]) == 0
        assert len(result["relations"].get("source_claim", [])) == 0

    def test_エッジケース_空テーマで空結果(self) -> None:
        data = {"session_id": "test", "mode": "incremental", "themes": {}}
        result = map_wealth_scrape_incremental(data)
        assert len(result["sources"]) == 0
        assert len(result["topics"]) == 0
        assert len(result["claims"]) == 0


# ---------------------------------------------------------------------------
# run(): wealth-scrape ディレクトリ入力
# ---------------------------------------------------------------------------


class TestRunWealthScrapeDirectory:
    """run() のディレクトリ入力テスト（wealth-scrape backfill）。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_ディレクトリ入力で複数キューファイルが生成される(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)
        output_dir = tmp_path / "output"

        import emit_graph_queue

        monkeypatch.setattr(emit_graph_queue, "WEALTH_THEME_CONFIG_PATH", config_path)

        exit_code = run(
            command="wealth-scrape",
            input_path=wealth_dir,
            output_base=output_dir,
            cleanup=False,
        )

        assert exit_code == 0
        output_files = list(output_dir.glob("wealth-scrape/*.json"))
        assert len(output_files) == 2  # 2 domains

    @freeze_time(FROZEN_TIME)
    def test_正常系_各キューファイルがgraph_queue標準フォーマットに準拠(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)
        output_dir = tmp_path / "output"

        import emit_graph_queue

        monkeypatch.setattr(emit_graph_queue, "WEALTH_THEME_CONFIG_PATH", config_path)

        run(
            command="wealth-scrape",
            input_path=wealth_dir,
            output_base=output_dir,
            cleanup=False,
        )

        output_files = list(output_dir.glob("wealth-scrape/*.json"))
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
            "facts",
            "entities",
            "chunks",
            "financial_datapoints",
            "fiscal_periods",
            "relations",
        }
        for f in output_files:
            data = json.loads(f.read_text(encoding="utf-8"))
            assert required_keys.issubset(set(data.keys()))
            assert data["command_source"] == "wealth-scrape"

    @freeze_time(FROZEN_TIME)
    def test_正常系_JSON入力でも通常通り動作する(self, tmp_path: Path) -> None:
        """wealth-scrape コマンドでJSON入力（incremental mode）が動作することを確認。"""
        input_file = tmp_path / "input.json"
        input_file.write_text(
            json.dumps(_wealth_scrape_backfill_data(), ensure_ascii=False),
            encoding="utf-8",
        )
        output_dir = tmp_path / "output"

        exit_code = run(
            command="wealth-scrape",
            input_path=input_file,
            output_base=output_dir,
            cleanup=False,
        )

        assert exit_code == 0
        output_files = list(output_dir.glob("wealth-scrape/*.json"))
        assert len(output_files) == 1

    def test_異常系_空ディレクトリでexit1(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        output_dir = tmp_path / "output"

        exit_code = run(
            command="wealth-scrape",
            input_path=empty_dir,
            output_base=output_dir,
            cleanup=False,
        )

        assert exit_code == 1


# ---------------------------------------------------------------------------
# COMMANDS list: wealth-scrape が含まれることを確認
# ---------------------------------------------------------------------------


class TestWealthScrapeInCommands:
    """wealth-scrape が COMMANDS リストに含まれることを確認。"""

    def test_正常系_wealth_scrapeがCOMMANDSに含まれる(self) -> None:
        assert "wealth-scrape" in COMMANDS


# ---------------------------------------------------------------------------
# topic-discovery: _magnitude_from_score
# ---------------------------------------------------------------------------


class TestMagnitudeFromScore:
    """_magnitude_from_score ヘルパーのテスト。"""

    def test_正常系_40以上でstrong(self) -> None:
        assert _magnitude_from_score(40) == "strong"
        assert _magnitude_from_score(50) == "strong"

    def test_正常系_30以上40未満でmoderate(self) -> None:
        assert _magnitude_from_score(30) == "moderate"
        assert _magnitude_from_score(39) == "moderate"

    def test_正常系_30未満でslight(self) -> None:
        assert _magnitude_from_score(29) == "slight"
        assert _magnitude_from_score(0) == "slight"


# ---------------------------------------------------------------------------
# topic-discovery: TOPIC_DISCOVERY_CATEGORIES
# ---------------------------------------------------------------------------


class TestTopicDiscoveryCategories:
    """TOPIC_DISCOVERY_CATEGORIES 定数のテスト。"""

    def test_正常系_7カテゴリが定義されている(self) -> None:
        assert len(TOPIC_DISCOVERY_CATEGORIES) == 7

    def test_正常系_全キーが期待通り(self) -> None:
        expected_keys = {
            "market_report",
            "stock_analysis",
            "macro_economy",
            "asset_management",
            "side_business",
            "quant_analysis",
            "investment_education",
        }
        assert set(TOPIC_DISCOVERY_CATEGORIES.keys()) == expected_keys


# ---------------------------------------------------------------------------
# topic-discovery: map_topic_discovery
# ---------------------------------------------------------------------------


def _topic_discovery_mapper_data(
    *,
    no_search: bool = False,
    suggestions: list[dict[str, Any]] | None = None,
    search_insights: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build configurable topic-discovery input data for mapper tests."""
    if suggestions is None:
        suggestions = [
            {
                "rank": 1,
                "topic": "S&P500 週間レビュー",
                "category": "market_report",
                "suggested_symbols": ["^GSPC", "^DJI"],
                "suggested_period": "2026-03-10 to 2026-03-14",
                "scores": {
                    "timeliness": 9,
                    "information_availability": 8,
                    "reader_interest": 8,
                    "feasibility": 9,
                    "uniqueness": 7,
                    "total": 41,
                },
                "rationale": "市場の動向が注目されている",
                "key_points": ["ポイント1", "ポイント2"],
                "target_audience": "intermediate",
                "estimated_word_count": 4000,
                "selected": None,
            },
            {
                "rank": 2,
                "topic": "日銀金利政策の行方",
                "category": "macro_economy",
                "suggested_symbols": ["^N225"],
                "suggested_period": "2026-03-01 to 2026-03-14",
                "scores": {
                    "timeliness": 8,
                    "information_availability": 7,
                    "reader_interest": 7,
                    "feasibility": 6,
                    "uniqueness": 5,
                    "total": 33,
                },
                "rationale": "金融政策への関心が高まっている",
                "key_points": ["金利動向"],
                "target_audience": "beginner",
                "estimated_word_count": 3000,
                "selected": None,
            },
        ]
    if search_insights is None and not no_search:
        search_insights = {
            "queries_executed": 10,
            "trends": [
                {
                    "query": "S&P 500 weekly performance",
                    "source": "tavily",
                    "key_findings": ["S&P500が2%上昇", "テック株が牽引"],
                },
                {
                    "query": "日銀 金利 最新",
                    "source": "gemini",
                    "key_findings": ["日銀が利上げを見送り"],
                },
            ],
        }
    return {
        "session_id": "topic-suggestion-2026-03-16T1430",
        "generated_at": "2026-03-16T14:30:00+09:00",
        "parameters": {"category": None, "count": 5, "no_search": no_search},
        "search_insights": search_insights,
        "suggestions": suggestions,
        "recommendation": "マーケットレポートの執筆を推奨",
    }


class TestMapTopicDiscovery:
    """map_topic_discovery のテスト。"""

    def test_正常系_ソースノードが1つ生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        assert len(result["sources"]) == 1
        src = result["sources"][0]
        assert src["source_id"] == "topic-suggestion-2026-03-16T1430"
        assert src["source_type"] == "original"
        assert src["command_source"] == "topic-discovery"
        assert src["suggestion_count"] == 2
        assert src["top_score"] == 41
        assert src["language"] == "ja"

    def test_正常系_トピックノードがカテゴリごとに生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        assert len(result["topics"]) == 2
        topic_ids = {t["topic_id"] for t in result["topics"]}
        assert topic_ids == {"content:market_report", "content:macro_economy"}
        for t in result["topics"]:
            assert t["category"] == "content_planning"

    def test_正常系_トピックノードが重複しない(self) -> None:
        """同じカテゴリが複数提案に含まれる場合、トピックは1つだけ生成。"""
        suggestions = [
            {
                "rank": 1,
                "topic": "トピックA",
                "category": "market_report",
                "scores": {"total": 35},
            },
            {
                "rank": 2,
                "topic": "トピックB",
                "category": "market_report",
                "scores": {"total": 30},
            },
        ]
        result = map_topic_discovery(
            _topic_discovery_mapper_data(suggestions=suggestions)
        )
        assert len(result["topics"]) == 1
        assert result["topics"][0]["topic_id"] == "content:market_report"

    def test_正常系_クレイムノードが提案ごとに生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        assert len(result["claims"]) == 2
        c1 = result["claims"][0]
        assert c1["claim_id"] == "ts:topic-suggestion-2026-03-16T1430:rank1"
        assert c1["claim_type"] == "recommendation"
        assert c1["sentiment"] == "neutral"
        assert c1["magnitude"] == "strong"
        assert c1["rank"] == 1
        assert c1["total_score"] == 41
        assert c1["timeliness"] == 9
        assert c1["topic_title"] == "S&P500 週間レビュー"
        assert c1["content"] == "S&P500 週間レビュー: 市場の動向が注目されている"
        assert c1["estimated_word_count"] == 4000
        assert c1["target_audience"] == "intermediate"
        assert c1["selected"] is None
        assert '"ポイント1"' in c1["key_points"]

    def test_正常系_クレイムのmagnitudeがスコアで判定される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        c1 = result["claims"][0]  # total=41 → strong
        c2 = result["claims"][1]  # total=33 → moderate
        assert c1["magnitude"] == "strong"
        assert c2["magnitude"] == "moderate"

    def test_正常系_エンティティノードがティッカーから生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        assert len(result["entities"]) == 3  # ^GSPC, ^DJI, ^N225
        entity_ids = {e["entity_id"] for e in result["entities"]}
        assert entity_ids == {"symbol:^GSPC", "symbol:^DJI", "symbol:^N225"}

    def test_正常系_エンティティタイプが正しく判定される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        for e in result["entities"]:
            if e["ticker"].startswith("^"):
                assert e["entity_type"] == "index"
            else:
                assert e["entity_type"] == "stock"

    def test_正常系_stock銘柄のエンティティタイプ(self) -> None:
        suggestions = [
            {
                "rank": 1,
                "topic": "トヨタ分析",
                "category": "stock_analysis",
                "suggested_symbols": ["7203.T"],
                "scores": {"total": 35},
            },
        ]
        result = map_topic_discovery(
            _topic_discovery_mapper_data(suggestions=suggestions)
        )
        assert len(result["entities"]) == 1
        assert result["entities"][0]["entity_type"] == "stock"
        assert result["entities"][0]["entity_id"] == "symbol:7203.T"

    def test_正常系_エンティティノードが重複しない(self) -> None:
        """複数提案に同じティッカーが含まれる場合、エンティティは1つだけ。"""
        suggestions = [
            {
                "rank": 1,
                "topic": "A",
                "category": "market_report",
                "suggested_symbols": ["^GSPC"],
                "scores": {"total": 35},
            },
            {
                "rank": 2,
                "topic": "B",
                "category": "stock_analysis",
                "suggested_symbols": ["^GSPC"],
                "scores": {"total": 30},
            },
        ]
        result = map_topic_discovery(
            _topic_discovery_mapper_data(suggestions=suggestions)
        )
        assert len(result["entities"]) == 1

    def test_正常系_ファクトノードがトレンドから生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        # 2 trends: first has 2 findings, second has 1 → 3 facts total
        assert len(result["facts"]) == 3
        f0 = result["facts"][0]
        assert f0["fact_id"] == "trend:topic-suggestion-2026-03-16T1430:0:0"
        assert f0["content"] == "S&P500が2%上昇"
        assert f0["fact_type"] == "event"
        assert f0["search_query"] == "S&P 500 weekly performance"
        assert f0["search_source"] == "tavily"
        assert f0["as_of_date"] == "2026-03-16"

    def test_正常系_no_search時はファクトがスキップされる(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data(no_search=True))
        assert len(result["facts"]) == 0
        assert len(result["relations"]["source_fact"]) == 0

    def test_正常系_no_search時はsearch_queries_countが0(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data(no_search=True))
        assert result["sources"][0]["search_queries_count"] == 0

    def test_正常系_リレーションtaggedが正しく生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        tagged = result["relations"]["tagged"]
        # Source->Topic: 2 (2 categories) + Claim->Topic: 2 (2 claims) = 4
        assert len(tagged) == 4
        source_tagged = [
            r for r in tagged if r["from_id"].startswith("topic-suggestion")
        ]
        assert len(source_tagged) == 2

    def test_正常系_リレーションsource_claimが正しく生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        sc = result["relations"]["source_claim"]
        assert len(sc) == 2
        for r in sc:
            assert r["from_id"] == "topic-suggestion-2026-03-16T1430"
            assert r["type"] == "MAKES_CLAIM"

    def test_正常系_リレーションclaim_entityが正しく生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        ce = result["relations"]["claim_entity"]
        # Claim 1 has 2 symbols, Claim 2 has 1 symbol → 3
        assert len(ce) == 3
        for r in ce:
            assert r["type"] == "ABOUT"

    def test_正常系_リレーションsource_factが正しく生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        sf = result["relations"]["source_fact"]
        assert len(sf) == 3
        for r in sf:
            assert r["from_id"] == "topic-suggestion-2026-03-16T1430"
            assert r["type"] == "STATES_FACT"

    def test_正常系_IDが全て文字列ベース(self) -> None:
        """UUID5 ではなく文字列ベースの ID が使用されていることを確認。"""
        result = map_topic_discovery(_topic_discovery_mapper_data())

        # Source ID is session_id directly
        assert result["sources"][0]["source_id"] == "topic-suggestion-2026-03-16T1430"

        # Topic ID is content:{category_key}
        for t in result["topics"]:
            assert t["topic_id"].startswith("content:")

        # Claim ID is ts:{session_id}:rank{rank}
        for c in result["claims"]:
            assert c["claim_id"].startswith("ts:")

        # Entity ID is symbol:{ticker}
        for e in result["entities"]:
            assert e["entity_id"].startswith("symbol:")

        # Fact ID is trend:{session_id}:{i}:{j}
        for f in result["facts"]:
            assert f["fact_id"].startswith("trend:")

    def test_正常系_batch_labelがtopic_discovery(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        assert result["batch_label"] == "topic-discovery"

    def test_エッジケース_空のsuggestions(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data(suggestions=[]))
        assert len(result["sources"]) == 1
        assert result["sources"][0]["suggestion_count"] == 0
        assert result["sources"][0]["top_score"] == 0
        assert len(result["topics"]) == 0
        assert len(result["claims"]) == 0
        assert len(result["entities"]) == 0

    def test_エッジケース_suggested_symbolsなしの提案(self) -> None:
        suggestions = [
            {
                "rank": 1,
                "topic": "副業ガイド",
                "category": "side_business",
                "scores": {"total": 25},
                "rationale": "理由",
            },
        ]
        result = map_topic_discovery(
            _topic_discovery_mapper_data(suggestions=suggestions)
        )
        assert len(result["entities"]) == 0
        assert len(result["relations"]["claim_entity"]) == 0

    def test_エッジケース_search_insightsがnull(self) -> None:
        data = _topic_discovery_mapper_data()
        data["search_insights"] = None
        result = map_topic_discovery(data)
        assert len(result["facts"]) == 0

    def test_正常系_5ノードタイプが全て生成される(self) -> None:
        """受け入れ条件: 5ノードタイプ + 4リレーション全て生成。"""
        result = map_topic_discovery(_topic_discovery_mapper_data())
        assert len(result["sources"]) > 0, "Source ノードが必要"
        assert len(result["topics"]) > 0, "Topic ノードが必要"
        assert len(result["claims"]) > 0, "Claim ノードが必要"
        assert len(result["entities"]) > 0, "Entity ノードが必要"
        assert len(result["facts"]) > 0, "Fact ノードが必要"

    def test_正常系_4リレーションが全て生成される(self) -> None:
        """受け入れ条件: 5ノードタイプ + 4リレーション全て生成。"""
        result = map_topic_discovery(_topic_discovery_mapper_data())
        rels = result["relations"]
        assert len(rels["tagged"]) > 0, "tagged リレーションが必要"
        assert len(rels["source_claim"]) > 0, "source_claim リレーションが必要"
        assert len(rels["claim_entity"]) > 0, "claim_entity リレーションが必要"
        assert len(rels["source_fact"]) > 0, "source_fact リレーションが必要"


# ---------------------------------------------------------------------------
# topic-discovery が COMMANDS に含まれることを確認
# ---------------------------------------------------------------------------


class TestTopicDiscoveryInCommands:
    """topic-discovery が COMMANDS リストに含まれることを確認。"""

    def test_正常系_topic_discoveryがCOMMANDSに含まれる(self) -> None:
        assert "topic-discovery" in COMMANDS
