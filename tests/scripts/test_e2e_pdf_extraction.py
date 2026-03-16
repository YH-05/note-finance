"""E2E integration tests for pdf-extraction graph-queue pipeline.

Issue #68: [KG v2] E2E 検証 — サンプル PDF での graph-queue 生成確認

Tests cover:
- サンプル PDF 抽出データから graph-queue JSON を生成
- schema_version が '2.0' であること
- facts[] と claims[] が分離されていること
- confidence がどのノードにも含まれないこと
- chunks[] が出力に存在すること
- financial_datapoints[] と fiscal_periods[] の v2 ノード生成
- 10 種のリレーションキーが存在すること
- 冪等性（同一データで同一 ID 生成）
- ノード間の参照整合性

Neo4j への実投入テストは別スコープ。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from emit_graph_queue import (
    SCHEMA_VERSION,
    generate_chunk_id,
    generate_claim_id,
    generate_entity_id,
    generate_fact_id,
    generate_source_id,
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
"""graph-queue JSON v2.0 の必須トップレベルキー。"""

PDF_RELATION_KEYS: set[str] = {
    "source_fact",
    "source_claim",
    "fact_entity",
    "claim_entity",
    "contains_chunk",
    "extracted_from_fact",
    "extracted_from_claim",
    "has_datapoint",
    "for_period",
    "datapoint_entity",
    "tagged",
}
"""pdf-extraction で生成される 11 種のリレーションキー。"""


# ---------------------------------------------------------------------------
# Realistic sample data (DocumentExtractionResult 形式)
# ---------------------------------------------------------------------------


def _realistic_pdf_extraction_data() -> dict[str, Any]:
    """HSBC ISAT 3Q25 レポートを模したリアルな PDF 抽出データを生成。

    Returns
    -------
    dict[str, Any]
        DocumentExtractionResult 互換の辞書。3 チャンク、複数のエンティティ、
        ファクト、クレーム、財務データポイントを含む。
    """
    return {
        "source_hash": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6abcd",
        "session_id": "pdf-extraction-20260307-120000",
        "chunks": [
            {
                "chunk_index": 0,
                "section_title": "Executive Summary",
                "content": (
                    "Indosat Ooredoo Hutchison (ISAT IJ) reported 3Q25 results. "
                    "Revenue grew 5% YoY to IDR 15.8 trillion. "
                    "EBITDA margin expanded to 52.1%."
                ),
                "entities": [
                    {
                        "name": "Indosat Ooredoo Hutchison",
                        "entity_type": "company",
                        "ticker": "ISAT",
                        "aliases": ["ISAT", "Indosat"],
                    },
                    {
                        "name": "Indonesia",
                        "entity_type": "country",
                        "ticker": None,
                        "aliases": [],
                    },
                ],
                "facts": [
                    {
                        "content": "Revenue grew 5% YoY to IDR 15.8 trillion in 3Q25",
                        "fact_type": "statistic",
                        "as_of_date": "2025-Q3",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "content": "EBITDA margin expanded to 52.1% in 3Q25",
                        "fact_type": "data_point",
                        "as_of_date": "2025-Q3",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
                "claims": [
                    {
                        "content": "We maintain Buy rating with a target price of IDR 3,200",
                        "claim_type": "recommendation",
                        "sentiment": "bullish",
                        "magnitude": "strong",
                        "target_price": 3200.0,
                        "rating": "Buy",
                        "time_horizon": "12M",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
                "financial_datapoints": [
                    {
                        "metric_name": "Revenue",
                        "value": 15800.0,
                        "unit": "IDR bn",
                        "is_estimate": False,
                        "currency": "IDR",
                        "period_label": "3Q25",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "metric_name": "EBITDA Margin",
                        "value": 52.1,
                        "unit": "%",
                        "is_estimate": False,
                        "currency": None,
                        "period_label": "3Q25",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
            },
            {
                "chunk_index": 1,
                "section_title": "Financial Highlights",
                "content": (
                    "Net income reached IDR 2.1 trillion, up 12% YoY. "
                    "ARPU grew approximately 10% QoQ to IDR 42,000. "
                    "Total subscribers stood at 100.5 million."
                ),
                "entities": [
                    {
                        "name": "Indosat Ooredoo Hutchison",
                        "entity_type": "company",
                        "ticker": "ISAT",
                        "aliases": ["ISAT"],
                    },
                ],
                "facts": [
                    {
                        "content": "Net income reached IDR 2.1 trillion, up 12% YoY",
                        "fact_type": "statistic",
                        "as_of_date": "2025-Q3",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "content": "ARPU grew approximately 10% QoQ to IDR 42,000",
                        "fact_type": "data_point",
                        "as_of_date": "2025-Q3",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
                "claims": [
                    {
                        "content": "ARPU growth is expected to sustain in FY26 driven by market repair",
                        "claim_type": "prediction",
                        "sentiment": "bullish",
                        "magnitude": "moderate",
                        "target_price": None,
                        "rating": None,
                        "time_horizon": "FY26",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
                "financial_datapoints": [
                    {
                        "metric_name": "Net Income",
                        "value": 2100.0,
                        "unit": "IDR bn",
                        "is_estimate": False,
                        "currency": "IDR",
                        "period_label": "3Q25",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "metric_name": "ARPU",
                        "value": 42000.0,
                        "unit": "IDR",
                        "is_estimate": False,
                        "currency": "IDR",
                        "period_label": "3Q25",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
            },
            {
                "chunk_index": 2,
                "section_title": "Outlook and Estimates",
                "content": (
                    "We forecast FY2025 revenue of IDR 62.5 trillion and FY2026 "
                    "revenue of IDR 68.0 trillion. EBITDA is estimated at IDR 33.0 "
                    "trillion for FY2025."
                ),
                "entities": [
                    {
                        "name": "Indosat Ooredoo Hutchison",
                        "entity_type": "company",
                        "ticker": "ISAT",
                        "aliases": [],
                    },
                ],
                "facts": [],
                "claims": [
                    {
                        "content": "We forecast FY2025 revenue of IDR 62.5 trillion",
                        "claim_type": "forecast",
                        "sentiment": "bullish",
                        "magnitude": "moderate",
                        "target_price": None,
                        "rating": None,
                        "time_horizon": "FY25",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "content": "FY2026 revenue is estimated at IDR 68.0 trillion",
                        "claim_type": "forecast",
                        "sentiment": "bullish",
                        "magnitude": "moderate",
                        "target_price": None,
                        "rating": None,
                        "time_horizon": "FY26",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
                "financial_datapoints": [
                    {
                        "metric_name": "Revenue",
                        "value": 62500.0,
                        "unit": "IDR bn",
                        "is_estimate": True,
                        "currency": "IDR",
                        "period_label": "FY2025",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "metric_name": "Revenue",
                        "value": 68000.0,
                        "unit": "IDR bn",
                        "is_estimate": True,
                        "currency": "IDR",
                        "period_label": "FY2026",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                    {
                        "metric_name": "EBITDA",
                        "value": 33000.0,
                        "unit": "IDR bn",
                        "is_estimate": True,
                        "currency": "IDR",
                        "period_label": "FY2025",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                    },
                ],
            },
        ],
    }


def _minimal_pdf_extraction_data() -> dict[str, Any]:
    """最小限の PDF 抽出データ（1 チャンク、データポイントなし）。

    Returns
    -------
    dict[str, Any]
        エンティティ 1、ファクト 1、クレーム 1 の最小構成。
    """
    return {
        "source_hash": "minimal_hash_for_testing",
        "session_id": "pdf-minimal-test",
        "chunks": [
            {
                "chunk_index": 0,
                "section_title": "Summary",
                "content": "Apple reported Q4 revenue of $100B.",
                "entities": [
                    {
                        "name": "Apple",
                        "entity_type": "company",
                        "ticker": "AAPL",
                    },
                ],
                "facts": [
                    {
                        "content": "Apple reported Q4 revenue of $100B",
                        "fact_type": "statistic",
                        "as_of_date": "2025-Q4",
                        "about_entities": ["Apple"],
                    },
                ],
                "claims": [
                    {
                        "content": "We expect continued growth in services revenue",
                        "claim_type": "prediction",
                        "sentiment": "bullish",
                        "about_entities": ["Apple"],
                    },
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_pdf_queue_file(
    tmp_path: Path,
    data: dict[str, Any],
) -> Path:
    """pdf-extraction コマンドでキューファイルを生成して出力パスを返す。

    Parameters
    ----------
    tmp_path : Path
        Pytest 一時ディレクトリ。
    data : dict[str, Any]
        DocumentExtractionResult 互換の入力データ。

    Returns
    -------
    Path
        生成されたキューファイルのパス。
    """
    input_file = tmp_path / "pdf-extraction-input.json"
    input_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    output_base = tmp_path / "graph-queue"
    exit_code = run(
        command="pdf-extraction",
        input_path=input_file,
        output_base=output_base,
        cleanup=False,
    )
    assert exit_code == 0, "Queue generation failed for pdf-extraction"

    output_files = list(output_base.glob("pdf-extraction/*.json"))
    assert len(output_files) == 1, "Expected 1 output file for pdf-extraction"
    return output_files[0]


def _load_queue_file(path: Path) -> dict[str, Any]:
    """キューファイルを読み込んで辞書として返す。"""
    return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _collect_all_nodes(queue_data: dict[str, Any]) -> list[dict[str, Any]]:
    """キューデータ内の全ノード（配列要素）をフラットに収集する。

    Parameters
    ----------
    queue_data : dict[str, Any]
        graph-queue JSON データ。

    Returns
    -------
    list[dict[str, Any]]
        全ノードのリスト。
    """
    node_keys = [
        "sources",
        "entities",
        "facts",
        "claims",
        "chunks",
        "financial_datapoints",
        "fiscal_periods",
    ]
    nodes: list[dict[str, Any]] = []
    for key in node_keys:
        for item in queue_data.get(key, []):
            nodes.append(item)
    return nodes


# ---------------------------------------------------------------------------
# E2E: graph-queue フォーマット準拠テスト
# ---------------------------------------------------------------------------


class TestPdfExtractionFormatCompliance:
    """pdf-extraction の graph-queue JSON が v2.0 フォーマットに準拠することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_サンプルデータで正常実行できる(self, tmp_path: Path) -> None:
        """受け入れ条件: サンプルデータで正常実行できること。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data is not None
        assert isinstance(queue_data, dict)

    @freeze_time(FROZEN_TIME)
    def test_正常系_schema_versionが2_0である(self, tmp_path: Path) -> None:
        """受け入れ条件: schema_version が '2.0' であること。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["schema_version"] == "2.0"
        assert SCHEMA_VERSION == "2.0"

    @freeze_time(FROZEN_TIME)
    def test_正常系_必須トップレベルキーが全て存在する(self, tmp_path: Path) -> None:
        """v2.0 の全 15 キーが graph-queue JSON に存在すること。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        missing = GRAPH_QUEUE_REQUIRED_KEYS - set(queue_data.keys())
        assert not missing, f"Missing top-level keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_command_sourceがpdf_extractionである(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["command_source"] == "pdf-extraction"

    @freeze_time(FROZEN_TIME)
    def test_正常系_queue_idがgqプレフィックスで始まる(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["queue_id"].startswith("gq-")

    @freeze_time(FROZEN_TIME)
    def test_正常系_created_atがISO8601形式(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert "T" in queue_data["created_at"]

    @freeze_time(FROZEN_TIME)
    def test_正常系_batch_labelがpdf_extractionである(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["batch_label"] == "pdf-extraction"


# ---------------------------------------------------------------------------
# E2E: facts/claims 分離テスト
# ---------------------------------------------------------------------------


class TestFactsClaimsSeparation:
    """facts[] と claims[] が正しく分離されていることを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsとclaimsが分離されている(self, tmp_path: Path) -> None:
        """受け入れ条件: facts[] と claims[] が分離されていること。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert isinstance(queue_data["facts"], list)
        assert isinstance(queue_data["claims"], list)
        assert len(queue_data["facts"]) > 0, "facts[] should not be empty"
        assert len(queue_data["claims"]) > 0, "claims[] should not be empty"

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsにfact_idが存在しclaim_idがない(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for fact in queue_data["facts"]:
            assert "fact_id" in fact, "facts[] items must have fact_id"
            assert "claim_id" not in fact, "facts[] items must NOT have claim_id"

    @freeze_time(FROZEN_TIME)
    def test_正常系_claimsにclaim_idが存在しfact_idがない(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for claim in queue_data["claims"]:
            assert "claim_id" in claim, "claims[] items must have claim_id"
            assert "fact_id" not in claim, "claims[] items must NOT have fact_id"

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsの件数が入力データと一致(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        expected_facts = sum(len(c.get("facts", [])) for c in data["chunks"])

        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["facts"]) == expected_facts

    @freeze_time(FROZEN_TIME)
    def test_正常系_claimsの件数が入力データと一致(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        expected_claims = sum(len(c.get("claims", [])) for c in data["chunks"])

        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["claims"]) == expected_claims

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsにcategoryが含まれない(self, tmp_path: Path) -> None:
        """facts はカテゴリを持たない（claims のみ）。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for fact in queue_data["facts"]:
            assert "category" not in fact, "facts[] must NOT have category"


# ---------------------------------------------------------------------------
# E2E: confidence フィールド不在テスト
# ---------------------------------------------------------------------------


class TestConfidenceAbsent:
    """confidence がどのノードにも含まれないことを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_confidenceがどのノードにも含まれない(self, tmp_path: Path) -> None:
        """受け入れ条件: confidence がどのノードにも含まれないこと。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        all_nodes = _collect_all_nodes(queue_data)
        for node in all_nodes:
            assert "confidence" not in node, f"confidence field found in node: {node}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsにconfidenceが含まれない(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for fact in queue_data["facts"]:
            assert "confidence" not in fact

    @freeze_time(FROZEN_TIME)
    def test_正常系_claimsにconfidenceが含まれない(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for claim in queue_data["claims"]:
            assert "confidence" not in claim

    @freeze_time(FROZEN_TIME)
    def test_正常系_最小データでもconfidenceが含まれない(self, tmp_path: Path) -> None:
        data = _minimal_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        all_nodes = _collect_all_nodes(queue_data)
        for node in all_nodes:
            assert "confidence" not in node


# ---------------------------------------------------------------------------
# E2E: chunks[] 存在テスト
# ---------------------------------------------------------------------------


class TestChunksPresent:
    """chunks[] が出力に存在し正しい構造を持つことを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_chunksが出力に存在する(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert "chunks" in queue_data
        assert isinstance(queue_data["chunks"], list)
        assert len(queue_data["chunks"]) > 0

    @freeze_time(FROZEN_TIME)
    def test_正常系_chunks数が入力チャンク数と一致(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["chunks"]) == len(data["chunks"])

    @freeze_time(FROZEN_TIME)
    def test_正常系_各chunkにchunk_idとchunk_indexが存在する(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for chunk in queue_data["chunks"]:
            assert "chunk_id" in chunk
            assert "chunk_index" in chunk

    @freeze_time(FROZEN_TIME)
    def test_正常系_chunk_idがsource_hashとindexから決定論的に生成される(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        source_hash = data["source_hash"]
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for i, chunk in enumerate(queue_data["chunks"]):
            expected_id = generate_chunk_id(source_hash, i)
            assert chunk["chunk_id"] == expected_id

    @freeze_time(FROZEN_TIME)
    def test_正常系_chunk_indexが連番で並ぶ(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        indices = [c["chunk_index"] for c in queue_data["chunks"]]
        assert indices == list(range(len(queue_data["chunks"])))

    @freeze_time(FROZEN_TIME)
    def test_正常系_各chunkにsection_titleが存在する(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        expected_titles = [c["section_title"] for c in data["chunks"]]
        actual_titles = [c["section_title"] for c in queue_data["chunks"]]
        assert actual_titles == expected_titles


# ---------------------------------------------------------------------------
# E2E: v2 ノード生成テスト (entities, financial_datapoints, fiscal_periods)
# ---------------------------------------------------------------------------


class TestV2NodeGeneration:
    """v2 で追加されたノードタイプの E2E 生成を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_entitiesが重複排除されて生成される(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        # "Indosat Ooredoo Hutchison" は 3 チャンクに登場するが 1 エンティティ
        entity_names = [e["name"] for e in queue_data["entities"]]
        assert entity_names.count("Indosat Ooredoo Hutchison") == 1
        # "Indonesia" は 1 チャンクにのみ登場
        assert "Indonesia" in entity_names

    @freeze_time(FROZEN_TIME)
    def test_正常系_financial_datapointsが生成される(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["financial_datapoints"]) > 0
        dp = queue_data["financial_datapoints"][0]
        assert "datapoint_id" in dp
        assert "metric_name" in dp
        assert "value" in dp
        assert "unit" in dp

    @freeze_time(FROZEN_TIME)
    def test_正常系_financial_datapointsの件数が入力と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        expected_count = sum(
            len(c.get("financial_datapoints", [])) for c in data["chunks"]
        )
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["financial_datapoints"]) == expected_count

    @freeze_time(FROZEN_TIME)
    def test_正常系_estimateフラグが保持される(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        actuals = [
            dp
            for dp in queue_data["financial_datapoints"]
            if dp["is_estimate"] is False
        ]
        estimates = [
            dp for dp in queue_data["financial_datapoints"] if dp["is_estimate"] is True
        ]
        # チャンク 0, 1 に actual (4 件)、チャンク 2 に estimate (3 件)
        assert len(actuals) == 4
        assert len(estimates) == 3

    @freeze_time(FROZEN_TIME)
    def test_正常系_fiscal_periodsが派生生成される(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["fiscal_periods"]) > 0
        period = queue_data["fiscal_periods"][0]
        assert "period_id" in period
        assert "period_type" in period
        assert "period_label" in period

    @freeze_time(FROZEN_TIME)
    def test_正常系_fiscal_periodsが重複排除される(self, tmp_path: Path) -> None:
        """同一 period_label のデータポイントが複数あっても period は 1 つ。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        period_ids = [p["period_id"] for p in queue_data["fiscal_periods"]]
        assert len(period_ids) == len(set(period_ids)), (
            "Fiscal periods should be unique"
        )

    @freeze_time(FROZEN_TIME)
    def test_正常系_sourceノードにsource_typeがpdfと設定される(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["sources"]) == 1
        assert queue_data["sources"][0]["source_type"] == "pdf"


# ---------------------------------------------------------------------------
# E2E: リレーション検証テスト
# ---------------------------------------------------------------------------


class TestRelations:
    """11 種のリレーションキーが全て存在し、正しいリンクを持つことを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_全11種のリレーションキーが存在する(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        actual_keys = set(queue_data["relations"].keys())
        assert actual_keys == PDF_RELATION_KEYS, (
            f"Missing relation keys: {PDF_RELATION_KEYS - actual_keys}"
        )

    @freeze_time(FROZEN_TIME)
    def test_正常系_contains_chunkリレーションがチャンク数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["contains_chunk"]
        assert len(rels) == len(data["chunks"])
        for rel in rels:
            assert rel["type"] == "CONTAINS_CHUNK"

    @freeze_time(FROZEN_TIME)
    def test_正常系_source_factリレーションがfact数と一致(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        expected_facts = sum(len(c.get("facts", [])) for c in data["chunks"])

        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["source_fact"]
        assert len(rels) == expected_facts
        for rel in rels:
            assert rel["type"] == "STATES_FACT"

    @freeze_time(FROZEN_TIME)
    def test_正常系_source_claimリレーションがclaim数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        expected_claims = sum(len(c.get("claims", [])) for c in data["chunks"])

        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["source_claim"]
        assert len(rels) == expected_claims
        for rel in rels:
            assert rel["type"] == "MAKES_CLAIM"

    @freeze_time(FROZEN_TIME)
    def test_正常系_extracted_fromリレーションが正しいchunk_idを参照(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        chunk_ids = {c["chunk_id"] for c in queue_data["chunks"]}

        for rel in queue_data["relations"]["extracted_from_fact"]:
            assert rel["type"] == "EXTRACTED_FROM"
            assert rel["to_id"] in chunk_ids

        for rel in queue_data["relations"]["extracted_from_claim"]:
            assert rel["type"] == "EXTRACTED_FROM"
            assert rel["to_id"] in chunk_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_has_datapointリレーションがdatapoint数と一致(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()
        expected_dps = sum(
            len(c.get("financial_datapoints", [])) for c in data["chunks"]
        )
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["has_datapoint"]
        assert len(rels) == expected_dps
        for rel in rels:
            assert rel["type"] == "HAS_DATAPOINT"

    @freeze_time(FROZEN_TIME)
    def test_正常系_for_periodリレーションが存在する(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["for_period"]
        assert len(rels) > 0
        for rel in rels:
            assert rel["type"] == "FOR_PERIOD"


# ---------------------------------------------------------------------------
# E2E: 参照整合性テスト
# ---------------------------------------------------------------------------


class TestReferentialIntegrity:
    """ノード間の参照が整合していることを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsのsource_idがsourcesに存在する(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        source_ids = {s["source_id"] for s in queue_data["sources"]}
        for fact in queue_data["facts"]:
            assert fact["source_id"] in source_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_claimsのsource_idがsourcesに存在する(self, tmp_path: Path) -> None:
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        source_ids = {s["source_id"] for s in queue_data["sources"]}
        for claim in queue_data["claims"]:
            assert claim["source_id"] in source_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_リレーションのfrom_idとto_idが既存ノードを参照(
        self, tmp_path: Path
    ) -> None:
        """全リレーションの from_id/to_id が生成されたノードの ID セットに含まれる。"""
        data = _realistic_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        # 全ノード ID を収集
        all_ids: set[str] = set()
        all_ids.update(s["source_id"] for s in queue_data["sources"])
        all_ids.update(e["entity_id"] for e in queue_data["entities"])
        all_ids.update(f["fact_id"] for f in queue_data["facts"])
        all_ids.update(c["claim_id"] for c in queue_data["claims"])
        all_ids.update(ch["chunk_id"] for ch in queue_data["chunks"])
        all_ids.update(dp["datapoint_id"] for dp in queue_data["financial_datapoints"])
        all_ids.update(fp["period_id"] for fp in queue_data["fiscal_periods"])

        for rel_key, rels in queue_data["relations"].items():
            for rel in rels:
                assert rel["from_id"] in all_ids, (
                    f"Dangling from_id in {rel_key}: {rel['from_id']}"
                )
                assert rel["to_id"] in all_ids, (
                    f"Dangling to_id in {rel_key}: {rel['to_id']}"
                )


# ---------------------------------------------------------------------------
# E2E: 冪等性テスト
# ---------------------------------------------------------------------------


class TestPdfExtractionIdempotency:
    """同じ PDF 抽出データから同じ ID が生成され、冪等投入が可能なことを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもsource_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_pdf_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_pdf_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(s["source_id"] for s in q1["sources"])
        ids2 = sorted(s["source_id"] for s in q2["sources"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもfact_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_pdf_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_pdf_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(f["fact_id"] for f in q1["facts"])
        ids2 = sorted(f["fact_id"] for f in q2["facts"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもclaim_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_pdf_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_pdf_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(c["claim_id"] for c in q1["claims"])
        ids2 = sorted(c["claim_id"] for c in q2["claims"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもentity_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_pdf_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_pdf_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(e["entity_id"] for e in q1["entities"])
        ids2 = sorted(e["entity_id"] for e in q2["entities"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもchunk_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_pdf_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_pdf_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(ch["chunk_id"] for ch in q1["chunks"])
        ids2 = sorted(ch["chunk_id"] for ch in q2["chunks"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_同じデータで2回生成してもdatapoint_idが同一(
        self, tmp_path: Path
    ) -> None:
        data = _realistic_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_pdf_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_pdf_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(dp["datapoint_id"] for dp in q1["financial_datapoints"])
        ids2 = sorted(dp["datapoint_id"] for dp in q2["financial_datapoints"])
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# E2E: 最小データテスト
# ---------------------------------------------------------------------------


class TestMinimalPdfExtraction:
    """最小限のデータで基本的な変換が動作することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_最小データで正常実行できる(self, tmp_path: Path) -> None:
        data = _minimal_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["schema_version"] == "2.0"
        assert queue_data["command_source"] == "pdf-extraction"

    @freeze_time(FROZEN_TIME)
    def test_正常系_最小データでfactsとclaimsが分離される(self, tmp_path: Path) -> None:
        data = _minimal_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["facts"]) == 1
        assert len(queue_data["claims"]) == 1
        assert "fact_id" in queue_data["facts"][0]
        assert "claim_id" in queue_data["claims"][0]

    @freeze_time(FROZEN_TIME)
    def test_正常系_datapointsなしでも空リストが返る(self, tmp_path: Path) -> None:
        data = _minimal_pdf_extraction_data()
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["financial_datapoints"] == []
        assert queue_data["fiscal_periods"] == []

    @freeze_time(FROZEN_TIME)
    def test_正常系_空チャンクリストで空ノードが返る(self, tmp_path: Path) -> None:
        data = {
            "source_hash": "empty_hash",
            "session_id": "empty-test",
            "chunks": [],
        }
        output_file = _generate_pdf_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["schema_version"] == "2.0"
        assert len(queue_data["sources"]) == 1  # source always created
        assert queue_data["entities"] == []
        assert queue_data["facts"] == []
        assert queue_data["claims"] == []
        assert queue_data["chunks"] == []
        assert queue_data["financial_datapoints"] == []
        assert queue_data["fiscal_periods"] == []
