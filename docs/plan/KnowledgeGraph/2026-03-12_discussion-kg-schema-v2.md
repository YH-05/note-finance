# 議論メモ: ナレッジグラフスキーマ v2 設計

**日付**: 2026-03-12
**参加**: ユーザー + AI

## 背景・コンテキスト

PDFパイプライン（PR #61）で8本のセルサイドレポートの変換が完了し、`data/processed/` にチャンクデータが蓄積された。次のステップとして、抽出情報をNeo4jナレッジグラフに蓄積するためのDB設計を議論した。

既存スキーマ v1.0 は6ノード・9リレーションの基本構造だったが、実データ（ISAT関連の7ブローカーレポート）を分析した結果、以下の課題が判明：
- チャンク（Lexical層）のノードが未定義
- 財務数値データ（テーブル）の構造化ノードが未定義
- Claim の型が4種のみで不十分
- AI による創発的分析の保存先がない

## 議論のサマリー

### ラウンド1: 初期設計レビュー
- `data/processed/` の実データ構造を分析
- Chunk, FinancialDataPoint, FiscalPeriod の追加を提案
- Recommendation を独立ノードとして提案 → **却下**

### ラウンド2: Claim-centric への転換（ユーザー修正①）
**ユーザー指摘**: 「必ずしも銘柄に対するrecommendationが書いてあるわけではない。セクターレポートやマクロ経済レポートを使うこともある」

→ Recommendation ノードを撤回し、Claim(claim_type: recommendation) に統合。
Claim.claim_type を10種に拡張し、セクターレポート・マクロレポートにも対応。

### ラウンド3: Fact/Claim 境界の厳密化 + AI創発支援（ユーザー修正②）
**ユーザー指摘2点**:
1. 「バリュエーションは予想と実績値があるため、厳密には事実とは言えないのでは？」
2. 「重要なのは、このneo4jデータベースからAIが創発的な考察を行ったり、特定の主張を裏付ける情報の特定、欠落している情報を推測することなどができるようになること」

→ 以下の設計修正:
- **Fact の厳密化**: 検証済み過去の客観的情報のみ（WACC等の前提はClaim:assumptionへ）
- **FinancialDataPoint.is_estimate**: 実績値/予想値を区別するフラグ
- **Insight ノード新設**: AI生成の分析結果（synthesis, contradiction, gap, hypothesis, pattern）
- **SUPPORTED_BY 強化**: strength/reasoning プロパティ追加
- **知識循環フロー**: 蓄積 → 連結 → 発見 → 創造 → 行動 → 蓄積

### ラウンド4: confidence プロパティの削除（ユーザー修正③）
**ユーザー指摘**: 「Fact/Claim の confidence（確信度）は AI によるスコアであり、モデル間で結果が変わるため実装しない方がいい」

→ 以下の設計修正:
- **Fact.confidence 削除**: AI 抽出時の確信度スコアはモデル依存で再現性がないため削除
- **Claim.confidence 削除**（Pydantic モデル）: 同上の理由で削除
- **Insight.confidence 削除**: Insight は AI 生成物だが、同じ理由で confidence スコア自体に信頼性がないため削除

## 決定事項

### D1: スキーマバージョン v2.0 採用
10ノード・15リレーションの Claim-centric スキーマを採用。

### D2: Fact の定義を厳密化
Fact = 検証済み過去の客観的情報のみ。バリュエーション前提（WACC, Beta等）は Claim(assumption) に分類。

### D3: Recommendation ノード不採用
独立ノードではなく Claim(claim_type: recommendation) で統一。セクター・マクロレポートとの互換性を確保。

### D4: Claim.claim_type を10種に拡張
opinion, prediction, recommendation, analysis, assumption, guidance, risk_assessment, policy_stance, sector_view, forecast

### D5: Fact.fact_type を8種に拡張
statistic, event, data_point, quote, policy_action, economic_indicator, regulatory, corporate_action

### D6: Entity.entity_type に country, instrument を追加
マクロレポート（国別分析）と金融商品（債券・デリバティブ）への対応。

### D7: FinancialDataPoint ノード追加（is_estimate フラグ付き）
テーブル数値データの構造化。is_estimate で実績/予想を区別。

### D8: FiscalPeriod ノード追加
レポート間の期間正規化（FY2025, 4Q25 等）。

### D9: Insight ノード追加
AI生成の分析結果を保存。5タイプ: synthesis, contradiction, gap, hypothesis, pattern。ステータス管理（draft→validated→archived）付き。

### D10: SUPPORTED_BY を強化
strength (strong/moderate/weak/circumstantial) と reasoning プロパティを追加。Insight からも利用可能。

### D11: Fact/Claim の confidence プロパティを削除
AI が出力する確信度スコアはモデル依存で再現性がなく、実用上の信頼性が低い。Fact.confidence、ExtractedClaim.confidence、Insight.confidence をすべて削除する。

## アクションアイテム

- [ ] `data/config/knowledge-graph-schema.yaml` から Fact.confidence, Insight.confidence を削除 (優先度: 高)
- [ ] `data/config/neo4j-pdf-constraints.cypher` を v2 スキーマに合わせて更新 (優先度: 高)
- [ ] `src/pdf_pipeline/schemas/extraction.py` の Pydantic モデルを v2 に更新 (優先度: 高)
- [ ] `scripts/emit_graph_queue.py` の pdf-extraction マッパーを v2 対応に更新 — Chunk/FinancialDataPoint/FiscalPeriod ノード追加、Fact/Claim 分離 (優先度: 高)
- [ ] PDFパイプライン Step 5 (pipeline統合) の実装 (優先度: 高)
- [ ] PDFパイプライン Step 6 (Neo4j投入) の実装 — save-to-graph スキル活用 (優先度: 高)
- [ ] 既存 Neo4j データ（Source 693件, Claim 686件, Entity 70件）の v2 マイグレーション方針策定 (優先度: 中)
- [ ] Insight ノードの生成ロジック設計 (優先度: 中)
- [ ] 既存8レポートの再処理（v2スキーマでの抽出） (優先度: 中)

## 次回の議論トピック

- Insight 生成のトリガー設計（手動 vs 自動 vs ハイブリッド）
- マスターエンティティの名寄せ戦略（Indosat/ISAT/Indosat Ooredoo Hutchison の統合）— Entity.is_master / SUBSIDIARY_OF のスキーマ反映含む
- graph-queue JSON フォーマットの v2 対応 — Fact/FinancialDataPoint/Chunk/Insight の表現方法
- Author / Topic ノードの v1→v2 変更点の確認
- CONTRADICTS リレーション vs Insight(contradiction) の使い分け方針
- 抽出プロンプトの claim_type 分類精度向上

## 参考情報

- PDFパイプライン PR: #61
- 処理済みレポート: data/processed/ (7ブローカー, 8 PDF)
- 対象銘柄: ISAT (Indosat Ooredoo Hutchison)
- スキーマ SSoT: data/config/knowledge-graph-schema.yaml
