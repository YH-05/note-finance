# 議論メモ: Claude Code会話履歴のNeo4j保存

**日付**: 2026-03-13
**参加**: ユーザー + AI

## 背景・コンテキスト

Claude Codeとの過去の全会話履歴（70セッション）をNeo4jグラフDBに保存し、
プロジェクトの活動記録として検索・分析可能にしたい。

## 議論のサマリー

- 保存方式: ハイブリッド（セッション概要 + 重要な決定事項・アクション抽出）
- スコープ: 過去の全会話（70セッション）+ 今後の新規セッション
- 全メッセージ本文はNeo4jには入れない（ローカルJSONLが正）

## 決定事項

1. **ハイブリッド方式を採用**: メタデータ + トピック分類 + 最初のユーザーメッセージを保存
2. **スキーマ**: `ConversationSession` ノード + `ConversationTopic` ノード + `DISCUSSES` リレーション
3. **Projectとの接続**: `(Project:SideBusiness)-[:HAS_CONVERSATION]->(ConversationSession)`

## 実装結果

| 項目 | 値 |
|------|-----|
| 保存セッション数 | 70 |
| トピックカテゴリ | 15 |
| リンク数 | 188 (DISCUSSES) + 70 (HAS_CONVERSATION) |
| 期間 | 2026-03-01 〜 2026-03-12 |
| 総メッセージ数 | 6,279 |
| 総サイズ | 41,481 KB |

### トピック分布

| トピック | セッション数 |
|---------|------------|
| Neo4j/DB設計 | 24 |
| MCP設定 | 24 |
| プロジェクト方針 | 20 |
| その他 | 19 |
| スキル/エージェント開発 | 18 |
| Git/PR操作 | 16 |
| Reddit調査 | 16 |
| RSS/ニュース収集 | 11 |
| 記事執筆 | 11 |
| PDFパイプライン | 9 |
| KGスキーマ | 7 |
| 体験談DB | 5 |
| インフラ/Docker | 4 |
| 週次レポート | 2 |
| Obsidian統合 | 2 |

## スクリプト

```bash
# ドライラン（パースのみ）
uv run python3 scripts/save_conversations_to_neo4j.py --dry-run

# Neo4jに保存（.envからパスワード読み込み）
uv run python3 scripts/save_conversations_to_neo4j.py --neo4j-password "$NEO4J_PASSWORD"

# 特定セッションのみ
uv run python3 scripts/save_conversations_to_neo4j.py --session-id <uuid> --neo4j-password "$NEO4J_PASSWORD"
```

## アクションアイテム

- [ ] 新セッション追加時にスクリプトを再実行する運用 (優先度: 低)

## 次回の議論トピック

- 会話履歴から既存のDiscussion/Decisionノードへの自動リンク
- セッション間の「続き」(CONTINUED_AS) リレーションの自動検出
- LLMによるセッション要約の自動生成
