# KG v2.2 マイグレーション + research-neo4j Wave 1-4 統合実装計画

## Context

KG v2.1 Phase 1（Wave 0-4 コア実装）は commit `7c14ff1` で完了済み。Phase 2（research-neo4j 固有改修）のコードも commit `7e66218`, `4c36429` で実装済み。

**残タスク:**
- **article-neo4j** (port 7689): v2.2 スキーマの DDL 実行 + emit_graph_queue.py への `entity_key`/`topic_key` プロパティ追加
- **research-neo4j** (port 7688): バックフィルスクリプトの実行・検証 + E2E 統合検証

**Task 5 (`consensus_divergence` + `prediction_test`) は既に完了済み** — `extraction.py` L435-437、`knowledge_extractor.py` L116/136/138、`knowledge-graph-schema.yaml` L421 に実装確認済み。テスト実行のみで完了。

---

## 依存関係グラフ

```
Track A (article-neo4j)           Track B (research-neo4j)
  A1: 事前監査                      B0: 事前監査 + Metric確認
  A2: 制約・INDEX追加               B1: Wave 1 Stance backfill [#143]
  A3: レガシーノード Archived化       B2: Wave 3 Temporal chain [#144]
  A4: entity_key/topic_key backfill  B3: Task 5 テスト確認（コード変更なし）
  A5: emit_graph_queue.py 修正 ←──── 合流点
  A6: init cypher 更新
  A7: make check-all
                                    B4: E2E 統合検証 [#146]
```

Track A (A1-A4) と Track B (B0-B2) は**並列実行可能**（異なるDB）。
A5 のコード変更は Track B 完了を待たず実行可能。B4 は全ステップ完了後。

---

## Track A: article-neo4j v2.2 マイグレーション（タスク1）

### A1: 事前監査（2分）

```bash
docker start article-neo4j
# 現在の制約・INDEX確認
docker exec article-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" 'SHOW CONSTRAINTS'
docker exec article-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" 'SHOW INDEXES'
# ノード件数
docker exec article-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt ORDER BY cnt DESC'
```

### A2: Phase 1 — 制約・INDEX 同期（3分）

`bolt://localhost:7689` で実行:

```cypher
CREATE CONSTRAINT unique_entity_key IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;

-- topic_key は init cypher に既存の可能性あり → A1 で確認後に判断
CREATE CONSTRAINT unique_topic_key IF NOT EXISTS
FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;

CREATE INDEX idx_source_command_source IF NOT EXISTS
FOR (s:Source) ON (s.command_source);

-- domain INDEX は init cypher に既存の可能性あり → A1 で確認
CREATE INDEX idx_source_domain IF NOT EXISTS
FOR (s:Source) ON (s.domain);
```

検証:
```cypher
SHOW CONSTRAINTS YIELD name, labelsOrTypes, properties
WHERE labelsOrTypes = ['Entity'] OR labelsOrTypes = ['Topic'];
```

### A3: Phase 2 — レガシーノード Archived 化（3分）

```cypher
-- 件数確認
MATCH (n) WHERE any(l IN labels(n) WHERE l IN ['Discussion', 'Decision', 'ActionItem'])
RETURN labels(n) AS labels, count(n) AS cnt;

-- Archived ラベル付与
MATCH (n) WHERE any(l IN labels(n) WHERE l IN ['Discussion', 'Decision', 'ActionItem'])
SET n:Archived;

-- レガシーリレーション確認
MATCH ()-[r]->() WHERE type(r) IN ['RESULTED_IN', 'PRODUCED']
RETURN type(r), count(*) AS cnt;
```

### A4: Phase 3 — entity_key / topic_key バックフィル（5分）

```cypher
-- Entity に entity_key 設定（YAML定義: {name}::{entity_type}）
MATCH (e:Entity) WHERE e.entity_key IS NULL
SET e.entity_key = e.name + '::' + e.entity_type;

-- Topic に topic_key 設定（YAML定義: {name}::{category}）
MATCH (t:Topic) WHERE t.topic_key IS NULL
SET t.topic_key = t.name + '::' + coalesce(t.category, 'unknown');

-- 検証
MATCH (e:Entity) WHERE e.entity_key IS NULL RETURN count(e);  -- expect 0
MATCH (t:Topic) WHERE t.topic_key IS NULL RETURN count(t);    -- expect 0
```

### A5: emit_graph_queue.py 修正（10分）

**ファイル**: `scripts/emit_graph_queue.py`

**変更1**: `SCHEMA_VERSION` を `"2.1"` → `"2.2"` に更新（L113）

**変更2**: Entity dict に `entity_key` プロパティ追加（L1174-1180）
```python
# 現在
entities.append({
    "entity_id": eid,
    "name": name,
    "entity_type": entity_type,
    "ticker": entity.get("ticker"),
})

# 修正後
entities.append({
    "entity_id": eid,
    "name": name,
    "entity_type": entity_type,
    "ticker": entity.get("ticker"),
    "entity_key": f"{name}::{entity_type}",
})
```

**変更3**: Topic dict に `topic_key` プロパティ追加（複数箇所）

| 箇所 | 行 | category 値 |
|------|-----|-------------|
| asset-management マッパー | L1014-1021 | `"asset-management"` |
| reddit マッパー | L1073-1081 | `"reddit"` |
| wealth-management マッパー | L2467-2474 | `"wealth-management"` |
| topic-discovery マッパー | L2937-2943 | `"content_planning"` |
| PDF extraction マッパー | 要確認 | 各種 |

各 Topic dict に `"topic_key": f"{name}::{category}"` を追加。

**変更4**: save-to-graph guide の Entity/Topic MERGE Cypher に `entity_key`/`topic_key` SET 追加
- `.claude/skills/save-to-graph/guide.md`

### A6: init cypher 更新（5分）

**ファイル**: `docker/article-neo4j/init/01-constraints-indexes.cypher`

v2.1/v2.2 で追加されたノード（Stance, Question）の制約と、entity_key/command_source INDEX を追記:
```cypher
// v2.1 additions
CREATE CONSTRAINT stance_id IF NOT EXISTS FOR (st:Stance) REQUIRE st.stance_id IS UNIQUE;
CREATE CONSTRAINT question_id IF NOT EXISTS FOR (q:Question) REQUIRE q.question_id IS UNIQUE;

// v2.2 additions
CREATE CONSTRAINT unique_entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;
CREATE INDEX idx_source_command_source IF NOT EXISTS FOR (s:Source) ON (s.command_source);
```

### A7: 品質チェック（5分）

```bash
make check-all
uv run pytest tests/scripts/test_emit_graph_queue.py -v
```

**ロールバック手順（Track A）:**
- Phase 1: `DROP CONSTRAINT unique_entity_key IF EXISTS`
- Phase 2: `MATCH (n:Archived) REMOVE n:Archived`
- Phase 3: `MATCH (e:Entity) REMOVE e.entity_key; MATCH (t:Topic) REMOVE t.topic_key;`
- Code: `git checkout scripts/emit_graph_queue.py`

---

## Track B: research-neo4j Wave 1-4 + E2E（タスク3,4,5,6）

### B0: 事前監査 + Metric 確認（2分）

```bash
docker start research-neo4j

# ノード件数
docker exec research-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt ORDER BY cnt DESC'

# Metric + MEASURES 確認（Wave 3 の前提条件）
docker exec research-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH (m:Metric) RETURN count(m) AS metric_count'
docker exec research-neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" \
  'MATCH ()-[r:MEASURES]->() RETURN count(r) AS measures_count'
```

Metric ノードが 0 件の場合、先に `apply_metric_master.py` を実行:
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/apply_metric_master.py --dry-run
NEO4J_URI=bolt://localhost:7688 uv run python scripts/apply_metric_master.py
```

### B1: Wave 1 — Stance backfill [#143]（10分）

**B1a: dry-run**
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/backfill_stance_from_claims.py --dry-run
```

**B1b: 本番実行**
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/backfill_stance_from_claims.py
```

**B1c: 検証**
```cypher
MATCH (a:Author) RETURN count(a) AS author_count;
MATCH (st:Stance) RETURN count(st) AS stance_count;
MATCH (s1:Stance)-[:SUPERSEDES]->(s2:Stance) RETURN count(*) AS supersedes_count;
MATCH (s:Source)-[:AUTHORED_BY]->(a:Author) RETURN a.name, count(s) ORDER BY count(s) DESC;
MATCH (a:Author)-[:HOLDS_STANCE]->(st:Stance) RETURN a.name, count(st) ORDER BY count(st) DESC;
```

**B1d: 冪等性確認**（再実行して件数変化なし）
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/backfill_stance_from_claims.py
```

**ロールバック:**
```cypher
MATCH (st:Stance) DETACH DELETE st;
MATCH (a:Author) WHERE NOT exists((a)<-[:AUTHORED_BY]-()) DETACH DELETE a;
```

### B2: Wave 3 — Temporal chain backfill [#144]（10分）

**B2a: dry-run**
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/backfill_temporal_chain.py --dry-run
```

**B2b: 本番実行**
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/backfill_temporal_chain.py
```

**B2c: 検証**
```cypher
MATCH (fp1:FiscalPeriod)-[r:NEXT_PERIOD]->(fp2:FiscalPeriod)
RETURN fp1.period_label, fp2.period_label ORDER BY fp1.period_label;

MATCH ()-[r:TREND]->()
RETURN r.metric_id, r.direction, count(r) AS cnt, avg(r.change_pct) AS avg_change
ORDER BY cnt DESC;

-- MEASURES 未リンク DP が TREND に含まれていないこと
MATCH (d1:FinancialDataPoint)-[:TREND]->(d2:FinancialDataPoint)
WHERE NOT exists((d1)-[:MEASURES]->())
RETURN count(*) AS non_measures_trend;  -- expect 0
```

**B2d: 冪等性確認**
```bash
NEO4J_URI=bolt://localhost:7688 uv run python scripts/backfill_temporal_chain.py
```

**ロールバック:**
```cypher
MATCH ()-[r:NEXT_PERIOD]->() DELETE r;
MATCH ()-[r:TREND]->() DELETE r;
```

### B3: Task 5 テスト確認（コード変更なし）[#145]

**既に実装完了:**
- `extraction.py` L435-437: `prediction_test`, `consensus_divergence` 定義済み
- `knowledge_extractor.py` L116/136/138: プロンプト反映済み
- `knowledge-graph-schema.yaml` L421: enum 追加済み

```bash
uv run pytest tests/scripts/test_emit_graph_queue.py -v -k "question"
```

### B4: E2E 統合検証 [#146]（15分）

**B4a: graph-queue 生成テスト**
```bash
uv run python scripts/emit_graph_queue.py \
  --command pdf-extraction \
  --input data/processed/HSBC_ISAT/
```

**B4b: ノード・リレーション完全性**
```cypher
-- 全12ノードの件数
UNWIND ['Source','Author','Chunk','Fact','Claim','Entity',
        'FinancialDataPoint','FiscalPeriod','Topic','Insight',
        'Stance','Question'] AS label
CALL { WITH label MATCH (n) WHERE label IN labels(n) RETURN count(n) AS cnt }
RETURN label, cnt ORDER BY cnt DESC;

-- 主要リレーションの件数
UNWIND ['CONTAINS_CHUNK','EXTRACTED_FROM','STATES_FACT','MAKES_CLAIM',
        'RELATES_TO','ABOUT','AUTHORED_BY','TAGGED','FOR_PERIOD',
        'HAS_DATAPOINT','HOLDS_STANCE','ON_ENTITY','BASED_ON',
        'SUPERSEDES','CAUSES','NEXT_PERIOD','TREND','ASKS_ABOUT',
        'MOTIVATED_BY'] AS relType
CALL { WITH relType MATCH ()-[r]->() WHERE type(r) = relType RETURN count(r) AS cnt }
RETURN relType, cnt ORDER BY cnt DESC;
```

**B4c: 推論クエリ検証**
```cypher
-- 1. SUPERSEDES 連鎖
MATCH path = (s1:Stance)-[:SUPERSEDES*]->(s2:Stance)
RETURN length(path) AS chain_length, [n IN nodes(path) | n.rating] AS ratings LIMIT 5;

-- 2. コンセンサス分岐
MATCH (a:Author)-[:HOLDS_STANCE]->(st:Stance)-[:ON_ENTITY]->(e:Entity)
WITH e, collect({author: a.name, rating: st.rating, tp: st.target_price}) AS stances
WHERE size(stances) > 1
RETURN e.name, stances;

-- 3. CAUSES チェーン
MATCH (n1)-[r:CAUSES]->(n2)
RETURN labels(n1)[0], labels(n2)[0], count(*) ORDER BY count(*) DESC;

-- 4. TREND (metric_id 付き)
MATCH (d1:FinancialDataPoint)-[r:TREND]->(d2:FinancialDataPoint)
WHERE r.metric_id IS NOT NULL
RETURN r.metric_id, d1.value, d2.value, r.change_pct LIMIT 10;

-- 5. consensus_divergence
MATCH (q:Question {question_type: 'consensus_divergence'})-[:ASKS_ABOUT]->(e:Entity)
RETURN q.content, e.name;

-- 6. Source → Author → Stance → Entity フルパス
MATCH (s:Source)-[:AUTHORED_BY]->(a:Author)-[:HOLDS_STANCE]->(st:Stance)-[:ON_ENTITY]->(e:Entity)
RETURN a.name, e.name, st.rating, st.target_price, s.title LIMIT 10;
```

**B4d: 既存データ破壊なし確認**
```cypher
-- v2.0 ベースライン（Source/Claim/Entity 等）の件数が減少していないこと
-- B0 の監査結果と比較
```

---

## 変更対象ファイル一覧

| ファイル | 操作 | ステップ |
|---------|------|---------|
| `scripts/emit_graph_queue.py` | 修正 | A5: entity_key/topic_key追加, SCHEMA_VERSION bump |
| `docker/article-neo4j/init/01-constraints-indexes.cypher` | 修正 | A6: v2.1/v2.2制約追加 |
| `.claude/skills/save-to-graph/guide.md` | 修正 | A5: Entity/Topic MERGE Cypher更新 |
| `tests/scripts/test_emit_graph_queue.py` | 修正 | A7: entity_key/topic_keyのアサーション追加 |

**実行のみ（コード変更なし）:**
| スクリプト | ステップ |
|-----------|---------|
| `scripts/backfill_stance_from_claims.py` | B1 |
| `scripts/backfill_temporal_chain.py` | B2 |
| `scripts/apply_metric_master.py` | B0（必要時のみ） |

---

## 所要時間見積もり

| ステップ | 時間 | 並列化 |
|---------|------|--------|
| A1+B0: 事前監査 | 3分 | 並列 |
| A2: 制約追加 | 3分 | B1a と並列 |
| A3: Archived化 | 3分 | B1b と並列 |
| A4: backfill | 5分 | B1c と並列 |
| A5: コード修正 | 10分 | B2 と並列 |
| A6: init cypher | 5分 | — |
| A7: make check-all | 5分 | — |
| B1: Wave 1 実行+検証 | 10分 | Track A と並列 |
| B2: Wave 3 実行+検証 | 10分 | A5 と並列 |
| B3: Task 5 テスト | 2分 | — |
| B4: E2E 検証 | 15分 | 全ステップ完了後 |

**合計: 約50分**（並列実行時）
