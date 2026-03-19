# 議論メモ: article-research への KG ギャップ分析・永続化統合

**日付**: 2026-03-19
**参加**: ユーザー + AI

## 背景・コンテキスト

article-research コマンドは記事執筆ワークフローのリサーチフェーズを担当するが、これまで research-neo4j に蓄積された既存データを活用していなかった。リサーチのたびにゼロから検索を行うため、既に KG に存在するファクトやクレームとの重複が発生し、情報ギャップの特定も体系的に行えていなかった。

## 議論のサマリー

research-neo4j の既存データを活用してリサーチの質と効率を向上させるため、article-research コマンドに以下の2つのフェーズを追加した:

1. **Phase 0（KG照会+ギャップ分析）**: リサーチ前に research-neo4j を照会し、5観点で情報ギャップを特定
2. **Phase 5（KG永続化）**: リサーチ結果を標準パイプライン（emit_graph_queue.py → save-to-graph）経由で Neo4j に保存

## 決定事項

1. **Phase 0/5 を全カテゴリ共通で追加**: stock_analysis, macro_economy, quant_analysis, investment_education, asset_management, side_business, market_report の全カテゴリで KG 統合を適用
2. **5種のギャップ検出**:
   - `stale_data`: 最新ソースが30日以上前
   - `missing_bear_case` / `missing_bull_case`: センチメント偏り
   - `no_coverage`: 必要エンティティのファクト/クレームが0件
   - `open_questions`: 未回答 Question ノード存在
   - `missing_financials`: company/etf/index の FinancialDataPoint が0件
3. **検索予算のギャップ解消/通常リサーチ配分**: standard 深度で 12-18回のうち 6-10回をギャップ解消に割り当て
4. **グレースフルデグラデーション**: Neo4j 未起動時は Phase 0/4 をスキップし、入力 JSON を保持して後から投入可能
5. **標準パイプライン準拠**: neo4j-write-rules.md の直書き禁止ルールに従い、emit_graph_queue.py → save-to-graph 経由でのみ投入

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `.claude/skills/investment-research/references/kg-gap-analysis.md` | **新規**: Cypher クエリテンプレート集（6クエリ + 5観点ギャップ判定 + KG永続化ルール） |
| `.claude/skills/investment-research/SKILL.md` | Phase 0/5 追加、--skip-kg パラメータ、検索予算配分 |
| `.claude/commands/article-research.md` | Step 0/4 追加、全カテゴリ共通 KG 統合、Neo4j 未起動時フォールバック |

## アクションアイテム

- [ ] 実際の記事（例: boj-rate-hike-yen-structural-analysis）で動作確認 (優先度: 高)
- [ ] asset_management / side_business / market_report の委譲先スキルへの KG 統合検討 (優先度: 中)

## 次回の議論トピック

- KG ギャップ分析の精度評価（実際の記事での有効性検証後）
- Question ノードの自動 status 更新フロー（現状はユーザー承認必須）
