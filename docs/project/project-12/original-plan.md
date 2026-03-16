# Neo4j スキーマ整合性修正プラン — PascalCase統一

## Context

Neo4jデータベースに49個のノードラベルが存在し、3つの異なるデータソースが同一DBに混在している：

| 名前空間 | ラベル例 | 命名規則 | 状態 |
|---------|---------|---------|------|
| KG v2（10ノード） | Source, Claim, Entity | PascalCase | 問題なし |
| Conversation（3ノード） | ConversationSession, Project | PascalCase | 問題なし |
| Memory（16サブラベル） | Memory + decision, project, theme... | snake_case | **要修正** |
| Legacy（26ノード） | Decision(56個), Article, Person... | 混在 | **要クリーンアップ** |

### 根本原因

`mcp-neo4j-memory` OSSパッケージ（line 187: `SET e:\`{entity.type}\``）が `entity.type` の値をそのままラベルとして設定。上流OSSのため直接修正不可だが、**呼び出し側でPascalCaseを渡す**ことで統一可能。

### Memoryサブラベルの現状（16種）

```
decision(2), project(2), content_theme(5), theme(5),
implementation(3), phase(2), strategy(2), case_study(1),
architecture(1), schema(1), status(1), business_model(1),
workflow(1), research(1), todo(1), Discussion(1)※既にPascalCase
```

### 関連ファイル

| ファイル | 役割 |
|---------|------|
| `data/config/knowledge-graph-schema.yaml` | KG v2スキーマSSoT（10ノード・15リレーション） |
| `data/config/neo4j-pdf-constraints.cypher` | UNIQUE制約10個 + インデックス13個 |
| `.claude/skills/save-to-graph/guide.md` | KGデータ投入のCypherテンプレート |
| `scripts/emit_graph_queue.py` | graph-queue JSON生成（v2.0） |
| `scripts/save_conversations_to_neo4j.py` | 会話履歴保存（ConversationSession等） |
| `.claude/skills/project-discuss/SKILL.md` | Memory create_entities呼び出し例（既にPascalCase） |
| `.mcp.json` → `memory` | mcp-neo4j-memory サーバー設定 |

---

## Phase 1: 監査スナップショット

**目的**: 修正前のベースライン記録。結果を `data/processed/neo4j_audit_2026-03-15.json` に保存。

```cypher
-- 1a. 全ラベル×ノード数
MATCH (n) UNWIND labels(n) AS label
RETURN label, count(*) AS count ORDER BY count DESC;

-- 1b. Memoryサブラベル詳細
MATCH (m:Memory) WITH labels(m) AS allLabels, m
UNWIND allLabels AS lbl
WITH lbl, count(*) AS cnt WHERE lbl <> 'Memory'
RETURN lbl AS sub_label, cnt ORDER BY cnt DESC;

-- 1c. レガシーノード一覧（KG v2/Memory/Conversation以外）
MATCH (n)
WHERE NONE(l IN labels(n) WHERE l IN [
  'Source','Author','Chunk','Fact','Claim','Entity',
  'FinancialDataPoint','FiscalPeriod','Topic','Insight',
  'ConversationSession','ConversationTopic','Project','Memory'
])
RETURN labels(n) AS labels, count(*) AS cnt ORDER BY cnt DESC;

-- 1d. Memory/KGクロスコンタミネーション確認
MATCH (n)
WHERE 'Memory' IN labels(n)
AND ANY(l IN labels(n) WHERE l IN [
  'Source','Author','Chunk','Fact','Claim','Entity',
  'FinancialDataPoint','FiscalPeriod','Topic','Insight'
])
RETURN count(n) AS cross_contaminated;
```

---

## Phase 2: Memoryサブラベルのマイグレーション

既存Memoryノードの小文字ラベル → PascalCaseに変換。`m.type` プロパティも同時更新。

### マッピング表

| 旧ラベル (snake_case) | 新ラベル (PascalCase) | ノード数 |
|-----------------------|----------------------|---------|
| decision | Decision | 2 |
| project | Project | 2 |
| content_theme | ContentTheme | 5 |
| theme | Theme | 5 |
| implementation | Implementation | 3 |
| phase | Phase | 2 |
| strategy | Strategy | 2 |
| case_study | CaseStudy | 1 |
| architecture | Architecture | 1 |
| schema | Schema | 1 |
| status | Status | 1 |
| business_model | BusinessModel | 1 |
| workflow | Workflow | 1 |
| research | Research | 1 |
| todo | Todo | 1 |
| Discussion | Discussion | 1 (変更不要) |

### マイグレーションCypher

```cypher
// パターン: 旧ラベル削除 → 新ラベル追加 → typeプロパティ更新
MATCH (m:Memory) WHERE m.type = 'decision'
REMOVE m:decision SET m:Decision, m.type = 'Decision';

MATCH (m:Memory) WHERE m.type = 'project'
REMOVE m:project SET m:Project, m.type = 'Project';

MATCH (m:Memory) WHERE m.type = 'content_theme'
REMOVE m:content_theme SET m:ContentTheme, m.type = 'ContentTheme';

MATCH (m:Memory) WHERE m.type = 'theme'
REMOVE m:theme SET m:Theme, m.type = 'Theme';

MATCH (m:Memory) WHERE m.type = 'implementation'
REMOVE m:implementation SET m:Implementation, m.type = 'Implementation';

MATCH (m:Memory) WHERE m.type = 'phase'
REMOVE m:phase SET m:Phase, m.type = 'Phase';

MATCH (m:Memory) WHERE m.type = 'strategy'
REMOVE m:strategy SET m:Strategy, m.type = 'Strategy';

MATCH (m:Memory) WHERE m.type = 'case_study'
REMOVE m:case_study SET m:CaseStudy, m.type = 'CaseStudy';

MATCH (m:Memory) WHERE m.type = 'architecture'
REMOVE m:architecture SET m:Architecture, m.type = 'Architecture';

MATCH (m:Memory) WHERE m.type = 'schema'
REMOVE m:schema SET m:Schema, m.type = 'Schema';

MATCH (m:Memory) WHERE m.type = 'status'
REMOVE m:status SET m:Status, m.type = 'Status';

MATCH (m:Memory) WHERE m.type = 'business_model'
REMOVE m:business_model SET m:BusinessModel, m.type = 'BusinessModel';

MATCH (m:Memory) WHERE m.type = 'workflow'
REMOVE m:workflow SET m:Workflow, m.type = 'Workflow';

MATCH (m:Memory) WHERE m.type = 'research'
REMOVE m:research SET m:Research, m.type = 'Research';

MATCH (m:Memory) WHERE m.type = 'todo'
REMOVE m:todo SET m:Todo, m.type = 'Todo';
```

**重要**: `m.type` も同時にPascalCaseに更新する。MCP memory serverは `read_graph` 時に `e.type` を返すので、次回 `add_observations` 呼び出し時もPascalCase型名で正しく動作する。

---

## Phase 3: レガシーノードのクリーンアップ

### 3a. レガシーノード詳細監査（読取のみ）

```cypher
UNWIND ['ActionItem','Article','CandidateTheme','CaseStudy',
  'CaseStudyArticle','Community','Competitor','Concept',
  'ContentPolicy','Decision','Discussion','Document',
  'EmbeddableResource','ExperiencePattern','ExperienceSource',
  'FinancialProduct','MarketData','MonetizationModel','Organization',
  'Person','Platform','ReferenceArticle','ResearchReport',
  'SuccessCase','SuccessPattern'] AS label
CALL {
  WITH label
  MATCH (n) WHERE label IN labels(n) AND NOT 'Memory' IN labels(n)
  RETURN count(n) AS cnt
}
RETURN label, cnt ORDER BY cnt DESC;
```

### 3b. クリーンアップ方針

監査結果を見てからノードごとに判断。基本方針：

| 方針 | 条件 |
|------|------|
| `DETACH DELETE` | ノード数少 + リレーションなし + KG v2で代替済み |
| `:Archived` 追加 + 元ラベル削除 | 価値ある可能性 + 判断保留 |
| KG v2へ移行 | Organization→Entity(organization), Person→Entity(person) 等 |

### 3c. Decision/Project 重複解消

```cypher
// Decision (56個, 非Memory) は KG v1 時代の Claim に相当 → アーカイブ
MATCH (d:Decision) WHERE NOT 'Memory' IN labels(d)
SET d:Archived
REMOVE d:Decision;
```

### 3d. リレーションシップ正規化

```cypher
// HAS_CASE_STUDIES → HAS_CASE_STUDY に統一
MATCH (a)-[r:HAS_CASE_STUDIES]->(b)
MERGE (a)-[:HAS_CASE_STUDY]->(b)
DELETE r;
```

---

## Phase 4: 命名規約の文書化

### 4a. `.claude/rules/neo4j-namespace-convention.md` 新規作成

内容：
- **統一ルール**: 全ラベルはPascalCase
- **Memory create_entities呼び出し時**: `entityType`/`type` は必ずPascalCase
- **許可される型名**: Decision, Project, ContentTheme, Theme, Implementation, Phase, Strategy, CaseStudy, Architecture, Schema, Status, BusinessModel, Workflow, Research, Todo, Discussion
- **クエリガイドライン**: KG v2専用は `WHERE NOT 'Memory' IN labels(n)`、Memory専用は `MATCH (m:Memory)`

### 4b. `data/config/knowledge-graph-schema.yaml` に名前空間セクション追加

```yaml
namespaces:
  kg_v2:
    labels: [Source, Author, Chunk, Fact, Claim, Entity, FinancialDataPoint, FiscalPeriod, Topic, Insight]
    naming: PascalCase
  conversation:
    labels: [ConversationSession, ConversationTopic, Project]
    naming: PascalCase
  memory:
    root_label: Memory
    sub_labels_naming: PascalCase
    allowed_types: [Decision, Project, ContentTheme, Theme, Implementation, Phase, Strategy, CaseStudy, Architecture, Schema, Status, BusinessModel, Workflow, Research, Todo, Discussion]
```

### 4c. ドキュメント強化

- `topic_key` フォーマット（`{name}::{category}`）の明示化
- `entity_key` フォーマット（`{name}::{entity_type}`）の明示化

---

## Phase 5: スキーマ検証スクリプト

**ファイル**: `scripts/validate_neo4j_schema.py`

機能:
1. `knowledge-graph-schema.yaml` の `namespaces` セクションから許可ラベルを読込
2. DB上の全ラベルを取得し名前空間に分類
3. UNKNOWN名前空間（許可外ラベル）を検出・レポート
4. Memoryサブラベルが小文字でないか（PascalCase違反）をチェック
5. Memory/KGクロスコンタミネーションの検出
6. JSON形式でレポート出力

---

## Phase 6: 既存コード修正

`.claude/skills/save-to-graph/guide.md` 内のクロスファイルリレーション推論クエリに `WHERE NOT 'Memory' IN labels(n)` フィルタを追加。

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|---------|---------|
| `data/config/knowledge-graph-schema.yaml` | `namespaces` セクション追加 |
| `.claude/rules/neo4j-namespace-convention.md` | **新規作成**: ラベル命名規約・クエリガイドライン |
| `scripts/validate_neo4j_schema.py` | **新規作成**: スキーマ検証スクリプト |
| `.claude/skills/save-to-graph/guide.md` | クエリにMemoryフィルタ追加 |

## 実装順序

| Step | Phase | 内容 | リスク |
|------|-------|------|--------|
| 1 | 1 | 監査スナップショット取得 | なし（読取のみ） |
| 2 | 2 | Memoryラベルマイグレーション（約30ノード） | 低 |
| 3 | 3a | レガシーノード監査 | なし（読取のみ） |
| 4 | 3b-d | レガシーノードクリーンアップ | 中（Cypherで変更） |
| 5 | 4 | 命名規約ドキュメント作成 | なし |
| 6 | 5 | スキーマ検証スクリプト作成 | なし |
| 7 | 6 | 既存コード修正（save-to-graph） | 低 |

## 検証方法

```cypher
-- 全ラベルの名前空間分類（UNKNOWNが空なら成功）
CALL db.labels() YIELD label
WITH label,
  CASE
    WHEN label IN ['Source','Author','Chunk','Fact','Claim','Entity',
      'FinancialDataPoint','FiscalPeriod','Topic','Insight'] THEN 'kg_v2'
    WHEN label IN ['ConversationSession','ConversationTopic','Project'] THEN 'conversation'
    WHEN label = 'Memory' THEN 'memory_root'
    WHEN label IN ['Decision','ContentTheme','Theme','Implementation',
      'Phase','Strategy','CaseStudy','Architecture','Schema','Status',
      'BusinessModel','Workflow','Research','Todo','Discussion'] THEN 'memory_sub'
    WHEN label = 'Archived' THEN 'archived'
    ELSE 'UNKNOWN'
  END AS namespace
RETURN namespace, collect(label) AS labels
ORDER BY namespace;

-- 小文字ラベルが残っていないこと（0件で成功）
CALL db.labels() YIELD label
WHERE label =~ '^[a-z].*'
RETURN label;
```

追加検証:
- `mcp__memory__note-finance-read_graph` で既存Memoryノードが正常読取できること
- `python scripts/validate_neo4j_schema.py` でUNKNOWN = 0件
