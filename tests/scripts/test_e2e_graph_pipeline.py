"""E2E integration tests for graph-queue pipeline.

graph-queue 生成 → フォーマット検証 → 冪等性確認の一連の流れを検証。
Neo4j 接続は不要で、emit_graph_queue.py の出力品質と冪等性を保証する。

Issue #50: [Wave3] save-to-graph E2E 検証・冪等性テスト
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from emit_graph_queue import (
    generate_claim_id,
    generate_entity_id,
    generate_source_id,
    generate_topic_id,
    run,
)
from freezegun import freeze_time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FROZEN_TIME = "2026-03-07T12:00:00+00:00"
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
"""sources 配列要素の必須キー。"""

TOPIC_REQUIRED_KEYS: set[str] = {"topic_id", "name", "category"}
"""topics 配列要素の必須キー。"""

ENTITY_REQUIRED_KEYS: set[str] = {"entity_id", "name", "entity_type"}
"""entities 配列要素の必須キー。"""

CLAIM_REQUIRED_KEYS: set[str] = {"claim_id", "content"}
"""claims 配列要素の必須キー。"""


# ---------------------------------------------------------------------------
# Test Data Fixtures
# ---------------------------------------------------------------------------


def _realistic_news_batch(theme_key: str = "index") -> dict[str, Any]:
    """finance-news-workflow のリアルなバッチデータを生成。"""
    return {
        "session_id": "news-20260307-120000",
        "batch_label": theme_key,
        "articles": [
            {
                "url": "https://www.cnbc.com/2026/03/07/sp500-record.html",
                "title": "S&P 500 hits all-time high as tech rally continues",
                "summary": "The S&P 500 index closed at a record high, driven by gains in technology stocks.",
                "feed_source": "CNBC - Markets",
                "published": "2026-03-07T10:00:00+00:00",
            },
            {
                "url": "https://www.cnbc.com/2026/03/07/nasdaq-surge.html",
                "title": "Nasdaq surges 2% on AI chip demand optimism",
                "summary": "The Nasdaq composite surged as investors bet on continued AI infrastructure spending.",
                "feed_source": "CNBC - Markets",
                "published": "2026-03-07T11:30:00+00:00",
            },
            {
                "url": "https://www.reuters.com/2026/03/07/markets-wrap.html",
                "title": "Global markets rally on positive economic data",
                "summary": "Global equities advanced as strong employment data eased recession fears.",
                "feed_source": "Reuters",
                "published": "2026-03-07T14:00:00+00:00",
            },
        ],
    }


def _realistic_ai_research_batch() -> dict[str, Any]:
    """ai-research-collect のリアルなバッチデータを生成。"""
    return {
        "session_id": "ai-research-20260307-120000",
        "companies": [
            {
                "company_name": "NVIDIA",
                "ticker": "NVDA",
                "url": "https://example.com/nvidia-ai-revenue-q4-2026",
                "title": "NVIDIA Q4 2026 AI Revenue Analysis",
                "summary": "NVIDIA data center revenue exceeded expectations.",
                "published": "2026-03-07T08:00:00+00:00",
            },
            {
                "company_name": "AMD",
                "ticker": "AMD",
                "url": "https://example.com/amd-mi300x-adoption",
                "title": "AMD MI300X Enterprise Adoption Report",
                "summary": "AMD's MI300X gains traction in enterprise AI workloads.",
                "published": "2026-03-07T09:00:00+00:00",
            },
        ],
    }


def _realistic_market_report() -> dict[str, Any]:
    """generate-market-report のリアルなデータを生成。"""
    return {
        "session_id": "market-report-20260307",
        "report_date": "2026-03-07",
        "sections": [
            {
                "title": "Weekly Market Summary",
                "content": "Major indices posted gains this week. The S&P 500 rose 1.8%.",
                "sources": [
                    {
                        "url": "https://www.cnbc.com/2026/03/07/weekly-recap.html",
                        "title": "Weekly Market Recap",
                        "published": "2026-03-07T16:00:00+00:00",
                    },
                    {
                        "url": "https://www.bloomberg.com/2026/03/07/markets.html",
                        "title": "Bloomberg Markets Summary",
                        "published": "2026-03-07T16:30:00+00:00",
                    },
                ],
            },
            {
                "title": "Sector Performance",
                "content": "Technology and healthcare sectors led gains while energy lagged.",
                "sources": [
                    {
                        "url": "https://www.reuters.com/2026/03/07/sectors.html",
                        "title": "Sector Analysis",
                        "published": "2026-03-07T15:00:00+00:00",
                    },
                ],
            },
        ],
    }


def _realistic_asset_management_batch() -> dict[str, Any]:
    """asset-management のリアルなバッチデータを生成。"""
    return {
        "session_id": "asset-mgmt-20260307-120000",
        "themes": {
            "nisa": {
                "articles": [
                    {
                        "url": "https://example.com/nisa-2026-update",
                        "title": "2026年NISA制度の最新動向",
                        "summary": "新NISA制度の利用者数が1000万人を突破。",
                        "feed_source": "日経",
                        "published": "2026-03-07T06:00:00+00:00",
                    },
                ],
                "name_ja": "NISA制度",
            },
            "ideco": {
                "articles": [
                    {
                        "url": "https://example.com/ideco-reform",
                        "title": "iDeCo制度改正の影響分析",
                        "summary": "iDeCo拠出限度額引き上げの影響を分析。",
                        "feed_source": "東洋経済",
                        "published": "2026-03-07T07:00:00+00:00",
                    },
                ],
                "name_ja": "iDeCo",
            },
        },
    }


def _realistic_reddit_batch() -> dict[str, Any]:
    """reddit-finance-topics のリアルなバッチデータを生成。"""
    return {
        "session_id": "reddit-topics-20260307",
        "topics": [
            {
                "name": "VOO vs VTI for long-term investing",
                "url": "https://reddit.com/r/investing/comments/abc123",
                "title": "VOO vs VTI: Which is better for 30-year horizon?",
                "summary": "Community discusses S&P 500 vs Total Market for retirement.",
                "subreddit": "r/investing",
                "published": "2026-03-06T18:00:00+00:00",
                "score": 342,
            },
        ],
    }


def _realistic_finance_full() -> dict[str, Any]:
    """finance-full のリアルなデータを生成。"""
    return {
        "session_id": "finance-full-20260307",
        "sources": [
            {
                "url": "https://example.com/ai-investment-thesis",
                "title": "AI Investment Thesis 2026",
                "published": "2026-03-07T10:00:00+00:00",
            },
        ],
        "claims": [
            {
                "content": "AI semiconductor market is expected to grow 45% YoY in 2026.",
                "source_url": "https://example.com/ai-investment-thesis",
                "category": "ai",
            },
        ],
    }


ALL_COMMAND_DATA: dict[str, tuple[str, Any]] = {
    "finance-news-workflow": ("finance-news-workflow", _realistic_news_batch),
    "ai-research-collect": ("ai-research-collect", _realistic_ai_research_batch),
    "generate-market-report": ("generate-market-report", _realistic_market_report),
    "asset-management": ("asset-management", _realistic_asset_management_batch),
    "reddit-finance-topics": ("reddit-finance-topics", _realistic_reddit_batch),
    "finance-full": ("finance-full", _realistic_finance_full),
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
    assert len(output_files) == 1, f"Expected 1 output file for {command}"
    return output_files[0]


def _load_queue_file(path: Path) -> dict[str, Any]:
    """キューファイルを読み込んで辞書として返す。"""
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# E2E: graph-queue フォーマット準拠テスト
# ---------------------------------------------------------------------------


class TestGraphQueueFormatCompliance:
    """graph-queue JSON が標準フォーマットに準拠することを検証。"""

    @freeze_time(FROZEN_TIME)
    @pytest.mark.parametrize(
        "command",
        [
            "finance-news-workflow",
            "ai-research-collect",
            "generate-market-report",
            "asset-management",
            "reddit-finance-topics",
            "finance-full",
        ],
    )
    def test_正常系_全コマンドのキューファイルが必須キーを持つ(
        self, tmp_path: Path, command: str
    ) -> None:
        _, data_fn = ALL_COMMAND_DATA[command]
        output_file = _generate_queue_file(tmp_path, command, data_fn())
        data = _load_queue_file(output_file)

        missing = GRAPH_QUEUE_REQUIRED_KEYS - set(data.keys())
        assert not missing, f"Missing keys for {command}: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_schema_versionが2_0(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "finance-news-workflow", _realistic_news_batch()
        )
        data = _load_queue_file(output_file)
        assert data["schema_version"] == "2.0"

    @freeze_time(FROZEN_TIME)
    def test_正常系_queue_idがgqプレフィックスで始まる(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "finance-news-workflow", _realistic_news_batch()
        )
        data = _load_queue_file(output_file)
        assert data["queue_id"].startswith("gq-")

    @freeze_time(FROZEN_TIME)
    def test_正常系_created_atがISO8601形式(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "finance-news-workflow", _realistic_news_batch()
        )
        data = _load_queue_file(output_file)
        # ISO 8601: should contain 'T' and timezone info
        assert "T" in data["created_at"]

    @freeze_time(FROZEN_TIME)
    def test_正常系_sources配列要素が必須キーを持つ(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "finance-news-workflow", _realistic_news_batch()
        )
        data = _load_queue_file(output_file)

        for source in data["sources"]:
            missing = SOURCE_REQUIRED_KEYS - set(source.keys())
            assert not missing, f"Source missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_topics配列要素が必須キーを持つ(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "asset-management", _realistic_asset_management_batch()
        )
        data = _load_queue_file(output_file)

        assert len(data["topics"]) > 0
        for topic in data["topics"]:
            missing = TOPIC_REQUIRED_KEYS - set(topic.keys())
            assert not missing, f"Topic missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_entities配列要素が必須キーを持つ(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "ai-research-collect", _realistic_ai_research_batch()
        )
        data = _load_queue_file(output_file)

        assert len(data["entities"]) > 0
        for entity in data["entities"]:
            missing = ENTITY_REQUIRED_KEYS - set(entity.keys())
            assert not missing, f"Entity missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_claims配列要素が必須キーを持つ(self, tmp_path: Path) -> None:
        output_file = _generate_queue_file(
            tmp_path, "finance-news-workflow", _realistic_news_batch()
        )
        data = _load_queue_file(output_file)

        assert len(data["claims"]) > 0
        for claim in data["claims"]:
            missing = CLAIM_REQUIRED_KEYS - set(claim.keys())
            assert not missing, f"Claim missing keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_command_sourceが入力コマンドと一致(self, tmp_path: Path) -> None:
        for command, (_, data_fn) in ALL_COMMAND_DATA.items():
            sub_dir = tmp_path / command
            sub_dir.mkdir(parents=True, exist_ok=True)
            output_file = _generate_queue_file(sub_dir, command, data_fn())
            data = _load_queue_file(output_file)
            assert data["command_source"] == command


# ---------------------------------------------------------------------------
# E2E: 冪等性テスト
# ---------------------------------------------------------------------------


class TestIdempotency:
    """同じデータから同じ ID が生成され、冪等投入が可能なことを検証。"""

    def test_正常系_同じURLから同じsource_idが生成される(self) -> None:
        urls = [
            "https://www.cnbc.com/2026/03/07/sp500-record.html",
            "https://www.reuters.com/2026/03/07/markets-wrap.html",
            "https://example.com/nvidia-ai-revenue-q4-2026",
        ]
        for url in urls:
            id1 = generate_source_id(url)
            id2 = generate_source_id(url)
            assert id1 == id2, f"source_id mismatch for {url}"

    def test_正常系_同じtopic情報から同じtopic_idが生成される(self) -> None:
        topics = [
            ("NISA制度", "asset-management"),
            ("S&P 500", "stock"),
            ("AI半導体", "ai"),
        ]
        for name, category in topics:
            id1 = generate_topic_id(name, category)
            id2 = generate_topic_id(name, category)
            assert id1 == id2, f"topic_id mismatch for {name}::{category}"

    def test_正常系_同じentity情報から同じentity_idが生成される(self) -> None:
        entities = [
            ("NVIDIA", "company"),
            ("AMD", "company"),
            ("Jerome Powell", "person"),
        ]
        for name, entity_type in entities:
            id1 = generate_entity_id(name, entity_type)
            id2 = generate_entity_id(name, entity_type)
            assert id1 == id2, f"entity_id mismatch for {name}::{entity_type}"

    def test_正常系_同じcontent文字列から同じclaim_idが生成される(self) -> None:
        contents = [
            "The S&P 500 index closed at a record high.",
            "NVIDIA data center revenue exceeded expectations.",
            "AI semiconductor market is expected to grow 45% YoY.",
        ]
        for content in contents:
            id1 = generate_claim_id(content)
            id2 = generate_claim_id(content)
            assert id1 == id2, "claim_id mismatch for content"

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもsource_idが同一(
        self, tmp_path: Path
    ) -> None:
        """同じ入力で2回キューファイルを生成し、全 source_id が一致することを検証。"""
        data = _realistic_news_batch()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, "finance-news-workflow", data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, "finance-news-workflow", data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(s["source_id"] for s in q1["sources"])
        ids2 = sorted(s["source_id"] for s in q2["sources"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもclaim_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_news_batch()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, "finance-news-workflow", data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, "finance-news-workflow", data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(c["claim_id"] for c in q1["claims"])
        ids2 = sorted(c["claim_id"] for c in q2["claims"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもentity_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_ai_research_batch()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, "ai-research-collect", data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, "ai-research-collect", data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(e["entity_id"] for e in q1["entities"])
        ids2 = sorted(e["entity_id"] for e in q2["entities"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもtopic_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_asset_management_batch()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, "asset-management", data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, "asset-management", data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(t["topic_id"] for t in q1["topics"])
        ids2 = sorted(t["topic_id"] for t in q2["topics"])
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# E2E: マルチコマンド パイプラインテスト
# ---------------------------------------------------------------------------


class TestMultiCommandPipeline:
    """複数コマンドを連続実行し、全体の整合性を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_全6コマンドからキューファイルが生成される(
        self, tmp_path: Path
    ) -> None:
        """全コマンドのデータからキューファイルを生成し、それぞれが標準フォーマットに準拠することを検証。"""
        results: dict[str, dict[str, Any]] = {}

        for command, (_, data_fn) in ALL_COMMAND_DATA.items():
            sub_dir = tmp_path / command
            sub_dir.mkdir()
            output_file = _generate_queue_file(sub_dir, command, data_fn())
            data = _load_queue_file(output_file)
            results[command] = data

        # 全コマンドの結果が存在
        assert len(results) == 6

        # 全結果がフォーマット準拠
        for command, data in results.items():
            missing = GRAPH_QUEUE_REQUIRED_KEYS - set(data.keys())
            assert not missing, f"{command}: missing keys {missing}"
            assert data["schema_version"] == "2.0"
            assert data["command_source"] == command

    @freeze_time(FROZEN_TIME)
    def test_正常系_異なるコマンドのsource_idがURLベースで一意(
        self, tmp_path: Path
    ) -> None:
        """異なるコマンドから同じURLを含むデータを投入した場合、source_id が一致することを検証。"""
        # 同じ URL を持つニュースとレポートを作成
        shared_url = "https://www.cnbc.com/2026/03/07/sp500-record.html"

        news_data = {
            "session_id": "news-test",
            "batch_label": "index",
            "articles": [
                {
                    "url": shared_url,
                    "title": "S&P 500 Record",
                    "summary": "Record high.",
                    "feed_source": "CNBC",
                    "published": "2026-03-07T10:00:00+00:00",
                }
            ],
        }

        report_data = {
            "session_id": "report-test",
            "sections": [
                {
                    "title": "Summary",
                    "content": "Market summary.",
                    "sources": [
                        {
                            "url": shared_url,
                            "title": "S&P 500 Record",
                            "published": "2026-03-07T10:00:00+00:00",
                        }
                    ],
                }
            ],
        }

        dir1 = tmp_path / "news"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, "finance-news-workflow", news_data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "report"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, "generate-market-report", report_data)
        q2 = _load_queue_file(file2)

        # 同じ URL からは同じ source_id が生成される（MERGE で同一ノードに統合される）
        news_source_id = q1["sources"][0]["source_id"]
        report_source_id = q2["sources"][0]["source_id"]
        assert news_source_id == report_source_id

    @freeze_time(FROZEN_TIME)
    def test_正常系_キューファイル名がgqプレフィックスで始まる(
        self, tmp_path: Path
    ) -> None:
        output_file = _generate_queue_file(
            tmp_path, "finance-news-workflow", _realistic_news_batch()
        )
        assert output_file.name.startswith("gq-")
        assert output_file.name.endswith(".json")


# ---------------------------------------------------------------------------
# E2E: ノード数・データ量テスト
# ---------------------------------------------------------------------------


class TestNodeCounts:
    """生成されるノード数が入力データと一致することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_finance_newsのsource数が記事数と一致(self, tmp_path: Path) -> None:
        data = _realistic_news_batch()
        output_file = _generate_queue_file(tmp_path, "finance-news-workflow", data)
        q = _load_queue_file(output_file)

        assert len(q["sources"]) == len(data["articles"])

    @freeze_time(FROZEN_TIME)
    def test_正常系_finance_newsのclaim数がsummaryありの記事数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_news_batch()
        expected_claims = sum(1 for a in data["articles"] if a.get("summary", ""))
        output_file = _generate_queue_file(tmp_path, "finance-news-workflow", data)
        q = _load_queue_file(output_file)

        assert len(q["claims"]) == expected_claims

    @freeze_time(FROZEN_TIME)
    def test_正常系_ai_researchのentity数がcompany数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_ai_research_batch()
        output_file = _generate_queue_file(tmp_path, "ai-research-collect", data)
        q = _load_queue_file(output_file)

        assert len(q["entities"]) == len(data["companies"])

    @freeze_time(FROZEN_TIME)
    def test_正常系_asset_managementのtopic数がtheme数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_asset_management_batch()
        output_file = _generate_queue_file(tmp_path, "asset-management", data)
        q = _load_queue_file(output_file)

        assert len(q["topics"]) == len(data["themes"])

    @freeze_time(FROZEN_TIME)
    def test_正常系_market_reportのsource数が重複除外後のURL数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_market_report()
        unique_urls = set()
        for section in data["sections"]:
            for source in section.get("sources", []):
                url = source.get("url", "")
                if url:
                    unique_urls.add(url)

        output_file = _generate_queue_file(tmp_path, "generate-market-report", data)
        q = _load_queue_file(output_file)

        assert len(q["sources"]) == len(unique_urls)


# ---------------------------------------------------------------------------
# E2E: MAKES_CLAIM リレーション推論テスト
# ---------------------------------------------------------------------------


class TestRelationInference:
    """リレーション推論に必要なデータが正しく出力されることを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_claimにsource_idが設定されている(self, tmp_path: Path) -> None:
        """finance-news-workflow の claim に source_id が含まれ、MAKES_CLAIM 推論が可能。"""
        data = _realistic_news_batch()
        output_file = _generate_queue_file(tmp_path, "finance-news-workflow", data)
        q = _load_queue_file(output_file)

        for claim in q["claims"]:
            assert "source_id" in claim, "claim must have source_id for MAKES_CLAIM"
            # source_id は sources 配列のいずれかと一致するはず
            source_ids = {s["source_id"] for s in q["sources"]}
            assert claim["source_id"] in source_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_finance_fullのclaimにsource_urlが設定されている(
        self, tmp_path: Path
    ) -> None:
        """finance-full の claim に source_url が含まれ、MAKES_CLAIM 推論が可能。"""
        data = _realistic_finance_full()
        output_file = _generate_queue_file(tmp_path, "finance-full", data)
        q = _load_queue_file(output_file)

        for claim in q["claims"]:
            assert "source_url" in claim, "claim must have source_url for MAKES_CLAIM"

    @freeze_time(FROZEN_TIME)
    def test_正常系_source_urlからsource_idを逆算してMATCH可能(
        self, tmp_path: Path
    ) -> None:
        """finance-full の claim.source_url から generate_source_id で source_id を逆算し、
        sources 配列の source_id と一致することを検証。"""
        data = _realistic_finance_full()
        output_file = _generate_queue_file(tmp_path, "finance-full", data)
        q = _load_queue_file(output_file)

        source_ids = {s["source_id"] for s in q["sources"]}

        for claim in q["claims"]:
            source_url = claim.get("source_url", "")
            if source_url:
                derived_id = generate_source_id(source_url)
                assert derived_id in source_ids, (
                    f"Derived source_id {derived_id} from {source_url} "
                    f"not found in sources"
                )


# ---------------------------------------------------------------------------
# E2E: source_id の URL ユニーク性テスト
# ---------------------------------------------------------------------------


class TestSourceIdUniqueness:
    """source_id が URL に基づいて一意であることを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_異なるURLで異なるsource_id(self, tmp_path: Path) -> None:
        data = _realistic_news_batch()
        output_file = _generate_queue_file(tmp_path, "finance-news-workflow", data)
        q = _load_queue_file(output_file)

        source_ids = [s["source_id"] for s in q["sources"]]
        # 3 articles with different URLs should produce 3 unique IDs
        assert len(source_ids) == len(set(source_ids))

    @freeze_time(FROZEN_TIME)
    def test_正常系_URLの一意性がsource_idに反映される(self, tmp_path: Path) -> None:
        """URL が同じ記事は source_id も同じになることを検証（重複投入時の MERGE 保証）。"""
        url = "https://www.cnbc.com/2026/03/07/test-article.html"
        id1 = generate_source_id(url)
        id2 = generate_source_id(url)
        assert id1 == id2
