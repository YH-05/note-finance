# 議論メモ: topic-discovery への KG トピック発掘統合

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

article-research への KG ギャップ分析統合に続き、topic-discovery にも同様の research-neo4j 参照機能を追加。topic-discovery は既に Phase 5.3 で Neo4j に書き込んでいたが、読み取り参照はしていなかった。また Phase 5.3 は Cypher 直書き（`docker exec cypher-shell`）で neo4j-write-rules.md に違反していた。

## 議論のサマリー

3点の改善を一括で実装:
1. Phase 0（KGトピック発掘）の追加
2. スコアリングへの KG データ補正導入
3. Phase 5.3 のパイプライン準拠化

## 決定事項

1. **Phase 0 追加**: 8つのCypherクエリで KG をマイニングし、4種のトピック候補を生成
   - Knowledge Gap Topics（未回答Question + Insight gap）
   - Underexplored Entity Topics（薄カバレッジ Entity）
   - Trending Entity Topics（ソース急増）
   - Controversy Topics（センチメント拮抗）

2. **KG データ補正付きスコアリング**:
   - Information Availability: Fact >= 10件 & Claim >= 5件 → +2点
   - Uniqueness: KG由来トピック → +2点、Controversy → +1点
   - KG Gap Score ボーナス: 8-10 → +3点、5-7 → +2点、3-4 → +1点

3. **Phase 5.3 パイプライン準拠化**: `docker exec cypher-shell` → `emit_graph_queue.py → /save-to-graph`

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `references/kg-topic-mining.md` | **新規**: 8クエリテンプレート + 4種候補生成ロジック |
| `SKILL.md` | Phase 0追加、Phase 3 KG補正、Phase 5.3 パイプライン移行、`--skip-kg` パラメータ |
| `references/scoring-rubric.md` | KGデータ補正ルール（IA/Uniqueness補正 + KG Gap Scoreボーナス） |
| `references/neo4j-mapping.md` | Cypher直書き → emit_graph_queue + save-to-graph パイプラインに移行 |

## アクションアイテム

- [ ] /finance-suggest-topics でPhase 0の動作確認 (優先度: 高)
- [ ] emit_graph_queue.py の topic-discovery コマンド対応検証 (優先度: 中)

## 次回の議論トピック

- article-research と topic-discovery の KG 統合を他スキル（reddit-finance-topics, competitor-analysis）にも拡張するか
- KG Gap Score の実効性評価（実際のトピック提案での有効性）
