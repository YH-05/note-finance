"""Unit tests for data_pipeline.structurer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_pipeline.collectors.base import CollectedItem
from data_pipeline.structurer.converter import (
    build_from_extracted,
    build_minimal_output,
    build_source_entry,
)
from data_pipeline.structurer.emitter import save_emit_input
from data_pipeline.structurer.models import (
    AboutEntity,
    ClaimEntry,
    FactEntry,
    SourceEntry,
    StructuredOutput,
    TopicEntry,
)


def _make_item(
    url: str = "https://example.com/article",
    title: str = "Test Article",
    raw_text: str = "Article content.",
    collection_method: str = "rss",
    **kwargs,
) -> CollectedItem:
    return CollectedItem(
        source_id="test",
        url=url,
        title=title,
        raw_text=raw_text,
        collection_method=collection_method,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestStructuredOutput:
    """StructuredOutput のテスト."""

    def test_正常系_空の出力を生成できる(self) -> None:
        output = StructuredOutput()
        assert output.is_empty
        assert output.fact_count == 0
        assert output.claim_count == 0

    def test_正常系_to_emit_inputでdict変換(self) -> None:
        output = StructuredOutput(
            sources=[SourceEntry(url="https://a.com", authority_level="media")],
            facts=[FactEntry(content="Fact 1", source_url="https://a.com")],
            claims=[ClaimEntry(content="Claim 1", source_url="https://a.com")],
            topics=[TopicEntry(name="Finance")],
        )
        data = output.to_emit_input()
        assert isinstance(data, dict)
        assert len(data["sources"]) == 1
        assert len(data["facts"]) == 1
        assert len(data["claims"]) == 1
        assert len(data["topics"]) == 1

    def test_正常系_entity_names抽出(self) -> None:
        output = StructuredOutput(
            facts=[
                FactEntry(
                    content="Fact",
                    source_url="https://a.com",
                    about_entities=[
                        AboutEntity(name="Apple", entity_type="company"),
                        AboutEntity(name="NVDA", entity_type="ticker"),
                    ],
                ),
            ],
            claims=[
                ClaimEntry(
                    content="Claim",
                    about_entities=[
                        AboutEntity(name="Apple", entity_type="company"),
                        AboutEntity(name="FRB", entity_type="organization"),
                    ],
                ),
            ],
        )
        names = output.entity_names
        assert names == ["Apple", "FRB", "NVDA"]  # ソート済み、重複除去


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------


class TestBuildSourceEntry:
    """build_source_entry のテスト."""

    def test_正常系_デフォルト変換(self) -> None:
        item = _make_item()
        entry = build_source_entry(item)
        assert entry.url == "https://example.com/article"
        assert entry.title == "Test Article"
        assert entry.source_type == "rss"
        assert entry.data_source == "rss"

    @pytest.mark.parametrize(
        ("level", "expected"),
        [(5, "official"), (4, "analyst"), (3, "media"), (2, "blog"), (1, "social")],
    )
    def test_パラメトライズ_authority_levelマッピング(
        self, level: int, expected: str,
    ) -> None:
        item = _make_item()
        entry = build_source_entry(item, authority_level=level)
        assert entry.authority_level == expected

    def test_正常系_published_atが設定される(self) -> None:
        dt = datetime(2026, 3, 24, 10, 0, tzinfo=timezone.utc)
        item = _make_item(published_at=dt)
        entry = build_source_entry(item)
        assert "2026-03-24" in entry.published_at


class TestBuildMinimalOutput:
    """build_minimal_output のテスト."""

    def test_正常系_アイテムを構造化できる(self) -> None:
        items = [
            _make_item(url="https://a.com", raw_text="Fact A"),
            _make_item(url="https://b.com", raw_text="Fact B"),
        ]
        output = build_minimal_output(items, authority_level=4)

        assert len(output.sources) == 2
        assert output.fact_count == 2
        assert output.claim_count == 0
        assert not output.is_empty

    def test_正常系_空テキストはスキップ(self) -> None:
        items = [
            _make_item(url="https://a.com", raw_text="Has text"),
            _make_item(url="https://b.com", raw_text=""),
            _make_item(url="https://c.com", raw_text="   "),
        ]
        output = build_minimal_output(items)
        assert len(output.sources) == 1
        assert output.fact_count == 1

    def test_正常系_URL重複排除(self) -> None:
        items = [
            _make_item(url="https://a.com", raw_text="Version 1"),
            _make_item(url="https://a.com", raw_text="Version 2"),
        ]
        output = build_minimal_output(items)
        assert len(output.sources) == 1  # ソースは1つ
        assert output.fact_count == 2  # ファクトは2つ

    def test_エッジケース_空リスト(self) -> None:
        output = build_minimal_output([])
        assert output.is_empty
        assert len(output.sources) == 0


class TestBuildFromExtracted:
    """build_from_extracted のテスト."""

    def test_正常系_LLM抽出結果を構造化できる(self) -> None:
        items = [_make_item(url="https://a.com")]
        extractions = [
            {
                "facts": [
                    {
                        "content": "S&P 500 reached all-time high",
                        "fact_type": "market_event",
                        "confidence": 0.95,
                        "about_entities": [
                            {"name": "S&P 500", "entity_type": "index"},
                        ],
                    },
                ],
                "claims": [
                    {
                        "content": "Market will continue to rise",
                        "claim_type": "analyst_forecast",
                        "sentiment": "positive",
                        "about_entities": [
                            {"name": "S&P 500", "entity_type": "index"},
                        ],
                    },
                ],
                "topics": [
                    {"name": "US Equity Market", "category": "market"},
                ],
            },
        ]
        output = build_from_extracted(items, extractions, authority_level=4)

        assert len(output.sources) == 1
        assert output.fact_count == 1
        assert output.claim_count == 1
        assert len(output.topics) == 1
        assert output.facts[0].about_entities[0].name == "S&P 500"
        assert output.claims[0].sentiment == "positive"

    def test_正常系_トピック重複排除(self) -> None:
        items = [
            _make_item(url="https://a.com"),
            _make_item(url="https://b.com"),
        ]
        extractions = [
            {"facts": [], "topics": [{"name": "Finance"}]},
            {"facts": [], "topics": [{"name": "finance"}]},  # 大小異なるが同一
        ]
        output = build_from_extracted(items, extractions)
        assert len(output.topics) == 1

    def test_エッジケース_空の抽出結果(self) -> None:
        items = [_make_item()]
        extractions = [{}]
        output = build_from_extracted(items, extractions)
        assert output.fact_count == 0
        assert output.claim_count == 0


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------


class TestSaveEmitInput:
    """save_emit_input のテスト."""

    def test_正常系_JSONファイルを保存できる(self, tmp_path: Path) -> None:
        output = StructuredOutput(
            sources=[SourceEntry(url="https://a.com", authority_level="media")],
            facts=[FactEntry(content="Fact 1", source_url="https://a.com")],
        )
        path = save_emit_input(output, output_dir=tmp_path, filename="test.json")

        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data["sources"]) == 1
        assert len(data["facts"]) == 1
        assert data["sources"][0]["url"] == "https://a.com"

    def test_正常系_ファイル名自動生成(self, tmp_path: Path) -> None:
        output = StructuredOutput()
        path = save_emit_input(output, output_dir=tmp_path)

        assert path.exists()
        assert "pipeline_emit_input_" in path.name


# ---------------------------------------------------------------------------
# E2E: RawStore → 構造化 → emit入力JSON
# ---------------------------------------------------------------------------


class TestStructurerIntegration:
    """Layer 2 → Layer 3 の統合テスト."""

    def test_正常系_CollectedItemsから構造化してJSON保存(self, tmp_path: Path) -> None:
        items = [
            _make_item(
                url="https://www.fsa.go.jp/news/test",
                title="金融庁テストニュース",
                raw_text="金融庁は新しい規制を発表しました。",
                published_at=datetime(2026, 3, 24, tzinfo=timezone.utc),
            ),
            _make_item(
                url="https://www.boj.or.jp/news/test",
                title="日銀テストニュース",
                raw_text="日銀は金利を据え置きました。",
            ),
        ]

        # Layer 3: 構造化
        output = build_minimal_output(items, authority_level=5)
        assert output.fact_count == 2
        assert output.sources[0].authority_level == "official"

        # JSON保存
        path = save_emit_input(output, output_dir=tmp_path)
        data = json.loads(path.read_text())

        # emit_research_queue.py の入力として妥当か検証
        assert "sources" in data
        assert "facts" in data
        assert "claims" in data
        assert "topics" in data
        assert all(s["authority_level"] in ["official", "analyst", "media", "blog", "social", "academic"] for s in data["sources"])
        assert all(f["source_url"] for f in data["facts"])
        assert all(f["source_url"] in {s["url"] for s in data["sources"]} for f in data["facts"])
