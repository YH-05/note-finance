# PDF→Markdown変換パイプライン設計

Created: 2026-03-11
Status: Phase 2-4（PDF→MD変換）を優先実装。知識抽出・Neo4j投入は後続Phase。

## Context

ナレッジグラフ構築（`docs/plan/KnowledgeGraph/2026-03-11_first-memo.md`）の一環として、セルサイド・中央銀行・コンサル等の調査レポートPDFをMarkdownに変換するパイプラインを設計する。

Docling MCP + Gemini CLIでの変換を試みたが、以下の課題が発生:
1. 出力結果が安定しない
2. 免責事項などノイズを拾う
3. 複雑な表（財務諸表等）をパースできない

### 方針決定

- **処理エンジン**: Gemini CLI主体。Doclingはレイアウト解析（ノイズ除去フィルター）にのみ使用
- **実装スコープ**: まずPDF→Markdown変換（Phase 2-4）の品質安定化に集中
- **後続**: 知識抽出（Phase 5-6）→ graph-queue出力（Phase 7）→ Neo4j投入（Phase 8）は別プランで実施
- **Docling**: 使い方自体がまだ試行錯誤段階。パイプライン内ではDocling非依存でも動作する設計にし、Doclingは精度向上のオプションとして位置づける

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
          Gemini          Gemini
          Vision-first    Structured Output
          → Markdown      → JSON (Pydantic)
                │             │
                └──────┬──────┘
                       ▼
                  チャンキング
                  (セクション単位)
                       │
                       ▼
                  知識抽出 (Gemini)
                  Fact / Claim / Entity
                       │
                       ▼
                  Entity名寄せ
                       │
                       ▼
                  graph-queue JSON出力
                       │
                       ▼
                  save-to-graph → Neo4j
```

**設計判断**: Markdownは本文テキスト（Track A）にのみ使用。表・数値データ（Track B）はJSON形式で直接構造化抽出する。グラフDB保存が最終目的であり、Markdown化は中間ステップに過ぎない。

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

### Phase 3A: Vision-first Markdown変換（Gemini CLI）

- **デュアルインプット方式**: 元PDFファイル + Phase 2Aのフィルター済みテキストの両方をGeminiに渡す
  - PDFから視覚的コンテキスト（レイアウト・強調・図表位置）を取得
  - Doclingテキストで文字精度をアンカリング
- セクション分割されたMarkdownを出力
- 見出し階層(H1/H2/H3)を保持

**出力**: `{source_hash}/body.md`

### Phase 3B: 表再構築（Gemini Structured Output）

- 切り出した表画像をGeminiに渡し、**Pydanticスキーマ準拠のJSON**で出力
- 中間形式としてHTMLテーブルも保持（結合セル・多段ヘッダー対応）
- Pydanticバリデーションで出力を検証

```python
class FinancialRow(BaseModel):
    metric: str
    values: dict[str, float | str | None]  # period -> value

class FinancialStatementTable(BaseModel):
    table_type: Literal["pnl", "cashflow", "balance_sheet", "valuation", "generic"]
    title: str
    periods: list[str]
    rows: list[FinancialRow]
    source_page: int | None = None
```

**出力**: `{source_hash}/tables/table_001.json` + `table_001.md`

### Phase 4: チャンキング

- Markdownを見出し境界でセクション分割
- 表は親セクション内のサブチャンク or 独立チャンクとして付与
- `chunk_index` で順序管理

**出力**: `{source_hash}/chunks.json`

### Phase 5: 知識抽出（Gemini CLI）

- チャンクごとにFact / Claim / Entityを抽出
- Pydanticスキーマで出力を標準化

```python
class ExtractedFact(BaseModel):
    content: str
    fact_type: Literal["statistic", "event", "data_point", "quote"]
    as_of_date: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

class ExtractedClaim(BaseModel):
    content: str
    claim_type: Literal["opinion", "prediction", "recommendation", "analysis"]
    sentiment: Literal["bullish", "bearish", "neutral"] | None = None
    confidence: float = Field(ge=0.0, le=1.0)

class ExtractedEntity(BaseModel):
    name: str
    entity_type: Literal["company", "index", "sector", "indicator", "currency", "commodity", "person", "organization"]
    ticker: str | None = None
    aliases: list[str] = []
```

### Phase 6: Entity名寄せ

- バッチ内のEntity重複排除（完全一致 + エイリアスマッチ）
- Neo4j既存Entityとの照合（`mcp-neo4j-cypher`経由）
- 正規化された `entity_id` を付与

### Phase 7: graph-queue JSON出力

- 既存の `save-to-graph` スキルが消費可能な形式で出力
- 出力先: `.tmp/graph-queue/pdf-report-pipeline/`

### Phase 8: Neo4j投入

- 既存 `/save-to-graph --source pdf-report-pipeline` で冪等投入

---

## スキーマ拡張

既存 `data/config/knowledge-graph-schema.yaml` への追加:

### 新規ノード: Chunk

```yaml
Chunk:
  description: "Text chunk from a source document for traceability"
  properties:
    chunk_id:
      type: string
      unique: true
      required: true
    text:
      type: string
      required: true
    chunk_index:
      type: integer
      required: true
    chunk_type:
      type: string
      enum: [text, table, figure]
      indexed: true
    section_title:
      type: string
    page_ref:
      type: string
```

### 新規リレーション

```yaml
HAS_CHUNK:
  from: Source
  to: Chunk
  description: "Source contains this chunk"

EXTRACTED_FROM:
  from: [Fact, Claim]
  to: Chunk
  description: "Fact/Claim was extracted from this chunk (traceability)"
```

### Neo4j制約追加

```cypher
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS
  FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
```

---

## ファイル構成（Phase 2-4スコープ）

```
src/pdf_pipeline/
├── __init__.py
├── types.py                    # Pydanticモデル（ProcessingState, PdfMetadata等）
├── schemas/
│   └── tables.py               # 表再構築用Pydanticスキーマ
├── config/
│   └── loader.py               # YAML設定ローダー
├── core/
│   ├── pipeline.py             # パイプラインオーケストレーター
│   ├── pdf_scanner.py          # PDF検出・ハッシュ計算
│   ├── noise_filter.py         # ノイズフィルター（正規表現ベース、Doclingオプション）
│   ├── table_detector.py       # 表検出・画像切り出し
│   ├── markdown_converter.py   # Gemini Vision-first変換
│   ├── table_reconstructor.py  # 表→JSON再構築
│   └── chunker.py              # セクション単位チャンキング
├── services/
│   ├── gemini_client.py        # Gemini CLI ラッパー（subprocess）
│   └── state_manager.py        # 処理状態管理（冪等性）
└── cli/
    └── main.py                 # Click CLI（process / status / reprocess）

data/config/
└── pdf-pipeline-config.yaml    # パイプライン設定

tests/pdf_pipeline/
├── unit/                       # noise_filter, chunker, schemas等
└── integration/                # E2Eテスト（サンプルPDF使用）
```

**後続Phaseで追加予定**: `schemas/extraction.py`, `core/knowledge_extractor.py`, `core/entity_resolver.py`, `services/docling_client.py`

---

## 依存ライブラリ

| ライブラリ | 用途 | 状態 |
|-----------|------|------|
| `pydantic` | スキーマ定義・バリデーション | 既存 |
| `structlog` | 構造化ログ | 既存 |
| `pyyaml` | 設定読み込み | 既存 |
| `click` | CLI | 既存 |
| `pymupdf` | PDF画像切り出し | **新規追加** |

**外部ツール**: `gemini` CLI, `docling-mcp-server`（共に設定済み）

---

## 実装ロードマップ（今回のスコープ: Phase 2-4）

### Step 1: 基盤 + PDF取り込み

1. `src/pdf_pipeline/` パッケージ作成（pyproject.toml登録含む）
2. `types.py` Pydanticモデル定義
3. `config/loader.py` + `data/config/pdf-pipeline-config.yaml`
4. `core/pdf_scanner.py` PDF検出・ハッシュ計算
5. `services/state_manager.py` 処理状態管理（冪等性）
6. 単体テスト

### Step 2: ノイズ除去 + Gemini Vision-first変換

1. `services/gemini_client.py` Gemini CLIラッパー（subprocess）
2. `core/noise_filter.py` 正規表現ベースのノイズフィルター（Docling非依存で動作、Docling連携はオプション）
3. `core/markdown_converter.py` Gemini Vision-first変換（PDFを直接Geminiに渡す）
4. Geminiプロンプトテンプレート設計
5. サンプルPDF（HSBC ISAT 3Q25）での変換精度検証

### Step 3: 表専用パース

1. `schemas/tables.py` Pydanticテーブルスキーマ
2. `core/table_detector.py` 表検出（pymupdf or Geminiに委任）
3. `core/table_reconstructor.py` 表画像→JSON再構築（Gemini Structured Output）
4. 財務諸表サンプルでの検証（HSBC ISAT P&L, Balance Sheet）

### Step 4: チャンキング + 統合パイプライン

1. `core/chunker.py` セクション単位チャンキング
2. `core/pipeline.py` Phase 2-4のオーケストレーター
3. `cli/main.py` Click CLI（`process` / `status` コマンド）
4. E2Eテスト（サンプルPDF → Markdown + JSON出力）

### 後続（別プラン）

- Phase 5-6: 知識抽出（Fact/Claim/Entity） + Entity名寄せ
- Phase 7: graph-queue JSON出力
- Phase 8: save-to-graph拡張 + Neo4j投入
- スキーマ拡張（Chunkノード追加等）は知識抽出Phase時に実施

---

## 検証方法

### 変換品質の検証

- `data/sample_report/HSBC_ISAT_3Q25_Complete_Faithful.md` を正解データとして使用
- Gemini出力とのセクション・表の一致率を比較
- ノイズ（免責事項・ヘッダ・フッタ）の除去率を計測

### 表パース精度の検証

- HSBC ISAT 3Q25の財務諸表（P&L, Balance Sheet, Cashflow）を対象
- 数値の一致率を検証（元PDFの数値 vs 抽出JSON）

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
|-------|--------|
| Gemini出力の不安定性 | デュアルインプット（PDF+Doclingテキスト）でアンカリング + Pydanticバリデーション |
| 表パース精度 | HTML中間形式 + Pydantic検証 + 低信頼度テーブルに手動レビューフラグ |
| 免責事項の混入 | 3層フィルター（Doclingレイアウト + 正規表現 + 位置ヒューリスティック） |
| 大規模PDFの処理時間 | ページ単位処理 + バッチサイズ制限 + タイムアウト設定 |
| Entity名寄せの誤検出 | 保守的マッチング（entity_type一致 + 名前類似度閾値） |

---

## 関連ファイル

| ファイル | 役割 |
|---------|------|
| `docs/plan/KnowledgeGraph/2026-03-11_first-memo.md` | ナレッジグラフ構築メモ（上位計画） |
| `data/config/knowledge-graph-schema.yaml` | グラフスキーマ定義（拡張対象） |
| `.claude/skills/save-to-graph/SKILL.md` | Neo4j投入スキル（拡張対象） |
| `src/report_scraper/storage/pdf_store.py` | PDF保存パターン（参考） |
| `src/report_scraper/types.py` | Pydantic+dataclassパターン（参考） |
| `data/sample_report/` | 検証用サンプルPDF・Markdown |
