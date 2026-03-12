# KG スキーマ v2 実装プラン

## Context

KG スキーマ v2 設計議論（`docs/plan/KnowledgeGraph/2026-03-12_discussion-kg-schema-v2.md`）で決定した 11 項目の設計変更を実装する。現在のコードベースは v1 仕様のままであり、v2 SSoT（`data/config/knowledge-graph-schema.yaml`）との間に大きな乖離がある。

主な変更:
- confidence プロパティの全削除（D11）
- Pydantic モデルの enum 拡張 + 新フィールド追加
- FinancialDataPoint / FiscalPeriod の Pydantic モデル新設
- LLM 抽出プロンプトの v2 対応
- emit_graph_queue.py の Fact/Claim 分離 + 新ノード対応
- neo4j-pdf-constraints.cypher の全制約・インデックス追加

**スコープ外**: Step 5（pipeline 統合）、Step 6（Neo4j 投入）、既存データマイグレーション、Insight 生成ロジック — これらは本プラン完了後に別途実装。

## Phase 1: YAML スキーマから confidence 削除

**ファイル**: `data/config/knowledge-graph-schema.yaml`

- Fact ノード定義から `confidence` プロパティを削除（L142-144）
- Insight ノード定義から `confidence` プロパティを削除（L332-334）

## Phase 2: Pydantic モデル v2 更新

**ファイル**: `src/pdf_pipeline/schemas/extraction.py`

### 2.1 confidence 削除

- `ExtractedFact.confidence` フィールド削除（L109-111）
- `ExtractedClaim.confidence` フィールド削除（L152-154）
- docstring の confidence 関連記載も削除（L92-93, L133-134）

### 2.2 enum 拡張

| モデル | フィールド | 現在 | 追加 |
|--------|-----------|------|------|
| `ExtractedEntity` | `entity_type` | 8種 | +`country`, `instrument` |
| `ExtractedFact` | `fact_type` | 4種 | +`policy_action`, `economic_indicator`, `regulatory`, `corporate_action` |
| `ExtractedClaim` | `claim_type` | 4種 | +`assumption`, `guidance`, `risk_assessment`, `policy_stance`, `sector_view`, `forecast` |
| `ExtractedClaim` | `sentiment` | 3種 | +`mixed` |

### 2.3 新フィールド追加

`ExtractedEntity`:
```python
isin: str | None = Field(default=None, description="ISIN code")
```

`ExtractedClaim`:
```python
magnitude: Literal["strong", "moderate", "slight"] | None = Field(default=None)
target_price: float | None = Field(default=None)
rating: str | None = Field(default=None)
time_horizon: str | None = Field(default=None)
```

### 2.4 新モデル追加

```python
class ExtractedFinancialDataPoint(BaseModel):
    metric_name: str
    value: float
    unit: str
    is_estimate: bool = False
    currency: str | None = None
    period_label: str | None = None  # → FiscalPeriod 生成に使用
    about_entities: list[str] = []

# ChunkExtractionResult に追加:
financial_datapoints: list[ExtractedFinancialDataPoint] = []
```

**注**: FiscalPeriod は抽出対象ではなく `period_label` から emit_graph_queue で派生生成する。Source / Author / Insight は抽出パイプラインのスコープ外（パイプラインメタデータまたは後段処理）。

## Phase 3: LLM プロンプト v2 更新

### 3.1 knowledge_extractor.py

**ファイル**: `src/pdf_pipeline/core/knowledge_extractor.py`

`_EXTRACTION_PROMPT`（L42-85）を以下のように更新:

- `entity_type` enum に `country`, `instrument` 追加
- `fact_type` enum に 4 種追加
- `claim_type` enum に 6 種追加
- `sentiment` に `mixed` 追加
- `confidence` フィールドを facts/claims の JSON 例から削除
- `confidence` に関するルール（L81）を削除
- Claim に `magnitude`, `target_price`, `rating`, `time_horizon` 追加
- `financial_datapoints` セクション追加:
  ```json
  "financial_datapoints": [
    {"metric_name": "Revenue", "value": 12345.6, "unit": "IDR bn", "is_estimate": true, "currency": "IDR", "period_label": "FY2025", "about_entities": ["ISAT"]}
  ]
  ```

### 3.2 gemini_provider.py

**ファイル**: `src/pdf_pipeline/services/gemini_provider.py`

`_KNOWLEDGE_EXTRACT_PROMPT`（L90-103）を knowledge_extractor.py と同じ v2 仕様に更新。

## Phase 4: emit_graph_queue.py v2 更新

**ファイル**: `scripts/emit_graph_queue.py`

### 4.1 `map_pdf_extraction()` の修正（L530-662）

#### Fact を Claim から分離

現在: Fact を `claims[]` に `category: "pdf-fact"` として統合
変更: `facts[]` として独立出力

```python
# 新しい ID 生成関数
def generate_fact_id(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
```

#### 新ノード追加

`_mapped_result()` の返り値に以下を追加:

```python
"facts": facts,                    # Fact ノード（Claim から分離）
"chunks": chunks,                  # Chunk ノード
"financial_datapoints": datapoints, # FinancialDataPoint ノード
"fiscal_periods": periods,         # FiscalPeriod ノード（period_label から派生）
```

#### 新リレーション追加

```python
"relations": {
    "source_fact": [...],          # 既存: STATES_FACT
    "source_claim": [...],         # 既存: MAKES_CLAIM
    "fact_entity": [...],          # 既存: RELATES_TO
    "claim_entity": [...],         # 既存: ABOUT
    "contains_chunk": [...],       # 新規: Source → Chunk
    "extracted_from_fact": [...],   # 新規: Fact → Chunk
    "extracted_from_claim": [...],  # 新規: Claim → Chunk
    "has_datapoint": [...],        # 新規: Source → FinancialDataPoint
    "for_period": [...],           # 新規: FinancialDataPoint → FiscalPeriod
    "datapoint_entity": [...],     # 新規: FinancialDataPoint → Entity
}
```

#### FiscalPeriod 派生ロジック

```python
# period_label → FiscalPeriod ノード生成
seen_periods: dict[str, dict] = {}
for dp in datapoints:
    label = dp.get("period_label")
    if label and label not in seen_periods:
        seen_periods[label] = {
            "period_id": f"{entity_ticker}_{label}",
            "period_label": label,
            "period_type": _infer_period_type(label),  # FY→annual, Q→quarterly 等
        }
```

### 4.2 confidence 参照の削除

- L599: `"confidence": fact.get("confidence", 0.8)` → 削除
- L630: `"confidence": claim.get("confidence", 0.8)` → 削除

## Phase 5: neo4j-pdf-constraints.cypher v2 更新

**ファイル**: `data/config/neo4j-pdf-constraints.cypher`

現在は Fact/Claim の 2 制約のみ。v2 では 10 制約 + 13 インデックスに拡張。

### UNIQUE 制約（+8）

```cypher
CREATE CONSTRAINT unique_source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.source_id IS UNIQUE;
CREATE CONSTRAINT unique_author_id IF NOT EXISTS FOR (a:Author) REQUIRE a.author_id IS UNIQUE;
CREATE CONSTRAINT unique_chunk_id IF NOT EXISTS FOR (ch:Chunk) REQUIRE ch.chunk_id IS UNIQUE;
CREATE CONSTRAINT unique_entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
CREATE CONSTRAINT unique_datapoint_id IF NOT EXISTS FOR (dp:FinancialDataPoint) REQUIRE dp.datapoint_id IS UNIQUE;
CREATE CONSTRAINT unique_period_id IF NOT EXISTS FOR (fp:FiscalPeriod) REQUIRE fp.period_id IS UNIQUE;
CREATE CONSTRAINT unique_topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.topic_id IS UNIQUE;
CREATE CONSTRAINT unique_insight_id IF NOT EXISTS FOR (i:Insight) REQUIRE i.insight_id IS UNIQUE;
```

### インデックス（+13）

```cypher
CREATE INDEX idx_fact_type IF NOT EXISTS FOR (f:Fact) ON (f.fact_type);
CREATE INDEX idx_fact_as_of_date IF NOT EXISTS FOR (f:Fact) ON (f.as_of_date);
CREATE INDEX idx_claim_type IF NOT EXISTS FOR (c:Claim) ON (c.claim_type);
CREATE INDEX idx_claim_sentiment IF NOT EXISTS FOR (c:Claim) ON (c.sentiment);
CREATE INDEX idx_entity_type IF NOT EXISTS FOR (e:Entity) ON (e.entity_type);
CREATE INDEX idx_entity_ticker IF NOT EXISTS FOR (e:Entity) ON (e.ticker);
CREATE INDEX idx_datapoint_metric IF NOT EXISTS FOR (dp:FinancialDataPoint) ON (dp.metric_name);
CREATE INDEX idx_datapoint_is_estimate IF NOT EXISTS FOR (dp:FinancialDataPoint) ON (dp.is_estimate);
CREATE INDEX idx_period_label IF NOT EXISTS FOR (fp:FiscalPeriod) ON (fp.period_label);
CREATE INDEX idx_insight_type IF NOT EXISTS FOR (i:Insight) ON (i.insight_type);
CREATE INDEX idx_insight_status IF NOT EXISTS FOR (i:Insight) ON (i.status);
CREATE INDEX idx_source_type IF NOT EXISTS FOR (s:Source) ON (s.source_type);
CREATE INDEX idx_source_hash IF NOT EXISTS FOR (s:Source) ON (s.source_hash);
```

## Phase 6: テスト更新

### 6.1 test_extraction_schema.py

**ファイル**: `tests/pdf_pipeline/unit/test_extraction_schema.py`

- `TestExtractedFact`: confidence 関連テスト 3 件削除（L85, L98, L105-111）、fact_type 8 種のテスト更新（L100-103）
- `TestExtractedClaim`: confidence 関連テスト 2 件削除（L135, L146, L170-176）、claim_type 10 種・sentiment 4 種のテスト更新（L148-151, L153-160）、新フィールド（magnitude, target_price, rating, time_horizon）のテスト追加
- `TestExtractedEntity`: entity_type 10 種のテスト更新（L49-62）、isin フィールドのテスト追加
- 新クラス `TestExtractedFinancialDataPoint` 追加

### 6.2 test_knowledge_extractor.py

**ファイル**: `tests/pdf_pipeline/unit/test_knowledge_extractor.py`

- `_make_valid_extraction_json()`: confidence 削除（L66, L75）、v2 enum 値使用、financial_datapoints 追加
- テストの assertion から confidence 関連チェック削除

### 6.3 test_emit_graph_queue_pdf.py

**ファイル**: `tests/pdf_pipeline/unit/test_emit_graph_queue_pdf.py`

- `_make_extraction_data()`: confidence 削除（L66, L75）、financial_datapoints 追加
- `test_正常系_Fact_Claimがclaimsに含まれる`: Fact/Claim 分離に合わせて修正 → `result["facts"]` と `result["claims"]` を別々に検証
- 新テスト追加: Chunk ノード生成、FinancialDataPoint ノード生成、FiscalPeriod 派生生成、新リレーション検証

## 実装順序

```
Phase 1 (YAML)
  ↓
Phase 2 (Pydantic) → Phase 3 (プロンプト) を並列可
  ↓
Phase 5 (constraints) — Phase 2/3 と並列可
  ↓
Phase 4 (emit_graph_queue) — Phase 2 完了後
  ↓
Phase 6 (テスト) — 各 Phase と同時に TDD で実施
```

## 検証

### ユニットテスト

```bash
uv run pytest tests/pdf_pipeline/unit/test_extraction_schema.py -v
uv run pytest tests/pdf_pipeline/unit/test_knowledge_extractor.py -v
uv run pytest tests/pdf_pipeline/unit/test_emit_graph_queue_pdf.py -v
```

### 品質チェック

```bash
make check-all  # format, lint, typecheck, test
```

### Neo4j 制約適用

```bash
# Docker Neo4j に制約を適用
cat data/config/neo4j-pdf-constraints.cypher | cypher-shell -u neo4j -p <password>
```

### E2E 検証（Phase 4 完了後）

1. サンプル PDF でチャンク→抽出→graph-queue JSON 生成
2. graph-queue JSON の構造確認（facts/claims 分離、financial_datapoints 存在、FiscalPeriod 派生）
3. `save-to-graph` スキルで Neo4j 投入（別プランのスコープだが手動確認は可能）

## 対象ファイル一覧

| ファイル | Phase | 変更内容 |
|---------|-------|---------|
| `data/config/knowledge-graph-schema.yaml` | 1 | confidence 削除 |
| `src/pdf_pipeline/schemas/extraction.py` | 2 | confidence 削除、enum 拡張、新フィールド、新モデル |
| `src/pdf_pipeline/core/knowledge_extractor.py` | 3 | プロンプト v2 更新 |
| `src/pdf_pipeline/services/gemini_provider.py` | 3 | プロンプト v2 更新 |
| `scripts/emit_graph_queue.py` | 4 | Fact 分離、新ノード、新リレーション、confidence 削除 |
| `data/config/neo4j-pdf-constraints.cypher` | 5 | 全制約・インデックス追加 |
| `tests/pdf_pipeline/unit/test_extraction_schema.py` | 6 | confidence テスト削除、v2 テスト追加 |
| `tests/pdf_pipeline/unit/test_knowledge_extractor.py` | 6 | confidence 削除、v2 データ更新 |
| `tests/pdf_pipeline/unit/test_emit_graph_queue_pdf.py` | 6 | Fact/Claim 分離テスト、新ノードテスト |
