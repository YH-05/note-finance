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
    _build_authored_by_rels,
    _build_causal_links,
    _build_next_period_chain,
    _build_question_nodes,
    _build_stance_nodes,
    _build_supersedes_chain,
    _build_trend_edges,
    _infer_period_type,
    _load_metric_alias_index,
    _load_wealth_themes,
    _magnitude_from_score,
    _match_domain_to_theme,
    _parse_yaml_frontmatter,
    _period_sort_key,
    _scan_wealth_directory,
    cleanup_old_files,
    generate_chunk_id,
    generate_claim_id,
    generate_datapoint_id,
    generate_entity_id,
    generate_fact_id,
    generate_queue_id,
    generate_source_id,
    generate_topic_id,
    main,
    map_ai_research,
    map_asset_management,
    map_finance_full,
    map_finance_news,
    map_market_report,
    map_pdf_extraction,
    map_reddit_topics,
    map_topic_discovery,
    map_wealth_scrape,
    map_wealth_scrape_backfill,
    map_wealth_scrape_incremental,
    map_web_research,
    parse_args,
    resolve_category,
    resolve_metric_id,
    run,
)
from freezegun import freeze_time

from pdf_pipeline.services.id_generator import (
    generate_author_id,
    generate_question_id,
    generate_stance_id,
)

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
# _infer_period_type
# ---------------------------------------------------------------------------


class TestInferPeriodType:
    """_infer_period_type 関数のテスト。"""

    def test_正常系_FY付きラベルでannual(self) -> None:
        assert _infer_period_type("FY2025") == "annual"
        assert _infer_period_type("FY26") == "annual"

    def test_正常系_Q付きラベルでquarterly(self) -> None:
        assert _infer_period_type("4Q25") == "quarterly"
        assert _infer_period_type("Q4 2025") == "quarterly"
        assert _infer_period_type("1Q26") == "quarterly"

    def test_正常系_H付きラベルでhalf_year(self) -> None:
        assert _infer_period_type("1H26") == "half_year"
        assert _infer_period_type("2H25") == "half_year"

    def test_正常系_年のみでannualにフォールバック(self) -> None:
        assert _infer_period_type("2025") == "annual"
        assert _infer_period_type("unknown") == "annual"

    def test_正常系_小文字でも正しく判定(self) -> None:
        assert _infer_period_type("fy2025") == "annual"
        assert _infer_period_type("q4") == "quarterly"
        assert _infer_period_type("1h26") == "half_year"

    def test_エッジケース_FQ含む文字列はquarterlyにならない(self) -> None:
        """FQ (fiscal quarter reference) は quarterly と誤判定しない。"""
        assert _infer_period_type("FQ1") == "annual"
        assert _infer_period_type("FQ4 2025") == "annual"
        assert _infer_period_type("fq2") == "annual"

    def test_エッジケース_3Q25はquarterly_FQ3はannual(self) -> None:
        """通常の四半期ラベルは quarterly、FQ付きは annual。"""
        assert _infer_period_type("3Q25") == "quarterly"
        assert _infer_period_type("FQ3 2025") == "annual"


# ---------------------------------------------------------------------------
# generate_datapoint_id
# ---------------------------------------------------------------------------


class TestGenerateDatapointId:
    """generate_datapoint_id 関数のテスト。"""

    def test_正常系_同じ入力で同じIDを生成(self) -> None:
        id1 = generate_datapoint_id("abc123", "Revenue", "FY2025")
        id2 = generate_datapoint_id("abc123", "Revenue", "FY2025")
        assert id1 == id2

    def test_正常系_異なる入力で異なるIDを生成(self) -> None:
        id1 = generate_datapoint_id("abc123", "Revenue", "FY2025")
        id2 = generate_datapoint_id("abc123", "EBITDA", "FY2025")
        assert id1 != id2

    def test_正常系_異なるperiodで異なるIDを生成(self) -> None:
        id1 = generate_datapoint_id("abc123", "Revenue", "FY2025")
        id2 = generate_datapoint_id("abc123", "Revenue", "4Q25")
        assert id1 != id2

    def test_正常系_異なるsource_hashで異なるIDを生成(self) -> None:
        id1 = generate_datapoint_id("abc123", "Revenue", "FY2025")
        id2 = generate_datapoint_id("def456", "Revenue", "FY2025")
        assert id1 != id2

    def test_正常系_32文字のhex文字列を返す(self) -> None:
        result = generate_datapoint_id("hash", "metric", "period")
        assert len(result) == 32
        int(result, 16)


# ---------------------------------------------------------------------------
# generate_chunk_id
# ---------------------------------------------------------------------------


class TestGenerateChunkId:
    """generate_chunk_id 関数のテスト。"""

    def test_正常系_同じ入力で同じIDを生成(self) -> None:
        id1 = generate_chunk_id("abc123", 0)
        id2 = generate_chunk_id("abc123", 0)
        assert id1 == id2

    def test_正常系_異なるchunk_indexで異なるIDを生成(self) -> None:
        id1 = generate_chunk_id("abc123", 0)
        id2 = generate_chunk_id("abc123", 1)
        assert id1 != id2

    def test_正常系_異なるsource_hashで異なるIDを生成(self) -> None:
        id1 = generate_chunk_id("abc123", 0)
        id2 = generate_chunk_id("def456", 0)
        assert id1 != id2

    def test_正常系_期待するフォーマットで返る(self) -> None:
        result = generate_chunk_id("abc123", 5)
        assert result == "abc123_chunk_5"


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

    def test_正常系_entity_keyが生成される(self) -> None:
        batch = _ai_research_batch()
        result = map_ai_research(batch)

        assert result["entities"][0]["entity_key"] == "NVIDIA::company"

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

    def test_正常系_topic_keyが生成される(self) -> None:
        batch = _asset_management_batch()
        result = map_asset_management(batch)
        topic = result["topics"][0]
        assert topic["topic_key"] == f"{topic['name']}::asset-management"

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

    def test_正常系_topic_keyが生成される(self) -> None:
        batch = _reddit_topics_batch()
        result = map_reddit_topics(batch)
        topic = result["topics"][0]
        assert topic["topic_key"] == f"{topic['name']}::reddit"

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

    @freeze_time(FROZEN_TIME)
    def test_正常系_7日以上前のファイルを削除(self, tmp_path: Path) -> None:
        # Create an old file (set mtime to 8 days ago from frozen time)
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
        assert data["schema_version"] == "2.2"
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

    def test_正常系_entity_keyが生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for entity in result["entities"]:
            assert entity["entity_key"] == f"{entity['name']}::{entity['entity_type']}"

    def test_正常系_topic_keyが生成される(self) -> None:
        data = _wealth_scrape_backfill_data()
        result = map_wealth_scrape_backfill(data)
        for topic in result["topics"]:
            assert topic["topic_key"] == f"{topic['name']}::wealth-management"

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

    def test_正常系_entity_keyが生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        for e in result["entities"]:
            assert e["entity_key"] == f"{e['name']}::{e['entity_type']}"

    def test_正常系_topic_keyが生成される(self) -> None:
        result = map_topic_discovery(_topic_discovery_mapper_data())
        for t in result["topics"]:
            assert t["topic_key"] == f"{t['name']}::content_planning"

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
# TestMapPdfExtraction
# ---------------------------------------------------------------------------


def _pdf_extraction_data(
    *,
    claims: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    financial_datapoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """pdf-extraction 形式のサンプルデータを生成。

    claim に全プロパティ（target_price, rating, magnitude, time_horizon）を含む。
    """
    if claims is None:
        claims = [
            {
                "content": "We maintain our Buy rating with a target price of $250.",
                "claim_type": "recommendation",
                "sentiment": "bullish",
                "magnitude": "strong",
                "target_price": "$250",
                "rating": "Buy",
                "time_horizon": "12 months",
                "about_entities": ["ACME Corp"],
            },
        ]
    if entities is None:
        entities = [
            {
                "name": "ACME Corp",
                "entity_type": "company",
                "ticker": "ACME",
            },
        ]
    if financial_datapoints is None:
        financial_datapoints = [
            {
                "metric": "revenue",
                "value": 1_000_000,
                "unit": "USD",
                "period_label": "FY2025",
                "about_entities": ["ACME Corp"],
            },
        ]
    return {
        "session_id": "pdf-extraction-test",
        "source_hash": "abc123def456",
        "chunks": [
            {
                "chunk_index": 0,
                "section_title": "Investment Summary",
                "content": "ACME Corp analysis and recommendation.",
                "entities": entities,
                "claims": claims,
                "facts": [],
                "financial_datapoints": financial_datapoints,
            },
        ],
    }


class TestMapPdfExtraction:
    """map_pdf_extraction のテスト基盤。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_Claimのtarget_priceとratingが保持される(self) -> None:
        """受け入れ条件: _build_claim_nodes が target_price, rating, magnitude, time_horizon を含める。"""
        result = map_pdf_extraction(_pdf_extraction_data())
        claims = result["claims"]
        assert len(claims) == 1
        claim = claims[0]
        assert claim["target_price"] == "$250"
        assert claim["rating"] == "Buy"
        assert claim["magnitude"] == "strong"
        assert claim["time_horizon"] == "12 months"
        assert claim["sentiment"] == "bullish"
        assert claim["claim_type"] == "recommendation"

    @freeze_time(FROZEN_TIME)
    def test_正常系_FiscalPeriodが正しく派生される(self) -> None:
        """受け入れ条件: financial_datapoints から FiscalPeriod が派生される。"""
        result = map_pdf_extraction(_pdf_extraction_data())
        periods = result["fiscal_periods"]
        assert len(periods) >= 1
        period = periods[0]
        assert "FY2025" in period["period_id"]
        assert period["period_label"] == "FY2025"
        assert period["period_type"] == "annual"

    @freeze_time(FROZEN_TIME)
    def test_エッジケース_空チャンクでも正常動作(self) -> None:
        """空の chunks リストでもエラーなく空結果を返す。"""
        data = {
            "session_id": "pdf-extraction-empty",
            "source_hash": "empty000",
            "chunks": [],
        }
        result = map_pdf_extraction(data)
        assert result["claims"] == []
        assert result["entities"] == []
        assert result["facts"] == []
        assert result["fiscal_periods"] == []
        assert result["financial_datapoints"] == []
        assert len(result["sources"]) == 1  # Source ノードは常に生成


# ---------------------------------------------------------------------------
# generate_stance_id / generate_author_id
# ---------------------------------------------------------------------------


class TestGenerateStanceId:
    """generate_stance_id 関数のテスト。"""

    def test_正常系_同じ入力で同じIDを生成(self) -> None:
        id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        id2 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        assert id1 == id2

    def test_正常系_異なるauthorで異なるIDを生成(self) -> None:
        id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        id2 = generate_stance_id("Morgan Stanley", "Apple", "2026-03-15")
        assert id1 != id2

    def test_正常系_異なるentityで異なるIDを生成(self) -> None:
        id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        id2 = generate_stance_id("Goldman Sachs", "Google", "2026-03-15")
        assert id1 != id2

    def test_正常系_異なるdateで異なるIDを生成(self) -> None:
        id1 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-15")
        id2 = generate_stance_id("Goldman Sachs", "Apple", "2026-03-16")
        assert id1 != id2

    def test_正常系_UUID形式で返る(self) -> None:
        result = generate_stance_id("GS", "AAPL", "2026-03-15")
        parts = result.split("-")
        assert len(parts) == 5
        assert len(result) == 36


class TestGenerateAuthorId:
    """generate_author_id 関数のテスト。"""

    def test_正常系_同じ入力で同じIDを生成(self) -> None:
        id1 = generate_author_id("Goldman Sachs", "sell_side")
        id2 = generate_author_id("Goldman Sachs", "sell_side")
        assert id1 == id2

    def test_正常系_異なるnameで異なるIDを生成(self) -> None:
        id1 = generate_author_id("Goldman Sachs", "sell_side")
        id2 = generate_author_id("Morgan Stanley", "sell_side")
        assert id1 != id2

    def test_正常系_異なるtypeで異なるIDを生成(self) -> None:
        id1 = generate_author_id("John Smith", "person")
        id2 = generate_author_id("John Smith", "sell_side")
        assert id1 != id2

    def test_正常系_UUID形式で返る(self) -> None:
        result = generate_author_id("GS", "sell_side")
        parts = result.split("-")
        assert len(parts) == 5
        assert len(result) == 36


# ---------------------------------------------------------------------------
# _build_stance_nodes
# ---------------------------------------------------------------------------


def _stance_chunk(
    *,
    stances: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a chunk dict with stances for testing."""
    if stances is None:
        stances = [
            {
                "author_name": "Goldman Sachs",
                "author_type": "sell_side",
                "organization": "Goldman Sachs Group",
                "entity_name": "ACME Corp",
                "rating": "Buy",
                "sentiment": "bullish",
                "target_price": 250.0,
                "target_price_currency": "USD",
                "as_of_date": "2026-03-15",
                "based_on_claims": [
                    "We maintain our Buy rating with a target price of $250."
                ],
            },
        ]
    if entities is None:
        entities = [
            {
                "name": "ACME Corp",
                "entity_type": "company",
                "ticker": "ACME",
            },
        ]
    return {
        "chunk_index": 0,
        "content": "Investment stance text.",
        "entities": entities,
        "stances": stances,
    }


class TestBuildStanceNodes:
    """_build_stance_nodes 関数のテスト。"""

    def test_正常系_StanceとAuthorノードが生成される(self) -> None:
        """受け入れ条件: Stance/Authorノードが正しく生成されること。"""
        chunk = _stance_chunk()
        entity_name_to_id = {"ACME Corp": generate_entity_id("ACME Corp", "company")}
        seen_authors: set[str] = set()
        author_to_id: dict[str, str] = {}

        result = _build_stance_nodes(
            chunk, entity_name_to_id, seen_authors, author_to_id
        )
        stances = result["stances"]
        authors = result["authors"]

        assert len(stances) == 1
        assert stances[0]["rating"] == "Buy"
        assert stances[0]["sentiment"] == "bullish"
        assert stances[0]["target_price"] == 250.0
        assert stances[0]["target_price_currency"] == "USD"
        assert stances[0]["as_of_date"] == "2026-03-15"

        assert len(authors) == 1
        assert authors[0]["name"] == "Goldman Sachs"
        assert authors[0]["author_type"] == "sell_side"
        assert authors[0]["organization"] == "Goldman Sachs Group"

    def test_正常系_HOLDS_STANCEリレーションが生成される(self) -> None:
        """受け入れ条件: Author -> Stance の HOLDS_STANCE が生成されること。"""
        chunk = _stance_chunk()
        entity_name_to_id = {"ACME Corp": generate_entity_id("ACME Corp", "company")}
        seen_authors: set[str] = set()
        author_to_id: dict[str, str] = {}

        result = _build_stance_nodes(
            chunk, entity_name_to_id, seen_authors, author_to_id
        )
        stances = result["stances"]
        authors = result["authors"]
        hs = result["holds_stance"]

        assert len(hs) == 1
        assert hs[0]["type"] == "HOLDS_STANCE"
        assert hs[0]["from_id"] == authors[0]["author_id"]
        assert hs[0]["to_id"] == stances[0]["stance_id"]

    def test_正常系_ON_ENTITYリレーションが生成される(self) -> None:
        """受け入れ条件: Stance -> Entity の ON_ENTITY が生成されること。"""
        chunk = _stance_chunk()
        entity_id = generate_entity_id("ACME Corp", "company")
        entity_name_to_id = {"ACME Corp": entity_id}
        seen_authors: set[str] = set()
        author_to_id: dict[str, str] = {}

        result = _build_stance_nodes(
            chunk, entity_name_to_id, seen_authors, author_to_id
        )
        stances = result["stances"]
        oe = result["on_entity"]

        assert len(oe) == 1
        assert oe[0]["type"] == "ON_ENTITY"
        assert oe[0]["from_id"] == stances[0]["stance_id"]
        assert oe[0]["to_id"] == entity_id

    def test_正常系_BASED_ONリレーションが生成される(self) -> None:
        """受け入れ条件: Stance -> Claim の BASED_ON が生成されること。"""
        chunk = _stance_chunk()
        entity_name_to_id = {"ACME Corp": generate_entity_id("ACME Corp", "company")}
        seen_authors: set[str] = set()
        author_to_id: dict[str, str] = {}

        result = _build_stance_nodes(
            chunk, entity_name_to_id, seen_authors, author_to_id
        )
        stances = result["stances"]
        bo = result["based_on"]

        assert len(bo) == 1
        assert bo[0]["type"] == "BASED_ON"
        assert bo[0]["from_id"] == stances[0]["stance_id"]
        assert bo[0]["role"] == "supporting"

    def test_正常系_Authorが重複排除される(self) -> None:
        """受け入れ条件: 同一Authorは1つのみ生成されること。"""
        chunk = _stance_chunk(
            stances=[
                {
                    "author_name": "Goldman Sachs",
                    "author_type": "sell_side",
                    "entity_name": "ACME Corp",
                    "rating": "Buy",
                    "as_of_date": "2026-03-15",
                },
                {
                    "author_name": "Goldman Sachs",
                    "author_type": "sell_side",
                    "entity_name": "Beta Inc",
                    "rating": "Hold",
                    "as_of_date": "2026-03-15",
                },
            ],
            entities=[
                {"name": "ACME Corp", "entity_type": "company"},
                {"name": "Beta Inc", "entity_type": "company"},
            ],
        )
        entity_name_to_id = {
            "ACME Corp": generate_entity_id("ACME Corp", "company"),
            "Beta Inc": generate_entity_id("Beta Inc", "company"),
        }
        seen_authors: set[str] = set()
        author_to_id: dict[str, str] = {}

        result = _build_stance_nodes(
            chunk, entity_name_to_id, seen_authors, author_to_id
        )
        stances = result["stances"]
        authors = result["authors"]

        assert len(stances) == 2
        assert len(authors) == 1  # Deduplicated

    def test_エッジケース_空stancesで空結果(self) -> None:
        """stances が空の場合に空のリストを返す。"""
        chunk = _stance_chunk(stances=[], entities=[])
        result = _build_stance_nodes(chunk, {}, set(), {})
        stances = result["stances"]
        authors = result["authors"]
        hs = result["holds_stance"]
        oe = result["on_entity"]
        bo = result["based_on"]
        assert stances == []
        assert authors == []
        assert hs == []
        assert oe == []
        assert bo == []

    def test_エッジケース_entity_nameが未解決でON_ENTITYがスキップされる(
        self,
    ) -> None:
        """entity_name_to_id に存在しない entity_name を持つ stance は ON_ENTITY を生成しない。"""
        chunk = _stance_chunk(
            stances=[
                {
                    "author_name": "Goldman Sachs",
                    "author_type": "sell_side",
                    "entity_name": "UnknownCorp",  # not in entity_name_to_id
                    "rating": "Buy",
                    "as_of_date": "2026-03-15",
                }
            ],
            entities=[],
        )
        # entity_name_to_id does NOT contain "UnknownCorp"
        entity_name_to_id: dict[str, str] = {}
        seen_authors: set[str] = set()
        author_to_id: dict[str, str] = {}

        result = _build_stance_nodes(
            chunk, entity_name_to_id, seen_authors, author_to_id
        )
        stances = result["stances"]
        authors = result["authors"]
        hs = result["holds_stance"]
        oe = result["on_entity"]

        assert len(stances) == 1
        assert len(authors) == 1
        assert len(hs) == 1  # HOLDS_STANCE is still generated
        assert len(oe) == 0  # ON_ENTITY is skipped because entity_id is None


# ---------------------------------------------------------------------------
# _build_supersedes_chain
# ---------------------------------------------------------------------------


class TestBuildSupersedesChain:
    """_build_supersedes_chain 関数のテスト。"""

    def test_正常系_as_of_date昇順でSUPERSEDES連鎖が構築される(self) -> None:
        """受け入れ条件: 同一(author, entity)内でas_of_date昇順に連鎖されること。"""
        stances = [
            {
                "stance_id": "stance-old",
                "author_name": "Goldman Sachs",
                "entity_name": "Apple",
                "as_of_date": "2026-01-01",
            },
            {
                "stance_id": "stance-mid",
                "author_name": "Goldman Sachs",
                "entity_name": "Apple",
                "as_of_date": "2026-02-01",
            },
            {
                "stance_id": "stance-new",
                "author_name": "Goldman Sachs",
                "entity_name": "Apple",
                "as_of_date": "2026-03-01",
            },
        ]

        supersedes = _build_supersedes_chain(stances)

        assert len(supersedes) == 2
        # mid supersedes old
        assert supersedes[0]["from_id"] == "stance-mid"
        assert supersedes[0]["to_id"] == "stance-old"
        assert supersedes[0]["type"] == "SUPERSEDES"
        # new supersedes mid
        assert supersedes[1]["from_id"] == "stance-new"
        assert supersedes[1]["to_id"] == "stance-mid"

    def test_正常系_異なるauthor_entityグループは独立した連鎖(self) -> None:
        """異なる(author, entity)グループは独立してSUPERSEDES連鎖される。"""
        stances = [
            {
                "stance_id": "gs-apple-old",
                "author_name": "Goldman Sachs",
                "entity_name": "Apple",
                "as_of_date": "2026-01-01",
            },
            {
                "stance_id": "gs-apple-new",
                "author_name": "Goldman Sachs",
                "entity_name": "Apple",
                "as_of_date": "2026-02-01",
            },
            {
                "stance_id": "ms-apple-old",
                "author_name": "Morgan Stanley",
                "entity_name": "Apple",
                "as_of_date": "2026-01-01",
            },
            {
                "stance_id": "ms-apple-new",
                "author_name": "Morgan Stanley",
                "entity_name": "Apple",
                "as_of_date": "2026-02-01",
            },
        ]

        supersedes = _build_supersedes_chain(stances)

        assert len(supersedes) == 2
        from_to_pairs = {(r["from_id"], r["to_id"]) for r in supersedes}
        assert ("gs-apple-new", "gs-apple-old") in from_to_pairs
        assert ("ms-apple-new", "ms-apple-old") in from_to_pairs

    def test_エッジケース_単一スタンスではSUPERSEDESなし(self) -> None:
        """1つのスタンスしかない場合、SUPERSEDES は生成されない。"""
        stances = [
            {
                "stance_id": "only-one",
                "author_name": "Goldman Sachs",
                "entity_name": "Apple",
                "as_of_date": "2026-03-15",
            },
        ]
        supersedes = _build_supersedes_chain(stances)
        assert supersedes == []

    def test_エッジケース_空リストでSUPERSEDESなし(self) -> None:
        """空のスタンスリストではSUPERSEDES は生成されない。"""
        supersedes = _build_supersedes_chain([])
        assert supersedes == []


# ---------------------------------------------------------------------------
# map_pdf_extraction: Stance 統合テスト
# ---------------------------------------------------------------------------


class TestMapPdfExtractionWithStances:
    """map_pdf_extraction での Stance 統合テスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_stancesがmap_pdf_extractionに統合される(self) -> None:
        """stances を含む pdf-extraction データが正しくマッピングされること。"""
        data = {
            "session_id": "pdf-stance-test",
            "source_hash": "stancehash123",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "GS initiates coverage of ACME.",
                    "entities": [
                        {
                            "name": "ACME Corp",
                            "entity_type": "company",
                            "ticker": "ACME",
                        },
                    ],
                    "claims": [
                        {
                            "content": "We initiate with a Buy rating and $250 TP.",
                            "claim_type": "recommendation",
                            "sentiment": "bullish",
                            "about_entities": ["ACME Corp"],
                        },
                    ],
                    "facts": [],
                    "financial_datapoints": [],
                    "stances": [
                        {
                            "author_name": "Goldman Sachs",
                            "author_type": "sell_side",
                            "organization": "Goldman Sachs Group",
                            "entity_name": "ACME Corp",
                            "rating": "Buy",
                            "sentiment": "bullish",
                            "target_price": 250.0,
                            "target_price_currency": "USD",
                            "as_of_date": "2026-03-15",
                            "based_on_claims": [
                                "We initiate with a Buy rating and $250 TP.",
                            ],
                        },
                    ],
                },
            ],
        }
        result = map_pdf_extraction(data)

        # Stances present
        assert len(result["stances"]) == 1
        assert result["stances"][0]["rating"] == "Buy"

        # Authors present
        assert len(result["authors"]) == 1
        assert result["authors"][0]["name"] == "Goldman Sachs"

        # Relations present
        rels = result["relations"]
        assert len(rels["holds_stance"]) == 1
        assert len(rels["on_entity"]) == 1
        assert len(rels["based_on"]) == 1
        assert len(rels["supersedes"]) == 0  # Only 1 stance, no chain

    @freeze_time(FROZEN_TIME)
    def test_正常系_SUPERSEDES連鎖がmap_pdf_extractionで構築される(self) -> None:
        """複数チャンクにまたがるstancesのSUPERSEDES連鎖が構築されること。"""
        data = {
            "session_id": "pdf-supersedes-test",
            "source_hash": "supersedeshash",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "Initial coverage.",
                    "entities": [
                        {
                            "name": "ACME Corp",
                            "entity_type": "company",
                            "ticker": "ACME",
                        },
                    ],
                    "claims": [],
                    "facts": [],
                    "financial_datapoints": [],
                    "stances": [
                        {
                            "author_name": "Goldman Sachs",
                            "author_type": "sell_side",
                            "entity_name": "ACME Corp",
                            "rating": "Buy",
                            "sentiment": "bullish",
                            "target_price": 200.0,
                            "target_price_currency": "USD",
                            "as_of_date": "2026-01-15",
                        },
                    ],
                },
                {
                    "chunk_index": 1,
                    "content": "Updated coverage.",
                    "entities": [],
                    "claims": [],
                    "facts": [],
                    "financial_datapoints": [],
                    "stances": [
                        {
                            "author_name": "Goldman Sachs",
                            "author_type": "sell_side",
                            "entity_name": "ACME Corp",
                            "rating": "Buy",
                            "sentiment": "bullish",
                            "target_price": 250.0,
                            "target_price_currency": "USD",
                            "as_of_date": "2026-03-15",
                        },
                    ],
                },
            ],
        }
        result = map_pdf_extraction(data)

        assert len(result["stances"]) == 2
        assert len(result["authors"]) == 1  # Deduplicated
        assert len(result["relations"]["supersedes"]) == 1

        supersedes = result["relations"]["supersedes"][0]
        assert supersedes["type"] == "SUPERSEDES"
        # Newer (March) supersedes older (January)
        assert supersedes["superseded_at"] == "2026-03-15"


# ---------------------------------------------------------------------------
# _build_causal_links
# ---------------------------------------------------------------------------


def _causal_chunk(
    *,
    facts: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
    financial_datapoints: list[dict[str, Any]] | None = None,
    causal_links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a chunk dict with causal links for testing."""
    if facts is None:
        facts = [
            {
                "content": "Revenue grew 15% YoY",
                "fact_type": "statistic",
            },
        ]
    if claims is None:
        claims = [
            {
                "content": "Stock will outperform the market",
                "claim_type": "prediction",
                "sentiment": "bullish",
            },
        ]
    if financial_datapoints is None:
        financial_datapoints = [
            {
                "metric_name": "Revenue",
                "value": 1000.0,
                "unit": "USD mn",
                "is_estimate": False,
                "period_label": "FY2025",
            },
        ]
    if causal_links is None:
        causal_links = [
            {
                "from_type": "fact",
                "from_content": "Revenue grew 15% YoY",
                "to_type": "claim",
                "to_content": "Stock will outperform the market",
                "mechanism": "strong revenue growth drives bullish outlook",
                "confidence": "high",
            },
        ]
    return {
        "chunk_index": 0,
        "content": "Financial analysis text.",
        "facts": facts,
        "claims": claims,
        "financial_datapoints": financial_datapoints,
        "causal_links": causal_links,
    }


class TestBuildCausalLinks:
    """_build_causal_links 関数のテスト。"""

    def test_正常系_fact_to_claimのCAUSESが生成される(self) -> None:
        """受け入れ条件: Fact -> Claim の CAUSES リレーションが生成されること。"""
        chunk = _causal_chunk()
        facts = [
            {
                "fact_id": generate_fact_id("Revenue grew 15% YoY"),
                "content": "Revenue grew 15% YoY",
            }
        ]
        claims = [
            {
                "claim_id": generate_claim_id("Stock will outperform the market"),
                "content": "Stock will outperform the market",
            }
        ]
        datapoints: list[dict[str, Any]] = []
        source_id = generate_source_id("pdf:testhash")

        rels = _build_causal_links(chunk, facts, claims, datapoints, source_id)

        assert len(rels) == 1
        assert rels[0]["type"] == "CAUSES"
        assert rels[0]["from_id"] == facts[0]["fact_id"]
        assert rels[0]["to_id"] == claims[0]["claim_id"]
        assert rels[0]["from_label"] == "Fact"
        assert rels[0]["to_label"] == "Claim"
        assert rels[0]["mechanism"] == "strong revenue growth drives bullish outlook"
        assert rels[0]["confidence"] == "high"
        assert rels[0]["source_id"] == source_id

    def test_正常系_datapoint_to_factのCAUSESが生成される(self) -> None:
        """受け入れ条件: FinancialDataPoint -> Fact の CAUSES が生成されること。"""
        chunk = _causal_chunk(
            causal_links=[
                {
                    "from_type": "datapoint",
                    "from_content": "Revenue",
                    "to_type": "fact",
                    "to_content": "Revenue grew 15% YoY",
                    "mechanism": "data supports the fact",
                    "confidence": "medium",
                },
            ],
        )
        source_hash = "testhash"
        facts = [
            {
                "fact_id": generate_fact_id("Revenue grew 15% YoY"),
                "content": "Revenue grew 15% YoY",
            }
        ]
        claims: list[dict[str, Any]] = []
        datapoints = [
            {
                "datapoint_id": generate_datapoint_id(source_hash, "Revenue", "FY2025"),
                "metric_name": "Revenue",
            }
        ]
        source_id = generate_source_id(f"pdf:{source_hash}")

        rels = _build_causal_links(chunk, facts, claims, datapoints, source_id)

        assert len(rels) == 1
        assert rels[0]["from_label"] == "FinancialDataPoint"
        assert rels[0]["to_label"] == "Fact"
        assert rels[0]["from_id"] == datapoints[0]["datapoint_id"]
        assert rels[0]["to_id"] == facts[0]["fact_id"]

    def test_正常系_未解決参照がwarningでスキップされる(self) -> None:
        """受け入れ条件: 未解決参照がwarningログ後にスキップされること。"""
        chunk = _causal_chunk(
            causal_links=[
                {
                    "from_type": "fact",
                    "from_content": "Nonexistent fact content",
                    "to_type": "claim",
                    "to_content": "Stock will outperform the market",
                },
            ],
        )
        facts: list[dict[str, Any]] = []
        claims = [
            {
                "claim_id": generate_claim_id("Stock will outperform the market"),
                "content": "Stock will outperform the market",
            }
        ]
        datapoints: list[dict[str, Any]] = []
        source_id = generate_source_id("pdf:testhash")

        rels = _build_causal_links(chunk, facts, claims, datapoints, source_id)

        assert len(rels) == 0

    def test_エッジケース_空causal_linksで空結果(self) -> None:
        """causal_links が空の場合に空のリストを返す。"""
        chunk = _causal_chunk(causal_links=[])
        rels = _build_causal_links(chunk, [], [], [], "src-id")
        assert rels == []


# ---------------------------------------------------------------------------
# map_pdf_extraction: CAUSES 統合テスト
# ---------------------------------------------------------------------------


class TestMapPdfExtractionWithCausalLinks:
    """map_pdf_extraction での CAUSES 統合テスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_causal_linksがmap_pdf_extractionに統合される(self) -> None:
        """causal_links を含む pdf-extraction データが正しくマッピングされること。"""
        data = {
            "session_id": "pdf-causal-test",
            "source_hash": "causalhash123",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "Revenue grew 15% YoY, driving bullish outlook.",
                    "entities": [],
                    "facts": [
                        {
                            "content": "Revenue grew 15% YoY",
                            "fact_type": "statistic",
                        },
                    ],
                    "claims": [
                        {
                            "content": "Stock will outperform the market",
                            "claim_type": "prediction",
                            "sentiment": "bullish",
                            "about_entities": [],
                        },
                    ],
                    "financial_datapoints": [],
                    "stances": [],
                    "causal_links": [
                        {
                            "from_type": "fact",
                            "from_content": "Revenue grew 15% YoY",
                            "to_type": "claim",
                            "to_content": "Stock will outperform the market",
                            "mechanism": "revenue growth drives bullish outlook",
                            "confidence": "high",
                        },
                    ],
                },
            ],
        }
        result = map_pdf_extraction(data)

        # CAUSES relations present
        rels = result["relations"]
        assert "causes" in rels
        assert len(rels["causes"]) == 1
        assert rels["causes"][0]["type"] == "CAUSES"
        assert rels["causes"][0]["from_label"] == "Fact"
        assert rels["causes"][0]["to_label"] == "Claim"
        assert rels["causes"][0]["mechanism"] == "revenue growth drives bullish outlook"
        assert rels["causes"][0]["confidence"] == "high"


# ---------------------------------------------------------------------------
# topic-discovery が COMMANDS に含まれることを確認
# ---------------------------------------------------------------------------


class TestTopicDiscoveryInCommands:
    """topic-discovery が COMMANDS リストに含まれることを確認。"""

    def test_正常系_topic_discoveryがCOMMANDSに含まれる(self) -> None:
        assert "topic-discovery" in COMMANDS


# ---------------------------------------------------------------------------
# Wave 3: Temporal Chain — _period_sort_key
# ---------------------------------------------------------------------------


class TestPeriodSortKey:
    """_period_sort_key が FY/Q/H フォーマットを正しくパースすること。"""

    def test_正常系_FY4桁年度をパース(self) -> None:
        assert _period_sort_key("FY2025") == (2025, 0)

    def test_正常系_FY2桁年度をパース(self) -> None:
        assert _period_sort_key("FY25") == (2025, 0)

    def test_正常系_四半期ラベルをパース(self) -> None:
        assert _period_sort_key("3Q25") == (2025, 3)
        assert _period_sort_key("1Q2024") == (2024, 1)
        assert _period_sort_key("4Q25") == (2025, 4)

    def test_正常系_半期ラベルをパース(self) -> None:
        assert _period_sort_key("1H26") == (2026, 1)
        assert _period_sort_key("2H2025") == (2025, 2)

    def test_異常系_不正ラベルがwarningログ後に末尾配置(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = _period_sort_key("INVALID")
        assert result == (9999, 0)
        assert "Unrecognised period label" in caplog.text


# ---------------------------------------------------------------------------
# Wave 3: Temporal Chain — _build_next_period_chain
# ---------------------------------------------------------------------------


class TestBuildNextPeriodChain:
    """ticker別・period_type別に独立した NEXT_PERIOD 連鎖が生成されること。"""

    def test_正常系_同一ticker同一typeで連鎖生成(self) -> None:
        periods = [
            {
                "period_id": "ISAT_FY2024",
                "period_type": "annual",
                "period_label": "FY2024",
            },
            {
                "period_id": "ISAT_FY2025",
                "period_type": "annual",
                "period_label": "FY2025",
            },
            {
                "period_id": "ISAT_FY2026",
                "period_type": "annual",
                "period_label": "FY2026",
            },
        ]
        rels = _build_next_period_chain(periods)
        assert len(rels) == 2
        assert rels[0]["from_id"] == "ISAT_FY2024"
        assert rels[0]["to_id"] == "ISAT_FY2025"
        assert rels[0]["type"] == "NEXT_PERIOD"
        assert rels[0]["gap_months"] == 12
        assert rels[1]["from_id"] == "ISAT_FY2025"
        assert rels[1]["to_id"] == "ISAT_FY2026"

    def test_正常系_異なるtickerは独立した連鎖(self) -> None:
        periods = [
            {
                "period_id": "ISAT_FY2024",
                "period_type": "annual",
                "period_label": "FY2024",
            },
            {
                "period_id": "ISAT_FY2025",
                "period_type": "annual",
                "period_label": "FY2025",
            },
            {
                "period_id": "TLKM_FY2024",
                "period_type": "annual",
                "period_label": "FY2024",
            },
            {
                "period_id": "TLKM_FY2025",
                "period_type": "annual",
                "period_label": "FY2025",
            },
        ]
        rels = _build_next_period_chain(periods)
        assert len(rels) == 2
        # Each ticker gets its own chain
        from_ids = {r["from_id"] for r in rels}
        assert "ISAT_FY2024" in from_ids
        assert "TLKM_FY2024" in from_ids

    def test_正常系_異なるperiod_typeは独立した連鎖(self) -> None:
        periods = [
            {
                "period_id": "ISAT_FY2024",
                "period_type": "annual",
                "period_label": "FY2024",
            },
            {
                "period_id": "ISAT_FY2025",
                "period_type": "annual",
                "period_label": "FY2025",
            },
            {
                "period_id": "ISAT_1Q25",
                "period_type": "quarterly",
                "period_label": "1Q25",
            },
            {
                "period_id": "ISAT_2Q25",
                "period_type": "quarterly",
                "period_label": "2Q25",
            },
        ]
        rels = _build_next_period_chain(periods)
        assert len(rels) == 2
        # Find quarterly rel
        q_rels = [r for r in rels if r["gap_months"] == 3]
        assert len(q_rels) == 1
        assert q_rels[0]["from_id"] == "ISAT_1Q25"
        assert q_rels[0]["to_id"] == "ISAT_2Q25"

    def test_エッジケース_単一periodは連鎖なし(self) -> None:
        periods = [
            {
                "period_id": "ISAT_FY2025",
                "period_type": "annual",
                "period_label": "FY2025",
            },
        ]
        rels = _build_next_period_chain(periods)
        assert rels == []

    def test_エッジケース_空リストで空結果(self) -> None:
        rels = _build_next_period_chain([])
        assert rels == []


# ---------------------------------------------------------------------------
# Wave 3: Temporal Chain — _build_trend_edges
# ---------------------------------------------------------------------------


class TestBuildTrendEdges:
    """変化率と方向が正しく計算されること。"""

    def _make_dp(
        self, dp_id: str, metric: str, value: float, period_label: str
    ) -> dict[str, Any]:
        return {
            "datapoint_id": dp_id,
            "metric_name": metric,
            "value": value,
            "period_label": period_label,
        }

    def _make_fp(self, period_id: str, period_type: str, label: str) -> dict[str, Any]:
        return {
            "period_id": period_id,
            "period_type": period_type,
            "period_label": label,
        }

    def test_正常系_上昇トレンドを検出(self) -> None:
        dps = [
            self._make_dp("dp1", "Revenue", 100.0, "FY2024"),
            self._make_dp("dp2", "Revenue", 120.0, "FY2025"),
        ]
        fps = [
            self._make_fp("ISAT_FY2024", "annual", "FY2024"),
            self._make_fp("ISAT_FY2025", "annual", "FY2025"),
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
        ]
        rels = _build_trend_edges(dps, fps, for_period)
        assert len(rels) == 1
        assert rels[0]["from_id"] == "dp1"
        assert rels[0]["to_id"] == "dp2"
        assert rels[0]["type"] == "TREND"
        assert rels[0]["change_pct"] == 20.0
        assert rels[0]["direction"] == "up"

    def test_正常系_下降トレンドを検出(self) -> None:
        dps = [
            self._make_dp("dp1", "NetIncome", 200.0, "FY2024"),
            self._make_dp("dp2", "NetIncome", 150.0, "FY2025"),
        ]
        fps = [
            self._make_fp("ISAT_FY2024", "annual", "FY2024"),
            self._make_fp("ISAT_FY2025", "annual", "FY2025"),
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
        ]
        rels = _build_trend_edges(dps, fps, for_period)
        assert len(rels) == 1
        assert rels[0]["change_pct"] == -25.0
        assert rels[0]["direction"] == "down"

    def test_正常系_変化率1パーセント以内はflat(self) -> None:
        dps = [
            self._make_dp("dp1", "ARPU", 100.0, "FY2024"),
            self._make_dp("dp2", "ARPU", 100.5, "FY2025"),
        ]
        fps = [
            self._make_fp("ISAT_FY2024", "annual", "FY2024"),
            self._make_fp("ISAT_FY2025", "annual", "FY2025"),
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
        ]
        rels = _build_trend_edges(dps, fps, for_period)
        assert len(rels) == 1
        assert rels[0]["change_pct"] == 0.5
        assert rels[0]["direction"] == "flat"

    def test_エッジケース_prev_value_0でゼロ除算回避(self) -> None:
        dps = [
            self._make_dp("dp1", "Revenue", 0.0, "FY2024"),
            self._make_dp("dp2", "Revenue", 100.0, "FY2025"),
        ]
        fps = [
            self._make_fp("ISAT_FY2024", "annual", "FY2024"),
            self._make_fp("ISAT_FY2025", "annual", "FY2025"),
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
        ]
        rels = _build_trend_edges(dps, fps, for_period)
        assert len(rels) == 1
        assert rels[0]["change_pct"] == 0.0
        assert rels[0]["direction"] == "flat"

    def test_正常系_異なるmetricは独立したトレンド(self) -> None:
        dps = [
            self._make_dp("dp1", "Revenue", 100.0, "FY2024"),
            self._make_dp("dp2", "Revenue", 120.0, "FY2025"),
            self._make_dp("dp3", "EBITDA", 50.0, "FY2024"),
            self._make_dp("dp4", "EBITDA", 40.0, "FY2025"),
        ]
        fps = [
            self._make_fp("ISAT_FY2024", "annual", "FY2024"),
            self._make_fp("ISAT_FY2025", "annual", "FY2025"),
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
            {"from_id": "dp3", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp4", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
        ]
        rels = _build_trend_edges(dps, fps, for_period)
        assert len(rels) == 2
        # One should be up (Revenue +20%), one should be down (EBITDA -20%)
        directions = {r["direction"] for r in rels}
        assert "up" in directions
        assert "down" in directions

    def test_エッジケース_valueがNoneのデータポイントはスキップされる(self) -> None:
        """value が None のデータポイントを含むペアは TREND エッジを生成しない。"""
        dps = [
            {
                "datapoint_id": "dp1",
                "metric_name": "Revenue",
                "value": None,  # None value — should be skipped
                "period_label": "FY2024",
            },
            self._make_dp("dp2", "Revenue", 120.0, "FY2025"),
        ]
        fps = [
            self._make_fp("ISAT_FY2024", "annual", "FY2024"),
            self._make_fp("ISAT_FY2025", "annual", "FY2025"),
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024", "type": "FOR_PERIOD"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025", "type": "FOR_PERIOD"},
        ]
        rels = _build_trend_edges(dps, fps, for_period)
        # No TREND edge because prev_val is None
        assert len(rels) == 0


# ---------------------------------------------------------------------------
# _build_question_nodes helper
# ---------------------------------------------------------------------------


def _question_chunk(
    *,
    questions: list[dict[str, Any]] | None = None,
    entities: list[dict[str, Any]] | None = None,
    facts: list[dict[str, Any]] | None = None,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a chunk dict with questions for testing."""
    if questions is None:
        questions = [
            {
                "content": "What is the revenue breakdown by segment?",
                "question_type": "data_gap",
                "priority": "high",
                "about_entities": ["ACME Corp"],
                "motivated_by_contents": ["Revenue grew 15% YoY"],
            },
        ]
    if entities is None:
        entities = [
            {
                "name": "ACME Corp",
                "entity_type": "company",
                "ticker": "ACME",
            },
        ]
    if facts is None:
        facts = [
            {
                "content": "Revenue grew 15% YoY",
                "fact_type": "statistic",
            },
        ]
    if claims is None:
        claims = [
            {
                "content": "Stock will outperform the market",
                "claim_type": "prediction",
                "sentiment": "bullish",
            },
        ]
    return {
        "chunk_index": 0,
        "content": "Financial analysis text with knowledge gaps.",
        "entities": entities,
        "facts": facts,
        "claims": claims,
        "questions": questions,
    }


# ---------------------------------------------------------------------------
# _build_question_nodes
# ---------------------------------------------------------------------------


class TestBuildQuestionNodes:
    """_build_question_nodes 関数のテスト。"""

    def test_正常系_Questionノードが生成される(self) -> None:
        """受け入れ条件: Question ノードが正しいプロパティで生成されること。"""
        chunk = _question_chunk()
        entity_name_to_id = {"ACME Corp": generate_entity_id("ACME Corp", "company")}
        facts = [
            {
                "fact_id": generate_fact_id("Revenue grew 15% YoY"),
                "content": "Revenue grew 15% YoY",
            }
        ]
        claims = [
            {
                "claim_id": generate_claim_id("Stock will outperform the market"),
                "content": "Stock will outperform the market",
            }
        ]

        questions, _aa, _mb = _build_question_nodes(
            chunk, entity_name_to_id, facts, claims
        )

        assert len(questions) == 1
        q = questions[0]
        assert q["content"] == "What is the revenue breakdown by segment?"
        assert q["question_type"] == "data_gap"
        assert q["priority"] == "high"
        assert q["status"] == "open"
        expected_id = generate_question_id("What is the revenue breakdown by segment?")
        assert q["question_id"] == expected_id

    def test_正常系_ASKS_ABOUTリレーションが生成される(self) -> None:
        """受け入れ条件: Question -> Entity の ASKS_ABOUT が生成されること。"""
        chunk = _question_chunk()
        entity_id = generate_entity_id("ACME Corp", "company")
        entity_name_to_id = {"ACME Corp": entity_id}
        facts = [
            {
                "fact_id": generate_fact_id("Revenue grew 15% YoY"),
                "content": "Revenue grew 15% YoY",
            }
        ]
        claims: list[dict[str, Any]] = []

        questions, aa, _mb = _build_question_nodes(
            chunk, entity_name_to_id, facts, claims
        )

        assert len(aa) == 1
        assert aa[0]["type"] == "ASKS_ABOUT"
        assert aa[0]["from_id"] == questions[0]["question_id"]
        assert aa[0]["to_id"] == entity_id

    def test_正常系_MOTIVATED_BYリレーションが生成される(self) -> None:
        """受け入れ条件: Question -> Fact の MOTIVATED_BY が生成されること。"""
        chunk = _question_chunk()
        entity_name_to_id = {"ACME Corp": generate_entity_id("ACME Corp", "company")}
        fact_id = generate_fact_id("Revenue grew 15% YoY")
        facts = [
            {
                "fact_id": fact_id,
                "content": "Revenue grew 15% YoY",
            }
        ]
        claims: list[dict[str, Any]] = []

        questions, _aa, mb = _build_question_nodes(
            chunk, entity_name_to_id, facts, claims
        )

        assert len(mb) == 1
        assert mb[0]["type"] == "MOTIVATED_BY"
        assert mb[0]["from_id"] == questions[0]["question_id"]
        assert mb[0]["to_id"] == fact_id

    def test_正常系_MOTIVATED_BYがClaimにも解決される(self) -> None:
        """受け入れ条件: motivated_by_contents が Claim にも解決されること。"""
        chunk = _question_chunk(
            questions=[
                {
                    "content": "Is the bullish outlook justified?",
                    "question_type": "assumption_check",
                    "about_entities": [],
                    "motivated_by_contents": ["Stock will outperform the market"],
                },
            ],
        )
        entity_name_to_id: dict[str, str] = {}
        facts: list[dict[str, Any]] = []
        claim_id = generate_claim_id("Stock will outperform the market")
        claims = [
            {
                "claim_id": claim_id,
                "content": "Stock will outperform the market",
            }
        ]

        _questions, _aa, mb = _build_question_nodes(
            chunk, entity_name_to_id, facts, claims
        )

        assert len(mb) == 1
        assert mb[0]["to_id"] == claim_id

    def test_エッジケース_空questionsで空結果(self) -> None:
        """questions が空の場合に空のリストを返す。"""
        chunk = _question_chunk(questions=[], entities=[], facts=[], claims=[])
        questions, aa, mb = _build_question_nodes(chunk, {}, [], [])
        assert questions == []
        assert aa == []
        assert mb == []


# ---------------------------------------------------------------------------
# map_pdf_extraction: Question 統合テスト
# ---------------------------------------------------------------------------


class TestMapPdfExtractionWithQuestions:
    """map_pdf_extraction での Question 統合テスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_questionsがmap_pdf_extractionに統合される(self) -> None:
        """questions を含む pdf-extraction データが正しくマッピングされること。"""
        data = {
            "session_id": "pdf-question-test",
            "source_hash": "questionhash123",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "Analysis text.",
                    "entities": [
                        {
                            "name": "ACME Corp",
                            "entity_type": "company",
                            "ticker": "ACME",
                        }
                    ],
                    "facts": [
                        {
                            "content": "Revenue grew 15% YoY",
                            "fact_type": "statistic",
                            "about_entities": ["ACME Corp"],
                        }
                    ],
                    "claims": [],
                    "financial_datapoints": [],
                    "stances": [],
                    "causal_links": [],
                    "questions": [
                        {
                            "content": "What is the revenue breakdown by segment?",
                            "question_type": "data_gap",
                            "priority": "high",
                            "about_entities": ["ACME Corp"],
                            "motivated_by_contents": ["Revenue grew 15% YoY"],
                        }
                    ],
                }
            ],
        }

        result = map_pdf_extraction(data)

        assert len(result["questions"]) == 1
        q = result["questions"][0]
        assert q["question_type"] == "data_gap"
        assert q["status"] == "open"
        assert q["priority"] == "high"

        # Verify ASKS_ABOUT relation
        asks_about = result["relations"]["asks_about"]
        assert len(asks_about) == 1
        assert asks_about[0]["type"] == "ASKS_ABOUT"

        # Verify MOTIVATED_BY relation
        motivated_by = result["relations"]["motivated_by"]
        assert len(motivated_by) == 1
        assert motivated_by[0]["type"] == "MOTIVATED_BY"


# ---------------------------------------------------------------------------
# _build_authored_by_rels (Phase 2 Step A-1)
# ---------------------------------------------------------------------------


class TestBuildAuthoredByRels:
    """_build_authored_by_rels 関数のテスト。"""

    def test_正常系_publisherからAuthorとAUTHORED_BYが生成される(self) -> None:
        """受け入れ条件: publisher から Author ノードと AUTHORED_BY rel が生成されること。"""
        source_id = generate_source_id("pdf:testhash")
        seen: set[str] = set()
        name_to_id: dict[str, str] = {}

        authors, rels = _build_authored_by_rels(source_id, "HSBC", seen, name_to_id)

        assert len(authors) == 1
        assert authors[0]["name"] == "HSBC"
        assert authors[0]["author_type"] == "sell_side"
        assert authors[0]["organization"] == "HSBC"
        assert len(rels) == 1
        assert rels[0]["from_id"] == source_id
        assert rels[0]["to_id"] == authors[0]["author_id"]
        assert rels[0]["type"] == "AUTHORED_BY"

    def test_正常系_既存AuthorとのID統合(self) -> None:
        """LLM抽出で既に Author が作成されている場合、同一 ID を再利用すること。"""
        source_id = generate_source_id("pdf:testhash2")
        existing_author_id = generate_author_id("Citi", "sell_side")
        seen: set[str] = {"Citi:sell_side"}
        name_to_id: dict[str, str] = {"Citi": existing_author_id}

        authors, rels = _build_authored_by_rels(source_id, "Citi", seen, name_to_id)

        # Author は重複排除で新規生成されない
        assert len(authors) == 0
        # AUTHORED_BY は既存 author_id を使う
        assert len(rels) == 1
        assert rels[0]["to_id"] == existing_author_id

    def test_エッジケース_空publisherで空結果(self) -> None:
        """publisher が空文字列の場合、何も生成されないこと。"""
        source_id = generate_source_id("pdf:testhash3")
        authors, rels = _build_authored_by_rels(source_id, "", set(), {})
        assert authors == []
        assert rels == []

    def test_正常系_name_to_idに未知publisherが追加される(self) -> None:
        """初めて見る publisher が name_to_id に登録されること。"""
        source_id = generate_source_id("pdf:testhash4")
        seen: set[str] = set()
        name_to_id: dict[str, str] = {}

        _build_authored_by_rels(source_id, "BofA Securities", seen, name_to_id)

        assert "BofA Securities" in name_to_id
        assert "BofA Securities:sell_side" in seen


# ---------------------------------------------------------------------------
# map_pdf_extraction: AUTHORED_BY 統合テスト (Phase 2)
# ---------------------------------------------------------------------------


class TestMapPdfExtractionWithAuthoredBy:
    """map_pdf_extraction での AUTHORED_BY 統合テスト。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_publisherありでAUTHORED_BYが生成される(self) -> None:
        """publisher を含む pdf-extraction データで AUTHORED_BY が生成されること。"""
        data = {
            "session_id": "pdf-authored-by-test",
            "source_hash": "authoredtesthash",
            "publisher": "HSBC",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "Analysis text.",
                    "entities": [],
                    "facts": [],
                    "claims": [],
                    "financial_datapoints": [],
                    "stances": [],
                    "causal_links": [],
                    "questions": [],
                }
            ],
        }

        result = map_pdf_extraction(data)

        # Source に publisher が含まれること
        assert result["sources"][0].get("publisher") == "HSBC"

        # Author が生成されること
        assert len(result["authors"]) == 1
        assert result["authors"][0]["name"] == "HSBC"
        assert result["authors"][0]["author_type"] == "sell_side"

        # AUTHORED_BY が生成されること
        authored_by = result["relations"]["authored_by"]
        assert len(authored_by) == 1
        assert authored_by[0]["type"] == "AUTHORED_BY"
        assert authored_by[0]["from_id"] == result["sources"][0]["source_id"]
        assert authored_by[0]["to_id"] == result["authors"][0]["author_id"]

    @freeze_time(FROZEN_TIME)
    def test_正常系_publisherなしでAUTHORED_BYなし(self) -> None:
        """publisher がない場合、AUTHORED_BY が生成されないこと。"""
        data = {
            "session_id": "pdf-no-publisher",
            "source_hash": "nopubhash",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "Analysis text.",
                    "entities": [],
                    "facts": [],
                    "claims": [],
                    "financial_datapoints": [],
                    "stances": [],
                    "causal_links": [],
                    "questions": [],
                }
            ],
        }

        result = map_pdf_extraction(data)

        assert result["relations"]["authored_by"] == []

    @freeze_time(FROZEN_TIME)
    def test_正常系_publisherとStanceのAuthorが統合される(self) -> None:
        """publisher Author と Stance 由来 Author が重複排除されること。"""
        data = {
            "session_id": "pdf-author-merge",
            "source_hash": "mergehash",
            "publisher": "HSBC",
            "chunks": [
                {
                    "chunk_index": 0,
                    "content": "Analysis text.",
                    "entities": [
                        {
                            "name": "ISAT",
                            "entity_type": "company",
                            "ticker": "ISAT IJ",
                        }
                    ],
                    "facts": [],
                    "claims": [],
                    "financial_datapoints": [],
                    "stances": [
                        {
                            "author_name": "HSBC",
                            "author_type": "sell_side",
                            "entity_name": "ISAT",
                            "rating": "Buy",
                            "sentiment": "bullish",
                            "target_price": 3200.0,
                            "target_price_currency": "IDR",
                            "as_of_date": "2025-10-29",
                        }
                    ],
                    "causal_links": [],
                    "questions": [],
                }
            ],
        }

        result = map_pdf_extraction(data)

        # Author は1つだけ（Stance由来 + publisher が統合）
        hsbc_authors = [a for a in result["authors"] if a["name"] == "HSBC"]
        assert len(hsbc_authors) == 1

        # AUTHORED_BY も存在
        assert len(result["relations"]["authored_by"]) == 1

        # HOLDS_STANCE も存在
        assert len(result["relations"]["holds_stance"]) == 1


# ---------------------------------------------------------------------------
# _load_metric_alias_index / resolve_metric_id (Phase 2 Step B-2)
# ---------------------------------------------------------------------------


class TestLoadMetricAliasIndex:
    """_load_metric_alias_index 関数のテスト。"""

    def test_正常系_エイリアスインデックスが読み込まれる(self) -> None:
        """metric_master.json からエイリアスインデックスを読み込めること。"""
        index = _load_metric_alias_index()
        assert len(index) > 0
        # canonical_name がキーに含まれる
        assert "revenue" in index
        assert index["revenue"] == "metric-revenue"

    def test_正常系_エイリアスが正規化される(self) -> None:
        """表記揺れのエイリアスが同一 metric_id に解決されること。"""
        index = _load_metric_alias_index()
        # "Revenue" と "Total Revenue" が同じ metric_id に解決
        assert index.get("revenue") == index.get("total revenue")
        assert index.get("revenue") == "metric-revenue"

    def test_正常系_display_nameもキーに含まれる(self) -> None:
        """display_name もルックアップキーとして使えること。"""
        index = _load_metric_alias_index()
        assert index.get("ebitda margin") == "metric-ebitda-margin"


class TestResolveMetricId:
    """resolve_metric_id 関数のテスト。"""

    def test_正常系_エイリアスからmetric_idを解決(self) -> None:
        assert resolve_metric_id("Total Revenue") == "metric-revenue"

    def test_正常系_canonical_nameからmetric_idを解決(self) -> None:
        assert resolve_metric_id("ebitda") == "metric-ebitda"

    def test_正常系_大文字小文字を無視(self) -> None:
        assert resolve_metric_id("EBITDA Margin") == "metric-ebitda-margin"

    def test_エッジケース_未知metric_nameでNone(self) -> None:
        assert resolve_metric_id("Unknown Metric XYZ") is None

    def test_エッジケース_空文字列でNone(self) -> None:
        assert resolve_metric_id("") is None


# ---------------------------------------------------------------------------
# _build_trend_edges: metric_id テスト (Phase 2 Step B-3)
# ---------------------------------------------------------------------------


class TestBuildTrendEdgesWithMetricId:
    """_build_trend_edges の metric_id 関連テスト。"""

    def test_正常系_既知metricでmetric_idが付与される(self) -> None:
        """metric_master.json に存在する metric_name の TREND に metric_id が付くこと。"""
        periods = [
            {"period_id": "ISAT_FY2024", "period_label": "FY2024"},
            {"period_id": "ISAT_FY2025", "period_label": "FY2025"},
        ]
        datapoints = [
            {
                "datapoint_id": "dp1",
                "metric_name": "Revenue",
                "value": 100,
            },
            {
                "datapoint_id": "dp2",
                "metric_name": "Revenue",
                "value": 120,
            },
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025"},
        ]

        edges = _build_trend_edges(datapoints, periods, for_period)

        assert len(edges) == 1
        assert edges[0]["metric_id"] == "metric-revenue"
        assert edges[0]["direction"] == "up"

    def test_正常系_未知metricでmetric_idなし(self) -> None:
        """metric_master.json に存在しない metric_name の TREND に metric_id がないこと。"""
        periods = [
            {"period_id": "ISAT_FY2024", "period_label": "FY2024"},
            {"period_id": "ISAT_FY2025", "period_label": "FY2025"},
        ]
        datapoints = [
            {"datapoint_id": "dp1", "metric_name": "Unknown Metric", "value": 100},
            {"datapoint_id": "dp2", "metric_name": "Unknown Metric", "value": 110},
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025"},
        ]

        edges = _build_trend_edges(datapoints, periods, for_period)

        assert len(edges) == 1
        assert "metric_id" not in edges[0]

    def test_正常系_表記揺れが同一グループに統合される(self) -> None:
        """'Revenue' と 'Total Revenue' が同じ metric_id でグルーピングされること。"""
        periods = [
            {"period_id": "ISAT_FY2024", "period_label": "FY2024"},
            {"period_id": "ISAT_FY2025", "period_label": "FY2025"},
        ]
        datapoints = [
            {"datapoint_id": "dp1", "metric_name": "Revenue", "value": 100},
            {"datapoint_id": "dp2", "metric_name": "Total Revenue", "value": 120},
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025"},
        ]

        edges = _build_trend_edges(datapoints, periods, for_period)

        # Both resolve to metric-revenue → grouped together → 1 TREND edge
        assert len(edges) == 1
        assert edges[0]["metric_id"] == "metric-revenue"

    def test_正常系_measures_linked_dp_idsでフィルタリング(self) -> None:
        """measures_linked_dp_ids で DP をフィルタすること。"""
        periods = [
            {"period_id": "ISAT_FY2024", "period_label": "FY2024"},
            {"period_id": "ISAT_FY2025", "period_label": "FY2025"},
        ]
        datapoints = [
            {"datapoint_id": "dp1", "metric_name": "Revenue", "value": 100},
            {"datapoint_id": "dp2", "metric_name": "Revenue", "value": 120},
            {"datapoint_id": "dp3", "metric_name": "Revenue", "value": 130},
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025"},
            {"from_id": "dp3", "to_id": "ISAT_FY2025"},
        ]

        # Only dp1 and dp2 are MEASURES-linked
        edges = _build_trend_edges(
            datapoints,
            periods,
            for_period,
            measures_linked_dp_ids={"dp1", "dp2"},
        )

        assert len(edges) == 1
        # dp3 is excluded
        assert edges[0]["from_id"] == "dp1"
        assert edges[0]["to_id"] == "dp2"

    def test_正常系_異なるsource_hashは独立したTRENDグループ(self) -> None:
        """異なる source_hash の DP は別グループとして TREND が分離されること。"""
        periods = [
            {"period_id": "ISAT_FY2024", "period_label": "FY2024"},
            {"period_id": "ISAT_FY2025", "period_label": "FY2025"},
        ]
        datapoints = [
            # Source A: IDR bn
            {
                "datapoint_id": "dp_a1",
                "metric_name": "Revenue",
                "value": 55887,
                "source_hash": "hash_hsbc",
            },
            {
                "datapoint_id": "dp_a2",
                "metric_name": "Revenue",
                "value": 56518,
                "source_hash": "hash_hsbc",
            },
            # Source B: IDR (different unit, same metric_id after resolve)
            {
                "datapoint_id": "dp_b1",
                "metric_name": "Revenue",
                "value": 150000000000000,
                "source_hash": "hash_citi",
            },
            {
                "datapoint_id": "dp_b2",
                "metric_name": "Revenue",
                "value": 155000000000000,
                "source_hash": "hash_citi",
            },
        ]
        for_period = [
            {"from_id": "dp_a1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp_a2", "to_id": "ISAT_FY2025"},
            {"from_id": "dp_b1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp_b2", "to_id": "ISAT_FY2025"},
        ]

        edges = _build_trend_edges(datapoints, periods, for_period)

        # 2 separate TREND edges (one per source), not cross-source
        assert len(edges) == 2
        edge_pairs = {(e["from_id"], e["to_id"]) for e in edges}
        assert ("dp_a1", "dp_a2") in edge_pairs
        assert ("dp_b1", "dp_b2") in edge_pairs

        # HSBC: ~1.1% increase
        hsbc_edge = next(e for e in edges if e["from_id"] == "dp_a1")
        assert hsbc_edge["change_pct"] == pytest.approx(1.13, abs=0.01)

        # Citi: ~3.3% increase
        citi_edge = next(e for e in edges if e["from_id"] == "dp_b1")
        assert citi_edge["change_pct"] == pytest.approx(3.33, abs=0.01)

    def test_正常系_source_hashなしは同一グループ(self) -> None:
        """source_hash が空/未設定の DP は従来通り同一グループになること。"""
        periods = [
            {"period_id": "ISAT_FY2024", "period_label": "FY2024"},
            {"period_id": "ISAT_FY2025", "period_label": "FY2025"},
        ]
        datapoints = [
            {"datapoint_id": "dp1", "metric_name": "Revenue", "value": 100},
            {"datapoint_id": "dp2", "metric_name": "Revenue", "value": 120},
        ]
        for_period = [
            {"from_id": "dp1", "to_id": "ISAT_FY2024"},
            {"from_id": "dp2", "to_id": "ISAT_FY2025"},
        ]

        edges = _build_trend_edges(datapoints, periods, for_period)
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# map_web_research
# ---------------------------------------------------------------------------


def _web_research_mapper_data() -> dict[str, Any]:
    """Return a minimal web-research input for testing."""
    return {
        "session_id": "web-research-test-001",
        "research_question": "日銀の金融政策動向",
        "sources": [
            {
                "url": "https://www.boj.or.jp/policy/2026/mar.html",
                "title": "日銀 金融政策決定会合（2026年3月）",
                "published_at": "2026-03-15",
                "source_type": "central_bank_report",
                "authority_level": "official",
            },
            {
                "url": "https://www.reuters.com/markets/boj-policy-2026",
                "title": "BOJ holds rates steady in March",
                "published_at": "2026-03-15",
                "source_type": "news_article",
                "authority_level": "media",
            },
        ],
        "facts": [
            {
                "content": "日銀は2026年3月の金融政策決定会合で金利を据え置いた",
                "source_url": "https://www.boj.or.jp/policy/2026/mar.html",
                "confidence": 0.95,
                "about_entities": [
                    {"name": "日本銀行", "entity_type": "organization"},
                    {"name": "日本", "entity_type": "country"},
                ],
            },
            {
                "content": "市場は次回会合での利上げを織り込んでいる",
                "source_url": "https://www.reuters.com/markets/boj-policy-2026",
                "confidence": 0.80,
                "about_entities": [
                    {"name": "日本銀行", "entity_type": "organization"},
                ],
            },
        ],
        "topics": [
            {"name": "金融政策", "category": "monetary_policy"},
            {"name": "日本経済", "category": "macro"},
        ],
    }


class TestMapWebResearch:
    """Tests for map_web_research mapper."""

    def test_正常系_基本マッピング_ソースとファクトとエンティティ(self) -> None:
        """sources/facts/entities が正しくマッピングされること。"""
        data = _web_research_mapper_data()
        result = map_web_research(data)

        assert result["session_id"] == "web-research-test-001"
        assert result["batch_label"] == "web-research"
        assert len(result["sources"]) == 2
        assert len(result["facts"]) == 2

        # Entity: 日本銀行, 日本 の2つ（重複排除後）
        entity_names = {e["name"] for e in result["entities"]}
        assert entity_names == {"日本銀行", "日本"}

        # Sources have authority_level from input
        for src in result["sources"]:
            assert "authority_level" in src
            assert "source_id" in src

    def test_正常系_全4リレーション種が生成される(self) -> None:
        """source_fact, fact_entity, tagged, extracted_from_fact の4種が存在すること。"""
        data = _web_research_mapper_data()
        result = map_web_research(data)
        rels = result["relations"]

        assert "source_fact" in rels
        assert "fact_entity" in rels
        assert "tagged" in rels
        assert "extracted_from_fact" in rels

        assert len(rels["source_fact"]) == 2
        assert len(rels["fact_entity"]) == 3  # 2 + 1 entity refs
        assert len(rels["tagged"]) > 0
        assert len(rels["extracted_from_fact"]) == 2

        # fact_entity uses RELATES_TO type
        for rel in rels["fact_entity"]:
            assert rel["type"] == "RELATES_TO"

        # extracted_from_fact has no 'type' field
        for rel in rels["extracted_from_fact"]:
            assert "type" not in rel

    def test_正常系_エンティティ重複排除(self) -> None:
        """同名+同typeのエンティティが重複しないことを確認。"""
        data = _web_research_mapper_data()
        # 日本銀行 appears in both facts
        result = map_web_research(data)

        entity_keys = [e["entity_key"] for e in result["entities"]]
        assert len(entity_keys) == len(set(entity_keys))

        # 日本銀行::organization should appear only once
        boj_entities = [e for e in result["entities"] if e["name"] == "日本銀行"]
        assert len(boj_entities) == 1
        assert boj_entities[0]["entity_key"] == "日本銀行::organization"

    def test_正常系_ソースURL紐付け_ファクトからソースへ(self) -> None:
        """extracted_from_fact でファクトが正しいソースに紐付くこと。"""
        data = _web_research_mapper_data()
        result = map_web_research(data)

        # Build source_id lookup by URL
        url_to_source_id = {s["url"]: s["source_id"] for s in result["sources"]}

        extracted_rels = result["relations"]["extracted_from_fact"]
        assert len(extracted_rels) == 2

        # Each fact's to_id should match its source_url's source_id
        fact_id_to_source_url = {}
        for f in result["facts"]:
            fact_id_to_source_url[f["fact_id"]] = data["facts"][
                result["facts"].index(f)
            ]["source_url"]

        for rel in extracted_rels:
            expected_source_id = url_to_source_id[fact_id_to_source_url[rel["from_id"]]]
            assert rel["to_id"] == expected_source_id

    def test_エッジケース_空のfacts配列(self) -> None:
        """facts=[] のとき正常に空結果が返ること。"""
        data = _web_research_mapper_data()
        data["facts"] = []
        result = map_web_research(data)

        assert result["facts"] == []
        assert result["entities"] == []
        assert result["relations"]["source_fact"] == []
        assert result["relations"]["fact_entity"] == []
        assert result["relations"]["extracted_from_fact"] == []
        # topics and tagged rels should still be present
        assert len(result["topics"]) == 2
        assert len(result["relations"]["tagged"]) > 0

    def test_エッジケース_about_entities未指定時(self) -> None:
        """about_entities が存在しないファクトで正常動作すること。"""
        data = _web_research_mapper_data()
        for fact in data["facts"]:
            del fact["about_entities"]
        result = map_web_research(data)

        assert result["entities"] == []
        assert result["relations"]["fact_entity"] == []
        # facts and source_fact rels should still exist
        assert len(result["facts"]) == 2
        assert len(result["relations"]["source_fact"]) == 2
