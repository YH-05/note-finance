# PDF→ナレッジグラフ パイプライン設計

Created: 2026-03-11
Revised: 2026-03-12（Gemini CLI呼び出し修正・パイプライン耐障害性改善を反映）
Status: Phase 2-4（PDF→MD変換）を優先実装。Phase 5以降は後続。

---

## Context

ナレッジグラフ構築（`docs/plan/KnowledgeGraph/2026-03-11_first-memo.md`）の一環として、セルサイド・中央銀行・コンサル等の調査レポートPDFを構造化し、Neo4jグラフDBに投入するパイプラインを設計する。

Docling MCP + Gemini CLIでの変換を試みたが、以下の課題が発生:

1. 出力結果が安定しない
2. 免責事項などノイズを拾う
3. 複雑な表（財務諸表等）をパースできない

### 方針決定

- **処理エンジン**: Gemini CLI主体（LLMProvider Protocol経由）。Doclingはレイアウト解析に使用
- **Docling**: Gemini CLIで扱えることを確認済み。Docling非依存でも動作する設計にし、精度向上のオプションとして位置づける
- **実装スコープ**: まずPDF→Markdown変換（Phase 2-4）の品質安定化に集中
- **後続**: 知識抽出（Phase 5）→ Entity名寄せ（Phase 6）→ Neo4j投入（Phase 7）

---

## アーキテクチャ: 2トラック構成

```
                    PDF Input
                       │
                ┌──────┴──────┐
                ▼             ▼
          Track A:       Track B:
          本文テキスト    構造化データ(表)
                │             │
                ▼             ▼
          Docling         Docling
          レイアウト解析   表領域検出
          + ノイズ除去     + 画像切り出し
                │             │
                ▼             ▼
          LLMProvider     LLMProvider
          Vision-first    Structured Output
          → Markdown      → JSON (3層Pydantic)
                │             │
                └──────┬──────┘
                       ▼
                  チャンキング (Phase 4)
                  (セクション単位)
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     Phase 5A      Phase 5B     Phase 5C/5D
     テキスト      テーブルJSON   FiscalPeriod +
     → Entity      → Financial   Entity間リレーション
     → Fact/Claim  DataPoint
     (2パスLLM)    (ルールベース)
                       │
                       ▼
                  Entity名寄せ (Phase 6)
                  (master-entities.yaml参照)
                       │
                       ▼
                  graph_writer.py → Neo4j (Phase 7)
                  (MERGEベース冪等書き込み)
```

**設計判断**:
- Markdownは本文テキスト（Track A）にのみ使用。表・数値データ（Track B）はJSON形式で直接構造化抽出
- グラフDB保存が最終目的であり、Markdown化は中間ステップ
- Neo4j書き込みはPython `graph_writer.py` で直接実行（save-to-graphスキルのMERGEパターン/ID生成を継承）

---

## Phase詳細

### Phase 1: PDF取り込み・登録

- PDFディレクトリをスキャンし未処理ファイルを検出
- SHA-256ハッシュで冪等性を保証（同一PDFの再処理防止）
- 処理状態を `.tmp/pdf-pipeline/state.json` で管理

**入力**: `data/raw/report-scraper/pdfs/`, `data/raw/ai-research/pdfs/`
**出力**: バッチマニフェスト（`.tmp/pdf-pipeline/manifests/{batch_id}.json`）

### Phase 2A: 本文テキスト抽出（Docling + ノイズフィルター）

- Docling MCPでレイアウト解析を実行
- 以下の要素をプログラム的に除去:
    - `header` / `footer` / `page_number`
    - `footnote` / `disclaimer`
    - 正規表現パターン（"This report must be read with the disclosures" 等）
- フィルター設定は `data/config/pdf-pipeline-config.yaml` に外出し

**出力**: フィルター済みテキスト要素（`.tmp/pdf-pipeline/docling-output/{source_hash}/body.json`）

### Phase 2B: 表検出・画像切り出し

- Docling MCPで表・チャートのバウンディングボックスを検出
- `pymupdf` (fitz) で該当領域を画像(PNG)として切り出し

**出力**: `{source_hash}/tables/table_001.png` + メタデータJSON

### Phase 3A: Vision-first Markdown変換（LLMProvider経由）

- **デュアルインプット方式**: 元PDFファイル + Phase 2Aのフィルター済みテキストの両方をLLMに渡す
    - PDFから視覚的コンテキスト（レイアウト・強調・図表位置）を取得
    - Doclingテキストで文字精度をアンカリング
- セクション分割されたMarkdownを出力
- 見出し階層(H1/H2/H3)を保持

**出力**: `{source_hash}/body.md`

### Phase 3B: 表再構築（LLMProvider Structured Output）

切り出した表画像をLLMに渡し、**3層Pydanticスキーマ準拠のJSON**で出力する。

#### 3層テーブルスキーマ（`src/pdf_pipeline/schemas/tables.py`）

```
Tier 1: RawTable       — 全テーブル共通。データ損失なしの汎用コンテナ（常に生成）
Tier 2: 型付きテーブル  — テーブル種別ごとの構造化モデル（分類成功時）
Tier 3: ExtractedTables — 1PDF分の全テーブルを束ねるエンベロープ
```

**Tier 1: RawTable（常に生成 — フォールバック保証）**

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

**Tier 2: 型付きテーブル**

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

**Tier 3: エンベロープ**

```python
class ExtractedTables(BaseModel):
    source_hash: str
    raw_tables: list[RawTable]                      # 常に生成
    timeseries_tables: list[TimeSeriesTable] = []    # 分類成功時
    estimate_tables: list[EstimateChangeTable] = []
    kv_tables: list[KeyValueTable] = []
    unclassified: list[int] = []                     # raw_tables へのインデックス
```

**設計判断**:
- Tier 1は常に生成: LLMが分類に失敗してもデータは失われない
- `level` フィールド: 階層行（"Cost of Services" → "Radio frequency fee" at level=1）を表現
- `currency` + `scale` をテーブルレベルに: セルごとの冗長な単位情報を排除
- 多段ヘッダー: `headers: list[list[TableCell]]` でセルサイドレポート特有の結合ヘッダーに対応

**出力**: `{source_hash}/tables/table_001.json` + `table_001.md`

### Phase 4: チャンキング

- Markdownを見出し境界でセクション分割
- 表は親セクション内のサブチャンク or 独立チャンクとして付与
- `chunk_index` で順序管理

**出力**: `{source_hash}/chunks.json`

### Phase 5: 知識抽出

Phase 5は4つのサブフェーズに分割する。

#### Phase 5A: Fact + Claim + Entity抽出（テキストチャンク、2パスLLM）

テキストチャンクからの知識抽出は**2パス方式**で行う。

**Pass 1: Entity抽出**
```
入力: チャンクテキスト + 既知Entity一覧（名寄せ用）
出力: ExtractedEntity[] (name, entity_type, ticker, aliases)
指示: テキスト中の固有名詞を抽出。既知Entity一覧にマッチするものはそのIDを返す
```

**Pass 2: Fact/Claim抽出**
```
入力: チャンクテキスト + Pass 1のEntity一覧
出力: ExtractedFact[] + ExtractedClaim[] (各にabout_entity_ids付き)
指示:
  - Fact = 検証可能な事実（数値、日付、イベント）
  - Claim = 主観的主張（予想、意見、推奨）
  - 各Fact/Claimに関連するEntity IDを紐づける
```

**理由**: 1パスだと出力JSONが大きくなりLLMが構造を壊しやすい。Entity先行でABOUTリレーションの精度が向上する。

**Pydanticスキーマ（`src/pdf_pipeline/schemas/extraction.py`）**:

```python
class ExtractedFact(BaseModel):
    content: str
    fact_type: Literal["statistic", "event", "data_point", "quote"]
    as_of_date: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    about_entity_ids: list[str] = []

class ExtractedClaim(BaseModel):
    content: str
    claim_type: Literal["opinion", "prediction", "recommendation", "analysis"]
    sentiment: Literal["bullish", "bearish", "neutral"] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    target_price: float | None = None
    target_currency: str | None = None
    rating: Literal["buy", "overweight", "neutral", "underweight", "sell"] | None = None
    about_entity_ids: list[str] = []

class ExtractedEntity(BaseModel):
    name: str
    entity_type: Literal["company", "index", "sector", "indicator", "currency", "commodity", "person", "organization"]
    ticker: str | None = None
    aliases: list[str] = []
    matched_master_id: str | None = None  # 既知Entityにマッチした場合
```

#### Phase 5B: FinancialDataPoint抽出（テーブルJSON、ルールベース変換）

Phase 3Bで生成済みの構造化JSONからFinancialDataPointを**ルールベース**で変換する。LLM不要。

```
TimeSeriesTable.rows[].metric   → FinancialDataPoint.metric_name
TimeSeriesTable.rows[].values[] → FinancialDataPoint.value
TimeSeriesTable.periods[]       → FinancialDataPoint.period
TimeSeriesTable.currency        → FinancialDataPoint.unit
TimeSeriesTable.period_types[]  → FinancialDataPoint.is_estimate
```

**例外**: `ExtractedTables.unclassified`（RawTableのまま分類失敗した表）のみLLMフォールバックでFinancialDataPoint抽出を試行する。

**コスト削減効果**: テーブルデータ（全体の40-60%のデータポイント）がLLM不要。

```python
class FinancialDataPoint(BaseModel):
    datapoint_id: str
    metric_name: str
    value: float
    unit: str | None = None
    period: str                                      # "2025e", "3Q25"
    period_type: Literal["annual", "quarterly", "half_year", "ytd"] | None = None
    is_estimate: bool = False
    estimator: str | None = None                     # "HSBC", "consensus", "company_guidance"
    source_table_id: str | None = None               # 元テーブルへの参照
```

#### Phase 5C: FiscalPeriod生成 + PERTAINS_TOリンク

5A・5Bの出力から期間情報を正規化し、FiscalPeriodノードを生成してPERTAINS_TOリレーションを作成。

```python
class FiscalPeriod(BaseModel):
    period_id: str
    period_label: str                                # "FY2025", "3Q25"
    year: int
    quarter: int | None = None
    period_type: Literal["annual", "quarterly", "half_year"]
```

#### Phase 5D: Entity間リレーション抽出

テキスト全体から企業間関係（SUBSIDIARY_OF等）をLLMで抽出。

### Phase 6: Entity名寄せ

**Entity拡張方式**: Organization/Securityを別ノードにせず、既存Entityノードにプロパティを追加。

**Entityノード拡張フィールド**:
```yaml
Entity:
    properties:
        # 既存
        entity_id, name, entity_type, ticker, aliases
        # 追加（Master Entity用）
        isin: { type: string }
        official_name: { type: string }
        sector: { type: string }
        is_master: { type: boolean, default: false }
```

**名寄せプロセス（3段階照合）**:

1. **エイリアス完全一致**: `master-entities.yaml` の aliases と抽出Entity名を比較
2. **ticker一致**: 抽出Entity.ticker と master-entities のtickerを比較
3. **LLMベース判定**: 上記で一致しない場合、LLMに照合を依頼

**Master Entity参照テーブル（`data/config/master-entities.yaml`）**:
```yaml
NVDA:
    official_name: "NVIDIA Corporation"
    aliases: ["NVIDIA", "Nvidia", "エヌビディア"]
    isin: "US67066G1040"
    sector: "Semiconductors"
ISAT:
    official_name: "Indosat Ooredoo Hutchison"
    aliases: ["ISAT", "Indosat", "IOH"]
    isin: "ID1000097600"
    sector: "Telecommunications"
```

- 一致 → 既存Master EntityにMERGE
- 不一致 → 新規Entityとして作成（`is_master: false`）

### Phase 7: Neo4j投入（Python graph_writer.py）

save-to-graphスキルは使用せず、**Python実装のgraph_writer.py**で直接書き込む。

**設計判断**:
- save-to-graphはプロンプトベースで記事レベルの粒度向け。PDFパイプラインは1PDFあたり数百ノードのバルク投入が必要
- save-to-graphのMERGEパターン + ID生成ロジック（UUID5/SHA256）は継承
- 既存ワークフロー（ニュース収集等）でのsave-to-graph使用には影響なし

**書き込み方式**: `cypher-shell` CLI経由のMERGEベース冪等クエリ（save-to-graphと同じパターン）

**ID生成（`emit_graph_queue.py`から移植）**:
| ノード | 生成方式 | 形式 |
|--------|---------|------|
| Source | UUID5(NAMESPACE_URL, url) | UUID v5 |
| Entity | UUID5(NAMESPACE_URL, "entity:{name}:{type}") | UUID v5 |
| Chunk | UUID5(NAMESPACE_URL, "chunk:{source_hash}:{index}") | UUID v5 |
| Claim | SHA-256(content)[:16] | Hex |
| Fact | SHA-256(content)[:16] | Hex |
| FinancialDataPoint | UUID5(NAMESPACE_URL, "fdp:{source_hash}:{metric}:{period}") | UUID v5 |
| FiscalPeriod | UUID5(NAMESPACE_URL, "fp:{label}:{year}:{quarter}") | UUID v5 |

---

## スキーマ拡張

既存 `data/config/knowledge-graph-schema.yaml` への追加。

### 新規ノード

**Chunk**

```yaml
Chunk:
    description: "Text chunk from a source document for traceability"
    properties:
        chunk_id: { type: string, unique: true, required: true }
        text: { type: string, required: true }
        chunk_index: { type: integer, required: true }
        chunk_type: { type: string, enum: [text, table, figure], indexed: true }
        section_title: { type: string }
        page_ref: { type: string }
```

**FinancialDataPoint**

```yaml
FinancialDataPoint:
    description: "Structured quantitative data from financial reports"
    properties:
        datapoint_id: { type: string, unique: true, required: true }
        metric_name: { type: string, required: true, indexed: true }
        value: { type: float, required: true }
        unit: { type: string }
        period: { type: string, indexed: true }
        period_type: { type: string, enum: [annual, quarterly, half_year, ytd] }
        is_estimate: { type: boolean, default: false }
        estimator: { type: string }
```

**FiscalPeriod**

```yaml
FiscalPeriod:
    description: "Temporal anchor for financial data"
    properties:
        period_id: { type: string, unique: true, required: true }
        period_label: { type: string, required: true }
        year: { type: integer, indexed: true }
        quarter: { type: integer }
        period_type: { type: string, enum: [annual, quarterly, half_year] }
```

### 既存ノードの拡張

**Entity（Master Entity統合）**:
```yaml
Entity:
    properties:
        # 追加フィールド
        isin: { type: string }
        official_name: { type: string }
        sector: { type: string }
        is_master: { type: boolean, default: false }
```

**Claim（アナリスト推奨フィールド追加）**:
```yaml
Claim:
    properties:
        # 追加フィールド
        target_price: { type: float }
        target_currency: { type: string }
        rating: { type: string, enum: [buy, overweight, neutral, underweight, sell] }
```

### 新規リレーション

```yaml
HAS_CHUNK:
    from: Source
    to: Chunk
    description: "Source contains this chunk"

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
        ownership_pct: { type: float }
```

### Neo4j制約追加

```cypher
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS
  FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;

CREATE CONSTRAINT unique_datapoint_id IF NOT EXISTS
  FOR (dp:FinancialDataPoint) REQUIRE dp.datapoint_id IS UNIQUE;

CREATE CONSTRAINT unique_period_id IF NOT EXISTS
  FOR (fp:FiscalPeriod) REQUIRE fp.period_id IS UNIQUE;

CREATE INDEX idx_datapoint_metric IF NOT EXISTS
  FOR (dp:FinancialDataPoint) ON (dp.metric_name);

CREATE INDEX idx_datapoint_period IF NOT EXISTS
  FOR (dp:FinancialDataPoint) ON (dp.period);

CREATE INDEX idx_period_year IF NOT EXISTS
  FOR (fp:FiscalPeriod) ON (fp.year);
```

---

## mcp-neo4j-data-modeling 活用

`.mcp.json` に設定済みだが `allowedTools` 未登録のため実質未使用だった。以下を追加して活用する。

### allowedTools への追加

`.claude/settings.local.json` に以下を追加:

```
"mcp__neo4j-data-modeling__validate_data_model",
"mcp__neo4j-data-modeling__validate_node",
"mcp__neo4j-data-modeling__validate_relationship",
"mcp__neo4j-data-modeling__export_to_pydantic_models",
"mcp__neo4j-data-modeling__get_constraints_cypher_queries"
```

### パイプラインでの用途

| MCPツール | 用途 | 使用Phase |
|-----------|------|-----------|
| `validate_data_model` | スキーマYAML変更時のバリデーション | スキーマ進化時 |
| `validate_node` | 抽出Fact/Claim/Entityの構造検証 | Phase 5 |
| `validate_relationship` | リレーション構造の検証 | Phase 5 |
| `export_to_pydantic_models` | YAMLスキーマ → Pydanticモデル自動生成 | Phase 5セットアップ |
| `get_constraints_cypher_queries` | Neo4j制約DDL自動生成 | 初期セットアップ |

### スキーマの Single Source of Truth

```
knowledge-graph-schema.yaml (SSOT)
  → export_to_pydantic_models → src/pdf_pipeline/schemas/extraction.py
  → get_constraints_cypher_queries → data/config/neo4j-constraints.cypher
  → validate_data_model で整合性チェック
```

---

## LLMプロバイダー

### LLMProvider Protocol + ProviderChain

Gemini CLI主体、Claude Codeフォールバックの構成。

```python
# src/pdf_pipeline/services/llm_provider.py
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

### GeminiCLIProvider

> **⚠️ 2026-03-12 修正**: 初期設計の `--file` フラグ・`convert-pdf` サブコマンドは Gemini CLI に存在しない。
> 実装は `-p`（非対話プロンプト）+ `-y`（YOLO モード）+ プロンプト内ファイルパス埋め込み方式に変更済み。

```python
# src/pdf_pipeline/services/gemini_provider.py
class GeminiCLIProvider:
    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def _run_gemini(self, *, prompt: str, files: list[Path] | None = None, operation: str) -> str:
        # ファイルパスはプロンプト内に埋め込む（--file フラグは存在しない）
        full_prompt = prompt
        if files:
            file_list = "\n".join(f"- {f}" for f in files)
            full_prompt = f"Files to process:\n{file_list}\n\n{prompt}"

        # -p: 非対話プロンプトモード、-y: ツール呼び出し自動承認（YOLO）
        cmd: list[str] = ["gemini", "-p", full_prompt, "-y"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        if result.returncode != 0:
            raise LLMProviderError(f"Gemini CLI failed: {result.stderr}")
        return result.stdout
```

**Gemini CLI 正しい呼び出しパターン**:

| 用途 | コマンド |
|------|---------|
| PDF→Markdown変換 | `gemini -p "Files to process:\n- /path/to/file.pdf\n\n<変換プロンプト>" -y` |
| テキスト→JSON抽出 | `gemini -p "<抽出プロンプト>\n<テキスト>" -y` |
| 利用可能性チェック | `shutil.which("gemini")` |

**出力サニタイズ**: Gemini CLIの出力には以下のノイズが混入するため、正規表現で除去する:
- MCP警告（`MCP issues detected...`）
- 思考ログ（`I will...`, `I'll...`, `Let me...`, `First, I will...`）
- コードフェンス（`` ```markdown ``, `` ``` ``）
- プリアンブル（`Here is the converted/extracted/structured...`）

**出力バリデーション**: `convert_pdf_to_markdown` はATX見出し（`# `, `## ` 等）が1つ以上含まれることを検証。見出しなしの場合は `LLMProviderError` を送出。

### ClaudeCodeProvider

```python
# src/pdf_pipeline/services/claude_provider.py
# AIDEV-NOTE: AgentProcessor._get_sdk() パターン踏襲（lazy import）
class ClaudeCodeProvider:
    def is_available(self) -> bool:
        try:
            import claude_agent_sdk  # noqa: F401
            return True
        except ImportError:
            return False
```

### ProviderChain

```python
# src/pdf_pipeline/services/provider_chain.py
class ProviderChain:
    def execute_with_fallback(self, method_name: str, *args, **kwargs) -> Any:
        """各プロバイダーを順に試行。全失敗時にLLMProviderError"""
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

### 設定（`data/config/pdf-pipeline-config.yaml`）

```yaml
llm:
    provider_order: ["gemini_cli", "claude_code"]
    fallback_enabled: true
    gemini:
        timeout: 120
        model: null
    claude:
        timeout: 120
```

---

## ファイル構成

```
src/pdf_pipeline/
├── __init__.py
├── types.py                        # ProcessingState, PdfMetadata 等
├── schemas/
│   ├── tables.py                   # 3層テーブルスキーマ
│   └── extraction.py               # Fact/Claim/Entity/FinancialDataPoint スキーマ
├── config/
│   └── loader.py                   # YAML設定ローダー
├── core/
│   ├── pipeline.py                 # パイプラインオーケストレーター
│   ├── pdf_scanner.py              # PDF検出・ハッシュ計算
│   ├── noise_filter.py             # ノイズフィルター（正規表現ベース、Doclingオプション）
│   ├── table_detector.py           # 表検出・画像切り出し
│   ├── markdown_converter.py       # Phase 3A: Vision-first変換
│   ├── table_reconstructor.py      # Phase 3B: 表→JSON再構築
│   ├── chunker.py                  # Phase 4: セクション単位チャンキング
│   ├── knowledge_extractor.py      # Phase 5A: 2パスLLM抽出
│   ├── datapoint_converter.py      # Phase 5B: ルールベースDataPoint変換
│   └── entity_resolver.py          # Phase 6: Entity名寄せ
├── services/
│   ├── llm_provider.py             # LLMProvider Protocol + LLMProviderError
│   ├── gemini_provider.py          # GeminiCLIProvider
│   ├── claude_provider.py          # ClaudeCodeProvider（lazy import）
│   ├── provider_chain.py           # フォールバック制御
│   ├── graph_writer.py             # Neo4j MERGEベース書き込み（save-to-graphパターン継承）
│   ├── id_generator.py             # UUID5/SHA256 ID生成（emit_graph_queue.pyから移植）
│   ├── schema_validator.py         # スキーマバリデーション（mcp-neo4j-data-modeling連携）
│   └── state_manager.py            # 処理状態管理（冪等性）
└── cli/
    └── main.py                     # Click CLI（process / status / reprocess）

data/config/
├── pdf-pipeline-config.yaml        # パイプライン設定（llmセクション含む）
├── knowledge-graph-schema.yaml     # グラフスキーマ定義（拡張済み）
└── master-entities.yaml            # Master Entity参照テーブル（手動キュレーション）

data/sample_report/
├── ground_truth.json               # 構造化グラウンドトゥルース（人手作成）
├── *.pdf                           # 8ブローカーのサンプルPDF
└── docling_output/                 # Docling出力（参考）

tests/pdf_pipeline/
├── unit/
│   ├── test_tables_schema.py       # テーブルスキーマのバリデーション
│   ├── test_provider_chain.py      # フォールバック動作
│   ├── test_noise_filter.py        # ノイズ除去
│   ├── test_datapoint_converter.py # ルールベース変換
│   └── test_id_generator.py        # ID生成の決定性
└── integration/
    └── test_conversion_accuracy.py # 3軸検証
```

---

## 依存ライブラリ

| ライブラリ  | 用途                         | 状態         |
| ----------- | ---------------------------- | ------------ |
| `pydantic`  | スキーマ定義・バリデーション | 既存         |
| `structlog` | 構造化ログ                   | 既存         |
| `pyyaml`    | 設定読み込み                 | 既存         |
| `click`     | CLI                          | 既存         |
| `pymupdf`   | PDF画像切り出し              | **新規追加** |

**外部ツール**: `gemini` CLI, `docling-mcp-server`（共に設定済み）

---

## 実装ロードマップ

### Step 1: 基盤 + PDF取り込み（Phase 1）

1. `src/pdf_pipeline/` パッケージ作成（pyproject.toml登録含む）
2. `types.py` Pydanticモデル定義
3. `config/loader.py` + `data/config/pdf-pipeline-config.yaml`
4. `core/pdf_scanner.py` PDF検出・ハッシュ計算
5. `services/state_manager.py` 処理状態管理（冪等性）
6. 単体テスト

### Step 2: LLMプロバイダー + ノイズ除去 + Markdown変換（Phase 2A, 3A）

1. `services/llm_provider.py` + `gemini_provider.py` + `claude_provider.py` + `provider_chain.py`
2. `core/noise_filter.py` 正規表現ベースのノイズフィルター
3. `core/markdown_converter.py` Vision-first変換
4. LLMプロンプトテンプレート設計
5. サンプルPDF（HSBC ISAT 3Q25）での変換精度検証

### Step 3: 表専用パース（Phase 2B, 3B）

1. `schemas/tables.py` 3層Pydanticテーブルスキーマ
2. `core/table_detector.py` 表検出（pymupdf or LLMに委任）
3. `core/table_reconstructor.py` 表画像→JSON再構築
4. 財務諸表サンプルでの検証（HSBC ISAT P&L, Balance Sheet）

### Step 4: チャンキング + 統合パイプライン（Phase 4）

1. `core/chunker.py` セクション単位チャンキング
2. `core/pipeline.py` Phase 1-4のオーケストレーター
3. `cli/main.py` Click CLI
4. E2Eテスト（サンプルPDF → Markdown + JSON出力）

### Step 5: 知識抽出（Phase 5A-5D）

1. `schemas/extraction.py` 抽出スキーマ定義
2. `core/knowledge_extractor.py` 2パスLLM抽出（5A）
3. `core/datapoint_converter.py` ルールベースDataPoint変換（5B）
4. FiscalPeriod生成ロジック（5C）
5. Entity間リレーション抽出（5D）

### Step 6: Entity名寄せ + Neo4j投入（Phase 6-7）

1. `data/config/master-entities.yaml` 初期データ作成
2. `core/entity_resolver.py` 3段階照合ロジック
3. `services/id_generator.py` ID生成（emit_graph_queue.pyから移植）
4. `services/graph_writer.py` Neo4j MERGEベース書き込み
5. E2Eテスト（PDF → Neo4jノード生成）

---

## 検証方法

### 構造化グラウンドトゥルース方式

AI出力をAI出力の正解データにするのは循環的なため、**人手で検証可能な離散データポイント**をグラウンドトゥルースとして使う。

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

`data/sample_report/ground_truth.json` — 人手で作成。初期は以下3ブローカーで重点検証:

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

```python
# tests/pdf_pipeline/integration/test_conversion_accuracy.py
class TestConversionAccuracy:
    def test_正常系_数値抽出精度が95パーセント以上(self, ground_truth, extracted):
        """ground_truth.key_metrics の値が extracted table JSON に存在する"""

    def test_正常系_セクション見出しが全て保持される(self, ground_truth, markdown):
        """ground_truth.sections の heading が markdown 中に出現する"""

    def test_正常系_ノイズフレーズが除去されている(self, ground_truth, markdown):
        """ground_truth.noise_phrases が markdown 中に含まれない"""
```

### 冪等性の検証

- 同一PDFを2回処理し、出力Markdownが同一であることを確認

### CLI動作検証

```bash
# 単一PDF変換
uv run python -m pdf_pipeline.cli process data/sample_report/HSBC*.pdf

# 処理状態確認
uv run python -m pdf_pipeline.cli status

# 再処理
uv run python -m pdf_pipeline.cli reprocess --hash <sha256>
```

---

## リスクと軽減策

| リスク | 軽減策 |
|--------|--------|
| LLM出力の不安定性 | デュアルインプット（PDF+Doclingテキスト）でアンカリング + Pydanticバリデーション + ProviderChainフォールバック |
| 表パース精度 | 3層スキーマ（RawTableフォールバック保証）+ HTML中間形式 + Pydantic検証 |
| 免責事項の混入 | 3層フィルター（Doclingレイアウト + 正規表現 + 位置ヒューリスティック） |
| 大規模PDFの処理時間 | ページ単位処理 + バッチサイズ制限 + タイムアウト設定 + 1日あたりのGemini CLI限界で制御 |
| Entity名寄せの誤検出 | 3段階照合（エイリアス→ticker→LLM）+ master-entities.yaml手動キュレーション |
| 知識抽出のJSON構造破壊 | 2パス方式で出力サイズを制限 + テーブルデータはルールベース変換でLLM回避 |

---

## 議論経緯

本プランは以下の議論を経て策定:

| ファイル | 内容 | Status |
|---------|------|--------|
| `2026-03-11_pdf-pipeline-5-discussion-points.md` | 5論点（テーブルスキーマ、ノード拡張、MCP活用、検証方法、LLMプロバイダー） | 合意済み |
| `2026-03-11_pipeline-discussion-resolution.md` | 追加3論点（Master Entity、抽出戦略、Graph Writer）+ 全8論点合意サマリー | 合意済み |

---

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `docs/plan/KnowledgeGraph/2026-03-11_first-memo.md` | ナレッジグラフ構築メモ（上位計画） |
| `data/config/knowledge-graph-schema.yaml` | グラフスキーマ定義（拡張対象） |
| `data/config/master-entities.yaml` | Master Entity参照テーブル（新規作成） |
| `scripts/emit_graph_queue.py` | ID生成パターン（移植元） |
| `.claude/skills/save-to-graph/guide.md` | MERGEパターン参考 |
| `src/report_scraper/storage/pdf_store.py` | PDF保存パターン（参考） |
| `src/report_scraper/types.py` | Pydantic+dataclassパターン（参考） |
| `data/sample_report/` | 検証用サンプルPDF |

---

## 実装修正ログ

### 2026-03-12: Gemini CLI呼び出し修正 + パイプライン耐障害性改善

#### 問題

初期実装でJefferies ISATレポートPDFを変換した結果、`chunks.json` にレポート本文が含まれず、Geminiの内部思考ログ（`I will read the file...`）がそのまま出力された。

#### 根本原因

設計ドキュメントに記載していた Gemini CLI の呼び出し方法が実際のCLI仕様と乖離していた:

| 設計時の想定 | 実際のCLI仕様 |
|-------------|-------------|
| `gemini convert-pdf <path>` | `convert-pdf` サブコマンドは存在しない |
| `gemini --file <path> --prompt <text>` | `--file` フラグは存在しない（`Unknown argument: file`） |
| `gemini --prompt <text>` | `-p` が正しいフラグ名 |
| （なし） | `-y` (YOLO) でツール呼び出し自動承認が必要 |

#### 修正内容

**1. `gemini_provider.py` — CLI呼び出し方式の修正**

- `gemini -p <prompt> -y` 方式に変更
- ファイルパスはプロンプト内に `Files to process:` として埋め込み
- PDF→Markdown変換用の専用プロンプト（`_PDF_TO_MARKDOWN_PROMPT`）を追加
  - ATX見出し保持、テーブルMarkdown化、数値正確性保持、ノイズ除去を指示
- テーブルJSON抽出用プロンプト（`_TABLE_EXTRACT_PROMPT`）を追加
- 知識抽出用プロンプト（`_KNOWLEDGE_EXTRACT_PROMPT`）を追加
- `_sanitize_output()` 関数: 7パターンの正規表現でGemini CLIノイズを除去
- `convert_pdf_to_markdown()` にATX見出しバリデーションを追加

**2. `pipeline.py` — テーブル再構築のグレースフルデグラデーション**

```python
# 修正前: テーブル再構築の例外がパイプライン全体をクラッシュさせる
reconstructed_tables = self.table_reconstructor.reconstruct(...)

# 修正後: 例外時はraw_tablesにフォールバック
try:
    extracted = self.table_reconstructor.reconstruct(
        pdf_path=str(pdf_path), raw_tables=raw_tables,
    )
    reconstructed_tables = extracted.raw_tables
except Exception as table_exc:
    logger.warning("Table reconstruction failed, continuing with raw tables", ...)
    reconstructed_tables = raw_tables
```

**3. テスト追加（`test_llm_providers.py`）**

- コマンド引数アサーションを `-p` / `-y` に更新
- `TestSanitizeOutput` クラス追加（6テスト: MCP noise, 思考ログ, コードフェンス, 空行圧縮, クリーンパススルー, プリアンブル）
- 見出しなし出力でのLLMProviderErrorテスト追加
- `.pdf` 拡張子バリデーションテスト追加
- 全44テスト PASS

#### 検証結果

JefferiesレポートPDF（`Jefferies ISAT@IJ ISAT IJ 4Q25 Results Strong Earnings Beat.pdf`, 1.4MB）で検証:

| 項目 | 結果 |
|------|------|
| チャンク数 | 10 |
| 本文テキスト | 正常抽出（4Q25 Revenue, EBITDA, PATAMI分析等） |
| テーブル（Markdown形式） | Stock Data, Key Financials, FIGURE 1（4Q25 Results）, Operating Stats |
| 数値精度 | Revenue Rp15,357bn (+9.1% YoY), EBITDA Rp7,249bn (+13.7% YoY) 等、PDF原本と一致 |
| ノイズ除去 | Gemini思考ログ・MCP警告の混入なし |
| 免責事項 | 除去済み |

#### 残存課題

| 課題 | 優先度 | 詳細 |
|------|--------|------|
| PyMuPDFテーブル検出の互換性 | 中 | `'tuple' object has no attribute 'row'` 警告。`tables`フィールドのセル値が空になる |
| テーブル再構築タイムアウト | 低 | Gemini CLIでのテーブルJSON抽出が300sでタイムアウト。Phase 3のMarkdown変換で既にテーブルが抽出されるため実害なし |
| 出力のデュアルインプット未実装 | 中 | 設計ではPDF+Doclingテキストの両方をLLMに渡す方針だが、現時点ではPDFのみ。`filtered_text` パラメータは `MarkdownConverter` に渡されるが、Geminiプロンプトには未反映 |
