# article-neo4j スキーマ v2.2 マイグレーション計画

## 背景

2026-03-17 の調査で article-neo4j (port 7689) に以下の課題を特定:

- v2 以降のノード (Author, FinancialDataPoint, FiscalPeriod, Insight, Stance, Question) が全て 0 件
- 431 Chunk が知識抽出に未使用 (EXTRACTED_FROM が 0)
- スキーマ外ノード (Discussion/Decision/ActionItem) が残存
- Claim にトピック提案用の非標準プロパティが混在
- entity_key / topic_key が YAML 未定義
- Source に command_source / domain が YAML 未定義

## v2.2 スキーマ変更内容

| 変更 | 対象 | 内容 |
|------|------|------|
| 追加 | Source.command_source | 投入元コマンド名 |
| 追加 | Source.domain | ドメイン名 |
| 追加 | Source.source_type | `blog` を enum に追加 |
| 追加 | Entity.entity_key | MERGE 用複合キー (UNIQUE) |
| 追加 | Topic.topic_key | MERGE 用複合キー (UNIQUE) |
| 拡張 | Topic.category | `content_planning`, `wealth-management`, `wealth` を追加 |

## マイグレーション手順

### Phase 1: 制約・インデックス同期 (即時)

```cypher
-- 新規 UNIQUE 制約
CREATE CONSTRAINT unique_entity_key IF NOT EXISTS
FOR (e:Entity) REQUIRE e.entity_key IS UNIQUE;

CREATE CONSTRAINT unique_topic_key IF NOT EXISTS
FOR (t:Topic) REQUIRE t.topic_key IS UNIQUE;

-- 新規インデックス
CREATE INDEX idx_source_command_source IF NOT EXISTS
FOR (s:Source) ON (s.command_source);

CREATE INDEX idx_source_domain IF NOT EXISTS
FOR (s:Source) ON (s.domain);
```

### Phase 2: レガシーノード整理 (今週中)

```cypher
-- スキーマ外ノードに Archived ラベルを付与
MATCH (n) WHERE any(l IN labels(n) WHERE l IN ['Discussion', 'Decision', 'ActionItem'])
SET n:Archived;

-- スキーマ外リレーション確認
MATCH ()-[r]->() WHERE type(r) IN ['RESULTED_IN', 'PRODUCED']
RETURN type(r), count(*) AS cnt;
```

### Phase 3: 既存データの entity_key / topic_key バックフィル (今週中)

```cypher
-- Entity に entity_key を設定
MATCH (e:Entity) WHERE e.entity_key IS NULL
SET e.entity_key = e.name + '::' + e.entity_type;

-- Topic に topic_key を設定
MATCH (t:Topic) WHERE t.topic_key IS NULL
SET t.topic_key = t.name + '::' + coalesce(t.category, 'unknown');
```

### Phase 4: PDF 抽出パイプライン実行 (来週以降)

- 既存 431 Chunk に対して LLM 抽出を実行
- Author, FinancialDataPoint, FiscalPeriod, Stance ノードを生成
- EXTRACTED_FROM, AUTHORED_BY リレーションを接続

## 優先度

| Phase | 優先度 | 所要時間 |
|-------|--------|---------|
| 1 | 高 | 5分 |
| 2 | 中 | 10分 |
| 3 | 中 | 5分 |
| 4 | 低 | 要見積もり |
