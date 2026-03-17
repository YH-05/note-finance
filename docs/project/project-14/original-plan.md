# KG v2.1: AI推論最適化スキーマ設計

**日付**: 2026-03-17
**目的**: article-neo4j のスキーマをAIの創発的推論に最適化する

## Context

現行 KG v2.0 は Storage-Oriented 設計で、投資スタンスの時系列変化、因果関係、知識ギャップ、時間軸の連鎖がプロパティに閉じ込められており、AIがグラフ走査だけでは発見できない。本計画では、推論に必要な情報を選択的にノード/エッジに昇格（Selective Reification）する。

**除外**: Embedding + SIMILAR_TO（LLM APIリソース制約のため後回し）

## Wave 構成

```
Wave 0: Bug Fix + テスト基盤       ← 全Waveの前提
Wave 1: Stance + SUPERSEDES        ← P0（並列可）
Wave 2: CAUSES エッジ              ← P0（並列可）
Wave 3: Temporal Chain             ← P1（並列可）
Wave 4: Question ノード            ← P1（並列可）
```

---

## Wave 0: バグ修正 + テスト基盤

### 背景
`_build_claim_nodes()` で `target_price`, `rating`, `magnitude`, `time_horizon` がドロップされている（L891-899）。また `map_pdf_extraction` のテストが存在しない。

### 実装ステップ

1. **`scripts/emit_graph_queue.py` L891-899 修正**
   - Claim dict に `magnitude`, `target_price`, `rating`, `time_horizon` を追加

2. **`save-to-graph/guide.md` Claim MERGE Cypher 更新**
   - `target_price`, `rating`, `time_horizon` プロパティを SET に追加

3. **`tests/scripts/test_emit_graph_queue.py` に `TestMapPdfExtraction` 追加**
   - ヘルパー `_pdf_extraction_data()` で claim に全プロパティを含むサンプル生成
   - `test_正常系_Claimのtarget_priceとratingが保持される`
   - `test_正常系_FiscalPeriodが正しく派生される`
   - `test_エッジケース_空チャンクでも正常動作`

### 影響ファイル
- `scripts/emit_graph_queue.py` — 4行追加
- `.claude/skills/save-to-graph/guide.md` — Cypher更新
- `tests/scripts/test_emit_graph_queue.py` — ~80行追加

---

## Wave 1: Stance + SUPERSEDES（P0）

### 目的
アナリストの投資スタンス（Rating + TP + Sentiment）をAuthorごと・Entityごとに時系列追跡可能にする。

### 新スキーマ要素

**ノード:**
| ノード | プロパティ | ID戦略 |
|--------|-----------|--------|
| Stance | stance_id, rating, sentiment, target_price, target_price_currency, as_of_date, created_at | UUID5(author:entity:date) |
| Author | author_id, name, author_type, organization | UUID5(author:name:type) |

**リレーション:**
| リレーション | From → To | プロパティ |
|-------------|-----------|-----------|
| HOLDS_STANCE | Author → Stance | — |
| ON_ENTITY | Stance → Entity | — |
| BASED_ON | Stance → Claim | role |
| SUPERSEDES | Stance → Stance | superseded_at |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — Stance, Author ノード + 4リレーション追加

2. **`src/pdf_pipeline/services/id_generator.py`** — `generate_stance_id()`, `generate_author_id()` 追加

3. **`src/pdf_pipeline/schemas/extraction.py`** — `ExtractedStance` モデル追加、`ChunkExtractionResult.stances` フィールド追加

4. **`src/pdf_pipeline/core/knowledge_extractor.py`** — 抽出プロンプトに `stances[]` 出力フォーマット追加

5. **`scripts/emit_graph_queue.py`**:
   - `_build_stance_nodes()`: Stance/Author ノード + リレーション生成
   - `_build_supersedes_chain()`: 同一(author, entity)グループ内で日付順にSUPERSEDES連鎖生成
   - `_mapped_result()`: `stances`, `authors` キー追加
   - `_empty_rels()`: `holds_stance`, `on_entity`, `based_on`, `supersedes` 追加
   - `_process_chunk()`: `_build_stance_nodes()` 呼び出し追加
   - `map_pdf_extraction()`: 全チャンク処理後に `_build_supersedes_chain()` 呼び出し

6. **`.claude/skills/save-to-graph/guide.md`** — Author/Stance MERGE + 4リレーション Cypher テンプレート追加

7. **テスト**:
   - `TestBuildStanceNodes` — 基本生成、SUPERSEDES連鎖、Author重複排除
   - `test_generate_stance_id` — 決定論性テスト

### SUPERSEDES 連鎖ロジック
```python
# map_pdf_extraction() 内の後処理
stances_by_key = defaultdict(list)
for s in all_stances:
    stances_by_key[(s["author_name"], s["entity_name"])].append(s)

for key, group in stances_by_key.items():
    sorted_group = sorted(group, key=lambda x: x["as_of_date"])
    for i in range(1, len(sorted_group)):
        rels["supersedes"].append({
            "from_id": sorted_group[i]["stance_id"],
            "to_id": sorted_group[i-1]["stance_id"],
            "type": "SUPERSEDES"
        })
```

### AI推論パス（実現例）
```cypher
-- ISATに対するHSBCの見解変遷
MATCH (a:Author {name: "HSBC"})-[:HOLDS_STANCE]->(s:Stance)-[:ON_ENTITY]->(e:Entity {ticker: "ISAT"})
OPTIONAL MATCH (s)-[:SUPERSEDES]->(prev:Stance)
RETURN s.rating, s.target_price, s.as_of_date, prev.rating AS prev_rating
ORDER BY s.as_of_date

-- レーティング変更があった全ケース
MATCH (new:Stance)-[:SUPERSEDES]->(old:Stance)-[:ON_ENTITY]->(e:Entity)
WHERE new.rating <> old.rating
RETURN e.name, old.rating, new.rating, new.as_of_date
```

---

## Wave 2: CAUSES エッジ（P0）

### 目的
Fact/Claim/FinancialDataPoint 間の因果関係を明示化し、AIが根拠チェーンを走査可能にする。

### 新スキーマ要素

**リレーション:**
| リレーション | From → To | プロパティ |
|-------------|-----------|-----------|
| CAUSES | Fact/Claim/FinancialDataPoint → Fact/Claim/FinancialDataPoint | mechanism, confidence (stated/inferred/speculative), source_id |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — CAUSES リレーション追加

2. **`src/pdf_pipeline/schemas/extraction.py`** — `ExtractedCausalLink` モデル追加
   ```python
   class ExtractedCausalLink(BaseModel):
       cause_content: str       # 原因ノードのcontent
       cause_type: Literal["fact", "claim", "datapoint"]
       effect_content: str      # 結果ノードのcontent
       effect_type: Literal["fact", "claim", "datapoint"]
       mechanism: str | None    # "ARPU growth drove revenue increase"
       confidence: Literal["stated", "inferred", "speculative"]
   ```

3. **`src/pdf_pipeline/core/knowledge_extractor.py`** — 抽出プロンプトに `causal_links[]` 追加

4. **`scripts/emit_graph_queue.py`**:
   - `_build_causal_links()`: content-to-ID マッピングで from/to を解決、CAUSES rel 生成
   - `_empty_rels()`: `causes` 追加
   - graph-queue の `relations.causes` 各要素に `from_label`, `to_label` を含める（Neo4j CE 対応）

5. **`.claude/skills/save-to-graph/guide.md`** — CAUSES MERGE Cypher（ラベル別分岐）

6. **テスト**: `TestBuildCausalLinks` — Fact→Claim, Claim→DataPoint, 未解決参照の無視

### content-to-ID 解決戦略
```python
# _process_chunk() 内で蓄積した content → id マッピングを利用
content_to_id = {}
for f in facts:
    content_to_id[("fact", f["content"])] = f["fact_id"]
for c in claims:
    content_to_id[("claim", c["content"])] = c["claim_id"]
for dp in datapoints:
    content_to_id[("datapoint", dp["metric_name"])] = dp["datapoint_id"]
```

### AI推論パス（実現例）
```cypher
-- ISATのTP引き上げの根拠チェーンを遡る
MATCH chain = (effect:Claim {claim_type: "recommendation"})<-[:CAUSES*1..5]-(root)
WHERE (effect)-[:ABOUT]->(:Entity {ticker: "ISAT"})
RETURN [n IN nodes(chain) | n.content] AS causal_chain

-- 全因果チェーンのうち、statedレベルのみ
MATCH (cause)-[r:CAUSES {confidence: "stated"}]->(effect)
RETURN cause.content, r.mechanism, effect.content
```

---

## Wave 3: Temporal Chain（P1）

### 目的
FiscalPeriod 間の時系列順序と、同一メトリックの TREND を構造化する。

### 新スキーマ要素

**リレーション:**
| リレーション | From → To | プロパティ |
|-------------|-----------|-----------|
| NEXT_PERIOD | FiscalPeriod → FiscalPeriod | gap_months |
| TREND | FinancialDataPoint → FinancialDataPoint | change_pct, direction (up/down/flat) |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — 2リレーション追加

2. **`scripts/emit_graph_queue.py`**:
   - `_period_sort_key(label: str) -> tuple[int, int]`: 期間ラベルのソートキー
     - `FY2025` → `(2025, 0)`, `3Q25` → `(2025, 3)`, `1H26` → `(2026, 1)`
   - `_build_next_period_chain()`: ticker別・period_type別にソート → 連続ペアで NEXT_PERIOD 生成
   - `_build_trend_edges()`: (entity, metric_name)別にソート → 変化率計算 → TREND 生成
   - `_empty_rels()`: `next_period`, `trend` 追加

3. **`.claude/skills/save-to-graph/guide.md`** — NEXT_PERIOD, TREND Cypher テンプレート

4. **テスト**:
   - `TestPeriodSortKey` — 四半期/年次/半期のソート
   - `TestBuildNextPeriodChain` — 正常チェーン、異なるエンティティの独立性
   - `TestBuildTrendEdges` — up/down/flat、ゼロ除算回避

### TREND 計算ロジック
```python
change_pct = (current.value - prev.value) / abs(prev.value) * 100
direction = "up" if change_pct > 1 else ("down" if change_pct < -1 else "flat")
```

### AI推論パス（実現例）
```cypher
-- ISATのRevenue推移を時系列走査
MATCH (dp:FinancialDataPoint {metric_name: "Revenue"})-[:RELATES_TO]->(e:Entity {ticker: "ISAT"})
MATCH chain = (dp)-[:TREND*0..8]->(latest)
RETURN [n IN nodes(chain) | {value: n.value, period: n.period_label}]

-- 3期連続増加しているメトリック
MATCH (d1)-[t1:TREND {direction: "up"}]->(d2)-[t2:TREND {direction: "up"}]->(d3)-[t3:TREND {direction: "up"}]->(d4)
WHERE d1.metric_name = d2.metric_name
RETURN d1.metric_name, d4.value
```

---

## Wave 4: Question ノード（P1）

### 目的
知識ギャップを明示化し、AIが「何を調べるべきか」を構造的に把握できるようにする。

### 新スキーマ要素

**ノード:**
| ノード | プロパティ | ID戦略 |
|--------|-----------|--------|
| Question | question_id, content, question_type, priority, status, generated_at | SHA-256(question:content) |

**リレーション:**
| リレーション | From → To | プロパティ |
|-------------|-----------|-----------|
| ASKS_ABOUT | Question → Entity | — |
| MOTIVATED_BY | Question → Claim/Fact/Insight | — |
| ANSWERED_BY | Question → Fact/Claim/Source | answered_at |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — Question ノード + 3リレーション追加

2. **`src/pdf_pipeline/services/id_generator.py`** — `generate_question_id()`

3. **`src/pdf_pipeline/schemas/extraction.py`** — `ExtractedQuestion` モデル追加

4. **`src/pdf_pipeline/core/knowledge_extractor.py`** — 抽出プロンプトに `questions[]` 追加
   ```
   data_gap: このレポートに欠けている重要な情報
   contradiction: 一般的な認識と矛盾する主張
   prediction_test: 後日検証可能な定量的予測
   assumption_check: 検証が必要な前提条件
   ```

5. **`scripts/emit_graph_queue.py`**:
   - `_build_question_nodes()`: Question ノード + ASKS_ABOUT, MOTIVATED_BY リレーション生成
   - `_mapped_result()`: `questions` キー追加
   - `_empty_rels()`: `asks_about`, `motivated_by`, `answered_by` 追加

6. **`.claude/skills/save-to-graph/guide.md`** — Question MERGE + 3リレーション Cypher テンプレート

7. **テスト**: `TestBuildQuestionNodes`

### AI推論パス（実現例）
```cypher
-- ISATについて未解決のdata_gap
MATCH (q:Question {status: "open", question_type: "data_gap"})-[:ASKS_ABOUT]->(e:Entity {ticker: "ISAT"})
RETURN q.content, q.priority ORDER BY q.priority

-- 矛盾から生じたQuestion
MATCH (q:Question {question_type: "contradiction"})-[:MOTIVATED_BY]->(c:Claim)
RETURN q.content, c.content
```

---

## 非pdf-extraction マッパーへの影響

**変更不要。** `_mapped_result()` のキーワード引数にデフォルト `None` を追加するだけで、既存8マッパーは空配列を返す。save-to-graph は空配列をスキップ。

## スキーマ変更サマリー

| Wave | 新ノード | 新リレーション | 合計 |
|------|---------|--------------|------|
| 0 | — | — | バグ修正のみ |
| 1 | Stance, Author(実体化) | HOLDS_STANCE, ON_ENTITY, BASED_ON, SUPERSEDES | 2ノード + 4リレーション |
| 2 | — | CAUSES | 1リレーション |
| 3 | — | NEXT_PERIOD, TREND | 2リレーション |
| 4 | Question | ASKS_ABOUT, MOTIVATED_BY, ANSWERED_BY | 1ノード + 3リレーション |
| **合計** | **3ノード** | **10リレーション** | v2.0の10N/15R → v2.1の13N/25R |

## 検証方法

### 各Wave共通
```bash
make check-all                              # format + lint + typecheck + test
uv run pytest tests/scripts/test_emit_graph_queue.py -v  # graph-queue テスト
```

### Wave 1-4 追加検証
```bash
# 1. サンプルPDFで graph-queue 生成
uv run python scripts/emit_graph_queue.py --command pdf-extraction --input data/processed/HSBC_ISAT/

# 2. 出力JSONの新ノード/リレーション確認
cat .tmp/graph-queue/pdf-extraction/gq-*.json | python -m json.tool | grep -c "stance_id"

# 3. article-neo4j 起動 + 投入テスト
docker start article-neo4j
NEO4J_URI=bolt://localhost:7689 /save-to-graph --file .tmp/graph-queue/pdf-extraction/gq-*.json

# 4. 推論クエリで検証
cypher-shell -a bolt://localhost:7689 'MATCH (s:Stance)-[:SUPERSEDES]->(p:Stance) RETURN count(s)'
cypher-shell -a bolt://localhost:7689 'MATCH ()-[r:CAUSES]->() RETURN count(r)'
cypher-shell -a bolt://localhost:7689 'MATCH ()-[r:NEXT_PERIOD]->() RETURN count(r)'
cypher-shell -a bolt://localhost:7689 'MATCH (q:Question {status: "open"}) RETURN count(q)'
```

## 影響ファイル一覧

| ファイル | Wave | 変更内容 |
|---------|------|---------|
| `data/config/knowledge-graph-schema.yaml` | 0-4 | ノード/リレーション定義追加 |
| `src/pdf_pipeline/services/id_generator.py` | 1,4 | generate_stance_id, generate_author_id, generate_question_id |
| `src/pdf_pipeline/schemas/extraction.py` | 1,2,4 | ExtractedStance, ExtractedCausalLink, ExtractedQuestion |
| `src/pdf_pipeline/core/knowledge_extractor.py` | 1,2,4 | 抽出プロンプト拡張 |
| `scripts/emit_graph_queue.py` | 0-4 | バグ修正 + 新builder関数群 |
| `.claude/skills/save-to-graph/guide.md` | 0-4 | Cypher テンプレート追加 |
| `tests/scripts/test_emit_graph_queue.py` | 0-4 | TestMapPdfExtraction + 各Wave テスト |
