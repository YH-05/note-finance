# PDF→Markdown パイプライン設計 — 5論点の議論と改訂案

Created: 2026-03-11
Status: 議論中
Parent: `docs/plan/KnowledgeGraph/2026-03-11_pdf-to-markdown-pipeline.md`

---

## Context

`2026-03-11_pdf-to-markdown-pipeline.md` に対して5つの論点が提起された。
本ドキュメントは各論点への回答と、元プランへの改訂案をまとめる。

---

## 論点1: Phase 3B — Pydanticテーブルスキーマの設計

### 問題

元プランの `FinancialStatementTable` は単純すぎる。サンプルPDF（HSBC ISAT 3Q25）を分析すると、少なくとも以下9種のテーブル構造が存在:

| # | テーブル種別 | 例 | 特徴 |
|---|-------------|---|------|
| 1 | サマリー財務指標 | Financials and Ratios (p.1) | 時系列 + 実績/予想混在 |
| 2 | マーケットデータ | Market Data (p.1) | Key-Valueペア |
| 3 | 四半期業績 | ISAT 3Q25 results (p.3) | QoQ/YoY計算列あり |
| 4 | KPI | Subscribers/ARPU/BTS (p.3) | 数値+千人単位 |
| 5 | 費用内訳 | Operating expenses (p.3) | 階層行（小計+明細） |
| 6 | コスト詳細 | Cost of services (p.3) | 同上 |
| 7 | 推定変更 | Change in estimates (p.5) | New vs Previous vs Delta |
| 8 | バリュエーション | Valuation data (p.2) | 倍率時系列 |
| 9 | ESG指標 | ESG metrics (p.2) | 2つの副テーブルを並置 |

### 改訂案: 3層テーブルスキーマ

`src/pdf_pipeline/schemas/tables.py` に配置。

```
Tier 1: RawTable       — 全テーブル共通。データ損失なしの汎用コンテナ
Tier 2: 型付きテーブル  — テーブル種別ごとの構造化モデル
Tier 3: ExtractedTables — 1PDF分の全テーブルを束ねるエンベロープ
```

#### Tier 1: RawTable（常に生成 — フォールバック保証）

```python
class TableCell(BaseModel):
    value: str
    numeric_value: float | None = None
    unit: str | None = None           # "IDRb", "%", "x", "000s"
    is_bold: bool = False
    is_header: bool = False
    colspan: int = 1
    rowspan: int = 1

class RawTable(BaseModel):
    table_id: str                     # "{source_hash}_table_{seq:03d}"
    headers: list[list[TableCell]]    # 多段ヘッダー対応
    rows: list[list[TableCell]]
    source_page: int | None = None
    caption: str | None = None
    footnotes: list[str] = []
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
```

#### Tier 2: 型付きテーブル

```python
class FinancialMetric(BaseModel):
    metric: str                       # "Revenue", "EBITDA" 等
    level: int = 0                    # インデント深度（0=トップ, 1=明細）
    is_subtotal: bool = False
    values: dict[str, float | str | None]  # period_label -> value

class TimeSeriesTable(BaseModel):
    """P&L, BS, CF, Valuation, KPI, Segment, Opex 等"""
    table_type: Literal[
        "pnl", "cashflow", "balance_sheet", "valuation",
        "kpi", "segment", "opex", "generic_timeseries"
    ]
    title: str
    currency: str | None = None       # "IDR", "USD"
    scale: str | None = None          # "b", "m", "000s"
    periods: list[str]                # ["12/2024a", "12/2025e", ...]
    period_types: list[Literal["actual", "estimate", "quarterly"]] | None = None
    rows: list[FinancialMetric]
    source_page: int | None = None
    footnotes: list[str] = []

class EstimateChangeTable(BaseModel):
    """推定改訂テーブル（New vs Previous vs Delta）"""
    title: str
    scenarios: list[str]              # ["HSBC new", "HSBC previous", "Change %"]
    periods: list[str]
    rows: list[FinancialMetric]
    source_page: int | None = None

class KeyValueTable(BaseModel):
    """マーケットデータ、発行体情報等"""
    title: str
    pairs: dict[str, str | float | None]
    source_page: int | None = None
```

#### Tier 3: エンベロープ

```python
class ExtractedTables(BaseModel):
    source_hash: str
    raw_tables: list[RawTable]                      # 常に生成
    timeseries_tables: list[TimeSeriesTable] = []    # 分類成功時
    estimate_tables: list[EstimateChangeTable] = []
    kv_tables: list[KeyValueTable] = []
    unclassified: list[int] = []                     # raw_tables へのインデックス
```

### 設計判断

- **Tier 1は常に生成**: Geminiが分類に失敗してもデータは失われない
- **`level` フィールド**: 階層行（"Cost of Services" → "Radio frequency fee" at level=1）を表現
- **`currency` + `scale` をテーブルレベルに**: セルごとの冗長な単位情報を排除
- **多段ヘッダー**: `headers: list[list[TableCell]]` でセルサイドレポート特有の結合ヘッダーに対応

---

## 論点2: Phase 5 — Fact/Claim/Entity だけで十分か？

### 結論: 不十分。追加ノード・リレーションが必要

サンプルPDFを分析すると、現在の3ノードでは表現できないデータ型が複数ある:

| データ型 | HSBC ISATでの例 | 現スキーマでの扱い | ギャップ |
|---------|----------------|------------------|---------|
| 構造化財務数値 | "EBITDA 2025e: IDR26,667b" | Fact (data_point) | 数値・期間・単位が非構造化 |
| アナリスト推定 | "EPS 2026e: 180 IDR" | Fact | 実績/予想の区別なし |
| TP/レーティング | "Buy, TP IDR3,000" | Claim (recommendation) | target_price フィールドなし |
| 時間軸アンカー | "3Q25", "FY24-27e" | Fact.as_of_date | 単一日付のみ、期間範囲なし |
| 法人間関係 | "ISAT is subsidiary of Ooredoo" | Entity | Entity間リレーションなし |

### 改訂案: スキーマ拡張

`data/config/knowledge-graph-schema.yaml` への追加:

#### 新規ノード

**1. Chunk**（元プランに既出 — 確認）
```yaml
Chunk:
    description: "Text chunk from a source document for traceability"
    properties:
      chunk_id: {type: string, unique: true, required: true}
      text: {type: string, required: true}
      chunk_index: {type: integer, required: true}
      chunk_type: {type: string, enum: [text, table, figure], indexed: true}
      section_title: {type: string}
      page_ref: {type: string}
```

**2. FinancialDataPoint（新規）**
```yaml
FinancialDataPoint:
    description: "Structured quantitative data from financial reports"
    properties:
      datapoint_id: {type: string, unique: true, required: true}
      metric_name: {type: string, required: true, indexed: true}
      value: {type: float, required: true}
      unit: {type: string}
      period: {type: string, indexed: true}  # "2025e", "3Q25"
      period_type: {type: string, enum: [annual, quarterly, half_year, ytd]}
      is_estimate: {type: boolean, default: false}
      estimator: {type: string}  # "HSBC", "consensus", "company_guidance"
```

**3. FiscalPeriod（新規 — first-memoのTemporal Layer由来）**
```yaml
FiscalPeriod:
    description: "Temporal anchor for financial data"
    properties:
      period_id: {type: string, unique: true, required: true}
      period_label: {type: string, required: true}
      year: {type: integer, indexed: true}
      quarter: {type: integer}
      period_type: {type: string, enum: [annual, quarterly, half_year]}
```

#### 既存ノードの拡張

**Claim に analyst recommendation フィールドを追加:**
```yaml
Claim:
    properties:
      # ... 既存フィールド ...
      target_price: {type: float}
      target_currency: {type: string}
      rating: {type: string, enum: [buy, overweight, neutral, underweight, sell]}
```

#### 新規リレーション

```yaml
HAS_CHUNK:
    from: Source
    to: Chunk

EXTRACTED_FROM:
    from: [Fact, Claim, FinancialDataPoint]
    to: Chunk
    description: "トレーサビリティ: 元テキストチャンクへのリンク"

HAS_DATAPOINT:
    from: Source
    to: FinancialDataPoint

PERTAINS_TO:
    from: [FinancialDataPoint, Fact, Claim]
    to: FiscalPeriod
    description: "時間軸アンカー"

MEASURES:
    from: FinancialDataPoint
    to: Entity
    description: "このデータポイントがどのEntityの指標か"

SUBSIDIARY_OF:
    from: Entity
    to: Entity
    properties:
      ownership_pct: {type: float}
```

### Phase 5 の分割提案

Phase 5を一度に実装するのは大きすぎるため、サブフェーズに分割:

| サブフェーズ | 内容 | 入力 |
|------------|------|------|
| 5A | Fact + Claim + Entity 抽出（現行計画） | body.md (テキストチャンク) |
| 5B | FinancialDataPoint 抽出 | Phase 3B の table JSON（構造化済み） |
| 5C | FiscalPeriod 生成 + PERTAINS_TO リンク | 5A + 5B の出力 |
| 5D | Entity間リレーション抽出 (SUBSIDIARY_OF等) | テキスト全体 |

---

## 論点3: mcp-neo4j-data-modeling を使わない理由

### 現状

- `.mcp.json` に `neo4j-data-modeling` は**設定済み**
- `.claude/settings.local.json` の `enabledMcpjsonServers` にも**含まれている**
- しかし `allowedTools` に `mcp__neo4j-data-modeling__*` ツールが**未登録**
- → ツール呼び出しのたびに許可確認が必要で、実質的に使用されていなかった

### 改訂案: パイプラインへの統合ポイント

| MCPツール | パイプラインでの用途 | 使用Phase |
|----------|-------------------|----------|
| `validate_data_model` | スキーマYAML変更時のバリデーション | スキーマ進化時（Phase 5前） |
| `validate_node` | 抽出Fact/Claim/Entityの構造検証 | Phase 5（知識抽出後） |
| `validate_relationship` | リレーション構造の検証 | Phase 5 |
| `export_to_pydantic_models` | YAMLスキーマ → Pydanticモデル自動生成 | Phase 5セットアップ |
| `get_constraints_cypher_queries` | Neo4j制約DDL自動生成 | 初期セットアップ |

### 実施事項

1. **`.claude/settings.local.json` に以下を追加**:
   ```
   "mcp__neo4j-data-modeling__validate_data_model",
   "mcp__neo4j-data-modeling__validate_node",
   "mcp__neo4j-data-modeling__validate_relationship",
   "mcp__neo4j-data-modeling__export_to_pydantic_models",
   "mcp__neo4j-data-modeling__get_constraints_cypher_queries"
   ```

2. **スキーマの Single Source of Truth 確立**:
   ```
   knowledge-graph-schema.yaml (SSOT)
     → export_to_pydantic_models → src/pdf_pipeline/schemas/extraction.py
     → get_constraints_cypher_queries → data/config/neo4j-constraints.cypher
     → validate_data_model で整合性チェック
   ```

3. **Phase 5 の知識抽出後バリデーション**:
   LLM出力 → Pydanticバリデーション → `validate_node` で追加チェック → graph-queue emit

---

## 論点4: 検証方法 — Gemini生成MDではなく生PDFベースの検証

### 問題

`HSBC_ISAT_3Q25_Complete_Faithful.md` はGemini CLIで生成した出力であり、
AI出力をAI出力の正解データにするのは循環的で不適切。

### 改訂案: 構造化グラウンドトゥルース方式

全文比較ではなく、**人手で検証可能な離散データポイント**をグラウンドトゥルースとして使う。

#### グラウンドトゥルース・スキーマ

```python
class GroundTruthMetric(BaseModel):
    metric_name: str          # "Revenue 3Q25"
    expected_value: float     # 14052
    unit: str                 # "IDRb"
    source_page: int          # 3
    table_ref: str | None     # "Table 1: ISAT 3Q25 results"

class GroundTruthSection(BaseModel):
    heading: str              # "3Q25 results: Cellular revenue up 4%"
    heading_level: int        # 2
    page: int

class GroundTruthDocument(BaseModel):
    pdf_filename: str
    broker: str
    subject_entity: str
    rating: str | None
    target_price: float | None
    target_currency: str | None
    key_metrics: list[GroundTruthMetric]  # 各PDF 5-10個
    sections: list[GroundTruthSection]
    table_count: int
    page_count: int
    noise_phrases: list[str]  # 出力に含まれてはいけないフレーズ
```

#### 検証ファイル

`data/sample_report/ground_truth.json` — 人手で作成。8 PDFすべてをカバー。

初期は以下3ブローカーで重点検証（フォーマット多様性を確保）:

| ブローカー | サイズ | 選定理由 |
|-----------|--------|---------|
| HSBC | 354 KB | 既存MD変換結果と比較可能、ベースライン |
| Jefferies | 1.4 MB | 最大サイズ、複雑レイアウトの可能性 |
| UBS | 259 KB | 最小サイズ、シンプルフォーマットの確認 |

#### 3軸検証

| 検証軸 | 方法 | 目標 |
|--------|------|------|
| **数値抽出精度** | ground_truth.key_metrics の各値が抽出テーブルJSONに存在するか | 95%+ |
| **構造保持** | ground_truth.sections の見出しがMD出力に正しい階層で出現するか | 100% |
| **ノイズ除去率** | ground_truth.noise_phrases がMD出力に含まれないこと | 100% |

#### テスト配置

`tests/pdf_pipeline/integration/test_conversion_accuracy.py`

```python
class TestConversionAccuracy:
    def test_正常系_数値抽出精度が95パーセント以上(self, ground_truth, extracted):
        """ground_truth.key_metrics の値が extracted table JSON に存在する"""

    def test_正常系_セクション見出しが全て保持される(self, ground_truth, markdown):
        """ground_truth.sections の heading が markdown 中に出現する"""

    def test_正常系_ノイズフレーズが除去されている(self, ground_truth, markdown):
        """ground_truth.noise_phrases が markdown 中に含まれない"""
```

---

## 論点5: Gemini CLI主体 → Claude Codeフォールバック対応

### 現行パターン

プロジェクトには2つの既存AIパターンがある:

1. **Gemini CLI**: `subprocess.run(["gemini", "--prompt", ...])` — `scripts/collect_finance_news_*.py`
2. **Claude Agent SDK**: `AgentProcessor` ABC + lazy import — `src/news/processors/agent_base.py`

### 改訂案: LLMProvider Protocol + ProviderChain

#### ファイル構成

```
src/pdf_pipeline/services/
├── llm_provider.py       # LLMProvider Protocol + LLMProviderError
├── gemini_provider.py    # GeminiCLIProvider
├── claude_provider.py    # ClaudeCodeProvider（lazy import）
├── provider_chain.py     # フォールバック付きプロバイダーチェーン
└── state_manager.py      # 処理状態管理（元プランから変更なし）
```

元プランの `gemini_client.py` は `gemini_provider.py` + `llm_provider.py` に分割。

#### LLMProvider Protocol

```python
# src/pdf_pipeline/services/llm_provider.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class LLMProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    def convert_pdf_to_markdown(
        self, pdf_path: Path, filtered_text: str | None = None,
        prompt_template: str | None = None,
    ) -> str: ...

    def extract_table_json(
        self, table_image_path: Path, schema_hint: str | None = None,
    ) -> dict: ...

    def extract_knowledge(
        self, chunk_text: str, extraction_schema: str,
    ) -> dict: ...

    def is_available(self) -> bool: ...
```

#### GeminiCLIProvider

```python
# src/pdf_pipeline/services/gemini_provider.py
class GeminiCLIProvider:
    def __init__(self, timeout: int = 120, model: str | None = None): ...

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def _run_gemini(self, prompt: str, files: list[Path] | None = None) -> str:
        cmd = ["gemini"]
        if self._model:
            cmd.extend(["--model", self._model])
        for f in (files or []):
            cmd.extend(["--file", str(f)])
        cmd.extend(["--prompt", prompt])
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=self._timeout)
        if result.returncode != 0:
            raise LLMProviderError(f"Gemini CLI failed: {result.stderr}")
        return result.stdout
```

#### ClaudeCodeProvider

```python
# src/pdf_pipeline/services/claude_provider.py
# AIDEV-NOTE: AgentProcessor._get_sdk() パターン踏襲（lazy import）
class ClaudeCodeProvider:
    _sdk: Any = None

    def is_available(self) -> bool:
        try:
            import claude_agent_sdk  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_sdk(self) -> Any:
        # src/news/processors/agent_base.py:243-274 と同じパターン
        ...
```

#### ProviderChain（フォールバック制御）

```python
# src/pdf_pipeline/services/provider_chain.py
class ProviderChain:
    def __init__(self, providers: list[LLMProvider]) -> None: ...

    def execute_with_fallback(self, method_name: str, *args, **kwargs) -> Any:
        """各プロバイダーを順に試行。全失敗時にLLMProviderError"""
        errors = []
        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                return getattr(provider, method_name)(*args, **kwargs)
            except Exception as e:
                logger.warning("Provider failed", provider=provider.provider_name, error=str(e))
                errors.append((provider.provider_name, e))
        raise LLMProviderError(f"All providers failed: {errors}")
```

#### 設定

`data/config/pdf-pipeline-config.yaml` に追加:

```yaml
llm:
  provider_order: ["gemini_cli", "claude_code"]  # 順序 = 優先度
  fallback_enabled: true
  gemini:
    timeout: 120
    model: null          # デフォルトモデル使用
  claude:
    timeout: 120
```

#### パイプラインへの統合

```python
# src/pdf_pipeline/core/pipeline.py
class PdfPipeline:
    def __init__(self, config: PipelineConfig) -> None:
        providers = []
        for name in config.llm.provider_order:
            match name:
                case "gemini_cli":
                    providers.append(GeminiCLIProvider(...))
                case "claude_code":
                    providers.append(ClaudeCodeProvider(...))
        self._chain = ProviderChain(providers)

    def run_phase_3a(self, pdf_path: Path, filtered_text: str) -> str:
        return self._chain.execute_with_fallback(
            "convert_pdf_to_markdown", pdf_path=pdf_path, filtered_text=filtered_text
        )
```

---

## 改訂後のファイル構成（全体）

```
src/pdf_pipeline/
├── __init__.py
├── types.py                        # ProcessingState, PdfMetadata 等
├── schemas/
│   └── tables.py                   # 3層テーブルスキーマ（論点1）
├── config/
│   └── loader.py                   # YAML設定ローダー
├── core/
│   ├── pipeline.py                 # パイプラインオーケストレーター
│   ├── pdf_scanner.py              # PDF検出・ハッシュ計算
│   ├── noise_filter.py             # ノイズフィルター
│   ├── table_detector.py           # 表検出・画像切り出し
│   ├── markdown_converter.py       # Phase 3A: Vision-first変換
│   ├── table_reconstructor.py      # Phase 3B: 表→JSON再構築
│   └── chunker.py                  # Phase 4: セクション単位チャンキング
├── services/
│   ├── llm_provider.py             # LLMProvider Protocol（論点5）
│   ├── gemini_provider.py          # GeminiCLIProvider（論点5）
│   ├── claude_provider.py          # ClaudeCodeProvider（論点5）
│   ├── provider_chain.py           # フォールバック制御（論点5）
│   └── state_manager.py            # 処理状態管理（冪等性）
└── cli/
    └── main.py                     # Click CLI

data/config/
├── pdf-pipeline-config.yaml        # パイプライン設定（llmセクション追加）
└── knowledge-graph-schema.yaml     # スキーマ拡張（論点2）

data/sample_report/
├── ground_truth.json               # 構造化グラウンドトゥルース（論点4）
├── *.pdf                           # 8ブローカーのサンプルPDF
└── docling_output/                 # Docling出力（参考）

tests/pdf_pipeline/
├── unit/
│   ├── test_tables_schema.py       # テーブルスキーマのバリデーション
│   ├── test_provider_chain.py      # フォールバック動作
│   └── test_noise_filter.py        # ノイズ除去
└── integration/
    └── test_conversion_accuracy.py # 3軸検証（論点4）
```

---

## 次のアクション

元プラン `docs/plan/KnowledgeGraph/2026-03-11_pdf-to-markdown-pipeline.md` を本議論の合意事項で改訂する。主な変更箇所:

1. Phase 3B のスキーマ定義を3層設計に差し替え
2. Phase 5 を 5A-5D に分割、新規ノード/リレーション追加
3. mcp-neo4j-data-modeling の活用セクションを追加
4. 検証方法をグラウンドトゥルース方式に変更
5. AI サービス層を LLMProvider Protocol + ProviderChain に変更
6. ファイル構成を更新（`gemini_client.py` → provider系4ファイル）
