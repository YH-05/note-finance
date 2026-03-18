"""E2E dry-run tests for save-to-article-graph pipeline.

topic-discovery / wealth-scrape のグラフキュー生成とドライラン Cypher 出力を検証。
Neo4j 接続は不要。emit_graph_queue.py の出力がフォーマットに準拠し、
Cypher MERGE テンプレートに正しくマッピングできることを保証する。

Issue #134: [save-to-article-graph] D-1: E2E dry-run 検証
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
from emit_graph_queue import (
    _scan_wealth_directory,
    generate_source_id,
    generate_topic_id,
    map_topic_discovery,
    map_wealth_scrape,
    run,
)
from freezegun import freeze_time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FROZEN_TIME = "2026-03-16T12:00:00+00:00"
"""Fixed time for deterministic tests."""

GRAPH_QUEUE_REQUIRED_KEYS: set[str] = {
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
"""graph-queue JSON の必須トップレベルキー（v2.0）。"""

SOURCE_REQUIRED_KEYS: set[str] = {"source_id", "url", "title"}
"""sources 配列要素の必須キー（一般コマンド向け）。"""

# topic-discovery は特殊な Source 構造のため別途チェック
TOPIC_DISCOVERY_SOURCE_REQUIRED_KEYS: set[str] = {
    "source_id",
    "source_type",
    "command_source",
}
"""topic-discovery の sources 配列要素の必須キー。"""

TOPIC_REQUIRED_KEYS: set[str] = {"topic_id", "name", "category"}
"""topics 配列要素の必須キー。"""

ENTITY_REQUIRED_KEYS: set[str] = {"entity_id", "name", "entity_type"}
"""entities 配列要素の必須キー。"""

CLAIM_REQUIRED_KEYS: set[str] = {"claim_id", "content"}
"""claims 配列要素の必須キー。"""

FACT_REQUIRED_KEYS: set[str] = {"fact_id", "content"}
"""facts 配列要素の必須キー。"""

CHUNK_REQUIRED_KEYS: set[str] = {"chunk_id", "content"}
"""chunks 配列要素の必須キー。"""

# Cypher MERGE テンプレートパターン（パラメータ名をチェック）
CYPHER_NODE_LABELS: set[str] = {
    "Source",
    "Topic",
    "Entity",
    "Claim",
    "Fact",
    "Chunk",
    "Author",
    "FinancialDataPoint",
    "FiscalPeriod",
}
"""save-to-graph が MERGE するノードラベル一覧。"""

CYPHER_RELATION_TYPES: set[str] = {
    "TAGGED",
    "MAKES_CLAIM",
    "ABOUT",
    "STATES_FACT",
    "CONTAINS_CHUNK",
    "EXTRACTED_FROM",
    "HAS_DATAPOINT",
    "FOR_PERIOD",
    "RELATES_TO",
}
"""save-to-graph が MERGE するリレーションタイプ一覧。"""


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


def _topic_discovery_session() -> dict[str, Any]:
    """topic-discovery セッションのリアルなデータを生成。"""
    return {
        "session_id": "topic-suggestion-2026-03-16T1800",
        "generated_at": "2026-03-16T18:00:00+09:00",
        "parameters": {
            "category": None,
            "count": 5,
            "no_search": False,
        },
        "search_insights": {
            "queries_executed": 8,
            "trends": [
                {
                    "query": "S&P 500 weekly performance March 2026",
                    "source": "tavily",
                    "key_findings": [
                        "S&P 500 gained 2.1% on strong tech earnings",
                        "NVIDIA hit all-time high after AI revenue beat",
                    ],
                },
                {
                    "query": "日銀 金融政策 2026年3月",
                    "source": "gemini",
                    "key_findings": [
                        "日銀が追加利上げを見送り、ハト派姿勢を維持",
                    ],
                },
            ],
        },
        "content_gaps": {
            "category_distribution": {
                "market_report": 5,
                "stock_analysis": 3,
                "quant_analysis": 0,
            },
            "underserved_categories": ["quant_analysis"],
            "gap_topics": ["クオンツ分析の入門記事が不足"],
        },
        "suggestions": [
            {
                "rank": 1,
                "topic": "S&P 500 週次レビュー：AI銘柄が史上最高値を更新",
                "category": "market_report",
                "suggested_symbols": ["^GSPC", "NVDA", "MSFT"],
                "suggested_period": "2026-03-10 to 2026-03-16",
                "scores": {
                    "timeliness": 9,
                    "information_availability": 9,
                    "reader_interest": 8,
                    "feasibility": 9,
                    "uniqueness": 7,
                    "total": 42,
                },
                "rationale": "NVIDIAの好決算と市場のAI期待でS&P 500が週間で上昇。タイムリーな週次レビュー。",
                "key_points": [
                    "NVIDIA好決算の市場インパクト",
                    "テックセクター主導の上昇トレンド",
                    "VIXの低下と市場のリスク選好",
                ],
                "target_audience": "intermediate",
                "estimated_word_count": 4500,
                "selected": None,
            },
            {
                "rank": 2,
                "topic": "日銀の金融政策スタンスと円安の行方",
                "category": "macro_economy",
                "suggested_symbols": ["^N225", "USDJPY=X"],
                "suggested_period": "2026-03-01 to 2026-03-16",
                "scores": {
                    "timeliness": 8,
                    "information_availability": 7,
                    "reader_interest": 8,
                    "feasibility": 7,
                    "uniqueness": 6,
                    "total": 36,
                },
                "rationale": "日銀の政策据え置きで円安が進行。マクロ経済分析。",
                "key_points": [
                    "日銀のハト派姿勢の背景",
                    "ドル円150円突破の影響",
                ],
                "target_audience": "beginner",
                "estimated_word_count": 3500,
                "selected": None,
            },
            {
                "rank": 3,
                "topic": "2026年版 新NISA活用ガイド：最適ポートフォリオ構築",
                "category": "asset_management",
                "suggested_symbols": [],
                "suggested_period": "2026-03-01 to 2026-03-31",
                "scores": {
                    "timeliness": 6,
                    "information_availability": 8,
                    "reader_interest": 9,
                    "feasibility": 8,
                    "uniqueness": 5,
                    "total": 36,
                },
                "rationale": "NISAの活用記事は読者関心が高い。",
                "key_points": [
                    "NISA枠の最適配分",
                    "インデックスファンド比較",
                ],
                "target_audience": "beginner",
                "estimated_word_count": 5000,
                "selected": None,
            },
        ],
        "category_balance": {
            "market_report": 5,
            "stock_analysis": 3,
            "quant_analysis": 0,
        },
        "recommendation": "quant_analysis カテゴリの記事を優先的に執筆すべき",
    }


def _wealth_scrape_backfill_session() -> dict[str, Any]:
    """wealth-scrape backfill セッションのリアルなデータを生成。"""
    return {
        "session_id": "wealth-scrape-20260316-180000-000000",
        "timestamp": "2026-03-16T18:00:00+00:00",
        "mode": "backfill",
        "themes": {
            "data_driven_investing": {
                "name_en": "Data-Driven Investing",
                "keywords_en": [
                    "index fund",
                    "ETF",
                    "passive investing",
                    "portfolio",
                ],
                "articles": [
                    {
                        "url": "https://ofdollarsanddata.com/why-you-should-invest/",
                        "title": "Why You Should Invest: A Data-Driven Analysis",
                        "summary": "Data-driven analysis of long-term investing benefits using historical returns.",
                        "feed_source": "Of Dollars and Data",
                        "published": "2026-03-10T10:00:00+00:00",
                        "source_key": "ofdollarsanddata",
                        "domain": "ofdollarsanddata.com",
                    },
                    {
                        "url": "https://ofdollarsanddata.com/etf-comparison-2026/",
                        "title": "The Best ETF Comparison for 2026",
                        "summary": "Comparing major index ETFs by cost ratio and tracking error.",
                        "feed_source": "Of Dollars and Data",
                        "published": "2026-03-08T09:00:00+00:00",
                        "source_key": "ofdollarsanddata",
                        "domain": "ofdollarsanddata.com",
                    },
                ],
                "keywords_used": ["data-driven", "investing", "portfolio"],
            },
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
                        "title": "The Path to Financial Independence in 2026",
                        "summary": "A comprehensive guide to achieving FIRE with updated calculations.",
                        "feed_source": "Afford Anything",
                        "published": "2026-03-12T07:00:00+00:00",
                        "source_key": "affordanything",
                        "domain": "affordanything.com",
                    },
                ],
                "keywords_used": ["FIRE", "financial independence"],
            },
            "personal_finance": {
                "name_en": "Personal Finance",
                "keywords_en": [
                    "budgeting",
                    "save money",
                    "personal finance",
                    "emergency fund",
                ],
                "articles": [
                    {
                        "url": "https://moneycrashers.com/save-money-tips-2026/",
                        "title": "60 Ways to Save Money in 2026",
                        "summary": "Updated practical tips for reducing expenses and building emergency fund.",
                        "feed_source": "Money Crashers",
                        "published": "2026-03-05T08:00:00+00:00",
                        "source_key": "moneycrashers",
                        "domain": "moneycrashers.com",
                    },
                ],
                "keywords_used": ["savings", "budgeting", "personal finance"],
            },
        },
        "stats": {
            "total": 200,
            "filtered": 120,
            "matched": 40,
            "scraped": 30,
            "skipped": 10,
        },
    }


def _wealth_scrape_incremental_session() -> dict[str, Any]:
    """wealth-scrape incremental セッションのリアルなデータを生成。"""
    return {
        "session_id": "wealth-scrape-20260316-180000-000001",
        "timestamp": "2026-03-16T18:00:00+00:00",
        "mode": "incremental",
        "themes": {
            "dividend_income": {
                "name_en": "Dividend Income",
                "keywords_en": [
                    "dividend",
                    "yield",
                    "income investing",
                    "DRIP",
                ],
                "articles": [
                    {
                        "url": "https://seekingalpha.com/dividend-aristocrats-2026/",
                        "title": "Top Dividend Aristocrats for 2026 Income",
                        "summary": "Analysis of best dividend stocks with 25+ years of consecutive increases.",
                        "feed_source": "Seeking Alpha",
                        "published": "2026-03-15T14:00:00+00:00",
                        "source_key": "seekingalpha",
                        "domain": "seekingalpha.com",
                    },
                    {
                        "url": "https://investorplace.com/high-yield-etfs/",
                        "title": "Best High-Yield ETFs for Passive Income",
                        "summary": "Comparison of high-yield bond and equity ETFs for income seekers.",
                        "feed_source": "InvestorPlace",
                        "published": "2026-03-14T11:00:00+00:00",
                        "source_key": "investorplace",
                        "domain": "investorplace.com",
                    },
                ],
                "keywords_used": ["dividend", "yield", "income"],
            },
        },
        "stats": {
            "total": 50,
            "filtered": 35,
            "matched": 15,
            "scraped": 0,
            "skipped": 0,
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_queue_file(
    tmp_path: Path,
    command: str,
    data: dict[str, Any],
) -> Path:
    """キューファイルを生成して出力ファイルパスを返す。"""
    input_file = tmp_path / f"{command}-input.json"
    input_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    output_base = tmp_path / "graph-queue"
    exit_code = run(
        command=command,
        input_path=input_file,
        output_base=output_base,
        cleanup=False,
    )
    assert exit_code == 0, f"Queue generation failed for {command}"

    output_files = list(output_base.glob(f"{command}/*.json"))
    assert len(output_files) >= 1, f"Expected at least 1 output file for {command}"
    return output_files[0]


def _load_queue_file(path: Path) -> dict[str, Any]:
    """キューファイルを読み込んで辞書として返す。"""
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _generate_cypher_merge_statements(queue_data: dict[str, Any]) -> list[str]:
    """graph-queue JSON から dry-run 用 Cypher MERGE 文を生成する。

    save-to-graph スキルの Cypher テンプレートと同等のロジックで、
    各ノードとリレーションの MERGE 文を生成する。
    Neo4j 接続は不要。

    Parameters
    ----------
    queue_data : dict[str, Any]
        graph-queue JSON データ。

    Returns
    -------
    list[str]
        生成された Cypher MERGE 文のリスト。
    """
    statements: list[str] = []

    # --- Node MERGE statements ---

    for source in queue_data.get("sources", []):
        sid = source.get("source_id", "")
        statements.append(
            f"MERGE (s:Source {{source_id: '{sid}'}})\n"
            f"SET s.url = '{source.get('url', '')}', "
            f"s.title = '{_escape_cypher(source.get('title', ''))}', "
            f"s.command_source = '{queue_data.get('command_source', '')}'"
        )

    for topic in queue_data.get("topics", []):
        tid = topic.get("topic_id", "")
        name = _escape_cypher(topic.get("name", ""))
        cat = topic.get("category", "")
        statements.append(
            f"MERGE (t:Topic {{topic_id: '{tid}'}})\n"
            f"SET t.name = '{name}', "
            f"t.category = '{cat}', "
            f"t.topic_key = '{name}::{cat}'"
        )

    for entity in queue_data.get("entities", []):
        eid = entity.get("entity_id", "")
        ename = _escape_cypher(entity.get("name", ""))
        etype = entity.get("entity_type", "")
        statements.append(
            f"MERGE (e:Entity {{entity_id: '{eid}'}})\n"
            f"SET e.name = '{ename}', "
            f"e.entity_type = '{etype}', "
            f"e.entity_key = '{ename}::{etype}'"
        )

    for claim in queue_data.get("claims", []):
        cid = claim.get("claim_id", "")
        content = _escape_cypher(claim.get("content", ""))
        statements.append(
            f"MERGE (c:Claim {{claim_id: '{cid}'}})\nSET c.content = '{content}'"
        )

    for fact in queue_data.get("facts", []):
        fid = fact.get("fact_id", "")
        fcontent = _escape_cypher(fact.get("content", ""))
        statements.append(
            f"MERGE (f:Fact {{fact_id: '{fid}'}})\nSET f.content = '{fcontent}'"
        )

    for chunk in queue_data.get("chunks", []):
        chid = chunk.get("chunk_id", "")
        statements.append(
            f"MERGE (ch:Chunk {{chunk_id: '{chid}'}})\n"
            f"SET ch.chunk_index = {chunk.get('chunk_index', 0)}"
        )

    # --- Relation MERGE statements ---

    relations = queue_data.get("relations", {})

    for tagged in relations.get("tagged", []):
        from_id = tagged.get("from_id", tagged.get("source_id", ""))
        to_id = tagged.get("to_id", tagged.get("topic_id", ""))
        statements.append(
            f"MATCH (a {{source_id: '{from_id}'}}), (b {{topic_id: '{to_id}'}})\n"
            f"MERGE (a)-[:TAGGED]->(b)"
        )

    for sc in relations.get("source_claim", []):
        statements.append(
            f"MATCH (s {{source_id: '{sc['from_id']}'}}), "
            f"(c {{claim_id: '{sc['to_id']}'}})\n"
            f"MERGE (s)-[:MAKES_CLAIM]->(c)"
        )

    for ce in relations.get("claim_entity", []):
        statements.append(
            f"MATCH (c {{claim_id: '{ce['from_id']}'}}), "
            f"(e {{entity_id: '{ce['to_id']}'}})\n"
            f"MERGE (c)-[:ABOUT]->(e)"
        )

    for sf in relations.get("source_fact", []):
        statements.append(
            f"MATCH (s {{source_id: '{sf['from_id']}'}}), "
            f"(f {{fact_id: '{sf['to_id']}'}})\n"
            f"MERGE (s)-[:STATES_FACT]->(f)"
        )

    return statements


def _escape_cypher(text: str) -> str:
    """Cypher 文字列リテラル内の特殊文字をエスケープする。"""
    return text.replace("\\", "\\\\").replace("'", "\\'")


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
                    "fire_wealth_building": {
                        "name_en": "FIRE & Wealth Building",
                        "keywords_en": ["FIRE", "financial independence"],
                        "target_sources": ["affordanything", "madfientist"],
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
    """Create a wealth-scrape directory with three domains and sample articles."""
    wealth_dir = tmp_path / "wealth"
    wealth_dir.mkdir()

    # Domain 1: ofdollarsanddata.com (2 articles)
    domain1 = wealth_dir / "ofdollarsanddata.com"
    domain1.mkdir()
    _create_wealth_md(
        domain1,
        url="https://ofdollarsanddata.com/why-you-should-invest/",
        title="Why You Should Invest with ETF Strategy",
        published="2026-03-10T10:00:00+00:00",
        source="Of Dollars and Data",
        domain="ofdollarsanddata.com",
        body="Data-driven analysis of long-term investing benefits.",
    )
    _create_wealth_md(
        domain1,
        url="https://ofdollarsanddata.com/saving-vs-investing/",
        title="Saving vs Investing: A Quantitative Analysis",
        published="2026-03-08T09:00:00+00:00",
        source="Of Dollars and Data",
        domain="ofdollarsanddata.com",
        body="Comparing savings accounts and investment returns over 30 years.",
    )

    # Domain 2: moneycrashers.com (1 article)
    domain2 = wealth_dir / "moneycrashers.com"
    domain2.mkdir()
    _create_wealth_md(
        domain2,
        url="https://moneycrashers.com/save-money-tips/",
        title="50 Ways to Save Money on Personal Finance",
        published="2026-03-05T08:00:00+00:00",
        source="Money Crashers",
        domain="moneycrashers.com",
        body="Practical tips for reducing expenses and building emergency fund.",
    )

    # Domain 3: affordanything.com (1 article)
    domain3 = wealth_dir / "affordanything.com"
    domain3.mkdir()
    _create_wealth_md(
        domain3,
        url="https://affordanything.com/financial-independence/",
        title="The Path to Financial Independence and FIRE",
        published="2026-03-12T07:00:00+00:00",
        source="Afford Anything",
        domain="affordanything.com",
        body="A comprehensive guide to achieving financial independence.",
    )

    return wealth_dir


# ---------------------------------------------------------------------------
# E2E: topic-discovery graph-queue 生成検証
# ---------------------------------------------------------------------------


class TestTopicDiscoveryGraphQueue:
    """topic-discovery の graph-queue JSON が正常に生成されることを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_キューファイルが生成されフォーマット準拠(
        self, tmp_path: Path
    ) -> None:
        """受け入れ条件1: topic-discovery の graph-queue JSON が正常生成。"""
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        missing = GRAPH_QUEUE_REQUIRED_KEYS - set(q.keys())
        assert not missing, f"Missing keys: {missing}"
        assert q["schema_version"] == "2.2"
        assert q["command_source"] == "topic-discovery"

    @freeze_time(FROZEN_TIME)
    def test_正常系_ソースノードが1つ生成される(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        assert len(q["sources"]) == 1
        src = q["sources"][0]
        for key in TOPIC_DISCOVERY_SOURCE_REQUIRED_KEYS:
            assert key in src, f"Source missing key: {key}"
        assert src["source_id"] == "topic-suggestion-2026-03-16T1800"
        assert src["source_type"] == "original"

    @freeze_time(FROZEN_TIME)
    def test_正常系_トピックノードがカテゴリ数と一致(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        # 3 suggestions with 3 distinct categories
        assert len(q["topics"]) == 3
        for topic in q["topics"]:
            missing = TOPIC_REQUIRED_KEYS - set(topic.keys())
            assert not missing, f"Topic missing keys: {missing}"
            assert topic["category"] == "content_planning"

    @freeze_time(FROZEN_TIME)
    def test_正常系_クレイムノードが提案数と一致(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        assert len(q["claims"]) == 3
        for claim in q["claims"]:
            missing = CLAIM_REQUIRED_KEYS - set(claim.keys())
            assert not missing, f"Claim missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_エンティティノードがティッカーから生成(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        # Symbols: ^GSPC, NVDA, MSFT, ^N225, USDJPY=X (rank3 has [])
        entity_ids = {e["entity_id"] for e in q["entities"]}
        assert len(q["entities"]) == 5
        assert "symbol:^GSPC" in entity_ids
        assert "symbol:NVDA" in entity_ids
        assert "symbol:MSFT" in entity_ids
        assert "symbol:^N225" in entity_ids
        assert "symbol:USDJPY=X" in entity_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_ファクトノードがトレンドから生成(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        # 2 trends: first has 2 findings, second has 1 = 3 facts total
        assert len(q["facts"]) == 3
        for fact in q["facts"]:
            missing = FACT_REQUIRED_KEYS - set(fact.keys())
            assert not missing, f"Fact missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_4種のリレーションが全て存在(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        rels = q["relations"]
        assert len(rels.get("tagged", [])) > 0, "tagged リレーションが必要"
        assert len(rels.get("source_claim", [])) > 0, "source_claim リレーションが必要"
        assert len(rels.get("claim_entity", [])) > 0, "claim_entity リレーションが必要"
        assert len(rels.get("source_fact", [])) > 0, "source_fact リレーションが必要"

    @freeze_time(FROZEN_TIME)
    def test_正常系_IDが全て文字列ベースで冪等(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        f1 = _generate_queue_file(dir1, "topic-discovery", data)
        q1 = _load_queue_file(f1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        f2 = _generate_queue_file(dir2, "topic-discovery", data)
        q2 = _load_queue_file(f2)

        # Source IDs match
        assert q1["sources"][0]["source_id"] == q2["sources"][0]["source_id"]

        # Topic IDs match
        ids1 = sorted(t["topic_id"] for t in q1["topics"])
        ids2 = sorted(t["topic_id"] for t in q2["topics"])
        assert ids1 == ids2

        # Claim IDs match
        cids1 = sorted(c["claim_id"] for c in q1["claims"])
        cids2 = sorted(c["claim_id"] for c in q2["claims"])
        assert cids1 == cids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_キューファイル名がgqプレフィックスで始まる(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        assert output_file.name.startswith("gq-")
        assert output_file.name.endswith(".json")


# ---------------------------------------------------------------------------
# E2E: wealth-scrape graph-queue 生成検証
# ---------------------------------------------------------------------------


class TestWealthScrapeGraphQueue:
    """wealth-scrape の graph-queue JSON がドメインごとに分割生成されることを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_backfillデータからキューファイルが生成(
        self, tmp_path: Path
    ) -> None:
        """受け入れ条件2: wealth-scrape の graph-queue JSON がドメインごとに分割生成。"""
        data = _wealth_scrape_backfill_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        missing = GRAPH_QUEUE_REQUIRED_KEYS - set(q.keys())
        assert not missing, f"Missing keys: {missing}"
        assert q["schema_version"] == "2.2"
        assert q["command_source"] == "wealth-scrape"

    @freeze_time(FROZEN_TIME)
    def test_正常系_ディレクトリ入力でドメイン別に複数ファイル生成(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """受け入れ条件2: ディレクトリ入力で wealth-scrape がドメインごとに分割される。"""
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)
        output_dir = tmp_path / "graph-queue"

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
        # 3 domains -> 3 separate graph-queue files
        assert len(output_files) == 3, (
            f"Expected 3 domain-split files, got {len(output_files)}"
        )

        # 各ファイルが標準フォーマットに準拠
        domain_labels: set[str] = set()
        for f in output_files:
            q = _load_queue_file(f)
            missing = GRAPH_QUEUE_REQUIRED_KEYS - set(q.keys())
            assert not missing, f"File {f.name} missing keys: {missing}"
            assert q["command_source"] == "wealth-scrape"
            domain_labels.add(q["batch_label"])

        # 各ファイルが異なるバッチラベル（ドメイン名ベース）
        assert len(domain_labels) == 3

    @freeze_time(FROZEN_TIME)
    def test_正常系_backfillのsources数が記事数と一致(self, tmp_path: Path) -> None:
        data = _wealth_scrape_backfill_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        # 3 themes with 2+1+1 = 4 articles
        expected_articles = sum(
            len(theme.get("articles", [])) for theme in data["themes"].values()
        )
        assert len(q["sources"]) == expected_articles

    @freeze_time(FROZEN_TIME)
    def test_正常系_backfillのtopics数がテーマ数と一致(self, tmp_path: Path) -> None:
        data = _wealth_scrape_backfill_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        assert len(q["topics"]) == len(data["themes"])
        for topic in q["topics"]:
            missing = TOPIC_REQUIRED_KEYS - set(topic.keys())
            assert not missing, f"Topic missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_incrementalデータからキューファイルが生成(
        self, tmp_path: Path
    ) -> None:
        data = _wealth_scrape_incremental_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        assert q["command_source"] == "wealth-scrape"
        assert len(q["sources"]) == 2
        assert len(q["topics"]) == 1
        assert len(q["claims"]) == 2  # 2 articles with summaries

    @freeze_time(FROZEN_TIME)
    def test_正常系_source_idが冪等(self, tmp_path: Path) -> None:
        data = _wealth_scrape_backfill_session()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        f1 = _generate_queue_file(dir1, "wealth-scrape", data)
        q1 = _load_queue_file(f1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        f2 = _generate_queue_file(dir2, "wealth-scrape", data)
        q2 = _load_queue_file(f2)

        ids1 = sorted(s["source_id"] for s in q1["sources"])
        ids2 = sorted(s["source_id"] for s in q2["sources"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_ディレクトリ入力の各ファイルにsourcesとtopicsが存在(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wealth_dir = _create_wealth_directory(tmp_path)
        config_path = _create_wealth_theme_config(tmp_path)
        output_dir = tmp_path / "graph-queue"

        import emit_graph_queue

        monkeypatch.setattr(emit_graph_queue, "WEALTH_THEME_CONFIG_PATH", config_path)

        run(
            command="wealth-scrape",
            input_path=wealth_dir,
            output_base=output_dir,
            cleanup=False,
        )

        output_files = list(output_dir.glob("wealth-scrape/*.json"))
        for f in output_files:
            q = _load_queue_file(f)
            assert len(q["sources"]) >= 1, f"File {f.name} has no sources"
            # Each domain file should have at least 1 source


# ---------------------------------------------------------------------------
# E2E: dry-run Cypher 出力検証
# ---------------------------------------------------------------------------


class TestDryRunCypherOutput:
    """graph-queue JSON から dry-run Cypher MERGE 文が正しく生成されることを検証。

    受け入れ条件3: dry-run で Cypher が正常出力。
    """

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのCypher文にMERGEが含まれる(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)
        assert len(statements) > 0, "Cypher statements should be generated"

        # All statements should contain MERGE
        for stmt in statements:
            assert "MERGE" in stmt, f"Statement missing MERGE: {stmt[:80]}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryの全ノードラベルがCypherに含まれる(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)
        all_cypher = "\n".join(statements)

        # topic-discovery が生成するノード: Source, Topic, Claim, Entity, Fact
        expected_labels = {"Source", "Topic", "Claim", "Entity", "Fact"}
        for label in expected_labels:
            assert f":{label}" in all_cypher, (
                f"Node label '{label}' not found in Cypher"
            )

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのリレーションタイプがCypherに含まれる(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)
        all_cypher = "\n".join(statements)

        expected_rels = {"TAGGED", "MAKES_CLAIM", "ABOUT", "STATES_FACT"}
        for rel in expected_rels:
            assert f":{rel}]" in all_cypher or f"[:{rel}]" in all_cypher, (
                f"Relation type '{rel}' not found in Cypher"
            )

    @freeze_time(FROZEN_TIME)
    def test_正常系_wealth_scrapeのCypher文にMERGEが含まれる(
        self, tmp_path: Path
    ) -> None:
        data = _wealth_scrape_backfill_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)
        assert len(statements) > 0, "Cypher statements should be generated"

        for stmt in statements:
            assert "MERGE" in stmt, f"Statement missing MERGE: {stmt[:80]}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_wealth_scrapeのノードラベルがCypherに含まれる(
        self, tmp_path: Path
    ) -> None:
        data = _wealth_scrape_backfill_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)
        all_cypher = "\n".join(statements)

        # wealth-scrape backfill が生成するノード: Source, Topic, Entity
        expected_labels = {"Source", "Topic", "Entity"}
        for label in expected_labels:
            assert f":{label}" in all_cypher, (
                f"Node label '{label}' not found in wealth-scrape Cypher"
            )

    @freeze_time(FROZEN_TIME)
    def test_正常系_Cypher文のMERGEキーにIDが含まれる(self, tmp_path: Path) -> None:
        """各 MERGE 文が一意 ID プロパティを使用していることを検証。"""
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)

        # ID patterns that should appear in MERGE clauses
        id_patterns = [
            r"source_id:",
            r"topic_id:",
            r"entity_id:",
            r"claim_id:",
            r"fact_id:",
        ]
        found_patterns: set[str] = set()
        for stmt in statements:
            for pattern in id_patterns:
                if re.search(pattern, stmt):
                    found_patterns.add(pattern)

        expected = {
            r"source_id:",
            r"topic_id:",
            r"entity_id:",
            r"claim_id:",
            r"fact_id:",
        }
        missing = expected - found_patterns
        assert not missing, f"Missing ID patterns in MERGE: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_Cypher文の数がノード数とリレーション数の合計と一致(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        statements = _generate_cypher_merge_statements(q)

        # Count expected statements
        expected_nodes = (
            len(q["sources"])
            + len(q["topics"])
            + len(q["entities"])
            + len(q["claims"])
            + len(q["facts"])
            + len(q["chunks"])
        )
        rels = q["relations"]
        expected_rels = (
            len(rels.get("tagged", []))
            + len(rels.get("source_claim", []))
            + len(rels.get("claim_entity", []))
            + len(rels.get("source_fact", []))
        )

        assert len(statements) == expected_nodes + expected_rels


# ---------------------------------------------------------------------------
# E2E: topic-discovery + wealth-scrape ノード数・データ量テスト
# ---------------------------------------------------------------------------


class TestArticleGraphNodeCounts:
    """article-graph 対象コマンドのノード数が入力データと一致することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのsource数は常に1(self, tmp_path: Path) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)
        assert len(q["sources"]) == 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのclaim数がsuggestion数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)
        assert len(q["claims"]) == len(data["suggestions"])

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのentity数がユニークティッカー数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        unique_symbols: set[str] = set()
        for s in data["suggestions"]:
            for sym in s.get("suggested_symbols", []):
                unique_symbols.add(sym)

        assert len(q["entities"]) == len(unique_symbols)

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのfact数がkey_findings総数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        total_findings = sum(
            len(trend.get("key_findings", []))
            for trend in data["search_insights"]["trends"]
        )
        assert len(q["facts"]) == total_findings

    @freeze_time(FROZEN_TIME)
    def test_正常系_wealth_scrape_backfillのentity数がドメイン数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _wealth_scrape_backfill_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        # backfill: domain entities from all articles' domain field
        unique_domains: set[str] = set()
        for theme in data["themes"].values():
            for article in theme.get("articles", []):
                domain = article.get("domain", "")
                if domain:
                    unique_domains.add(domain)

        assert len(q["entities"]) == len(unique_domains)


# ---------------------------------------------------------------------------
# E2E: article-graph リレーション整合性テスト
# ---------------------------------------------------------------------------


class TestArticleGraphRelationIntegrity:
    """リレーションの from_id / to_id がノード配列内に存在することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_topic_discoveryのリレーション参照がノードに存在(
        self, tmp_path: Path
    ) -> None:
        data = _topic_discovery_session()
        output_file = _generate_queue_file(tmp_path, "topic-discovery", data)
        q = _load_queue_file(output_file)

        source_ids = {s["source_id"] for s in q["sources"]}
        topic_ids = {t["topic_id"] for t in q["topics"]}
        claim_ids = {c["claim_id"] for c in q["claims"]}
        entity_ids = {e["entity_id"] for e in q["entities"]}
        fact_ids = {f["fact_id"] for f in q["facts"]}
        rels = q["relations"]

        # tagged: from=source/claim, to=topic
        for r in rels.get("tagged", []):
            from_id = r.get("from_id", "")
            to_id = r.get("to_id", "")
            assert from_id in source_ids | claim_ids, (
                f"tagged from_id {from_id} not in sources or claims"
            )
            assert to_id in topic_ids, f"tagged to_id {to_id} not in topics"

        # source_claim: from=source, to=claim
        for r in rels.get("source_claim", []):
            assert r["from_id"] in source_ids, (
                f"source_claim from_id {r['from_id']} not in sources"
            )
            assert r["to_id"] in claim_ids, (
                f"source_claim to_id {r['to_id']} not in claims"
            )

        # claim_entity: from=claim, to=entity
        for r in rels.get("claim_entity", []):
            assert r["from_id"] in claim_ids, (
                f"claim_entity from_id {r['from_id']} not in claims"
            )
            assert r["to_id"] in entity_ids, (
                f"claim_entity to_id {r['to_id']} not in entities"
            )

        # source_fact: from=source, to=fact
        for r in rels.get("source_fact", []):
            assert r["from_id"] in source_ids, (
                f"source_fact from_id {r['from_id']} not in sources"
            )
            assert r["to_id"] in fact_ids, (
                f"source_fact to_id {r['to_id']} not in facts"
            )

    @freeze_time(FROZEN_TIME)
    def test_正常系_wealth_scrapeのリレーション参照がノードに存在(
        self, tmp_path: Path
    ) -> None:
        data = _wealth_scrape_incremental_session()
        output_file = _generate_queue_file(tmp_path, "wealth-scrape", data)
        q = _load_queue_file(output_file)

        source_ids = {s["source_id"] for s in q["sources"]}
        topic_ids = {t["topic_id"] for t in q["topics"]}
        claim_ids = {c["claim_id"] for c in q["claims"]}
        rels = q["relations"]

        # source_claim: from=source, to=claim
        for r in rels.get("source_claim", []):
            assert r["from_id"] in source_ids
            assert r["to_id"] in claim_ids

        # tagged: from=source, to=topic
        for r in rels.get("tagged", []):
            from_id = r.get("from_id", "")
            to_id = r.get("to_id", "")
            assert from_id in source_ids, f"tagged from_id {from_id} not in sources"
            assert to_id in topic_ids, f"tagged to_id {to_id} not in topics"


# ---------------------------------------------------------------------------
# E2E: 全8コマンド統合テスト
# ---------------------------------------------------------------------------


class TestAllCommandsPipeline:
    """wealth-scrape・topic-discovery を含む全8コマンドのキュー生成を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_8コマンド全てが登録されている(self) -> None:
        """COMMANDS リストに全8コマンドが含まれることを確認。"""
        from emit_graph_queue import COMMANDS

        expected = {
            "finance-news-workflow",
            "ai-research-collect",
            "generate-market-report",
            "asset-management",
            "reddit-finance-topics",
            "finance-full",
            "pdf-extraction",
            "wealth-scrape",
            "topic-discovery",
        }
        actual = set(COMMANDS)
        missing = expected - actual
        assert not missing, f"COMMANDS に不足: {missing}"
