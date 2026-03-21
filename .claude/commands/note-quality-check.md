---
description: note-neo4j (bolt://localhost:7687) の品質チェックを実行
---

# note-quality-check

note-neo4j のデータ品質を6カテゴリ + LLM-as-Judge で計測・評価します。

## スキル参照

`.claude/skills/note-quality-check/SKILL.md` を読み込み、全フェーズを順に実行してください。

## 実行手順

1. **Phase 1**: 6カテゴリの Cypher プローブを `mcp__neo4j-note__note-read_neo4j_cypher` で実行
   - Completeness（完全性）
   - Consistency（一貫性）
   - Orphan検出（孤立ノード）
   - Staleness（鮮度）
   - Structural（構造）
   - DocSync（ドキュメント連携）

2. **Phase 2**: LLM-as-Judge で Decision/ActionItem の整合性を評価

3. **Phase 3**: 総合スコアと改善提案を含む Markdown レポートを出力

## 注意

- 全ての Cypher は `mcp__neo4j-note__note-read_neo4j_cypher`（読み取り専用）で実行
- `mcp__neo4j-note__note-write_neo4j_cypher` は使用禁止
- research-neo4j (port 7688) のツールは使用しない
