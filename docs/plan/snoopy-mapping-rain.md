# PDF→Markdown パイプライン 5論点ドキュメント改訂プラン

Created: 2026-03-11
Status: 計画中
Parent: `docs/plan/KnowledgeGraph/2026-03-11_pdf-pipeline-5-discussion-points.md`

---

## Context

`2026-03-11_pdf-pipeline-5-discussion-points.md` に対して2つの改訂要求がある：

1. **論点1（テーブルスキーマ）**: HSBC ISATだけでなく全8ブローカーPDFを考慮し、個別テーブル型の列挙ではなく**汎用的なスキーマ + フォールバック**で対応する
2. **論点5（LLMプロバイダー）**: Claude Code/Agent SDK実装は見送り、**Gemini CLIのみ**に簡素化。LLMProvider Protocol / ProviderChain は不要

論点2, 3, 4は本改訂の対象外（変更なし）。

---

## 改訂1: 論点1 — 汎用テーブルスキーマ

### 問題

現行設計のTier 2は3つの型付きモデル（`TimeSeriesTable`, `EstimateChangeTable`, `KeyValueTable`）を定義。
全8ブローカーPDFをpymupdf (fitz) で横断分析した結果、**構造的には全グリッドテーブルが同一パターン**（行=指標 × 列=期間/シナリオ）であることが判明。個別テーブル型を増やすのではなく、汎用モデル + フォールバックで対応すべき。

### 全8ブローカーPDFテーブル横断分析

pymupdf (fitz) で全PDFのテキストを抽出し、テーブル構造を確認した。

#### ブローカー別テーブルパターン

| ブローカー | ページ数 | 主要テーブル | 特徴的なパターン |
|-----------|---------|-------------|----------------|
| **HSBC** | 9 | P&L/CF/BS/Ratio/Valuation (年次4期間), 四半期結果/KPI/Opex (5四半期+QoQ/YoY), Estimate Change (New/Prev/Change), Market Data (KV), ESG (並置KV) | 最も多様。18テーブル |
| **BofA** | 8 | Key Income Statement (年次5期間: 2023A-2027E), Key Cash Flow (同), Quarterly Variance (5四半期+YoY/QoQ/**A vs E**列), Wireless KPI (同) | **A vs E（実績 vs 予想）列**が特徴 |
| **JP Morgan** | 13 | Key Changes (**Prev/Cur/Δ** コンパクト3列), Company Data (KV), Key Metrics (年次4期間: FY25A-FY28E), Margins&Growth/Ratios/Valuation (同), 4Q25 Earnings Summary (四半期+YoY/QoQ/**JPMe列**/**Consensus列**) | 予想との乖離列が多い |
| **Jefferies** | 5 | 4Q25 Results **超ワイドテーブル**: 四半期(4Q24/3Q25/4Q25/4Q25F) + YoY/QoQ/Vs Mansek + 年次(FY24/FY25) + YoY + **% of FY25F(Mansek/Cons)** | **1テーブルに四半期+年次+達成率を全集約** |
| **Nomura** | 7 | Quarterly Operating Data (5四半期+Q-Q%/Y-Y%), Revenue/EBITDA Breakdowns by Segment (同+**YTD FY25/FY24/Y-Y列**), Rating History | **YTD列+セグメント別内訳**が特徴 |
| **Maybank IBG** | 15 | 主にチャート(Fig 1-12)。テーブルはチャート内データとして存在 | **テーブルよりチャート主体** |
| **Citi** | 14 | Earnings Revision Summary, Interim Performance Summary（テーブルは画像として埋め込み） | **テーブルが画像化されていてテキスト抽出困難** |
| **UBS** | 14 | Highlights (年次**8期間**: 12/22-12/29E), Results Summary (画像), Forecast Returns (KV) | **最長時系列（8年分）** |

#### 構造パターンの集約

全ブローカーを通じて、テーブルは以下の**3つの構造パターン**に分類される:

**パターン1: グリッドテーブル（全ブローカー共通、全テーブルの~80%）**
- 行 = 財務指標（Revenue, EBITDA, etc.）
- 列 = 期間ラベルまたはシナリオ
- バリエーション:
  - 年次期間: `["12/2024a", "12/2025e", ...]`（HSBC, BofA, UBS等）
  - 四半期期間: `["3Q24", "4Q24", "1Q25", ...]`（HSBC, BofA, JPM等）
  - 比較列: `["YoY", "QoQ", "A vs E"]`（BofA, JPM）, `["Vs Mansek's", "% of FY25F"]`（Jefferies）
  - 複合: 四半期 + 年次 + 達成率を1テーブルに（Jefferies）
  - YTD列: `["YTD FY25", "YTD FY24", "Y-Y"]`（Nomura）
  - 予想改訂: `["Prev", "Cur", "Δ"]`（JPM Key Changes）

**パターン2: Key-Valueテーブル（一部ブローカー）**
- HSBC: Market Data, Issuer Information
- JP Morgan: Company Data
- UBS: Forecast Returns

**パターン3: RawTableフォールバック対象**
- ESG並置テーブル（HSBC）
- Rating/TP History（HSBC, Nomura）
- Disclosure checklist（HSBC）
- 画像埋め込みテーブル（Citi, Maybank）

**核心的知見**:
1. 全グリッド型財務テーブルの構造は**同一**（行=指標 × 列=ラベル）
2. ブローカー間の差異は**列ラベルの種類**（期間/比較/達成率）であり、**構造の差異ではない**
3. `periods: list[str]` で `["4Q24", "3Q25", "4Q25", "YoY", "QoQ", "A vs E"]` のように全列を格納すれば対応可能
4. Jefferiesの超ワイドテーブルも `periods` リストが長くなるだけで同一モデルで表現可能
5. `EstimateChangeTable` は不要 — JPMの "Prev/Cur/Δ" も `FinancialTable` で表現可能

### 改訂案: 2モデルTier 2 + RawTableフォールバック

旧: `TimeSeriesTable` + `EstimateChangeTable` + `KeyValueTable`（3モデル）
新: `FinancialTable` + `KeyValueTable`（2モデル）

#### `src/pdf_pipeline/schemas/tables.py`

```python
"""3-tier table schema: RawTable(Tier1) → FinancialTable/KeyValueTable(Tier2) → ExtractedTables(Tier3)"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

type TableCategory = Literal[
    "income_statement", "balance_sheet", "cash_flow",   # 基本財務
    "valuation", "ratios", "kpi",                        # 分析
    "quarterly_results", "segment",                      # 内訳
    "estimate_revision",                                  # 予想改訂
    "generic",                                            # キャッチオール
]

# --- Tier 1: RawTable（常に生成、フォールバック保証） ---

class TableCell(BaseModel):
    value: str
    numeric_value: float | None = None
    unit: str | None = None
    is_bold: bool = False
    is_header: bool = False
    colspan: int = 1
    rowspan: int = 1

class RawTable(BaseModel):
    table_id: str  # "{source_hash}_table_{seq:03d}"
    headers: list[list[TableCell]] = Field(default_factory=list)  # 多段ヘッダー
    rows: list[list[TableCell]]
    source_page: int | None = None
    caption: str | None = None
    footnotes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)

# --- Tier 2: FinancialTable（汎用グリッドテーブル） ---

class FinancialMetric(BaseModel):
    metric: str                              # "Revenue", "EBITDA margin (%)"
    section: str | None = None               # "HSBC new estimates", "Profit & loss summary"
    level: int = 0                           # インデント深度
    is_subtotal: bool = False
    values: dict[str, float | str | None]    # period_label → value

class FinancialTable(BaseModel):
    table_category: TableCategory = "generic"
    title: str
    currency: str | None = None
    scale: str | None = None                 # "b", "m", "000s"
    periods: list[str]                       # ["12/2024a", "12/2025e", ...]
    rows: list[FinancialMetric]
    source_page: int | None = None
    footnotes: list[str] = Field(default_factory=list)
    raw_table_index: int | None = None       # Tier1へのトレーサビリティ

# --- Tier 2: KeyValueTable（構造的に別物） ---

class KeyValueTable(BaseModel):
    title: str
    pairs: dict[str, str | float | None]
    source_page: int | None = None
    raw_table_index: int | None = None

# --- Tier 3: ExtractedTables（1PDFのエンベロープ） ---

class ExtractedTables(BaseModel):
    source_hash: str
    raw_tables: list[RawTable]                        # 常に生成
    financial_tables: list[FinancialTable] = Field(default_factory=list)
    kv_tables: list[KeyValueTable] = Field(default_factory=list)
    unclassified: list[int] = Field(default_factory=list)  # raw_tablesへのインデックス
```

### 設計判断（全8ブローカー分析に基づく）

| 判断 | 根拠（ブローカー横断分析より） |
|------|------|
| `FinancialTable` 1モデルで全グリッドテーブルをカバー | 8社全てのグリッドテーブルが同一構造（行=指標×列=ラベル）。差異は列ラベルの種類のみ |
| `periods: list[str]` で全列ラベルを格納 | BofAの `"A vs E"`, JPMの `"JPMe"/"Consensus"`, Jefferiesの `"% of FY25F"`, Nomuraの `"YTD FY25"` — 全て文字列ラベルとして統一表現可能 |
| `FinancialMetric.section` フィールド追加 | HSBCのEstimate Change（New/Previous/Change区分）やJPMの四半期結果（セグメント別セクション）を表現。専用モデル不要 |
| `KeyValueTable` は残す | HSBC(Market Data/Issuer Info), JPM(Company Data), UBS(Forecast Returns)で共通。構造がグリッドと根本的に異なる |
| `raw_table_index` トレーサビリティ | Tier2からTier1への逆引き。Geminiの分類精度が低い場合にRawTableにフォールバック |
| `TableCategory` に `"generic"` キャッチオール | 新規ブローカーの未知テーブル型にも対応。分類失敗は正常動作 |
| ESG/Rating History/画像テーブルは `RawTable` のまま | HSBC ESG並置KV, Citi/Maybank画像埋め込みテーブル等。無理にTier2に押し込まない |

### ブローカー別のスキーマ適合例

| ブローカー | テーブル例 | `FinancialTable` での表現 |
|-----------|-----------|--------------------------|
| **Jefferies** | 超ワイドテーブル（四半期+年次+達成率） | `periods=["4Q24","3Q25","4Q25","4Q25F","YoY","QoQ","Vs Mansek","FY24","FY25","YoY","% FY25F Mansek","% FY25F Cons"]` |
| **BofA** | Quarterly Variance（A vs E列付き） | `periods=["3Q24","2Q25","3Q25E","3Q25A","YoY","QoQ","A vs E"]` |
| **JP Morgan** | Key Changes（コンパクト3列） | `periods=["Prev","Cur","Δ"]`, `table_category="estimate_revision"` |
| **Nomura** | Segment Breakdowns（YTD列付き） | `periods=["4Q24","1Q25","2Q25","3Q25","4Q25","Q-Q%","Y-Y%","YTD FY25","YTD FY24","Y-Y"]` |
| **UBS** | Highlights（8年時系列） | `periods=["12/22","12/23","12/24","12/25E","12/26E","12/27E","12/28E","12/29E"]` |
| **HSBC** | Estimate Change | `section="HSBC new estimates"` / `section="HSBC previous estimates"` / `section="Change in estimates"`, `table_category="estimate_revision"` |

---

## 改訂2: 論点5 — Gemini CLIのみに簡素化

### 問題

現行設計は `LLMProvider Protocol` + `ProviderChain` + `ClaudeCodeProvider` を定義（4ファイル）。
実装規模が大きすぎ、Claude Code/Agent SDKは見送り。

### 改訂案

4ファイル → 1ファイルに簡素化:

```
# 旧（4ファイル）
src/pdf_pipeline/services/
├── llm_provider.py       # 削除
├── gemini_provider.py    # → gemini_client.py に統合
├── claude_provider.py    # 削除
├── provider_chain.py     # 削除
└── state_manager.py

# 新（2ファイル）
src/pdf_pipeline/services/
├── gemini_client.py      # GeminiClient（subprocessラッパー）
└── state_manager.py
```

#### `src/pdf_pipeline/services/gemini_client.py`

```python
"""Gemini CLI subprocess wrapper.

Pattern: src/news/sinks/github.py:389-394
"""

class GeminiCLIError(Exception):
    def __init__(self, message: str, stderr: str = "", returncode: int = -1) -> None:
        super().__init__(message)
        self.stderr = stderr
        self.returncode = returncode

class GeminiClient:
    def __init__(self, timeout: int = 120, model: str | None = None) -> None:
        self._timeout = timeout
        self._model = model

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def convert_pdf_to_markdown(self, pdf_path: Path, ...) -> str:
        return self._run(prompt=..., files=[pdf_path])

    def extract_table_json(self, table_image_path: Path, schema_json: str) -> dict:
        raw = self._run(prompt=..., files=[table_image_path])
        return json.loads(raw)

    def _run(self, prompt: str, files: list[Path] | None = None) -> str:
        cmd = ["gemini"]
        if self._model:
            cmd.extend(["--model", self._model])
        for f in (files or []):
            cmd.extend(["--file", str(f)])
        cmd.extend(["--prompt", prompt])
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=self._timeout)
        if result.returncode != 0:
            raise GeminiCLIError(...)
        return result.stdout
```

#### Config簡素化

```yaml
# data/config/pdf-pipeline-config.yaml
gemini:
    timeout: 120
    model: null    # CLIデフォルト使用
```

旧: `llm.provider_order`, `llm.fallback_enabled`, `llm.claude.*` → 全て不要

---

## 下流への影響

### Phase 3B: `table_reconstructor.py`

**変更**: 3つの型付きモデルへのルーティングが不要に。フローが単純化:

1. 常に `RawTable` を生成
2. `FinancialTable` 分類を試行（Geminiに `table_category` 判定を依頼）
3. KV構造のヒューリスティック検出 → `KeyValueTable`
4. 分類失敗 → `unclassified`（`RawTable` で保存）

### Phase 5B: 知識抽出入力

**変更**: `timeseries_tables` + `estimate_tables` を別々に読む → `financial_tables` を一律に読む。
`table_category` で抽出プロンプトを調整するが、データアクセスパターンは統一。

### Pipeline orchestrator

**変更**: `ProviderChain` 不要。`GeminiClient` を直接使用:
```python
class PdfPipeline:
    def __init__(self, config):
        self._gemini = GeminiClient(timeout=config.gemini.timeout, model=config.gemini.model)
```

---

## 改訂後のファイル構成（Phase 2-4スコープ）

```
src/pdf_pipeline/
├── __init__.py
├── _logging.py                    # structlog logger
├── types.py                       # ProcessingState, PdfMetadata, PipelineConfig
├── schemas/
│   └── tables.py                  # 3層テーブルスキーマ（本プランのメイン成果物）
├── config/
│   └── loader.py                  # YAML設定ローダー
├── core/
│   ├── pipeline.py                # パイプラインオーケストレーター
│   ├── pdf_scanner.py             # PDF検出・ハッシュ計算
│   ├── noise_filter.py            # 正規表現ノイズフィルター
│   ├── table_detector.py          # 表検出・画像切り出し（pymupdf）
│   ├── markdown_converter.py      # Phase 3A: Vision-first MD変換
│   ├── table_reconstructor.py     # Phase 3B: 表→JSON再構築
│   └── chunker.py                 # Phase 4: セクション単位チャンキング
├── services/
│   ├── gemini_client.py           # GeminiClient（subprocessラッパー）
│   └── state_manager.py           # 処理状態管理（冪等性）
└── cli/
    └── main.py                    # Click CLI

data/config/
├── pdf-pipeline-config.yaml       # gemini: {timeout, model}
└── knowledge-graph-schema.yaml    # 変更なし（Phase 5で拡張）

tests/pdf_pipeline/
├── unit/
│   ├── test_tables_schema.py      # Pydanticモデル検証
│   ├── test_gemini_client.py      # subprocess mock テスト
│   └── test_noise_filter.py
└── integration/
    └── test_conversion_accuracy.py # 3軸検証（論点4、変更なし）
```

---

## 実施手順

1. `docs/plan/KnowledgeGraph/2026-03-11_pdf-pipeline-5-discussion-points.md` の論点1セクションを改訂
   - 3モデルTier2 → 2モデルTier2 + RawTableフォールバック
   - Pydanticモデル定義を差し替え
2. 同ドキュメントの論点5セクションを改訂
   - LLMProvider/ProviderChain/ClaudeCodeProvider → GeminiClientのみ
   - 設定・ファイル構成を簡素化
3. 改訂後のファイル構成セクションを更新
4. 元プラン `2026-03-11_pdf-to-markdown-pipeline.md` のPhase 3Bスキーマ定義を3層設計（改訂版）に差し替え
5. 元プランの `gemini_client.py` 記述はそのまま（既にGemini CLIのみ。services/配下の他ファイルは5論点ドキュメントのみで言及）

## 検証方法

- 改訂後のPydanticモデルが全8ブローカーのテーブルパターンを表現できることを確認
  - HSBC: 18テーブル（最多・最多様）
  - Jefferies: 超ワイドテーブル（`periods` リスト12列）
  - UBS: 8年時系列（`periods` リスト8列）
  - BofA/JPM: 比較列付き四半期テーブル
  - Nomura: YTD列 + セグメント別内訳
- 旧3モデル設計との差分レビュー（情報損失がないこと）
- Citi/Maybank の画像埋め込みテーブルが `RawTable` フォールバックで適切に処理されること
