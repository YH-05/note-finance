# KG v2.1: AI推論最適化スキーマ設計 (research-neo4j)

**日付**: 2026-03-17
**対象DB**: research-neo4j (bolt://localhost:7688, Browser: http://localhost:7475)
**ベースプラン**: `docs/plan/2026-03-17_kg-v2.1-reasoning-schema.md` (article-neo4j 向け)

## Context

article-neo4j 向け KG v2.1 プランをベースに、research-neo4j の特性に最適化する。
research-neo4j はセルサイドレポートのPDF変換結果が中心で、Claim 732件・FinancialDataPoint 166件・Metric 35件・FiscalPeriod 16件というリッチな既存データを持つ。
**Metric ノード + MEASURES リレーション**が既に存在する点が article-neo4j との最大の差異であり、Wave 3 の TREND 設計に大きく影響する。

## article-neo4j プランとの差分サマリー

| 項目 | article-neo4j | research-neo4j | 理由 |
|------|-------------|---------------|------|
| Author 生成 | LLM 抽出 | Source.publisher 実体化 | セルサイドレポート中心、publisher が確実 |
| Stance 遡及 | なし | `backfill_stance_from_claims.py` | 既存 Claim 732件を活用 |
| TREND グルーピング | metric_name 文字列 | Metric.metric_id (`metric_master.json`) | 表記揺れ回避、35 Metric の正規化活用 |
| TREND 対象外 | 全 DP 対象 | MEASURES 未リンク DP はスキップ | 未正規化 metric_name の比較は誤解を招く |
| 遡及バッチ | 不要 | `backfill_temporal_chain.py` | 既存 166 DP / 16 FP を活用 |
| AUTHORED_BY | あり | あり + 既存 895 Source との紐付け | publisher フィールド活用 |
| Question タイプ | 4種 | 4+2種 | consensus_divergence, prediction_test 追加 |
| TREND プロパティ | change_pct, direction | + **metric_id** | Metric 経由クエリ最適化 |

## Wave 構成

```
Wave 0: Bug Fix + テスト基盤       ← 全Waveの前提（article-neo4j と共有）
Wave 1: Stance + SUPERSEDES        ← P0（research-neo4j 固有: publisher → Author、Claim → Stance 遡及）
Wave 2: CAUSES エッジ              ← P0（article-neo4j と同一設計）
Wave 3: Temporal Chain             ← P1（research-neo4j 固有: Metric.metric_id でグルーピング）
Wave 4: Question ノード            ← P1（+ consensus_divergence, prediction_test タイプ）
```

---

## Wave 0: バグ修正 + テスト基盤

### 実装ステップ

1. **`scripts/emit_graph_queue.py` L891-899 修正** — `claims.append()` に4プロパティ追加:
   ```python
   "magnitude": claim.get("magnitude"),
   "target_price": claim.get("target_price"),
   "rating": claim.get("rating"),
   "time_horizon": claim.get("time_horizon"),
   ```

2. **`.claude/skills/save-to-graph/guide.md` Claim MERGE Cypher 更新** — `target_price`, `rating`, `time_horizon` を SET に追加

3. **`tests/scripts/test_emit_graph_queue.py` に `TestMapPdfExtraction` 追加** (~100行)
   - ヘルパー `_pdf_extraction_data()` で全プロパティ含むサンプル生成
   - `test_正常系_Claimのtarget_priceとratingが保持される`
   - `test_正常系_FiscalPeriodが正しく派生される`
   - `test_エッジケース_空チャンクでも正常動作`

---

## Wave 1: Stance + SUPERSEDES + Author実体化 (P0)

### research-neo4j 固有の設計判断

1. **Author は Source.publisher から実体化** — LLM 抽出ではなく、Source ノード(895件)の `publisher` フィールド("HSBC", "Citi" 等)から `author_type = "sell_side"` で Author を生成
2. **既存 Claim からの遡及 Stance 生成** — `backfill_stance_from_claims.py` で rating/target_price 付き Claim → Stance 変換
3. **Stance ID** — `UUID5(stance:author_name:entity_name:as_of_date)` で決定論的

### 新スキーマ要素

| ノード | プロパティ | ID戦略 |
|--------|-----------|--------|
| Stance | stance_id, rating, sentiment, target_price, target_price_currency, as_of_date, created_at | UUID5(stance:author:entity:date) |
| Author | author_id, name, author_type, organization | UUID5(author:name:type) |

| リレーション | From → To |
|-------------|-----------|
| HOLDS_STANCE | Author → Stance |
| ON_ENTITY | Stance → Entity |
| BASED_ON | Stance → Claim |
| SUPERSEDES | Stance → Stance |
| AUTHORED_BY | Source → Author |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — Stance ノード + 5リレーション追加
2. **`src/pdf_pipeline/services/id_generator.py`** — `generate_stance_id()`, `generate_author_id()` 追加
3. **`src/pdf_pipeline/schemas/extraction.py`** — `ExtractedStance` モデル追加、`ChunkExtractionResult.stances` フィールド追加
4. **`src/pdf_pipeline/core/knowledge_extractor.py`** — `_EXTRACTION_PROMPT` に `stances[]` 追加（author_name は除外、map_pdf_extraction 内で Source.publisher から自動設定）
5. **`scripts/emit_graph_queue.py`**:
   - `_build_author_node(publisher)` — Source.publisher → Author ノード dict
   - `_build_stance_nodes(chunk, source_id, publisher, entity_name_to_id)` — Stance + リレーション生成
   - `_build_supersedes_chain(all_stances)` — 同一(author, entity)で日付順にSUPERSEDES連鎖
   - `_mapped_result()` に `stances`, `authors` キーワード引数追加
   - `_empty_rels()` に `holds_stance`, `on_entity`, `based_on`, `supersedes`, `authored_by` 追加
   - `_process_chunk()` に `_build_stance_nodes()` 呼び出し追加
   - `map_pdf_extraction()` に後処理追加（Author構築、SUPERSEDES連鎖、AUTHORED_BY）
6. **`scripts/backfill_stance_from_claims.py` (新規)** — 既存 Claim → Stance 遡及バッチ（research-neo4j 固有）
7. **`.claude/skills/save-to-graph/guide.md`** — Author/Stance MERGE + 5リレーション Cypher + 制約/インデックス追加
8. **テスト** — `TestBuildStanceNodes`, `TestBuildSupersedesChain`, `TestGenerateStanceId`, `TestGenerateAuthorId`

### AI推論パス

```cypher
-- ISATに対するHSBCの見解変遷
MATCH (a:Author {name: "HSBC"})-[:HOLDS_STANCE]->(st:Stance)-[:ON_ENTITY]->(e:Entity {ticker: "ISAT IJ"})
OPTIONAL MATCH (st)-[:SUPERSEDES]->(prev:Stance)
RETURN st.rating, st.target_price, st.as_of_date, prev.rating AS prev_rating
ORDER BY st.as_of_date

-- コンセンサスの分岐: 同一Entityに対する最新Stanceの集計
MATCH (st:Stance)-[:ON_ENTITY]->(e:Entity {ticker: "ISAT IJ"})
WHERE NOT (st)<-[:SUPERSEDES]-()
MATCH (a:Author)-[:HOLDS_STANCE]->(st)
RETURN a.name, st.rating, st.target_price, st.sentiment
```

---

## Wave 2: CAUSES エッジ (P0)

article-neo4j プランと同一設計。

### 新リレーション

| リレーション | From → To | プロパティ |
|-------------|-----------|-----------|
| CAUSES | Fact/Claim/FinancialDataPoint → Fact/Claim/FinancialDataPoint | mechanism, confidence (stated/inferred/speculative), source_id |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — CAUSES リレーション追加
2. **`src/pdf_pipeline/schemas/extraction.py`** — `ExtractedCausalLink` モデル追加、`ChunkExtractionResult.causal_links` フィールド追加
3. **`src/pdf_pipeline/core/knowledge_extractor.py`** — `_EXTRACTION_PROMPT` に `causal_links[]` 追加
4. **`scripts/emit_graph_queue.py`** — `_build_causal_links(chunk, content_to_id_map)` 追加。`_empty_rels()` に `causes` 追加。graph-queue 要素に `from_label`, `to_label` を含める（Neo4j CE のラベル指定用）
5. **`.claude/skills/save-to-graph/guide.md`** — CAUSES MERGE Cypher（6パターンのラベル別分岐）
6. **テスト** — `TestBuildCausalLinks`

### AI推論パス

```cypher
-- ISATのTP引き上げの根拠チェーン
MATCH chain = (effect:Claim {claim_type: "recommendation"})<-[:CAUSES*1..5]-(root)
WHERE (effect)-[:ABOUT]->(:Entity {ticker: "ISAT IJ"})
RETURN [n IN nodes(chain) | coalesce(n.content, n.metric_name)] AS causal_chain
```

---

## Wave 3: Temporal Chain (P1)

### research-neo4j 固有の設計判断

1. **TREND は Metric.metric_id でグルーピング** — `metric_master.json` の alias_index を `emit_graph_queue.py` に組み込み、`(entity_id, metric_id, period_sort_key)` でグルーピング。表記揺れ（"Revenue" vs "Total Revenue"）を回避
2. **MEASURES 未リンク DP は TREND 対象外** — 未正規化の metric_name 同士を比較しても誤解を招く。`apply_metric_master.py` 再実行でカバレッジ改善が正道
3. **TREND に metric_id プロパティ付与** — Metric ノード経由せずに同一指標チェーンを辿れる（クエリ効率化）
4. **NEXT_PERIOD は Entity-scoped** — period_id が `{ticker}_{period_label}` 形式のため、同一 ticker 内でのみチェーン構築

### 新リレーション

| リレーション | From → To | プロパティ |
|-------------|-----------|-----------|
| NEXT_PERIOD | FiscalPeriod → FiscalPeriod | gap_months |
| TREND | FinancialDataPoint → FinancialDataPoint | change_pct, direction (up/down/flat), metric_id |

### 実装ステップ

1. **`data/config/knowledge-graph-schema.yaml`** — NEXT_PERIOD, TREND リレーション追加
2. **`scripts/emit_graph_queue.py`** に新関数追加:
   - `_load_metric_alias_index()` — `data/config/metric_master.json` からエイリアス→metric_id ルックアップ構築（`apply_metric_master.py` のロジック流用）
   - `_period_sort_key(label)` — `FY2025→(2025,0)`, `3Q25→(2025,3)`, `1H26→(2026,1)`
   - `_build_next_period_chain(fiscal_periods)` — 同一 ticker/period_type でソート → NEXT_PERIOD 生成
   - `_build_trend_edges(datapoints, dp_to_metric_id, dp_to_entity_id)` — Metric.metric_id グルーピング → 変化率計算 → TREND 生成
   - `map_pdf_extraction()` に後処理追加（`_build_next_period_chain`, `_build_trend_edges`）
   - `_empty_rels()` に `next_period`, `trend` 追加
3. **`scripts/backfill_temporal_chain.py` (新規)** — 既存 166 DP / 16 FP から NEXT_PERIOD + TREND 遡及生成（research-neo4j 固有）
4. **`.claude/skills/save-to-graph/guide.md`** — NEXT_PERIOD, TREND Cypher テンプレート
5. **テスト** — `TestPeriodSortKey`, `TestBuildNextPeriodChain`, `TestBuildTrendEdges`, `TestLoadMetricAliasIndex`

### TREND 計算ロジック

```python
change_pct = (current.value - prev.value) / abs(prev.value) * 100
direction = "up" if change_pct > 1 else ("down" if change_pct < -1 else "flat")
```

### AI推論パス

```cypher
-- ISATのRevenue推移（Metric正規化名で統一）
MATCH (met:Metric {canonical_name: "revenue"})<-[:MEASURES]-(dp:FinancialDataPoint)
      -[:RELATES_TO]->(e:Entity {ticker: "ISAT IJ"})
MATCH chain = (dp)-[:TREND*0..8]->(latest)
RETURN [n IN nodes(chain) | {value: n.value}] AS trend_data

-- ISAT vs TLKM の同一指標比較
MATCH (met:Metric {canonical_name: "ebitda_margin"})<-[:MEASURES]-(dp1)-[:RELATES_TO]->(e1:Entity {ticker: "ISAT IJ"})
MATCH (met)<-[:MEASURES]-(dp2)-[:RELATES_TO]->(e2:Entity {ticker: "TLKM IJ"})
MATCH (dp1)-[:FOR_PERIOD]->(fp:FiscalPeriod)<-[:FOR_PERIOD]-(dp2)
RETURN fp.period_label, dp1.value AS isat, dp2.value AS tlkm

-- 3期連続増加している指標
MATCH (d1)-[:TREND {direction:"up"}]->(d2)-[:TREND {direction:"up"}]->(d3)-[:TREND {direction:"up"}]->(d4)
MATCH (d1)-[:MEASURES]->(met:Metric), (d1)-[:RELATES_TO]->(e:Entity)
RETURN met.display_name, e.ticker, d4.value AS latest
```

---

## Wave 4: Question ノード (P1)

article-neo4j プランと基本同一 + research-neo4j 固有 question_type 2種追加。

### 新ノード

| ノード | プロパティ |
|--------|-----------|
| Question | question_id, content, question_type, priority, status, generated_at |

**question_type** (6種):
- `data_gap` / `contradiction` / `prediction_test` / `assumption_check` — article-neo4j と共通
- `consensus_divergence` — 複数アナリスト間のレーティング乖離（research-neo4j 固有）
- `prediction_test` — 後日検証可能な定量的予測（TP到達、EPS予想）

### 新リレーション

| リレーション | From → To |
|-------------|-----------|
| ASKS_ABOUT | Question → Entity |
| MOTIVATED_BY | Question → Claim/Fact/Insight |
| ANSWERED_BY | Question → Fact/Claim/Source |

### 実装ステップ

1. `data/config/knowledge-graph-schema.yaml` — Question + 3リレーション追加
2. `src/pdf_pipeline/services/id_generator.py` — `generate_question_id()` 追加
3. `src/pdf_pipeline/schemas/extraction.py` — `ExtractedQuestion` モデル追加
4. `src/pdf_pipeline/core/knowledge_extractor.py` — `_EXTRACTION_PROMPT` に `questions[]` 追加
5. `scripts/emit_graph_queue.py` — `_build_question_nodes()` + リレーション追加
6. `.claude/skills/save-to-graph/guide.md` — Question Cypher テンプレート
7. テスト — `TestBuildQuestionNodes`

---

## スキーマ変更サマリー

| Wave | 新ノード | 新リレーション | 合計 |
|------|---------|--------------|------|
| 0 | -- | -- | バグ修正のみ |
| 1 | Stance, Author(実体化) | HOLDS_STANCE, ON_ENTITY, BASED_ON, SUPERSEDES, AUTHORED_BY | 2N + 5R |
| 2 | -- | CAUSES | 1R |
| 3 | -- | NEXT_PERIOD, TREND | 2R |
| 4 | Question | ASKS_ABOUT, MOTIVATED_BY, ANSWERED_BY | 1N + 3R |
| **合計** | **3ノード** | **11リレーション** | v2.0(10N/15R) → v2.1(13N/26R) |

## 影響ファイル一覧

| ファイル | Wave | 変更内容 |
|---------|------|---------|
| `data/config/knowledge-graph-schema.yaml` | 0-4 | ノード/リレーション定義追加 |
| `src/pdf_pipeline/services/id_generator.py` | 1,4 | generate_stance_id, generate_author_id, generate_question_id |
| `src/pdf_pipeline/schemas/extraction.py` | 1,2,4 | ExtractedStance, ExtractedCausalLink, ExtractedQuestion |
| `src/pdf_pipeline/core/knowledge_extractor.py` | 1,2,4 | _EXTRACTION_PROMPT 拡張 |
| `scripts/emit_graph_queue.py` | 0-4 | バグ修正 + 新builder関数群 + _load_metric_alias_index |
| `.claude/skills/save-to-graph/guide.md` | 0-4 | Cypher テンプレート追加 |
| `tests/scripts/test_emit_graph_queue.py` | 0-4 | TestMapPdfExtraction + 各Wave テスト |
| `scripts/backfill_stance_from_claims.py` (新規) | 1 | 既存Claim → Stance遡及生成 |
| `scripts/backfill_temporal_chain.py` (新規) | 3 | 既存DP/FP → NEXT_PERIOD + TREND遡及生成 |
| `data/config/metric_master.json` | 3 | 参照のみ（変更なし） |

## 検証方法

```bash
# 各Wave共通
make check-all
uv run pytest tests/scripts/test_emit_graph_queue.py -v

# graph-queue 生成テスト
uv run python scripts/emit_graph_queue.py --command pdf-extraction --input data/processed/HSBC_ISAT/

# research-neo4j 投入テスト (port 7688)
docker start research-neo4j
NEO4J_URI=bolt://localhost:7688 /save-to-graph --file .tmp/graph-queue/pdf-extraction/gq-*.json

# 推論クエリ検証
cypher-shell -a bolt://localhost:7688 -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH (s:Stance)-[:SUPERSEDES]->(p:Stance) RETURN count(s)'
cypher-shell -a bolt://localhost:7688 -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH ()-[r:CAUSES]->() RETURN count(r)'
cypher-shell -a bolt://localhost:7688 -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH ()-[r:TREND]->() RETURN count(r), avg(r.change_pct)'

# 遡及バッチ検証
uv run python scripts/backfill_stance_from_claims.py --dry-run
uv run python scripts/backfill_temporal_chain.py --dry-run
```
