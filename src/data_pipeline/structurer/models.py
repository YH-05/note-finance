"""emit_research_queue.py web-research コマンドの入力形式に対応するモデル.

Layer 3 の出力 = emit_research_queue.py の入力。
このモデルに変換すれば、既存の Neo4j 投入パイプラインに乗せられる。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Source（情報源）
# ---------------------------------------------------------------------------


class SourceEntry(BaseModel):
    """emit_research_queue.py の sources[] エントリ."""

    url: str = Field(description="ソースURL")
    title: str = Field(default="", description="ソースタイトル")
    source_type: str = Field(default="web", description="ソースタイプ (web/pdf/rss等)")
    authority_level: Literal[
        "official", "analyst", "media", "blog", "social", "academic"
    ] = Field(description="信頼度レベル")
    publisher: str = Field(default="", description="パブリッシャー名")
    data_source: str = Field(default="", description="データ由来タグ (tavily/gemini/rss等)")
    published_at: str = Field(default="", description="公開日時 (ISO 8601)")


# ---------------------------------------------------------------------------
# Fact（事実）
# ---------------------------------------------------------------------------


class AboutEntity(BaseModel):
    """Fact/Claim に関連するエンティティ."""

    name: str = Field(description="エンティティ名")
    entity_type: str = Field(
        default="",
        description="エンティティタイプ (company/person/index/currency等)",
    )


class FactEntry(BaseModel):
    """emit_research_queue.py の facts[] エントリ."""

    content: str = Field(description="事実の記述")
    source_url: str = Field(description="ソースURL (sources[] 内のURLと一致)")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="確信度")
    fact_type: str = Field(
        default="general",
        description="事実タイプ (financial_metric/operational_kpi/market_event等)",
    )
    about_entities: list[AboutEntity] = Field(
        default_factory=list,
        description="関連エンティティ",
    )


# ---------------------------------------------------------------------------
# Claim（主張・意見）
# ---------------------------------------------------------------------------


class ClaimEntry(BaseModel):
    """emit_research_queue.py の claims[] エントリ."""

    content: str = Field(description="主張・意見の記述")
    source_url: str = Field(default="", description="ソースURL")
    claim_type: str = Field(
        default="analyst_opinion",
        description="主張タイプ (analyst_opinion/analyst_forecast/market_consensus等)",
    )
    sentiment: Literal["positive", "negative", "neutral"] = Field(
        default="neutral",
        description="センチメント",
    )
    about_entities: list[AboutEntity] = Field(
        default_factory=list,
        description="関連エンティティ",
    )


# ---------------------------------------------------------------------------
# Topic（トピック）
# ---------------------------------------------------------------------------


class TopicEntry(BaseModel):
    """emit_research_queue.py の topics[] エントリ."""

    name: str = Field(description="トピック名")
    category: str = Field(default="", description="トピックカテゴリ")


# ---------------------------------------------------------------------------
# StructuredOutput（Layer 3 の最終出力）
# ---------------------------------------------------------------------------


class StructuredOutput(BaseModel):
    """emit_research_queue.py web-research コマンドの入力形式.

    この形式に変換すれば:
    1. JSON として保存
    2. emit_research_queue.py --command web-research --input <file> で graph-queue 生成
    3. /save-to-research-graph で Neo4j 投入
    """

    sources: list[SourceEntry] = Field(default_factory=list)
    facts: list[FactEntry] = Field(default_factory=list)
    claims: list[ClaimEntry] = Field(default_factory=list)
    topics: list[TopicEntry] = Field(default_factory=list)

    def to_emit_input(self) -> dict[str, Any]:
        """emit_research_queue.py の入力 dict に変換する."""
        return self.model_dump(mode="json")

    @property
    def is_empty(self) -> bool:
        """構造化データが空か."""
        return not self.facts and not self.claims

    @property
    def fact_count(self) -> int:
        return len(self.facts)

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    @property
    def entity_names(self) -> list[str]:
        """全ファクト・クレームに含まれるエンティティ名の一覧."""
        names: set[str] = set()
        for f in self.facts:
            for e in f.about_entities:
                names.add(e.name)
        for c in self.claims:
            for e in c.about_entities:
                names.add(e.name)
        return sorted(names)
