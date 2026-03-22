# 議論メモ: creator-neo4j 設計・構築

**日付**: 2026-03-21
**参加**: ユーザー + AI
**Neo4j Discussion ID**: disc-2026-03-21-creator-neo4j-design
**前提議論**: disc-2026-03-21-persona-design-best-practices

## 背景・コンテキスト

ナレッジファイル（口調・テンプレート）だけでは投稿の深みが出ない。
KGにFact/Tip/Storyを蓄積し、ライターエージェントが参照して
データに裏打ちされた深みのある投稿を自動生成する。

## 決定事項

1. **dec-2026-03-21-creator-neo4j-infra**: 専用KG「creator-neo4j」(bolt://localhost:7689)を新規構築
   - research-neo4j(金融特化)とは完全に独立
   - 名前は「creator」（マルチプラットフォーム対応を反映）
   - 3アカウント全て（転職/美容恋愛/占いスピ）を1インスタンスに格納

## インフラ構成

| コンポーネント | 値 |
|-------------|-----|
| コンテナ名 | creator-neo4j |
| Bolt | bolt://localhost:7689 |
| Browser | http://localhost:7476 |
| Docker | docker/creator-neo4j/docker-compose.yml |
| MCP namespace | creator |
| MCP tools | mcp__neo4j-creator__creator-* |

## スキーマ（9ノード × 10リレーション）

### ノード

| ノード | 用途 | IDプロパティ |
|-------|------|------------|
| Fact | データ・統計 | fact_id |
| Tip | ノウハウ・アドバイス | tip_id |
| Story | 成功/失敗事例 | story_id |
| Source | 情報ソース | source_id |
| Topic | テーマ | topic_id |
| Genre | ジャンル（career/beauty-romance/spiritual） | genre_id |
| Service | ASP紹介サービス | service_id |
| Post | 投稿ログ | post_id |
| Account | アカウント情報 | account_id |

### リレーション

```
(Fact)-[:ABOUT]->(Topic)
(Tip)-[:ABOUT]->(Topic)
(Story)-[:ABOUT]->(Topic)
(Topic)-[:IN_GENRE]->(Genre)
(Service)-[:IN_GENRE]->(Genre)
(Fact)-[:FROM_SOURCE]->(Source)
(Tip)-[:FROM_SOURCE]->(Source)
(Story)-[:FROM_SOURCE]->(Source)
(Post)-[:USES]->(Fact|Tip|Story)
(Post)-[:PROMOTES]->(Service)
(Post)-[:POSTED_BY]->(Account)
(Account)-[:TARGETS]->(Genre)
```

### 初期データ

| genre_id | name |
|----------|------|
| career | 転職・キャリア |
| beauty-romance | 美容×恋愛 |
| spiritual | 占い・スピリチュアル |

## パイプライン・スキル（未実装）

| コンポーネント | 名前 | 役割 | ステータス |
|-------------|------|------|----------|
| スクリプト | scripts/emit_creator_queue.py | 入力JSON → graph-queue JSON | 未実装 |
| スキル | /save-to-creator-neo4j | graph-queue → creator-neo4j投入 | 未実装 |
| スキル | /creator-neo4j-quality-check | 品質計測・評価 | 未実装 |
| コマンド | /creator-research | Web検索→JSON→KG投入一括 | 未実装 |

## 2層ナレッジ構造

```
Layer 1: ナレッジファイル（スキル/テンプレート）
  → ペルソナ定義（口調・世界観・NGワード）
  → 投稿テンプレート（結論→ストーリー→問いかけの型）
  → ASP案件リスト・リンク集

Layer 2: ナレッジグラフ（creator-neo4j）
  → Fact: データ・統計（求人倍率、業界トレンド等）
  → Tip: ノウハウ（面接対策、書類選考のコツ等）
  → Story: 成功/失敗事例
  → Source: 情報ソース（URL、取得日）
```

## 次回の議論トピック

- emit_creator_queue.py の入力JSON仕様設計
- /save-to-creator-neo4j スキル実装
- /creator-neo4j-quality-check スキル実装（評価カテゴリ: Completeness/Freshness/Coverage/SourceGrounding/PostUtilization/EngagementInsight）
- 転職ジャンルの初期データ投入（Web検索 → KG投入）
