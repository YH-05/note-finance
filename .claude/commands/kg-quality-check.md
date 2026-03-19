---
description: KG品質計測（LLM-as-Judge accuracy評価込み）
skill: kg-quality-check
---

research-neo4j のナレッジグラフ品質を計測してください。

1. 6カテゴリ（accuracy以外）を Python スクリプトで計測
2. Claude Code 自身が LLM-as-Judge として Fact/Claim の accuracy を3軸評価
3. 全7カテゴリ統合スナップショットを保存
4. 前回比較・アラート・レポート出力

$ARGUMENTS
