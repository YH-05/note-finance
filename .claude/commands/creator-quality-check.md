---
description: creator-neo4j品質計測（LLM-as-Judge コンテンツ品質評価込み）
skill: creator-quality-check
---

creator-neo4j のナレッジグラフ品質を計測してください。

1. 7カテゴリ（Completeness, Consistency, Structural, Orphan, Content Balance, Source Quality, Taxonomy）を Cypher プローブで計測
2. Claude Code 自身が LLM-as-Judge として Fact/Tip/Story のコンテンツ品質を3軸評価
3. Concept → ConceptCategory の分類適切性を評価
4. スナップショット保存・前回比較・レポート出力

$ARGUMENTS
