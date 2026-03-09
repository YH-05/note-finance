# project-discuss 詳細ガイド

## sequential-thinking 活用パターン

### パターン1: コンテキスト復元後の論点整理

```json
{
  "thought": "Neo4jとドキュメントから以下の情報を収集した。\n\n【Neo4j】\n- Project: SideBusiness (status: planning)\n- Decision: ウェルスマネジメント市場をターゲット (2026-03-09)\n- ActionItem: ニッチ市場の深掘り調査 (status: pending)\n\n【ドキュメント】\n- wealth-management-market-research.md: 市場規模・競合分析\n- direction-discussion.md: 方向性の議論メモ\n- niche-deep-dive.md: ニッチ市場の深掘り\n\n【論点の整理】\n1. ニッチ市場の選定（未決定）\n2. MVP の機能スコープ（未決定）\n3. 収益モデル（議論中）\n4. ターゲット顧客の具体化（一部決定）\n\n【優先順位】\n1 → 4 → 2 → 3 の順で議論するのが効率的。ニッチ市場が決まらないと他の決定ができない。",
  "nextThoughtNeeded": true,
  "thoughtNumber": 1,
  "totalThoughts": 3
}
```

### パターン2: ユーザー回答の分析

```json
{
  "thought": "ユーザーの回答: 「富裕層向けの税金最適化ツールが面白そう」\n\n【分析】\n- 税金最適化 = 高付加価値領域\n- 規制リスクあり（税理士法との関係）\n- 競合: マネーフォワードME、freee個人\n- 差別化ポイント: 富裕層特化\n\n【追加で確認すべき点】\n- 「富裕層」の定義（金融資産3,000万以上？1億以上？）\n- ツール vs コンテンツ vs コンサルどのアプローチか\n- 規制面の懸念をどう考えるか\n\n【次の質問候補】\n→ 富裕層の定義を具体化する質問が最優先",
  "nextThoughtNeeded": false,
  "thoughtNumber": 1,
  "totalThoughts": 1
}
```

### パターン3: DB保存計画の策定

```json
{
  "thought": "今回の議論結果を保存する計画:\n\n【Discussionノード】\ndisc-2026-03-09-niche-selection\n- title: ニッチ市場選定の議論\n- summary: 富裕層向け税金最適化を第一候補として選定\n\n【Decisionノード】\n1. dec-2026-03-09-001: ターゲット = 金融資産5,000万以上の富裕層\n2. dec-2026-03-09-002: アプローチ = コンテンツ先行でツール開発に展開\n\n【ActionItemノード】\n1. act-2026-03-09-001: 税理士法の制約を調査 (優先度: 高)\n2. act-2026-03-09-002: 競合の富裕層向けサービスを5つ分析 (優先度: 高)\n3. act-2026-03-09-003: MVP コンテンツ3本の企画を作成 (優先度: 中)\n\n【リレーション】\n- SideBusiness -[:HAS_DISCUSSION]-> disc-2026-03-09-niche-selection\n- disc-... -[:RESULTED_IN]-> dec-2026-03-09-001, dec-2026-03-09-002\n- disc-... -[:PRODUCED]-> act-2026-03-09-001, act-2026-03-09-002, act-2026-03-09-003",
  "nextThoughtNeeded": false,
  "thoughtNumber": 1,
  "totalThoughts": 1
}
```

## AskUserQuestion の質問設計

### 良い質問の例

```
# 具体的で回答しやすい
"前回の議論でウェルスマネジメント市場をターゲットにする方向になりましたが、
特に注力したいニッチ領域はありますか？
例: 税金最適化、ポートフォリオ管理、不動産投資、相続対策"

# 選択肢を提示
"収益モデルとして以下の3つを検討していますが、どれが最も現実的だと思いますか？
1. サブスクリプション型（月額課金）
2. コンテンツ販売型（note記事・有料マガジン）
3. フリーミアム型（基本無料＋プレミアム機能）"

# 前回の決定を踏まえた深掘り
"前回『コンテンツ先行』で合意しましたが、最初の3本の記事テーマとして
何が良いと思いますか？市場調査の結果からは以下が候補です:
- 富裕層の節税戦略2026年版
- 金融資産5,000万からの資産配分
- iDeCo/NISA最適化の上級編"
```

### 悪い質問の例（避けるべき）

```
# 複数論点を同時に聞いている
"ターゲット顧客と収益モデルとMVP機能について教えてください"

# 抽象的すぎる
"プロジェクトについてどう思いますか？"

# Yes/Noで終わってしまう
"この方向で良いですか？"
```

## Neo4j クエリ集

### コンテキスト復元クエリ

```cypher
// プロジェクト全体の状態を取得
MATCH (p:Project)-[r]->(n)
RETURN p.name AS project, type(r) AS relation, labels(n) AS node_type,
       properties(n) AS details
ORDER BY CASE type(r)
  WHEN 'HAS_DISCUSSION' THEN 1
  WHEN 'RESULTED_IN' THEN 2
  WHEN 'PRODUCED' THEN 3
  ELSE 4
END

// 最近の議論を取得
MATCH (d:Discussion)
OPTIONAL MATCH (d)-[:RESULTED_IN]->(dec:Decision)
OPTIONAL MATCH (d)-[:PRODUCED]->(a:ActionItem)
RETURN d, collect(DISTINCT dec) AS decisions, collect(DISTINCT a) AS actions
ORDER BY d.date DESC
LIMIT 10

// 未完了のアクションアイテムを取得
MATCH (a:ActionItem {status: 'pending'})
OPTIONAL MATCH (d:Discussion)-[:PRODUCED]->(a)
RETURN a.description, a.priority, a.due_date, d.title AS from_discussion
ORDER BY
  CASE a.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
```

### 保存クエリ

```cypher
// Project ノードの確認/作成
MERGE (p:Project {name: $project_name})
SET p.updated_at = datetime()

// Discussion ノードの保存
MERGE (d:Discussion {discussion_id: $discussion_id})
SET d.title = $title,
    d.date = date($date),
    d.summary = $summary,
    d.topics = $topics,
    d.created_at = datetime()

// Decision ノードの保存
MERGE (dec:Decision {decision_id: $decision_id})
SET dec.content = $content,
    dec.context = $context,
    dec.decided_at = date($date),
    dec.status = 'active',
    dec.created_at = datetime()

// ActionItem ノードの保存
MERGE (a:ActionItem {action_id: $action_id})
SET a.description = $description,
    a.priority = $priority,
    a.status = 'pending',
    a.due_date = CASE WHEN $due_date IS NOT NULL THEN date($due_date) ELSE null END,
    a.created_at = datetime()

// ActionItem のステータス更新
MATCH (a:ActionItem {action_id: $action_id})
SET a.status = $new_status,
    a.completed_at = CASE WHEN $new_status = 'completed' THEN datetime() ELSE null END
```

## ドキュメント保存テンプレート

### 議論メモテンプレート

```markdown
# 議論メモ: {トピック}

**日付**: YYYY-MM-DD
**議論ID**: disc-YYYY-MM-DD-{topic-slug}
**参加**: ユーザー + AI

## 背景・コンテキスト

{議論の背景。前回の議論からの続きであればその旨を記載}

## 議論のサマリー

### 論点1: {論点}

{議論の内容}

**結論**: {合意事項}

### 論点2: {論点}

{議論の内容}

**結論**: {合意事項}

## 決定事項

| ID | 内容 | コンテキスト |
|----|------|------------|
| dec-YYYY-MM-DD-001 | {決定事項1} | {決定の背景} |
| dec-YYYY-MM-DD-002 | {決定事項2} | {決定の背景} |

## アクションアイテム

| ID | 内容 | 優先度 | 期限 |
|----|------|--------|------|
| act-YYYY-MM-DD-001 | {アクション1} | 高 | YYYY-MM-DD |
| act-YYYY-MM-DD-002 | {アクション2} | 中 | - |

## 次回の議論トピック

- {次回議論すべきこと1}
- {次回議論すべきこと2}

## 参考情報

### Web調査結果

{Web調査で得た情報があれば記載}

### 関連ドキュメント

- {関連する既存ドキュメントへのリンク}
```

## エラーハンドリング

| エラー | 対処 |
|--------|------|
| Neo4j 接続失敗 | ドキュメントのみでコンテキスト復元を行い、Neo4j保存はスキップ。ユーザーに通知する |
| docs/plan/SideBusiness/ が空 | 初回議論として扱い、プロジェクトの概要から聞き始める |
| sequential-thinking が利用不可 | スキル内で直接分析を行う（品質は落ちるが続行可能） |
| Web 調査が失敗 | 調査なしで議論を継続。ユーザーに調査失敗を通知 |

## 議論の再開パターン

前回の議論を引き継ぐ場合:

1. Neo4j から最新の Discussion ノードを取得
2. 関連する Decision と ActionItem を復元
3. ActionItem のステータスを確認（完了/未完了）
4. 未完了アイテムの進捗確認から議論を開始
5. 新しい論点があれば追加
