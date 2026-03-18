"""E2E integration tests for KG v2.1 all-Wave integration verification.

Issue #141: [統合検証] KG v2.1 全Wave統合後の E2E 検証

Tests cover:
- Wave 1 (Stance + SUPERSEDES): Stance/Author nodes, HOLDS_STANCE, ON_ENTITY,
  BASED_ON, SUPERSEDES chain
- Wave 2 (CAUSES): Causal links between Fact/Claim/FinancialDataPoint
- Wave 3 (TREND + NEXT_PERIOD): Temporal chains for FiscalPeriod and
  metric trend edges for FinancialDataPoint
- Wave 4 (Question): Question nodes, ASKS_ABOUT, MOTIVATED_BY relations
- Cross-wave integration: All 20 relation keys present, referential integrity
  across all node types, idempotency of new v2.1 IDs
- v2.0 backward compatibility: Existing schema elements not broken

Neo4j への実投入テストは別スコープ（Docker コンテナ依存）。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from emit_graph_queue import (
    SCHEMA_VERSION,
    generate_stance_id,
    run,
)
from freezegun import freeze_time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FROZEN_TIME = "2026-03-17T12:00:00+00:00"
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

V21_ALL_RELATION_KEYS: set[str] = {
    # v2.0 base (11 keys)
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
    # Wave 1: Stance relations
    "holds_stance",
    "on_entity",
    "based_on",
    "supersedes",
    # Wave 2: Causal chain
    "causes",
    # Wave 3: Temporal chain
    "next_period",
    "trend",
    # Wave 4: Question relations
    "asks_about",
    "motivated_by",
    # v2.2: Authorship
    "authored_by",
}
"""v2.2 で定義される全 21 種のリレーションキー。"""


# ---------------------------------------------------------------------------
# Realistic sample data with all Wave 1-4 features
# ---------------------------------------------------------------------------


def _full_v21_pdf_extraction_data() -> dict[str, Any]:
    """HSBC ISAT 分析レポートを模した KG v2.1 全Wave 対応 PDF 抽出データ。

    含まれる Wave 機能:
    - Wave 1: 2 つの Stance (HSBC の異なる日付 → SUPERSEDES chain)
    - Wave 2: 2 つの causal_links (CAUSES relations)
    - Wave 3: 複数 FiscalPeriod (3Q25, FY2025, FY2026 → NEXT_PERIOD)、
              同一メトリック・異なる期間 (Revenue 3Q25/FY2025/FY2026 → TREND)
    - Wave 4: 2 つの Question (ASKS_ABOUT, MOTIVATED_BY)

    Returns
    -------
    dict[str, Any]
        DocumentExtractionResult 互換の辞書。
    """
    return {
        "source_hash": "v21_test_hash_abcdef1234567890abcdef1234567890abcdef1234567890abcdef12",
        "session_id": "kg-v21-e2e-20260317-120000",
        "chunks": [
            {
                "chunk_index": 0,
                "section_title": "Executive Summary & Rating",
                "content": (
                    "Indosat Ooredoo Hutchison (ISAT IJ) reported 3Q25 results. "
                    "Revenue grew 5% YoY to IDR 15.8 trillion. "
                    "We maintain Buy with TP IDR 3,200. "
                    "Subscriber growth drives revenue expansion."
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
                # Wave 1: Stance nodes
                "stances": [
                    {
                        "author_name": "HSBC",
                        "author_type": "sell_side",
                        "organization": "HSBC Global Research",
                        "entity_name": "Indosat Ooredoo Hutchison",
                        "rating": "Buy",
                        "sentiment": "bullish",
                        "target_price": 3200.0,
                        "target_price_currency": "IDR",
                        "as_of_date": "2025-10-15",
                        "based_on_claims": [
                            "We maintain Buy rating with a target price of IDR 3,200",
                        ],
                    },
                ],
                # Wave 2: Causal links
                "causal_links": [
                    {
                        "from_content": "Revenue grew 5% YoY to IDR 15.8 trillion in 3Q25",
                        "from_type": "fact",
                        "to_content": "We maintain Buy rating with a target price of IDR 3,200",
                        "to_type": "claim",
                        "mechanism": "Revenue growth drives positive rating outlook",
                        "confidence": "high",
                    },
                ],
                # Wave 4: Question nodes
                "questions": [
                    {
                        "content": "What is the revenue breakdown by segment for ISAT in 3Q25?",
                        "question_type": "data_gap",
                        "priority": "high",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                        "motivated_by_contents": [
                            "Revenue grew 5% YoY to IDR 15.8 trillion in 3Q25",
                        ],
                    },
                ],
            },
            {
                "chunk_index": 1,
                "section_title": "Financial Highlights",
                "content": (
                    "Net income reached IDR 2.1 trillion, up 12% YoY. "
                    "ARPU grew to IDR 42,000. "
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
                        "content": "Net income reached IDR 2.1 trillion, up 12% YoY in 3Q25",
                        "fact_type": "statistic",
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
                ],
                "stances": [],
                "causal_links": [
                    {
                        "from_content": "Net income reached IDR 2.1 trillion, up 12% YoY in 3Q25",
                        "from_type": "fact",
                        "to_content": "ARPU growth is expected to sustain in FY26 driven by market repair",
                        "to_type": "claim",
                        "mechanism": "Strong net income supports growth forecast",
                        "confidence": "medium",
                    },
                ],
                "questions": [
                    {
                        "content": "Is ISAT's ARPU growth sustainable given competitive pressure from Telkomsel?",
                        "question_type": "assumption_check",
                        "priority": "medium",
                        "about_entities": ["Indosat Ooredoo Hutchison"],
                        "motivated_by_contents": [
                            "ARPU growth is expected to sustain in FY26 driven by market repair",
                        ],
                    },
                ],
            },
            {
                "chunk_index": 2,
                "section_title": "Outlook and Estimates",
                "content": (
                    "We forecast FY2025 revenue of IDR 62.5 trillion and "
                    "FY2026 revenue of IDR 68.0 trillion. "
                    "Revised upward from prior estimate."
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
                ],
                # Wave 1: Second stance (earlier date -> SUPERSEDES chain)
                "stances": [
                    {
                        "author_name": "HSBC",
                        "author_type": "sell_side",
                        "organization": "HSBC Global Research",
                        "entity_name": "Indosat Ooredoo Hutchison",
                        "rating": "Hold",
                        "sentiment": "neutral",
                        "target_price": 2800.0,
                        "target_price_currency": "IDR",
                        "as_of_date": "2025-07-20",
                        "based_on_claims": [],
                    },
                ],
                "causal_links": [],
                "questions": [],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_queue_file(
    tmp_path: Path,
    data: dict[str, Any],
) -> Path:
    """pdf-extraction でキューファイルを生成して出力パスを返す。

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


def _collect_all_node_ids(queue_data: dict[str, Any]) -> set[str]:
    """キューデータ内の全ノード ID をフラットに収集する。

    v2.1 の全ノードタイプ (Source, Entity, Fact, Claim, Chunk,
    FinancialDataPoint, FiscalPeriod, Author, Stance, Question) を網羅。

    Parameters
    ----------
    queue_data : dict[str, Any]
        graph-queue JSON データ。

    Returns
    -------
    set[str]
        全ノード ID のセット。
    """
    ids: set[str] = set()
    ids.update(s["source_id"] for s in queue_data.get("sources", []))
    ids.update(e["entity_id"] for e in queue_data.get("entities", []))
    ids.update(f["fact_id"] for f in queue_data.get("facts", []))
    ids.update(c["claim_id"] for c in queue_data.get("claims", []))
    ids.update(ch["chunk_id"] for ch in queue_data.get("chunks", []))
    ids.update(dp["datapoint_id"] for dp in queue_data.get("financial_datapoints", []))
    ids.update(fp["period_id"] for fp in queue_data.get("fiscal_periods", []))
    ids.update(a["author_id"] for a in queue_data.get("authors", []))
    ids.update(st["stance_id"] for st in queue_data.get("stances", []))
    ids.update(q["question_id"] for q in queue_data.get("questions", []))
    return ids


# ---------------------------------------------------------------------------
# E2E: graph-queue 基本フォーマット準拠テスト
# ---------------------------------------------------------------------------


class TestV21FormatCompliance:
    """v2.1 全Wave データで graph-queue JSON がフォーマットに準拠することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_全Wave入りデータで正常実行できる(self, tmp_path: Path) -> None:
        """受け入れ条件: graph-queue JSON が正常生成されること。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data is not None
        assert isinstance(queue_data, dict)

    @freeze_time(FROZEN_TIME)
    def test_正常系_schema_versionが2_0である(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["schema_version"] == "2.1"
        assert SCHEMA_VERSION == "2.1"

    @freeze_time(FROZEN_TIME)
    def test_正常系_必須トップレベルキーが全て存在する(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        missing = GRAPH_QUEUE_REQUIRED_KEYS - set(queue_data.keys())
        assert not missing, f"Missing top-level keys: {missing}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_command_sourceがpdf_extractionである(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert queue_data["command_source"] == "pdf-extraction"

    @freeze_time(FROZEN_TIME)
    def test_正常系_全20種のリレーションキーが存在する(self, tmp_path: Path) -> None:
        """v2.1 で定義される全 20 リレーションキーが relations に存在。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        actual_keys = set(queue_data["relations"].keys())
        assert actual_keys == V21_ALL_RELATION_KEYS, (
            f"Missing: {V21_ALL_RELATION_KEYS - actual_keys}, "
            f"Extra: {actual_keys - V21_ALL_RELATION_KEYS}"
        )


# ---------------------------------------------------------------------------
# E2E: Wave 1 — Stance + SUPERSEDES テスト
# ---------------------------------------------------------------------------


class TestWave1StanceSupersedes:
    """Wave 1: Stance/Author ノードと SUPERSEDES 連鎖を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_Stanceノードが生成される(self, tmp_path: Path) -> None:
        """受け入れ条件: stances[] に Stance ノードが含まれること。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        stances = queue_data.get("stances", [])
        assert len(stances) == 2, f"Expected 2 stances, got {len(stances)}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_Stanceにstance_idが存在する(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for stance in queue_data["stances"]:
            assert "stance_id" in stance, "Stance must have stance_id"
            assert stance["stance_id"], "stance_id must not be empty"

    @freeze_time(FROZEN_TIME)
    def test_正常系_Stanceのratingとtarget_priceが保持される(
        self, tmp_path: Path
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        ratings = {s["rating"] for s in queue_data["stances"]}
        assert "Buy" in ratings
        assert "Hold" in ratings

        buy_stance = next(s for s in queue_data["stances"] if s["rating"] == "Buy")
        assert buy_stance["target_price"] == 3200.0

        hold_stance = next(s for s in queue_data["stances"] if s["rating"] == "Hold")
        assert hold_stance["target_price"] == 2800.0

    @freeze_time(FROZEN_TIME)
    def test_正常系_Authorノードが生成される(self, tmp_path: Path) -> None:
        """2 つの Stance は同一 Author → Author は 1 つに重複排除。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        authors = queue_data.get("authors", [])
        assert len(authors) == 1, f"Expected 1 author (HSBC dedup), got {len(authors)}"
        assert authors[0]["name"] == "HSBC"
        assert authors[0]["author_type"] == "sell_side"

    @freeze_time(FROZEN_TIME)
    def test_正常系_HOLDS_STANCEリレーションが生成される(self, tmp_path: Path) -> None:
        """Author -> Stance リレーション。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["holds_stance"]
        assert len(rels) == 2, f"Expected 2 HOLDS_STANCE, got {len(rels)}"
        for rel in rels:
            assert rel["type"] == "HOLDS_STANCE"

    @freeze_time(FROZEN_TIME)
    def test_正常系_ON_ENTITYリレーションが生成される(self, tmp_path: Path) -> None:
        """Stance -> Entity リレーション。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["on_entity"]
        assert len(rels) == 2, f"Expected 2 ON_ENTITY, got {len(rels)}"
        for rel in rels:
            assert rel["type"] == "ON_ENTITY"

    @freeze_time(FROZEN_TIME)
    def test_正常系_BASED_ONリレーションが生成される(self, tmp_path: Path) -> None:
        """Stance -> Claim リレーション (based_on_claims 経由)。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        rels = queue_data["relations"]["based_on"]
        # chunk 0 の stance に 1 つの based_on_claims、chunk 2 は空
        assert len(rels) == 1, f"Expected 1 BASED_ON, got {len(rels)}"
        assert rels[0]["type"] == "BASED_ON"

    @freeze_time(FROZEN_TIME)
    def test_正常系_SUPERSEDES連鎖が日付順で生成される(self, tmp_path: Path) -> None:
        """同一 (Author, Entity) の Stance 間で SUPERSEDES が as_of_date 順に生成。

        HSBC の ISAT stance:
        - 2025-07-20 (Hold, TP 2800) -> 古い
        - 2025-10-15 (Buy, TP 3200) -> 新しい（SUPERSEDES old）

        newer.SUPERSEDES -> older の方向。
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        supersedes = queue_data["relations"]["supersedes"]
        assert len(supersedes) == 1, f"Expected 1 SUPERSEDES, got {len(supersedes)}"

        rel = supersedes[0]
        assert rel["type"] == "SUPERSEDES"

        # from_id = newer stance (2025-10-15), to_id = older stance (2025-07-20)
        newer_id = generate_stance_id("HSBC", "Indosat Ooredoo Hutchison", "2025-10-15")
        older_id = generate_stance_id("HSBC", "Indosat Ooredoo Hutchison", "2025-07-20")
        assert rel["from_id"] == newer_id
        assert rel["to_id"] == older_id

    @freeze_time(FROZEN_TIME)
    def test_正常系_stance_idが決定論的である(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(s["stance_id"] for s in q1["stances"])
        ids2 = sorted(s["stance_id"] for s in q2["stances"])
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# E2E: Wave 2 — CAUSES テスト
# ---------------------------------------------------------------------------


class TestWave2Causes:
    """Wave 2: CAUSES リレーション（因果チェーン）を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_CAUSESリレーションが生成される(self, tmp_path: Path) -> None:
        """受け入れ条件: causes[] に CAUSES リレーションが含まれること。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        causes = queue_data["relations"]["causes"]
        assert len(causes) == 2, f"Expected 2 CAUSES, got {len(causes)}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_CAUSESにmechanismとconfidenceが含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for rel in queue_data["relations"]["causes"]:
            assert rel["type"] == "CAUSES"
            assert "mechanism" in rel, "CAUSES must have mechanism"
            assert "confidence" in rel, "CAUSES must have confidence"
            assert rel["confidence"] in {"high", "medium", "low"}

    @freeze_time(FROZEN_TIME)
    def test_正常系_CAUSESのfrom_labelとto_labelが設定される(
        self,
        tmp_path: Path,
    ) -> None:
        """Neo4j CE でのマルチラベル MATCH ワークアラウンド用フィールド。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        valid_labels = {"Fact", "Claim", "FinancialDataPoint"}
        for rel in queue_data["relations"]["causes"]:
            assert rel.get("from_label") in valid_labels, (
                f"Invalid from_label: {rel.get('from_label')}"
            )
            assert rel.get("to_label") in valid_labels, (
                f"Invalid to_label: {rel.get('to_label')}"
            )

    @freeze_time(FROZEN_TIME)
    def test_正常系_CAUSESのfact_to_claim方向が正しい(self, tmp_path: Path) -> None:
        """テストデータの因果リンクは fact -> claim の方向。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        causes = queue_data["relations"]["causes"]
        # 2 つとも fact -> claim
        for rel in causes:
            assert rel["from_label"] == "Fact"
            assert rel["to_label"] == "Claim"

    @freeze_time(FROZEN_TIME)
    def test_正常系_CAUSESのsource_idが設定される(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        source_ids = {s["source_id"] for s in queue_data["sources"]}
        for rel in queue_data["relations"]["causes"]:
            assert rel.get("source_id") in source_ids, (
                "CAUSES.source_id must reference an existing Source"
            )


# ---------------------------------------------------------------------------
# E2E: Wave 3 — TREND + NEXT_PERIOD テスト
# ---------------------------------------------------------------------------


class TestWave3TrendNextPeriod:
    """Wave 3: TREND / NEXT_PERIOD リレーション（時系列チェーン）を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_NEXT_PERIODリレーションが生成される(self, tmp_path: Path) -> None:
        """FiscalPeriod の時系列チェーン。

        テストデータの FiscalPeriod:
        - ISAT_3Q25 (quarterly)
        - ISAT_FY2025 (annual)
        - ISAT_FY2026 (annual)

        同一 (ticker, period_type) グループ内で NEXT_PERIOD が生成される:
        - annual: ISAT_FY2025 -> ISAT_FY2026
        - quarterly: ISAT_3Q25 のみ（1 つなのでチェーンなし）
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        next_period = queue_data["relations"]["next_period"]
        # annual group に 1 つの NEXT_PERIOD (FY2025 -> FY2026)
        assert len(next_period) >= 1, (
            f"Expected at least 1 NEXT_PERIOD, got {len(next_period)}"
        )

        # annual の NEXT_PERIOD を検証
        annual_rels = [
            r
            for r in next_period
            if "FY" in r.get("from_id", "") or "FY" in r.get("to_id", "")
        ]
        assert len(annual_rels) == 1, (
            f"Expected 1 annual NEXT_PERIOD, got {len(annual_rels)}"
        )
        assert annual_rels[0]["type"] == "NEXT_PERIOD"
        assert annual_rels[0]["from_id"] == "ISAT_FY2025"
        assert annual_rels[0]["to_id"] == "ISAT_FY2026"

    @freeze_time(FROZEN_TIME)
    def test_正常系_NEXT_PERIODにgap_monthsが含まれる(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for rel in queue_data["relations"]["next_period"]:
            assert "gap_months" in rel, "NEXT_PERIOD must have gap_months"
            assert isinstance(rel["gap_months"], int)

    @freeze_time(FROZEN_TIME)
    def test_正常系_TRENDリレーションが生成される(self, tmp_path: Path) -> None:
        """同一 (entity, metric_name) の FinancialDataPoint 間で TREND が生成。

        Revenue データ: 3Q25(15800) -> FY2025(62500) -> FY2026(68000)
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        trend = queue_data["relations"]["trend"]
        assert len(trend) >= 1, f"Expected at least 1 TREND, got {len(trend)}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_TRENDにchange_pctとdirectionが含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for rel in queue_data["relations"]["trend"]:
            assert rel["type"] == "TREND"
            assert "change_pct" in rel, "TREND must have change_pct"
            assert "direction" in rel, "TREND must have direction"
            assert rel["direction"] in {"up", "down", "flat"}

    @freeze_time(FROZEN_TIME)
    def test_正常系_TREND方向が正しい(self, tmp_path: Path) -> None:
        """Revenue の増加は direction=up であること。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        trend = queue_data["relations"]["trend"]
        # Revenue は 15800 -> 62500 -> 68000 と増加
        up_trends = [r for r in trend if r["direction"] == "up"]
        assert len(up_trends) >= 1, "Revenue increase should produce direction='up'"


# ---------------------------------------------------------------------------
# E2E: Wave 4 — Question テスト
# ---------------------------------------------------------------------------


class TestWave4Question:
    """Wave 4: Question ノードと ASKS_ABOUT / MOTIVATED_BY を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_Questionノードが生成される(self, tmp_path: Path) -> None:
        """受け入れ条件: questions[] に Question ノードが含まれること。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        questions = queue_data.get("questions", [])
        assert len(questions) == 2, f"Expected 2 questions, got {len(questions)}"

    @freeze_time(FROZEN_TIME)
    def test_正常系_Questionにquestion_idが存在する(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for q in queue_data["questions"]:
            assert "question_id" in q, "Question must have question_id"
            assert q["question_id"], "question_id must not be empty"

    @freeze_time(FROZEN_TIME)
    def test_正常系_question_idがSHA256ベースで32文字(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for q in queue_data["questions"]:
            qid = q["question_id"]
            assert len(qid) == 32, f"question_id should be 32 chars, got {len(qid)}"
            assert all(c in "0123456789abcdef" for c in qid)

    @freeze_time(FROZEN_TIME)
    def test_正常系_Questionのstatusがopenである(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for q in queue_data["questions"]:
            assert q.get("status") == "open"

    @freeze_time(FROZEN_TIME)
    def test_正常系_question_typeが正しく設定される(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        valid_types = {
            "data_gap",
            "contradiction",
            "prediction_test",
            "assumption_check",
        }
        q_types = {q["question_type"] for q in queue_data["questions"]}
        assert q_types <= valid_types, f"Invalid question_type: {q_types - valid_types}"
        assert "data_gap" in q_types
        assert "assumption_check" in q_types

    @freeze_time(FROZEN_TIME)
    def test_正常系_ASKS_ABOUTリレーションが生成される(self, tmp_path: Path) -> None:
        """Question -> Entity リレーション。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        asks_about = queue_data["relations"]["asks_about"]
        assert len(asks_about) == 2, f"Expected 2 ASKS_ABOUT, got {len(asks_about)}"
        for rel in asks_about:
            assert rel["type"] == "ASKS_ABOUT"

    @freeze_time(FROZEN_TIME)
    def test_正常系_MOTIVATED_BYリレーションが生成される(self, tmp_path: Path) -> None:
        """Question -> Fact/Claim リレーション。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        motivated_by = queue_data["relations"]["motivated_by"]
        assert len(motivated_by) == 2, (
            f"Expected 2 MOTIVATED_BY, got {len(motivated_by)}"
        )
        for rel in motivated_by:
            assert rel["type"] == "MOTIVATED_BY"

    @freeze_time(FROZEN_TIME)
    def test_正常系_MOTIVATED_BYがFact_Claimの正しいIDを参照(
        self,
        tmp_path: Path,
    ) -> None:
        """motivated_by_contents の content から正しい Fact/Claim ID が解決される。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        fact_ids = {f["fact_id"] for f in queue_data["facts"]}
        claim_ids = {c["claim_id"] for c in queue_data["claims"]}
        valid_ids = fact_ids | claim_ids

        for rel in queue_data["relations"]["motivated_by"]:
            assert rel["to_id"] in valid_ids, (
                f"MOTIVATED_BY.to_id {rel['to_id']} not in facts or claims"
            )

    @freeze_time(FROZEN_TIME)
    def test_正常系_question_idが決定論的である(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(q["question_id"] for q in q1["questions"])
        ids2 = sorted(q["question_id"] for q in q2["questions"])
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# E2E: 全Wave 統合 — 参照整合性テスト
# ---------------------------------------------------------------------------


class TestCrossWaveReferentialIntegrity:
    """全 Wave のノード・リレーション間の参照整合性を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_全リレーションのfrom_idとto_idが既存ノードを参照(
        self,
        tmp_path: Path,
    ) -> None:
        """受け入れ条件: 全リレーションの from_id/to_id が生成ノード ID に含まれる。

        v2.0 テストでは Source/Entity/Fact/Claim/Chunk/DP/FP のみ検証していたが、
        v2.1 では Author, Stance, Question も含めて全ノードタイプを網羅する。
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        all_ids = _collect_all_node_ids(queue_data)

        for rel_key, rels in queue_data["relations"].items():
            for rel in rels:
                assert rel["from_id"] in all_ids, (
                    f"Dangling from_id in {rel_key}: {rel['from_id']}"
                )
                assert rel["to_id"] in all_ids, (
                    f"Dangling to_id in {rel_key}: {rel['to_id']}"
                )

    @freeze_time(FROZEN_TIME)
    def test_正常系_HOLDS_STANCEのfrom_idがauthorsのauthor_idに含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        author_ids = {a["author_id"] for a in queue_data["authors"]}
        for rel in queue_data["relations"]["holds_stance"]:
            assert rel["from_id"] in author_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_HOLDS_STANCEのto_idがstancesのstance_idに含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        stance_ids = {s["stance_id"] for s in queue_data["stances"]}
        for rel in queue_data["relations"]["holds_stance"]:
            assert rel["to_id"] in stance_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_ON_ENTITYのto_idがentitiesのentity_idに含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        entity_ids = {e["entity_id"] for e in queue_data["entities"]}
        for rel in queue_data["relations"]["on_entity"]:
            assert rel["to_id"] in entity_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_ASKS_ABOUTのfrom_idがquestionsのquestion_idに含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        question_ids = {q["question_id"] for q in queue_data["questions"]}
        for rel in queue_data["relations"]["asks_about"]:
            assert rel["from_id"] in question_ids

    @freeze_time(FROZEN_TIME)
    def test_正常系_ASKS_ABOUTのto_idがentitiesのentity_idに含まれる(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        entity_ids = {e["entity_id"] for e in queue_data["entities"]}
        for rel in queue_data["relations"]["asks_about"]:
            assert rel["to_id"] in entity_ids


# ---------------------------------------------------------------------------
# E2E: v2.0 後方互換性テスト
# ---------------------------------------------------------------------------


class TestV20BackwardCompatibility:
    """v2.0 スキーマの既存データが v2.1 Wave 追加で破壊されていないことを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_factsとclaimsが分離されている(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["facts"]) > 0
        assert len(queue_data["claims"]) > 0

        for fact in queue_data["facts"]:
            assert "fact_id" in fact
            assert "claim_id" not in fact

        for claim in queue_data["claims"]:
            assert "claim_id" in claim
            assert "fact_id" not in claim

    @freeze_time(FROZEN_TIME)
    def test_正常系_confidenceがどのノードにも含まれない(self, tmp_path: Path) -> None:
        """v2.0 で廃止された confidence フィールドが復活していないことを検証。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for fact in queue_data["facts"]:
            assert "confidence" not in fact
        for claim in queue_data["claims"]:
            assert "confidence" not in claim

    @freeze_time(FROZEN_TIME)
    def test_正常系_chunksが正しく生成される(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["chunks"]) == len(data["chunks"])
        for chunk in queue_data["chunks"]:
            assert "chunk_id" in chunk
            assert "chunk_index" in chunk

    @freeze_time(FROZEN_TIME)
    def test_正常系_financial_datapointsが正しく生成される(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()
        expected_count = sum(
            len(c.get("financial_datapoints", [])) for c in data["chunks"]
        )
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["financial_datapoints"]) == expected_count

    @freeze_time(FROZEN_TIME)
    def test_正常系_fiscal_periodsが重複排除される(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        period_ids = [p["period_id"] for p in queue_data["fiscal_periods"]]
        assert len(period_ids) == len(set(period_ids)), (
            "Fiscal periods should be unique"
        )

    @freeze_time(FROZEN_TIME)
    def test_正常系_entitiesが重複排除される(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        entity_names = [e["name"] for e in queue_data["entities"]]
        # "Indosat Ooredoo Hutchison" は 3 チャンク全てに登場するが 1 つ
        assert entity_names.count("Indosat Ooredoo Hutchison") == 1

    @freeze_time(FROZEN_TIME)
    def test_正常系_v20基本リレーションが保持される(self, tmp_path: Path) -> None:
        """v2.0 の 11 基本リレーションが全て存在し、非空であること。"""
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        v20_keys = {
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
        }
        for key in v20_keys:
            assert key in queue_data["relations"], f"Missing v2.0 relation: {key}"
            assert len(queue_data["relations"][key]) > 0, (
                f"v2.0 relation {key} should not be empty"
            )


# ---------------------------------------------------------------------------
# E2E: 全Wave 冪等性テスト
# ---------------------------------------------------------------------------


class TestV21Idempotency:
    """v2.1 の全新ノードタイプで冪等性（同一データ → 同一 ID）を検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_2回生成でauthor_idが同一(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(a["author_id"] for a in q1["authors"])
        ids2 = sorted(a["author_id"] for a in q2["authors"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_2回生成でstance_idが同一(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(s["stance_id"] for s in q1["stances"])
        ids2 = sorted(s["stance_id"] for s in q2["stances"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_2回生成でquestion_idが同一(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        ids1 = sorted(q["question_id"] for q in q1["questions"])
        ids2 = sorted(q["question_id"] for q in q2["questions"])
        assert ids1 == ids2

    @freeze_time(FROZEN_TIME)
    def test_正常系_2回生成でSUPERSEDESリレーションが同一(
        self,
        tmp_path: Path,
    ) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        rels1 = sorted(
            (r["from_id"], r["to_id"]) for r in q1["relations"]["supersedes"]
        )
        rels2 = sorted(
            (r["from_id"], r["to_id"]) for r in q2["relations"]["supersedes"]
        )
        assert rels1 == rels2

    @freeze_time(FROZEN_TIME)
    def test_正常系_2回生成でCAUSESリレーションが同一(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        dir1 = tmp_path / "run1"
        dir1.mkdir()
        file1 = _generate_queue_file(dir1, data)
        q1 = _load_queue_file(file1)

        dir2 = tmp_path / "run2"
        dir2.mkdir()
        file2 = _generate_queue_file(dir2, data)
        q2 = _load_queue_file(file2)

        rels1 = sorted((r["from_id"], r["to_id"]) for r in q1["relations"]["causes"])
        rels2 = sorted((r["from_id"], r["to_id"]) for r in q2["relations"]["causes"])
        assert rels1 == rels2


# ---------------------------------------------------------------------------
# E2E: ノード数整合性テスト
# ---------------------------------------------------------------------------


class TestNodeCounts:
    """全ノードタイプの生成数が入力データと整合することを検証。"""

    @freeze_time(FROZEN_TIME)
    def test_正常系_fact数が入力と一致(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        expected = sum(len(c.get("facts", [])) for c in data["chunks"])

        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["facts"]) == expected

    @freeze_time(FROZEN_TIME)
    def test_正常系_claim数が入力と一致(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        expected = sum(len(c.get("claims", [])) for c in data["chunks"])

        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["claims"]) == expected

    @freeze_time(FROZEN_TIME)
    def test_正常系_chunk数が入力と一致(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()

        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["chunks"]) == len(data["chunks"])

    @freeze_time(FROZEN_TIME)
    def test_正常系_stance数が入力と一致(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        expected = sum(len(c.get("stances", [])) for c in data["chunks"])

        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["stances"]) == expected

    @freeze_time(FROZEN_TIME)
    def test_正常系_question数が入力と一致(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        expected = sum(len(c.get("questions", [])) for c in data["chunks"])

        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["questions"]) == expected

    @freeze_time(FROZEN_TIME)
    def test_正常系_causal_links数が入力と一致(self, tmp_path: Path) -> None:
        data = _full_v21_pdf_extraction_data()
        expected = sum(len(c.get("causal_links", [])) for c in data["chunks"])

        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        assert len(queue_data["relations"]["causes"]) == expected


# ---------------------------------------------------------------------------
# E2E: Neo4j 推論クエリ互換性テスト（クエリ結果シミュレーション）
# ---------------------------------------------------------------------------


class TestNeo4jQueryCompatibility:
    """Issue #141 の推論クエリに必要なデータ構造が graph-queue に含まれることを検証。

    実際の Neo4j 接続は不要。クエリが期待するノード・リレーション構造が
    graph-queue JSON に正しく含まれていることをシミュレートする。
    """

    @freeze_time(FROZEN_TIME)
    def test_正常系_SUPERSEDES連鎖クエリ互換_Author_Stance_Entity参照可能(
        self,
        tmp_path: Path,
    ) -> None:
        """Wave 1 推論クエリ:
        MATCH (a:Author)-[:HOLDS_STANCE]->(s:Stance)-[:ON_ENTITY]->(e:Entity)
        OPTIONAL MATCH (s)-[:SUPERSEDES]->(prev:Stance)
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        # Author -> Stance (HOLDS_STANCE)
        author_ids = {a["author_id"] for a in queue_data["authors"]}
        stance_ids = {s["stance_id"] for s in queue_data["stances"]}
        entity_ids = {e["entity_id"] for e in queue_data["entities"]}

        for rel in queue_data["relations"]["holds_stance"]:
            assert rel["from_id"] in author_ids
            assert rel["to_id"] in stance_ids

        # Stance -> Entity (ON_ENTITY)
        for rel in queue_data["relations"]["on_entity"]:
            assert rel["from_id"] in stance_ids
            assert rel["to_id"] in entity_ids

        # Stance -> Stance (SUPERSEDES)
        for rel in queue_data["relations"]["supersedes"]:
            assert rel["from_id"] in stance_ids
            assert rel["to_id"] in stance_ids

        # Stance の rating, target_price, as_of_date が設定済み
        for stance in queue_data["stances"]:
            assert stance.get("rating") is not None
            assert stance.get("as_of_date") is not None

    @freeze_time(FROZEN_TIME)
    def test_正常系_因果チェーンクエリ互換_CAUSES_with_confidence(
        self,
        tmp_path: Path,
    ) -> None:
        """Wave 2 推論クエリ:
        MATCH (cause)-[r:CAUSES {confidence: "stated"}]->(effect)
        RETURN cause.content, r.mechanism, effect.content
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        for rel in queue_data["relations"]["causes"]:
            assert "mechanism" in rel
            assert "confidence" in rel
            # from_id/to_id は Fact/Claim/DP のいずれか
            assert "from_label" in rel
            assert "to_label" in rel

    @freeze_time(FROZEN_TIME)
    def test_正常系_TREND走査クエリ互換_DP_TREND_next(
        self,
        tmp_path: Path,
    ) -> None:
        """Wave 3 推論クエリ:
        MATCH (dp:FinancialDataPoint)-[t:TREND]->(next)
        RETURN dp.metric_name, dp.value, t.change_pct, t.direction, next.value
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        dp_ids = {dp["datapoint_id"] for dp in queue_data["financial_datapoints"]}
        dp_by_id = {dp["datapoint_id"]: dp for dp in queue_data["financial_datapoints"]}

        for rel in queue_data["relations"]["trend"]:
            assert rel["from_id"] in dp_ids
            assert rel["to_id"] in dp_ids
            assert "change_pct" in rel
            assert "direction" in rel

            # DP ノードに metric_name, value が存在
            from_dp = dp_by_id[rel["from_id"]]
            to_dp = dp_by_id[rel["to_id"]]
            assert "metric_name" in from_dp
            assert "value" in from_dp
            assert "value" in to_dp

    @freeze_time(FROZEN_TIME)
    def test_正常系_Questionクエリ互換_open_status_priority_entity(
        self,
        tmp_path: Path,
    ) -> None:
        """Wave 4 推論クエリ:
        MATCH (q:Question {status: "open"})-[:ASKS_ABOUT]->(e:Entity)
        RETURN q.content, q.question_type, q.priority, e.name
        ORDER BY q.priority
        """
        data = _full_v21_pdf_extraction_data()
        output_file = _generate_queue_file(tmp_path, data)
        queue_data = _load_queue_file(output_file)

        entity_by_id = {e["entity_id"]: e for e in queue_data["entities"]}
        question_by_id = {q["question_id"]: q for q in queue_data["questions"]}

        # status: open の Question が存在
        open_questions = [q for q in queue_data["questions"] if q["status"] == "open"]
        assert len(open_questions) == 2

        # ASKS_ABOUT で Entity に接続されている
        for rel in queue_data["relations"]["asks_about"]:
            q = question_by_id[rel["from_id"]]
            e = entity_by_id[rel["to_id"]]
            assert q["content"], "Question must have content"
            assert q["question_type"], "Question must have question_type"
            assert e["name"], "Entity must have name"
