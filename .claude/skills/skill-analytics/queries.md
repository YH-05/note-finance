# skill-analytics クエリ集

research-neo4j (bolt://localhost:7688) 上の `Memory:SkillRun` ノードを分析するための 6 クエリ群。

各クエリは `cypher-shell` で実行する。パラメータ `$days` はデフォルト 30 日。

## SkillRun ノードスキーマ（参考）

```
(:Memory:SkillRun {
  skill_run_id,      // UNIQUE
  skill_name,        // INDEX
  session_id,
  status,            // INDEX: running | success | failure | partial | timeout
  start_at,          // INDEX: datetime
  end_at,            // datetime
  duration_ms,       // int
  command_source,    // INDEX
  input_summary,
  output_summary,
  error_message,
  error_type,
  feedback_score     // float 0.0-1.0
})

(:Memory:SkillRun)-[:INVOKED_SKILL]->(:Memory:SkillRun)
```

---

## 1. スキル実行頻度（過去 N 日）

スキルごとの実行回数と成功率を算出する。

```cypher
// パラメータ: $days (デフォルト 30)
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
WITH sr.skill_name AS skill_name,
     count(sr) AS total,
     sum(CASE WHEN sr.status = 'success' THEN 1 ELSE 0 END) AS success,
     sum(CASE WHEN sr.status = 'failure' THEN 1 ELSE 0 END) AS failure,
     sum(CASE WHEN sr.status = 'partial' THEN 1 ELSE 0 END) AS partial,
     sum(CASE WHEN sr.status = 'timeout' THEN 1 ELSE 0 END) AS timeout,
     sum(CASE WHEN sr.status = 'running' THEN 1 ELSE 0 END) AS running
RETURN skill_name,
       total,
       success,
       failure,
       partial,
       timeout,
       running,
       round(toFloat(success) / total * 100, 1) AS success_rate_pct
ORDER BY total DESC
```

### 出力フォーマット

| スキル名 | 実行回数 | 成功 | 失敗 | partial | timeout | running | 成功率 (%) |
|----------|---------|------|------|---------|---------|---------|-----------|
| save-to-graph | 45 | 40 | 3 | 1 | 1 | 0 | 88.9 |
| finance-news-workflow | 30 | 28 | 2 | 0 | 0 | 0 | 93.3 |

---

## 2. スキル別失敗率

失敗率が高いスキルをランキング表示する。最低実行回数フィルタで統計的に有意なもののみ表示。

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
WITH sr.skill_name AS skill_name,
     count(sr) AS total,
     sum(CASE WHEN sr.status IN ['failure', 'timeout'] THEN 1 ELSE 0 END) AS fail_count,
     collect(
       CASE WHEN sr.status IN ['failure', 'timeout']
            THEN sr.error_type
            ELSE null
       END
     ) AS error_types
WHERE total >= 3
WITH skill_name,
     total,
     fail_count,
     round(toFloat(fail_count) / total * 100, 1) AS fail_rate_pct,
     [et IN error_types WHERE et IS NOT NULL | et] AS filtered_error_types
RETURN skill_name,
       total,
       fail_count,
       fail_rate_pct,
       CASE WHEN size(filtered_error_types) > 0
            THEN head(filtered_error_types)
            ELSE 'N/A'
       END AS primary_error_type
ORDER BY fail_rate_pct DESC
LIMIT 10
```

### 出力フォーマット

| スキル名 | 総実行 | 失敗数 | 失敗率 (%) | 主なエラータイプ |
|----------|--------|--------|-----------|-----------------|
| pdf-to-knowledge | 10 | 5 | 50.0 | cypher_execution |
| save-to-graph | 45 | 4 | 8.9 | neo4j_connection |

---

## 3. 平均実行時間トレンド（週次バケット）

週単位で実行時間の平均・中央値・最大値を追跡する。

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
  AND sr.duration_ms IS NOT NULL
  AND sr.status IN ['success', 'partial']
WITH date(sr.start_at) AS run_date,
     sr.duration_ms AS duration_ms
WITH run_date.year AS year,
     run_date.week AS week,
     duration_ms
WITH year + '-W' + CASE WHEN week < 10 THEN '0' + toString(week)
                        ELSE toString(week) END AS week_label,
     collect(duration_ms) AS durations,
     count(*) AS run_count
WITH week_label,
     run_count,
     // 平均
     reduce(s = 0, d IN durations | s + d) / size(durations) AS avg_ms,
     // 最大
     reduce(mx = 0, d IN durations | CASE WHEN d > mx THEN d ELSE mx END) AS max_ms,
     // 中央値: ソートして中央値を取得
     apoc.coll.sort(durations) AS sorted_durations
WITH week_label,
     run_count,
     avg_ms,
     max_ms,
     sorted_durations[size(sorted_durations) / 2] AS median_ms
RETURN week_label,
       avg_ms,
       median_ms,
       max_ms,
       run_count
ORDER BY week_label
```

> **Note**: `apoc.coll.sort` が利用できない環境では、中央値の計算を省略し `avg_ms` と `max_ms` のみ出力する。その場合は以下の APOC 不要版を使用する。

### APOC 不要版（中央値省略）

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
  AND sr.duration_ms IS NOT NULL
  AND sr.status IN ['success', 'partial']
WITH date(sr.start_at) AS run_date,
     sr.duration_ms AS duration_ms
WITH run_date.year AS year,
     run_date.week AS week,
     duration_ms
WITH year + '-W' + CASE WHEN week < 10 THEN '0' + toString(week)
                        ELSE toString(week) END AS week_label,
     collect(duration_ms) AS durations,
     count(*) AS run_count
RETURN week_label,
       run_count,
       reduce(s = 0, d IN durations | s + d) / size(durations) AS avg_ms,
       reduce(mx = 0, d IN durations | CASE WHEN d > mx THEN d ELSE mx END) AS max_ms
ORDER BY week_label
```

### 出力フォーマット

| 週 | 平均実行時間 (ms) | 中央値 (ms) | 最大値 (ms) | 実行数 |
|----|------------------|-------------|-------------|--------|
| 2026-W11 | 3200 | 2800 | 15000 | 12 |
| 2026-W12 | 2900 | 2500 | 12000 | 15 |

---

## 4. エラータイプ別発生数

`error_type` ごとの件数と代表的なエラーメッセージを集約する。

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
  AND sr.status IN ['failure', 'timeout']
  AND sr.error_type IS NOT NULL
WITH sr.error_type AS error_type,
     count(sr) AS count,
     collect(sr.error_message)[0] AS sample_error_message,
     collect(DISTINCT sr.skill_name) AS affected_skills
RETURN error_type,
       count,
       size(affected_skills) AS affected_skill_count,
       affected_skills,
       left(coalesce(sample_error_message, 'N/A'), 100) AS sample_message
ORDER BY count DESC
```

### 出力フォーマット

| エラータイプ | 件数 | 影響スキル数 | 影響スキル | 代表エラーメッセージ |
|-------------|------|-------------|-----------|---------------------|
| neo4j_connection | 8 | 3 | [save-to-graph, ...] | Connection refused to bolt://... |
| cypher_execution | 5 | 2 | [pdf-to-knowledge, ...] | SyntaxError: Invalid input... |

### error_type 分類一覧

| error_type | 説明 |
|------------|------|
| neo4j_connection | Neo4j 接続失敗 |
| queue_not_found | graph-queue ディレクトリ未検出 |
| schema_validation | JSON スキーマ検証エラー |
| cypher_execution | Cypher 実行エラー |
| file_operation | ファイル削除/移動エラー |
| api_error | 外部 API エラー |
| parse_error | データパースエラー |
| timeout | タイムアウト |

---

## 5. オーケストレータ→子カスケード失敗パターン

`INVOKED_SKILL` リレーションを辿り、親スキルの失敗が子スキルにどう伝播しているかを検出する。

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (parent:SkillRun)-[:INVOKED_SKILL]->(child:SkillRun)
WHERE parent.start_at >= cutoff
WITH parent.skill_name AS parent_skill,
     child.skill_name AS child_skill,
     parent.status AS parent_status,
     child.status AS child_status,
     count(*) AS occurrence
RETURN parent_skill,
       child_skill,
       parent_status,
       child_status,
       occurrence
ORDER BY occurrence DESC
```

### カスケード失敗のみ抽出

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (parent:SkillRun)-[:INVOKED_SKILL]->(child:SkillRun)
WHERE parent.start_at >= cutoff
  AND (parent.status IN ['failure', 'timeout']
       OR child.status IN ['failure', 'timeout'])
WITH parent.skill_name AS parent_skill,
     child.skill_name AS child_skill,
     parent.status AS parent_status,
     child.status AS child_status,
     count(*) AS occurrence
RETURN parent_skill,
       child_skill,
       parent_status,
       child_status,
       occurrence
ORDER BY occurrence DESC
LIMIT 10
```

### 出力フォーマット

| 親スキル | 子スキル | 親ステータス | 子ステータス | 発生回数 |
|----------|---------|-------------|-------------|---------|
| finance-news-workflow | save-to-graph | failure | failure | 3 |
| pdf-to-knowledge | save-to-graph | success | failure | 2 |

### カスケード深度分析（3 階層以上）

```cypher
WITH datetime() - duration({days: 30}) AS cutoff
MATCH path = (root:SkillRun)-[:INVOKED_SKILL*1..3]->(leaf:SkillRun)
WHERE root.start_at >= cutoff
  AND NOT EXISTS { (any:SkillRun)-[:INVOKED_SKILL]->(root) }
  AND leaf.status IN ['failure', 'timeout']
RETURN [n IN nodes(path) | n.skill_name] AS cascade_chain,
       [n IN nodes(path) | n.status] AS status_chain,
       length(path) AS depth
ORDER BY depth DESC, root.start_at DESC
LIMIT 10
```

---

## 6. KG ノード生産性

スキル実行が生産した KG ノード数を推定する。`command_source` をキーに、スキル実行前後の KG ノード数の差分から生産性を算出する。

### 方法 A: command_source ベースの Source ノード計数

```cypher
// スキルごとの成功実行数と、command_source 経由で投入された Source ノード数を集計
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
  AND sr.status = 'success'
  AND sr.command_source IS NOT NULL
WITH sr.skill_name AS skill_name,
     sr.command_source AS command_source,
     count(sr) AS run_count
// command_source と一致する Source ノードを集計
OPTIONAL MATCH (s:Source {command_source: command_source})
WHERE s.collected_at >= datetime() - duration({days: 30})
WITH skill_name,
     run_count,
     count(s) AS source_count
RETURN skill_name,
       run_count,
       source_count,
       CASE WHEN run_count > 0
            THEN round(toFloat(source_count) / run_count, 1)
            ELSE 0
       END AS sources_per_run
ORDER BY source_count DESC
```

### 方法 B: 全 KG ノードタイプの生産性集計

```cypher
// 全 KG ノードタイプを command_source ベースで集計
WITH datetime() - duration({days: 30}) AS cutoff
MATCH (sr:SkillRun)
WHERE sr.start_at >= cutoff
  AND sr.status = 'success'
  AND sr.command_source IS NOT NULL
WITH sr.skill_name AS skill_name,
     sr.command_source AS cmd_src,
     count(sr) AS run_count

// Source ノード
OPTIONAL MATCH (src:Source {command_source: cmd_src})
WHERE src.collected_at >= cutoff
WITH skill_name, cmd_src, run_count, count(src) AS source_count

// Entity ノード（Source 経由）
OPTIONAL MATCH (src2:Source {command_source: cmd_src})<-[:ABOUT]-(:Claim)-[:ABOUT]->(e:Entity)
WITH skill_name, cmd_src, run_count, source_count,
     count(DISTINCT e) AS entity_count

// Claim ノード（Source 経由）
OPTIONAL MATCH (src3:Source {command_source: cmd_src})-[:MAKES_CLAIM]->(c:Claim)
WITH skill_name, cmd_src, run_count, source_count, entity_count,
     count(DISTINCT c) AS claim_count

// Fact ノード（Source 経由）
OPTIONAL MATCH (src4:Source {command_source: cmd_src})-[:STATES_FACT]->(f:Fact)
WITH skill_name, run_count, source_count, entity_count, claim_count,
     count(DISTINCT f) AS fact_count

WITH skill_name,
     run_count,
     source_count,
     entity_count,
     claim_count,
     fact_count,
     source_count + entity_count + claim_count + fact_count AS total_nodes
RETURN skill_name,
       run_count,
       source_count,
       entity_count,
       claim_count,
       fact_count,
       total_nodes,
       CASE WHEN run_count > 0
            THEN round(toFloat(total_nodes) / run_count, 1)
            ELSE 0
       END AS nodes_per_run
ORDER BY total_nodes DESC
```

### 出力フォーマット

| スキル名 | 実行回数 | Source | Entity | Claim | Fact | 合計ノード | ノード/実行 |
|----------|---------|--------|--------|-------|------|-----------|------------|
| finance-news-workflow | 30 | 150 | 45 | 120 | 0 | 315 | 10.5 |
| pdf-to-knowledge | 12 | 12 | 60 | 36 | 80 | 188 | 15.7 |

---

## 補助クエリ

### A. データ存在確認

分析クエリ実行前に、SkillRun データの存在と期間を確認する。

```cypher
MATCH (sr:SkillRun)
WITH count(sr) AS total,
     min(sr.start_at) AS earliest,
     max(sr.start_at) AS latest
RETURN total,
       toString(earliest) AS earliest_run,
       toString(latest) AS latest_run
```

### B. スキル名一覧

登録されている全スキル名を取得する。

```cypher
MATCH (sr:SkillRun)
RETURN DISTINCT sr.skill_name AS skill_name,
       count(sr) AS run_count
ORDER BY run_count DESC
```

### C. 直近の失敗ログ

直近の失敗を詳細に確認する。

```cypher
MATCH (sr:SkillRun)
WHERE sr.status IN ['failure', 'timeout']
RETURN sr.skill_run_id AS id,
       sr.skill_name AS skill,
       sr.status AS status,
       toString(sr.start_at) AS started,
       sr.error_type AS error_type,
       left(coalesce(sr.error_message, ''), 200) AS error_message
ORDER BY sr.start_at DESC
LIMIT 20
```

---

## cypher-shell 実行例

```bash
# 環境変数設定
export NEO4J_URI="bolt://localhost:7688"
export NEO4J_USER="neo4j"
# NEO4J_PASSWORD は事前に設定済みであること

# クエリ 1: スキル実行頻度
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  --format plain \
  "WITH datetime() - duration({days: 30}) AS cutoff
   MATCH (sr:SkillRun)
   WHERE sr.start_at >= cutoff
   RETURN sr.skill_name AS skill, count(sr) AS runs
   ORDER BY runs DESC"

# 特定クエリをファイルから実行
cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" -a "$NEO4J_URI" \
  --format plain < query.cypher
```
