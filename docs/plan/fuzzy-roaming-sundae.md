# PDF パイプライン簡素化: テキストのみ抽出 → ナレッジグラフ保存

Created: 2026-03-12

---

## Context

現在の PDF パイプライン（Phase 1-4 実装済み）は、テキスト抽出に加えて **テーブル検出（PyMuPDF）+ テーブル再構築（LLM）** を行っている。テーブル再構築は1テーブルあたり60-300秒のLLM呼び出しが必要で、1PDFに10-20テーブルがあると合計10-100分かかる。

テキスト情報のみ抽出してナレッジグラフに保存する方式に簡素化し、コストと時間を削減する。

**見込み効果**: 処理時間 50-90% 削減、LLM呼び出し数 30-70% 削減

---

## 方針

1. テーブル/画像処理をスキップ可能にする（`text_only` フラグ）
2. テキストチャンクからEntity/Fact/Claimを LLM で抽出する（Phase 5）
3. 抽出結果を graph-queue JSON として出力し、既存の save-to-graph で Neo4j に投入する

**既存インフラの再利用を最大化**: emit_graph_queue.py のID生成パターン、save-to-graph の MERGE パターン、graph-queue フォーマットをそのまま活用。

---

## 実装ステップ

### Step 1: テーブル処理のオプション化

**目的**: `text_only=True` で Phase 4a/4b をスキップ

**変更ファイル**:
- `src/pdf_pipeline/types.py` — `PipelineConfig` に `text_only: bool = True` 追加
- `src/pdf_pipeline/core/pipeline.py` — `table_detector` と `table_reconstructor` を `| None = None` に変更、`text_only` 時はスキップ

**pipeline.py の変更箇所** (L127-L156, L314-L346):

```python
# __init__ の変更
def __init__(
    self,
    *,
    config: PipelineConfig,
    scanner: PdfScanner,
    noise_filter: NoiseFilter,
    markdown_converter: MarkdownConverter,
    table_detector: TableDetector | None = None,      # Optional に
    table_reconstructor: TableReconstructor | None = None,  # Optional に
    chunker: MarkdownChunker,
    state_manager: StateManager,
    text_extractor: TextExtractor | None = None,
) -> None: ...

# process_pdf 内の変更
if not self.config.text_only and self.table_detector is not None:
    raw_tables = self.table_detector.detect(str(pdf_path), doc=fitz_doc)
    # ... table reconstruction ...
else:
    raw_tables = []
    reconstructed_tables = []
```

**テスト** (`tests/pdf_pipeline/unit/test_pipeline.py` に追加):
- `test_正常系_text_onlyモードでテーブル検出スキップ`
- `test_正常系_table_detector_Noneで初期化成功`
- `test_正常系_text_only_Falseで従来通りテーブル処理`

---

### Step 2: 抽出スキーマ定義

**目的**: Entity/Fact/Claim の Pydantic モデルを定義

**新規ファイル**: `src/pdf_pipeline/schemas/extraction.py`

```python
class ExtractedEntity(BaseModel):
    name: str
    entity_type: Literal["company", "index", "sector", "indicator",
                         "currency", "commodity", "person", "organization"]
    ticker: str | None = None
    aliases: list[str] = []

class ExtractedFact(BaseModel):
    content: str
    fact_type: Literal["statistic", "event", "data_point", "quote"]
    as_of_date: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    about_entities: list[str] = []    # entity name のリスト

class ExtractedClaim(BaseModel):
    content: str
    claim_type: Literal["opinion", "prediction", "recommendation", "analysis"]
    sentiment: Literal["bullish", "bearish", "neutral"] | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    about_entities: list[str] = []

class ChunkExtractionResult(BaseModel):
    chunk_index: int
    section_title: str | None = None
    entities: list[ExtractedEntity] = []
    facts: list[ExtractedFact] = []
    claims: list[ExtractedClaim] = []

class DocumentExtractionResult(BaseModel):
    source_hash: str
    chunks: list[ChunkExtractionResult] = []
```

**テスト** (`tests/pdf_pipeline/unit/test_extraction_schema.py`):
- バリデーション正常系/異常系（confidence 範囲、Literal 制約等）

---

### Step 3: KnowledgeExtractor 実装

**目的**: テキストチャンクから Entity/Fact/Claim を LLM で抽出

**新規ファイル**: `src/pdf_pipeline/core/knowledge_extractor.py`

```python
class KnowledgeExtractor:
    def __init__(self, provider_chain: ProviderChain) -> None: ...

    def extract_from_chunks(
        self, *, chunks: list[dict[str, Any]], source_hash: str,
    ) -> DocumentExtractionResult:
        """全チャンクから知識を抽出"""
        results = []
        for chunk in chunks:
            result = self._extract_single(chunk)
            results.append(result)
        return DocumentExtractionResult(source_hash=source_hash, chunks=results)

    def _extract_single(self, chunk: dict[str, Any]) -> ChunkExtractionResult:
        """1チャンクの抽出。LLM失敗時は空結果を返す（グレースフルデグラデーション）"""
        try:
            raw_json = self.provider_chain.extract_knowledge(chunk["content"])
            parsed = json.loads(raw_json)
            return ChunkExtractionResult.model_validate(parsed)
        except Exception as e:
            logger.warning("Knowledge extraction failed for chunk", error=str(e))
            return ChunkExtractionResult(chunk_index=chunk["chunk_index"])
```

**変更ファイル**: `src/pdf_pipeline/services/gemini_provider.py`
- `_KNOWLEDGE_EXTRACT_PROMPT` を更新: Entity/Fact/Claim の詳細スキーマを指示し、`ChunkExtractionResult` 互換の JSON を出力させる

**テスト** (`tests/pdf_pipeline/unit/test_knowledge_extractor.py`):
- `test_正常系_チャンクからEntity_Fact_Claim抽出`
- `test_異常系_LLM失敗で空結果フォールバック`
- `test_異常系_不正JSON解析で空結果フォールバック`
- `test_エッジケース_空チャンクで空結果`

---

### Step 4: graph-queue JSON 出力

**目的**: 抽出結果を既存の graph-queue フォーマットに変換

**変更ファイル**: `scripts/emit_graph_queue.py`
- `pdf-extraction` マッパーを追加
- 入力: `DocumentExtractionResult` の JSON（`{output_dir}/{source_hash}/extraction.json`）
- 出力: graph-queue JSON（`.tmp/graph-queue/gq-{timestamp}-{hash}.json`）

**マッピング**:

| 抽出データ | graph-queue ノード | ID生成 |
|-----------|-------------------|--------|
| PDF ファイル | Source (source_type: "pdf") | UUID5(file_path) |
| ExtractedEntity | Entity | UUID5("entity:{name}:{type}") |
| ExtractedFact | Fact | SHA256(content)[:16] |
| ExtractedClaim | Claim | SHA256(content)[:16] |

**リレーション**:

| from | to | type | 条件 |
|------|-----|------|------|
| Source | Fact | STATES_FACT | 常に |
| Source | Claim | MAKES_CLAIM | 常に |
| Fact | Entity | RELATES_TO | about_entities に name がある |
| Claim | Entity | ABOUT | about_entities に name がある |

**ID生成**: 既存の `id_generator.py` に `generate_entity_id` を追加

```python
# src/pdf_pipeline/services/id_generator.py に追加
def generate_entity_id(name: str, entity_type: str) -> str:
    key = f"entity:{name}:{entity_type}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))
```

**テスト** (`tests/pdf_pipeline/unit/test_emit_graph_queue_pdf.py`):
- graph-queue JSON のフォーマット検証
- ID の決定論性検証

---

### Step 5: パイプライン統合

**目的**: Phase 5（知識抽出）+ JSON出力をパイプラインに組み込む

**変更ファイル**: `src/pdf_pipeline/core/pipeline.py`

```python
# __init__ に追加
knowledge_extractor: KnowledgeExtractor | None = None,

# process_pdf 内（チャンキング後に追加）
# -- Phase 5: Knowledge extraction (optional) --
if self.knowledge_extractor is not None:
    extraction = self.knowledge_extractor.extract_from_chunks(
        chunks=chunks, source_hash=source_hash,
    )
    self._save_extraction(source_hash=source_hash, extraction=extraction)

# _save_extraction メソッド追加
def _save_extraction(self, *, source_hash: str, extraction: DocumentExtractionResult) -> None:
    output_file = self.config.output_dir / source_hash / "extraction.json"
    output_file.write_text(
        extraction.model_dump_json(indent=2), encoding="utf-8",
    )
```

**変更ファイル**: `src/pdf_pipeline/types.py`
- `PipelineConfig` に `enable_knowledge_extraction: bool = False` 追加

**テスト**:
- `test_正常系_knowledge_extractor設定時にextraction_json出力`
- `test_正常系_knowledge_extractor_Noneでスキップ`
- `test_異常系_extraction失敗でもchunks保存は成功`

---

### Step 6: Neo4j 投入（既存スキル活用）

**目的**: save-to-graph スキルで graph-queue JSON を Neo4j に投入

**追加制約** (`data/config/neo4j-pdf-constraints.cypher`):

```cypher
CREATE CONSTRAINT unique_fact_id IF NOT EXISTS
  FOR (f:Fact) REQUIRE f.fact_id IS UNIQUE;
```

**実行フロー**:

```bash
# 1. テキストのみパイプライン実行
uv run python -m pdf_pipeline.cli process data/sample_report/*.pdf

# 2. extraction.json → graph-queue JSON 変換
python3 scripts/emit_graph_queue.py \
  --command pdf-extraction \
  --input data/processed/{source_hash}/extraction.json

# 3. Neo4j 投入（save-to-graph スキル）
# /save-to-graph コマンドで .tmp/graph-queue/ 内の JSON を投入
```

---

## 実装順序と依存関係

```
Step 1 (text_only フラグ)  ←── 独立、低リスク
Step 2 (抽出スキーマ)       ←── 独立
    ↓
Step 3 (KnowledgeExtractor) ←── Step 2 に依存
Step 4 (graph-queue 出力)   ←── Step 2 に依存、Step 3 と並行可
    ↓
Step 5 (パイプライン統合)   ←── Step 1, 3, 4 に依存
Step 6 (Neo4j 投入)         ←── Step 4, 5 の後
```

Step 1 と Step 2 は並行実施可。Step 3 と Step 4 も並行可。

---

## 主要ファイル一覧

| ファイル | 変更/新規 | 内容 |
|---------|----------|------|
| `src/pdf_pipeline/types.py` | 変更 | `text_only`, `enable_knowledge_extraction` 追加 |
| `src/pdf_pipeline/core/pipeline.py` | 変更 | テーブルOptional化、Phase 5 追加 |
| `src/pdf_pipeline/schemas/extraction.py` | **新規** | Entity/Fact/Claim Pydantic モデル |
| `src/pdf_pipeline/core/knowledge_extractor.py` | **新規** | LLM 知識抽出 |
| `src/pdf_pipeline/services/gemini_provider.py` | 変更 | 抽出プロンプト更新 |
| `src/pdf_pipeline/services/id_generator.py` | 変更 | `generate_entity_id` 追加 |
| `scripts/emit_graph_queue.py` | 変更 | `pdf-extraction` マッパー追加 |
| `data/config/neo4j-pdf-constraints.cypher` | **新規** | Fact 制約 |

---

## 検証方法

1. **既存テスト**: `make test` で 334 テストが全て PASS すること（後方互換性）
2. **テキストのみモード**: `text_only=True` でテーブル処理がスキップされ、chunks.json が生成されること
3. **知識抽出**: サンプル PDF（HSBC ISAT）で extraction.json が生成され、Entity/Fact/Claim が含まれること
4. **graph-queue 変換**: `emit_graph_queue.py --command pdf-extraction` で有効な graph-queue JSON が出力されること
5. **Neo4j 投入**: save-to-graph で graph-queue JSON が Neo4j に投入されること（MERGE で冪等）

```bash
# E2E 検証
uv run python -m pdf_pipeline.cli process data/sample_report/HSBC*.pdf
cat data/processed/*/extraction.json | python3 -m json.tool
python3 scripts/emit_graph_queue.py --command pdf-extraction --input data/processed/*/extraction.json
```

---

## リスク軽減

| リスク | 軽減策 |
|--------|--------|
| LLM 抽出のJSON構造不安定 | Pydantic バリデーション + 空結果フォールバック（パイプライン不停止） |
| 既存334テスト破壊 | table_detector/reconstructor は Optional 化のみ。既存テストの引数は変更不要 |
| 抽出品質が低い | 1-pass で MVP → 品質見て 2-pass 検討。プロンプトに few-shot 例を含める |
| Neo4j 未接続時 | extraction.json → graph-queue JSON → save-to-graph の3段階分離で各段階独立実行可 |
