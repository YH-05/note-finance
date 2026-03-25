"""Pydantic models for source registry and collection methods.

Layer 0 のデータモデル。データソースと収集方法を型安全に管理する。
収集方法は Enum ではなく文字列 + 外部定義（collection_methods.json）で
拡張性を確保する。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Collection Method (収集方法の定義)
# ---------------------------------------------------------------------------


class CollectionMethodDef(BaseModel):
    """収集方法の定義.

    collection_methods.json の各エントリに対応する。
    新しい収集方法はここに追加せず、JSONに追加するだけでよい。
    """

    method_id: str = Field(description="収集方法の一意キー (例: rss, scraping, api)")
    name: str = Field(description="表示名")
    description: str = Field(default="", description="説明")
    required_config: list[str] = Field(
        default_factory=list,
        description="この収集方法で必須の設定項目名",
    )
    optional_config: list[str] = Field(
        default_factory=list,
        description="この収集方法で任意の設定項目名",
    )
    default_schedule: str = Field(
        default="daily",
        description="デフォルトの収集スケジュール",
    )


class CollectionMethodRegistry(BaseModel):
    """収集方法レジストリ.

    collection_methods.json 全体に対応する。
    """

    version: str = Field(description="スキーマバージョン")
    methods: dict[str, CollectionMethodDef] = Field(
        description="method_id → 定義のマッピング",
    )

    def has_method(self, method_id: str) -> bool:
        """指定された収集方法が定義されているか."""
        return method_id in self.methods

    def method_ids(self) -> list[str]:
        """定義済みの全収集方法IDを返す."""
        return list(self.methods.keys())


# ---------------------------------------------------------------------------
# Data Source (データソース定義)
# ---------------------------------------------------------------------------


class ConfigRef(BaseModel):
    """既存設定ファイルへの参照.

    統合インデックスは「ポインタ」のみを持ち、
    詳細設定は既存の data/config/*.json に委譲する。
    """

    file: str = Field(description="設定ファイル名 (例: rss-presets.json)")
    key: str | None = Field(
        default=None,
        description="ファイル内のキー (特定セクションを指す場合)",
    )
    item_count: int | None = Field(
        default=None,
        description="管理アイテム数 (概算)",
    )


class DataSource(BaseModel):
    """データソース定義.

    source_registry.json の各エントリに対応する。
    プロバイダー単位の粒度で管理する。
    """

    source_id: str = Field(description="一意キー (例: cnbc, yfinance, fred)")
    name: str = Field(description="表示名 (英語)")
    name_ja: str | None = Field(default=None, description="表示名 (日本語)")
    collection_method: str = Field(
        description="収集方法ID (collection_methods.json に定義された値)",
    )
    authority_level: int = Field(
        ge=1,
        le=5,
        description="信頼度 (1=低, 5=高). 公的機関=5, 大手メディア=4, 専門メディア=3, ブログ=2, UGC=1",
    )
    target_instance: Literal["research", "creator", "note"] = Field(
        description="投入先Neo4jインスタンス",
    )
    enabled: bool = Field(default=True, description="有効フラグ")
    schedule: str = Field(
        default="daily",
        description="収集スケジュール (daily/weekly/on_demand/manual)",
    )
    config_ref: ConfigRef | None = Field(
        default=None,
        description="既存設定ファイルへの参照",
    )
    emit_command: str | None = Field(
        default=None,
        description="emit_research_queue.py の --command 値",
    )
    tags: list[str] = Field(default_factory=list, description="カテゴリタグ")
    url: str | None = Field(default=None, description="ソースのベースURL")
    neo4j_connected: bool = Field(
        default=True,
        description="Neo4j投入パイプライン接続済みか",
    )
    notes: str | None = Field(default=None, description="備考")

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, v: str) -> str:
        allowed = {"daily", "weekly", "on_demand", "manual"}
        if v not in allowed:
            msg = f"schedule must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Source Registry (統合レジストリ)
# ---------------------------------------------------------------------------


class SourceRegistry(BaseModel):
    """統合ソースレジストリ.

    source_registry.json 全体に対応する。
    全データソースをプロバイダー単位で一元管理する。
    """

    version: str = Field(description="スキーマバージョン")
    updated_at: str = Field(description="最終更新日時 (ISO 8601)")
    sources: list[DataSource] = Field(description="データソース一覧")

    def get_source(self, source_id: str) -> DataSource | None:
        """source_id でソースを検索."""
        for s in self.sources:
            if s.source_id == source_id:
                return s
        return None

    def filter_by_method(self, method: str) -> list[DataSource]:
        """収集方法でフィルタ."""
        return [s for s in self.sources if s.collection_method == method]

    def filter_by_instance(self, instance: str) -> list[DataSource]:
        """対象インスタンスでフィルタ."""
        return [s for s in self.sources if s.target_instance == instance]

    def filter_by_tag(self, tag: str) -> list[DataSource]:
        """タグでフィルタ."""
        return [s for s in self.sources if tag in s.tags]

    def get_enabled(self) -> list[DataSource]:
        """有効なソースのみ返す."""
        return [s for s in self.sources if s.enabled]

    def get_disconnected(self) -> list[DataSource]:
        """Neo4j未接続ソース一覧."""
        return [s for s in self.sources if not s.neo4j_connected]

    @property
    def source_ids(self) -> list[str]:
        """全source_idのリスト."""
        return [s.source_id for s in self.sources]


# ---------------------------------------------------------------------------
# Validation (バリデーション結果)
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    """バリデーション問題の報告."""

    level: Literal["error", "warning"] = Field(description="深刻度")
    source_id: str | None = Field(
        default=None,
        description="問題のあるソースID (全体の問題ならNone)",
    )
    message: str = Field(description="問題の説明")
