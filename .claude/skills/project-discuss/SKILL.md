---
name: project-discuss
description: |
  プロジェクトの方向性をユーザーと対話的に議論するスキル。Neo4jグラフDBとドキュメントからコンテキストを復元し、sequential-thinkingで構造化された議論を行い、合意事項をNeo4j+ドキュメントに保存する。
  Use PROACTIVELY when user wants to discuss project direction, review SideBusiness progress, brainstorm strategy, or align on next steps.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# project-discuss スキル

プロジェクトの方向性についてユーザーと対話的に議論し、合意形成を行うスキル。
Neo4j グラフ DB と `docs/plan/SideBusiness/` のドキュメントをベースに現状を復元し、構造化された議論を通じて意思決定を支援する。

## 処理フロー

```
Phase 1: コンテキスト復元
    |  Neo4j スキーマ確認 + データ取得
    |  docs/plan/SideBusiness/ ドキュメント読み込み
    |  sequential-thinking で論点整理
    |
Phase 2: サマリー提示 + 議論
    |  現状サマリーをユーザーに提示
    |  AskUserQuestion で論点ごとに質問（1問ずつ）
    |  各回答を sequential-thinking で分析
    |  必要に応じて Web 調査を挟む
    |
Phase 3: 合意形成 + 保存
    |  決定事項を sequential-thinking で整理
    |  Neo4j に MERGE ベースで保存
    |  docs/plan/SideBusiness/ にメモ保存
    |
Phase 4: アクションアイテム提示
    次のステップを明確化
```

## Phase 1: コンテキスト復元

### 1.1 Neo4j からプロジェクト関連データを取得

まず `mcp__neo4j-cypher__note-finance-get_neo4j_schema` でスキーマを確認し、関連ノードを把握する。

次に `mcp__neo4j-cypher__note-finance-read_neo4j_cypher` で以下を取得:

```cypher
// プロジェクト関連ノードを取得
MATCH (n)
WHERE n:Project OR n:Discussion OR n:Decision OR n:ActionItem
RETURN labels(n) AS labels, properties(n) AS props
ORDER BY n.created_at DESC
LIMIT 50

// リレーションも取得
MATCH (n)-[r]->(m)
WHERE n:Project OR n:Discussion OR n:Decision
RETURN labels(n) AS from_labels, type(r) AS rel, labels(m) AS to_labels,
       properties(n) AS from_props, properties(m) AS to_props
LIMIT 100
```

### 1.2 ドキュメントの読み込み

`docs/plan/SideBusiness/` 配下の全 Markdown ファイルを読み込む:

```bash
# ファイル一覧取得
Glob docs/plan/SideBusiness/*.md

# 各ファイルを Read で読み込み
```

### 1.3 sequential-thinking で論点整理

`mcp__sequential-thinking__sequentialthinking` を使い、以下を構造化:

- 現在のプロジェクト状態のサマリー
- これまでの決定事項
- 未解決の論点リスト
- 議論すべきトピックの優先順位

## Phase 2: 議論

### 2.1 サマリー提示

Phase 1 で整理した現状サマリーをユーザーに提示する。
提示内容:
- プロジェクトの現在地（何が決まっていて、何が未決か）
- 前回までの議論のハイライト
- 今回議論すべき論点の提案

### 2.2 対話ループ

以下のループを繰り返す:

1. **AskUserQuestion** で1つの論点について質問
   - **重要**: 一度に1つの論点のみ質問する（複数論点を同時に聞かない）
   - 質問は具体的で回答しやすい形式にする
2. ユーザーの回答を **sequential-thinking** で分析
   - 回答から得られた示唆
   - 追加で確認すべき点
   - 次に聞くべき論点
3. 必要に応じて **Web 調査**を挟む
   - `mcp__tavily__tavily_search` で市場データ・競合情報等を取得
   - `WebSearch` でトレンド情報を取得
   - 調査結果をユーザーに共有してから次の質問へ
4. 合意が形成されたら次の論点へ

### 2.3 議論の終了判定

以下のいずれかで議論を終了:
- 全論点について合意が得られた
- ユーザーが「ここまでにしよう」等の終了意思を示した
- 十分なアクションアイテムが出揃った

## Phase 3: 保存

### 3.1 Neo4j への保存

`mcp__neo4j-cypher__note-finance-write_neo4j_cypher` で MERGE ベースで保存。

**Discussion ノード**:
```cypher
MERGE (d:Discussion {discussion_id: $discussion_id})
SET d.title = $title,
    d.date = date($date),
    d.summary = $summary,
    d.created_at = datetime()
```

**Decision ノード**:
```cypher
MERGE (dec:Decision {decision_id: $decision_id})
SET dec.content = $content,
    dec.context = $context,
    dec.decided_at = date($date),
    dec.status = 'active'
```

**ActionItem ノード**:
```cypher
MERGE (a:ActionItem {action_id: $action_id})
SET a.description = $description,
    a.priority = $priority,
    a.status = 'pending',
    a.due_date = CASE WHEN $due_date IS NOT NULL THEN date($due_date) ELSE null END,
    a.created_at = datetime()
```

**リレーション**:
```cypher
// Discussion -> Decision
MATCH (d:Discussion {discussion_id: $discussion_id})
MATCH (dec:Decision {decision_id: $decision_id})
MERGE (d)-[:RESULTED_IN]->(dec)

// Discussion -> ActionItem
MATCH (d:Discussion {discussion_id: $discussion_id})
MATCH (a:ActionItem {action_id: $action_id})
MERGE (d)-[:PRODUCED]->(a)

// Project -> Discussion
MATCH (p:Project {name: $project_name})
MATCH (d:Discussion {discussion_id: $discussion_id})
MERGE (p)-[:HAS_DISCUSSION]->(d)
```

### 3.2 ドキュメントへの保存

`docs/plan/SideBusiness/` に日付付きメモを保存:

ファイル名: `YYYY-MM-DD_discussion-{topic-slug}.md`

```markdown
# 議論メモ: {トピック}

**日付**: YYYY-MM-DD
**参加**: ユーザー + AI

## 背景・コンテキスト

{議論の背景}

## 議論のサマリー

{主要な論点と議論の流れ}

## 決定事項

1. {決定事項1}
2. {決定事項2}

## アクションアイテム

- [ ] {アクション1} (優先度: 高/中/低)
- [ ] {アクション2} (優先度: 高/中/低)

## 次回の議論トピック

- {次回議論すべきこと}

## 参考情報

- {Web調査で得た情報等}
```

## Phase 4: アクションアイテム提示

議論の締めくくりとして以下を提示:

1. **決定事項の一覧**: 今回合意した内容
2. **アクションアイテム**: 優先度付きのタスクリスト
3. **次回の議論トピック**: 未解決の論点や次に議論すべきこと
4. **保存先**: Neo4j ノード ID とドキュメントパス

## sequential-thinking の活用方針

以下の場面で **必ず** `mcp__sequential-thinking__sequentialthinking` を使用する:

| 場面 | 用途 |
|------|------|
| Phase 1 完了時 | 収集データの整理、論点の優先順位付け |
| ユーザー回答の分析時 | 回答の示唆分析、次の質問の設計 |
| Web 調査結果の統合時 | 調査結果と議論の関連付け |
| Phase 3 開始前 | DB 保存計画の策定（ノード/リレーション設計） |
| 合意形成時 | 決定事項とアクションアイテムの構造化 |

## Neo4j ノード ID の生成規則

冪等性を保証するため、ID は決定論的に生成する:

| ノード | ID 形式 | 例 |
|--------|---------|-----|
| Discussion | `disc-{YYYY-MM-DD}-{topic-slug}` | `disc-2026-03-09-market-strategy` |
| Decision | `dec-{YYYY-MM-DD}-{sequential}` | `dec-2026-03-09-001` |
| ActionItem | `act-{YYYY-MM-DD}-{sequential}` | `act-2026-03-09-001` |

## 使用例

### 例1: プロジェクトの方向性議論

```
ユーザー: プロジェクトの方向性について話し合いたい
→ Phase 1 で Neo4j + docs から現状復元
→ Phase 2 で方向性の論点を1つずつ議論
→ Phase 3 で合意事項を保存
```

### 例2: SideBusiness の進捗確認

```
ユーザー: SideBusiness の進捗を確認したい
→ Phase 1 で docs/plan/SideBusiness/ を読み込み
→ Phase 2 で進捗状況を確認、課題を議論
→ Phase 3 で次のアクションを保存
```

### 例3: 戦略の再検討

```
ユーザー: 市場調査の結果を踏まえて戦略を見直したい
→ Phase 1 で既存の Decision ノードを復元
→ Phase 2 で Web 調査を挟みながら議論
→ Phase 3 で新しい Decision ノードを MERGE
```

### 例4: アクションアイテムのレビュー

```
ユーザー: 前回決めたアクションアイテムの進捗を確認
→ Phase 1 で ActionItem ノードを取得
→ Phase 2 で各アイテムのステータスを確認
→ Phase 3 で完了/未完了をステータス更新
```

## ガイドライン

### MUST

- sequential-thinking を可能な限り使い、議論を構造化する
- AskUserQuestion で一度に1つの論点のみ質問する
- Neo4j への保存は MERGE ベースで冪等に行う
- ドキュメント保存時はファイル名に日付を含める
- Phase 1 で必ずコンテキスト復元を行ってから議論を開始する

### SHOULD

- Web 調査結果はユーザーに共有してから次の質問に進む
- 既存の Decision ノードとの整合性を確認する
- 議論の流れを自然に保つ（機械的な質問にならないよう配慮）
- アクションアイテムには優先度を付ける

### NEVER

- 複数の論点を一度に質問する
- Neo4j への保存で CREATE を使う（MERGE を使うこと）
- コンテキスト復元をスキップして議論を開始する
- ユーザーの回答を分析せずに次の質問に進む

## 完了条件

- [ ] Phase 1 で Neo4j + ドキュメントからコンテキストが復元されている
- [ ] 少なくとも1つの論点について合意が形成されている
- [ ] 決定事項が Neo4j に Discussion/Decision ノードとして保存されている
- [ ] アクションアイテムが Neo4j に ActionItem ノードとして保存されている
- [ ] `docs/plan/SideBusiness/` に議論メモが保存されている
- [ ] アクションアイテムと次回議論トピックが提示されている

## 関連リソース

| リソース | パス |
|---------|------|
| 詳細ガイド | `.claude/skills/project-discuss/guide.md` |
| SideBusiness ドキュメント | `docs/plan/SideBusiness/` |
| Neo4j MCP ツール | `mcp__neo4j-cypher__note-finance-*` |
| save-to-graph スキル | `.claude/skills/save-to-graph/SKILL.md` |
