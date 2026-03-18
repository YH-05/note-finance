# 議論メモ: article-neo4j → research-neo4j 統合

**日付**: 2026-03-18
**参加**: ユーザー + AI

## 背景・コンテキスト

Neo4jコンテナが3台（finance-neo4j, research-neo4j, article-neo4j）稼働しており、運用コスト（メモリ、ポート管理、MCP設定）を削減するため統合を検討した。

## 議論のサマリー

### 統合範囲
- article-neo4j → research-neo4j のみ（2台統合）
- finance-neo4j（Memory/Conversation/Discussion）は別で残す

### データ区別方法
- 区別しない（KG v2スキーマ共通、URLやentity_keyで自然に区別可能）

### マイグレーション
- Python スクリプト（MERGE ベース、冪等）で移行
- Entity 5件の重複をentity_keyでMERGE（research側のentity_id/tickerを保持）

## 決定事項

1. article-neo4j を research-neo4j に統合する（2台体制へ）
2. データの区別はしない（namespace/追加ラベル不要）
3. MERGE on entity_key で Entity 重複を統合

## 実施結果

| 項目 | 値 |
|------|-----|
| ノード | 2,356 → 3,074 (+718) |
| リレーション | 3,498 → 4,423 (+925) |
| Entity重複統合 | 5件（NVIDIA, AMD, Intel, S&P 500, TSMC） |
| Source重複統合 | 200件 |

### 更新ファイル
- `.mcp.json`: neo4j-article 削除
- `.claude/settings.local.json`: article MCP権限削除
- `docker-compose.yml`: neo4j-article サービス削除
- `.claude/skills/save-to-article-graph/SKILL.md`: → research-neo4j
- `.claude/skills/topic-discovery/SKILL.md`: → research-neo4j
- `.claude/skills/topic-discovery/references/neo4j-mapping.md`: → research-neo4j

## Phase 2: authority_level 実装

### 決定事項

4. Source ノードに `authority_level` プロパティを追加（6分類）

| authority_level | 対象 | 件数 |
|----------------|------|------|
| official | 企業IR・SEC Filing・中銀・政府機関 | 4 |
| analyst | セルサイドレポート・格付け機関・自社リサーチ | 3 |
| media | 大手報道機関・ニュースメディア | 581 |
| blog | 個人メディア・専門ブログ・Seeking Alpha | 523 |
| social | SNS・コミュニティ（Reddit, X/Twitter） | 13 |
| academic | 学術論文・リサーチペーパー | 3 |

### 実施内容

- 全1,127 Source ノードに authority_level を付与
- Neo4j インデックス `source_authority_level` 作成
- 分類ロジックを `scripts/authority_classifier.py` として独立モジュール化
- `scripts/emit_graph_queue.py` の `_make_source` に自動分類を組み込み
- KG v2 スキーマ → v2.3 に更新（`data/config/knowledge-graph-schema.yaml`）
- save-to-graph スキルの Cypher テンプレートに authority_level 追加

### 更新ファイル（Phase 2）
- `scripts/authority_classifier.py`: 分類ロジックモジュール（新規）
- `scripts/classify_authority_level.py`: 既存データ一括分類スクリプト（新規）
- `scripts/emit_graph_queue.py`: `_make_source` に authority_level 自動付与
- `data/config/knowledge-graph-schema.yaml`: v2.3（authority_level 追加）
- `.claude/skills/save-to-graph/SKILL.md`: Cypher テンプレートに authority_level
- `.claude/skills/save-to-graph/guide.md`: 同上

## アクションアイテム

### Phase 1: DB統合
- [x] research-neo4j バックアップ
- [x] マイグレーションスクリプト作成・実行
- [x] MCP設定更新
- [x] スキル参照更新
- [x] article-neo4j 停止
- [x] メモリ更新

### Phase 2: authority_level
- [x] 既存1,127 Source に authority_level 付与
- [x] Neo4j インデックス作成
- [x] 分類ロジックのモジュール化（authority_classifier.py）
- [x] emit_graph_queue.py に自動分類組み込み
- [x] KG v2.3 スキーマ更新
- [x] save-to-graph Cypher テンプレート更新
