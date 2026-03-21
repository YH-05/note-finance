---
name: note-quality-check
description: |
  note-neo4j (bolt://localhost:7687) の品質を計測・評価するスキル。
  Discussion, Decision, ActionItem, Research の4ラベルに対して
  6カテゴリの定量指標を計測し、LLM-as-Judge による整合性チェックを実行する。
  「note品質」「note-neo4j品質」「ノート品質チェック」「議事録品質」「Decision品質」
  と言われたら必ずこのスキルを使うこと。
  Use PROACTIVELY when the user asks about note-neo4j quality, discussion/decision
  data quality, or after bulk data migration to verify integrity.
allowed-tools: Read, Write, Bash, Glob, Grep
---

# note-quality-check

note-neo4j (bolt://localhost:7687) のデータ品質を計測し、Claude Code が LLM-as-Judge として
Decision/ActionItem の整合性を直接評価するスキル。

## 目的

このスキルは以下を提供します：

- **定量計測**: 6カテゴリの品質指標を Cypher プローブで計測
- **整合性評価**: Decision の content/context 論理整合性を Claude Code が評価
- **レポート生成**: 定量スコア + 問題一覧 + 改善提案を Markdown レポートで出力

## いつ使用するか

### プロアクティブ使用（自動で検討）

以下の状況では、ユーザーが明示的に要求しなくても参照：

1. **note-neo4j のデータ品質を確認したい場合**
   - 「note-neo4j の品質は？」
   - 「Discussion データの充填率を調べて」
   - 「孤立ノードはある？」

2. **データ移行・一括投入後の検証**
   - 議事録データを一括投入した後
   - スキーマ変更を適用した後

3. **定期的な品質モニタリング**
   - 「Decision の status が正しいか確認」
   - 「古い pending の ActionItem は？」

### 明示的な使用

- `/note-quality-check` コマンドで直接実行

## 処理フロー

```
Phase 1: 定量計測（Cypher プローブ）
    |  note-neo4j から6カテゴリの指標を計測
    |  mcp__neo4j-note__note-read_neo4j_cypher を使用
    |
Phase 2: 整合性チェック（LLM-as-Judge）
    |  Decision の content/context の論理的整合性を Claude Code が評価
    |  ActionItem の status 妥当性を評価
    |
Phase 3: レポート出力
    定量スコア + 問題一覧 + 改善提案をユーザーに提示
```

## Phase 1: 定量計測（6カテゴリ）

全ての Cypher クエリは `mcp__neo4j-note__note-read_neo4j_cypher` を使用する（読み取りのみ）。

### 1.1 Completeness（完全性）

プロパティ充填率を計測する。各ラベルの必須/推奨プロパティの充填率を算出し、加重平均でスコア化。

**Discussion の充填率**:

```cypher
MATCH (d:Discussion)
RETURN
    count(d) AS total,
    count(d.discussion_id) AS has_id,
    count(d.title) AS has_title,
    count(d.date) AS has_date,
    count(d.summary) AS has_summary,
    count(d.topics) AS has_topics,
    count(d.doc_path) AS has_doc_path,
    count(d.created_at) AS has_created_at
```

**Decision の充填率**:

```cypher
MATCH (d:Decision)
RETURN
    count(d) AS total,
    count(d.decision_id) AS has_id,
    count(d.content) AS has_content,
    count(d.context) AS has_context,
    count(d.decided_at) AS has_decided_at,
    count(d.status) AS has_status,
    count(d.created_at) AS has_created_at
```

**ActionItem の充填率**:

```cypher
MATCH (a:ActionItem)
RETURN
    count(a) AS total,
    count(a.action_id) AS has_id,
    count(a.description) AS has_description,
    count(a.priority) AS has_priority,
    count(a.status) AS has_status,
    count(a.created_at) AS has_created_at
```

**Research の充填率**:

```cypher
MATCH (r:Research)
RETURN
    count(r) AS total,
    count(r.paper_id) AS has_id,
    count(r.title) AS has_title,
    count(r.authors) AS has_authors,
    count(r.year) AS has_year
```

**スコア算出**:
- 必須プロパティ（id, title/content/description, date/decided_at/created_at）: 重み 1.0
- 推奨プロパティ（summary, topics, context, priority）: 重み 0.7
- 任意プロパティ（doc_path, participants）: 重み 0.3
- スコア = 加重充填率の全ラベル平均

### 1.2 Consistency（一貫性）

ID フォーマット、status 値、リレーションタイプの妥当性を検証する。

**ID フォーマット検証**:

```cypher
MATCH (d:Discussion)
WHERE d.discussion_id IS NOT NULL
AND NOT d.discussion_id =~ 'disc-\\d{4}-\\d{2}-\\d{2}-.+'
RETURN d.discussion_id AS invalid_id, d.title AS title
```

```cypher
MATCH (d:Decision)
WHERE d.decision_id IS NOT NULL
AND NOT d.decision_id =~ 'dec-\\d{4}-\\d{2}-\\d{2}-\\d{3}'
RETURN d.decision_id AS invalid_id, left(d.content, 80) AS content
```

```cypher
MATCH (a:ActionItem)
WHERE a.action_id IS NOT NULL
AND NOT a.action_id =~ 'act-\\d{4}-\\d{2}-\\d{2}-\\d{3}'
RETURN a.action_id AS invalid_id, a.description AS description
```

**status 値の検証**:

```cypher
MATCH (d:Decision)
WHERE d.status IS NOT NULL
AND NOT d.status IN ['active', 'superseded', 'revoked']
RETURN d.decision_id AS id, d.status AS invalid_status
```

```cypher
MATCH (a:ActionItem)
WHERE a.status IS NOT NULL
AND NOT a.status IN ['pending', 'in_progress', 'completed', 'blocked']
RETURN a.action_id AS id, a.status AS invalid_status
```

**異常リレーション検出**:

```cypher
MATCH (a)-[r:RESULTED_IN]->(b)
WHERE NOT (a:Discussion AND b:Decision)
RETURN labels(a) AS from_labels, type(r) AS rel_type, labels(b) AS to_labels,
       coalesce(a.discussion_id, a.decision_id, '') AS from_id,
       coalesce(b.discussion_id, b.decision_id, '') AS to_id
```

**スコア算出**:
- 不正 ID 率、不正 status 率、異常リレーション率の逆数の平均

### 1.3 Orphan検出（孤立ノード）

リレーションを持たないノードを検出する。

```cypher
MATCH (d:Decision)
WHERE NOT (d)<-[:RESULTED_IN]-() AND NOT (d)<-[:BUILDS_ON]-()
RETURN d.decision_id AS id, left(d.content, 80) AS content
```

```cypher
MATCH (a:ActionItem)
WHERE NOT (a)<-[:PRODUCED]-()
RETURN a.action_id AS id, a.description AS description
```

```cypher
MATCH (r:Research)
WHERE NOT (r)<-[:REFERENCES]-()
RETURN r.paper_id AS id, r.title AS title
```

**スコア算出**:
- 孤立率 = 孤立ノード数 / 全ノード数
- スコア = 1.0 - 孤立率

### 1.4 Staleness（鮮度）

古くなったデータを検出する。

**30日以上 pending の ActionItem**:

```cypher
MATCH (a:ActionItem)
WHERE a.status = 'pending' AND a.created_at IS NOT NULL
AND datetime(a.created_at) < datetime() - duration('P30D')
RETURN a.action_id AS id, a.description AS description,
       toString(a.created_at) AS created_at
```

**90日以上レビューなしの active Decision**:

```cypher
MATCH (d:Decision)
WHERE d.status = 'active' AND d.decided_at IS NOT NULL
AND date(d.decided_at) < date() - duration('P90D')
RETURN d.decision_id AS id, left(d.content, 80) AS content,
       toString(d.decided_at) AS decided_at
```

**スコア算出**:
- stale率 = staleノード数 / 該当ステータスのノード数
- スコア = 1.0 - stale率

### 1.5 Structural（構造）

グラフ構造の統計を計測する。

**Discussion あたりの Decision/ActionItem 数**:

```cypher
MATCH (d:Discussion)
OPTIONAL MATCH (d)-[:RESULTED_IN]->(dec:Decision)
OPTIONAL MATCH (d)-[:PRODUCED]->(ai:ActionItem)
RETURN d.discussion_id AS id, d.title AS title,
       count(DISTINCT dec) AS decisions, count(DISTINCT ai) AS actions
ORDER BY decisions DESC
```

**全体統計**:

```cypher
MATCH (d:Discussion)
OPTIONAL MATCH (d)-[:RESULTED_IN]->(dec:Decision)
OPTIONAL MATCH (d)-[:PRODUCED]->(ai:ActionItem)
WITH d, count(DISTINCT dec) AS dec_count, count(DISTINCT ai) AS ai_count
RETURN
    avg(dec_count) AS avg_decisions,
    max(dec_count) AS max_decisions,
    min(dec_count) AS min_decisions,
    avg(ai_count) AS avg_actions,
    max(ai_count) AS max_actions,
    min(ai_count) AS min_actions
```

**FOLLOWED_BY チェーン長**:

```cypher
MATCH path = (d1:Discussion)-[:FOLLOWED_BY*]->(d2:Discussion)
RETURN length(path) AS chain_length,
       [n IN nodes(path) | n.discussion_id] AS chain_ids
ORDER BY chain_length DESC
LIMIT 5
```

**スコア算出**:
- Decision/ActionItem が 0 の Discussion の割合で減点
- 過度に集中（1つの Discussion に 10+ Decision）がある場合も減点

### 1.6 DocSync（ドキュメント連携）

Discussion の doc_path とファイルシステムの整合性を検証する。

**doc_path 一覧取得**:

```cypher
MATCH (d:Discussion)
WHERE d.doc_path IS NOT NULL AND d.doc_path <> ''
RETURN d.discussion_id AS id, d.title AS title, d.doc_path AS doc_path
```

取得した doc_path に対して、Glob ツールまたは Bash でファイル存在を確認する。

**doc_path 未設定の Discussion**:

```cypher
MATCH (d:Discussion)
WHERE d.doc_path IS NULL OR d.doc_path = ''
RETURN d.discussion_id AS id, d.title AS title, toString(d.date) AS date
```

**スコア算出**:
- doc_path 設定率 * ファイル存在率

## Phase 2: 整合性チェック（LLM-as-Judge）

Claude Code が直接、Decision と ActionItem の内容を評価する。

### 2.1 Decision の content/context 整合性

`mcp__neo4j-note__note-read_neo4j_cypher` で Decision を取得し、以下の2軸で評価する:

```cypher
MATCH (d:Decision)
WHERE d.content IS NOT NULL AND d.context IS NOT NULL
RETURN d.decision_id AS id, d.content AS content, d.context AS context,
       d.status AS status, toString(d.decided_at) AS decided_at
ORDER BY rand()
LIMIT 10
```

| 軸 | 重み | 評価基準 |
|---|---:|---|
| Content-Context Coherence | 60% | content（決定内容）が context（背景）から論理的に導かれるか |
| Specificity | 40% | content が具体的で実行可能な決定を記述しているか（曖昧な方針ではなく） |

**評価の目安**:
- **0.8-1.0**: content が context から自然に導かれ、具体的なアクションが明記
- **0.5-0.7**: 関連性はあるが、飛躍がある or やや抽象的
- **0.2-0.4**: context と content の関連が薄い or 極めて曖昧
- **0.0-0.1**: 無関係 or ノイズデータ

### 2.2 ActionItem の status 妥当性

```cypher
MATCH (a:ActionItem)
WHERE a.status IS NOT NULL AND a.description IS NOT NULL
RETURN a.action_id AS id, a.description AS description,
       a.status AS status, toString(a.created_at) AS created_at,
       toString(a.completed_at) AS completed_at,
       a.blocked_reason AS blocked_reason
ORDER BY rand()
LIMIT 10
```

| 軸 | 評価基準 |
|---|---|
| Status Consistency | status=completed なら completed_at が存在すべき。status=blocked なら blocked_reason が存在すべき |
| Description Clarity | description が明確で実行可能なタスクを記述しているか |

## Phase 3: レポート出力

以下の Markdown 形式でユーザーに提示する。

```markdown
## note-neo4j 品質チェックレポート

**計測日時**: YYYY-MM-DD HH:MM
**ノード数**: Discussion XX / Decision XX / ActionItem XX / Research XX

### 1. Completeness（完全性）スコア: XX%

| ラベル | プロパティ | 充填数/総数 | 充填率 | 重要度 |
|--------|-----------|------------|--------|--------|
| Discussion | discussion_id | XX/XX | 100% | 必須 |
| Discussion | title | XX/XX | 100% | 必須 |
| Discussion | topics | XX/XX | 17% | 推奨 |
...

### 2. Consistency（一貫性）スコア: XX%

- 不正 ID フォーマット: N件
  - [詳細リスト]
- 不正 status 値: N件
  - [詳細リスト]
- 異常リレーション: N件
  - [詳細リスト]

### 3. 孤立ノード スコア: XX%

- 孤立 Decision: N件
  - [ID と content の先頭80文字]
- 孤立 ActionItem: N件
  - [ID と description]
- 孤立 Research: N件
  - [ID と title]

### 4. Staleness（鮮度）スコア: XX%

- 30日以上 pending の ActionItem: N件
  - [ID, description, created_at]
- 90日以上レビューなしの Decision: N件
  - [ID, content の先頭80文字, decided_at]

### 5. 構造分析 スコア: XX%

- Discussion あたり平均 Decision 数: X.X
- Discussion あたり平均 ActionItem 数: X.X
- FOLLOWED_BY チェーン最大長: X

| Discussion | Decisions | ActionItems |
|------------|-----------|-------------|
| disc-2026-... | 5 | 3 |
...

### 6. ドキュメント連携 スコア: XX%

- doc_path 設定率: X/XX (XX%)
- ファイル存在確認: X/X件 OK
- doc_path 未設定の Discussion: N件

### 7. 整合性評価（LLM-as-Judge）

#### Decision の content/context 整合性

| Decision ID | Coherence | Specificity | 総合 | 備考 |
|-------------|-----------|-------------|------|------|
| dec-2026-... | 0.8 | 0.7 | 0.76 | - |
...

平均スコア: X.XX

#### ActionItem の status 妥当性

- status=completed で completed_at 欠損: N件
- status=blocked で blocked_reason 欠損: N件
- description が曖昧な ActionItem: N件

### 総合スコア: XX/100

| カテゴリ | スコア | 重み | 加重スコア |
|---------|--------|------|-----------|
| Completeness | XX% | 25% | XX |
| Consistency | XX% | 20% | XX |
| Orphan | XX% | 15% | XX |
| Staleness | XX% | 10% | XX |
| Structural | XX% | 10% | XX |
| DocSync | XX% | 5% | XX |
| LLM-as-Judge | XX% | 15% | XX |

### 改善提案

1. [優先度: 高] ...
2. [優先度: 中] ...
3. [優先度: 低] ...
```

## 使用する MCP ツール

| MCP ツール | 用途 |
|-----------|------|
| `mcp__neo4j-note__note-read_neo4j_cypher` | 全ての Cypher クエリ実行（読み取りのみ） |

**注意**: `mcp__neo4j-note__note-write_neo4j_cypher` は一切使用しない。

## 関連ファイル

| ファイル | 説明 |
|---------|------|
| `.claude/commands/note-quality-check.md` | スラッシュコマンド |
| `.claude/skills/kg-quality-check/SKILL.md` | research-neo4j 用の品質チェック（参考） |
| `data/processed/note_quality/` | レポート保存先（必要に応じて作成） |

## MUST / SHOULD / NEVER

### MUST

- Phase 1 の6カテゴリ全ての Cypher プローブを実行すること
- Phase 2 の LLM-as-Judge 評価を Decision/ActionItem 両方に実施すること
- 全ての Cypher は `mcp__neo4j-note__note-read_neo4j_cypher` で実行すること
- レポートに総合スコア（100点満点）を算出すること
- 問題が見つかった場合は具体的な改善提案を含めること

### SHOULD

- 各カテゴリでスコアが低い（50%未満）場合は警告マーク付きで報告すること
- doc_path のファイル存在確認は Glob ツールで実施すること
- 前回レポートが存在する場合は比較を行うこと
- 改善提案に優先度（高/中/低）を付けること

### NEVER

- `mcp__neo4j-note__note-write_neo4j_cypher` を使用してはならない（読み取り専用）
- research-neo4j (port 7688) のツールを使用してはならない（対象は note-neo4j）
- データを修正してはならない（検出と報告のみ）

## 完了条件

- [ ] 6カテゴリの Cypher プローブが全て実行されている
- [ ] LLM-as-Judge による整合性評価が実施されている
- [ ] 総合スコア（100点満点）が算出されている
- [ ] 問題点と改善提案を含む Markdown レポートがユーザーに提示されている
