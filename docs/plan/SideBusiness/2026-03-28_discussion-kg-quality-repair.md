# 議論メモ: KGクオリティチェックと決定論的修復

**日付**: 2026-03-28
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j のナレッジグラフ品質が低下しており、`/kg-quality-check` でフルスキャンを実施。
その後、LLMや新規データ収集を使わず「既存データだけで決定論的に修復できる範囲」を特定・実行した。

## 議論のサマリー

### Phase 1: KG品質スキャン（`/kg-quality-check`）

実施結果（修復前のベースライン）:

| カテゴリ | スコア | 問題 |
|---------|--------|------|
| structural | 60.0 | Connected Ratio 低下、孤立ノード増加 |
| consistency | 16.7 | entity_type違反 22%、Constraint Violations 34件 |
| completeness | 62.7 | fact_type欠落 1,393件、content欠落 393件 |
| accuracy (LLM) | 0.428 | Source Grounding 低め（計測バグあり） |
| timeliness | 75.0 | - |
| finance_specific | 66.7 | - |
| discoverability | 50.0 | - |
| **Overall** | **~53** | consistency/structural が足を引っ張り |

**創発的発見スコア**: 0.666（3件の仮説を生成）
- アジア通貨政策 → 半導体需要の波及連鎖仮説
- 米国規制 vs 中国企業 対立構造の分析
- エネルギー転換期の炭素クレジット市場ギャップ

### Phase 2: 決定論的修復の分析と実行

「LLM不使用・既存データのみ」で実行可能な修復を特定・実施:

| 修復項目 | 件数 | 手法 |
|---------|------|------|
| Claim → Source MAKES_CLAIM リレーション補完 | 590件 | source_idプロパティからMERGE |
| Entity → EntityType IS_TYPE リレーション補完 | 577件 | entity_typeプロパティからMERGE |
| Fact fact_type プロパティ同期（IS_FACT_TYPEから） | 447件 | IS_FACT_TYPEリレーションのターゲット名を転写 |
| Entity entity_id UUID生成 | 34件 | randomUUID()でNULL補完 |
| entity_type 正規化（69種 → 10種標準） | 349件 | CASE WHEN マッピング |
| fact_type キーワード分類（欠落1,393件） | 1,393件 | コンテンツキーワードマッチ優先ルール |
| Legacy fact_type 正規化 | 589件 | 旧表記 → 標準10種マッピング |
| Fact → FactType IS_FACT_TYPE 補完 | 1,405件 | fact_typeプロパティからMERGE |

**修復後スコア（推定）**:
- consistency: 16.7 → 83.3（entity_type正規化 + UUID生成）
- structural: 60.0 → 80.0（IS_FACT_TYPE補完でリレーション増加）
- completeness: 62.7 → ~80+ （fact_type補完で大幅改善）

## 決定事項

1. **決定論的修復アプローチの確立** (`dec-2026-03-28-kg-repair-deterministic`)
   - KG修復は「決定論的（既存データのみ）」と「確率論的（LLM/新規収集必要）」に分離する
   - 決定論的修復は毎回のKGメンテナンスで即実行可能
   - 確率論的修復は別途計画・リソース確保が必要

2. **fact_typeキーワード分類ポリシー** (`dec-2026-03-28-fact-type-keyword-classification`)
   - fact_type欠落はCypher CASE WHENのキーワードマッチで自動分類する（LLM不使用）
   - 優先順位: financial_metric → market_data → macro_indicator → regulatory → risk → empirical → methodology → event → strategic → statistic → HTMLノイズ(skip) → デフォルトempirical
   - 標準10種: empirical, event, financial_metric, macro_indicator, market_data, methodology, regulatory, risk, statistic, strategic

3. **entity_type正規化マッピング** (`dec-2026-03-28-entity-type-normalization`)
   - research-neo4jに69種の不統一entity_typeが存在していた
   - metric→indicator, model→technology, market→index, country→organization, company→companyなど統一ルールを策定
   - 今後の投入時は標準25種のALLOWED_ENTITY_TYPESに準拠する

## アクションアイテム

- [ ] Fact→Entity RELATES_TO リレーション 1,054件補完（優先度: 高）
  - LLMによるエンティティ抽出バッチ処理が必要
  - `act-2026-03-28-002`
- [ ] 孤立Fact 361件の修復（優先度: 中）
  - Source未発見のため新規データ収集または手動登録が必要
  - `act-2026-03-28-001`
- [ ] content欠落Fact 393件の修復（優先度: 中）
  - ソースから再取得またはChunkから内容補完
  - `act-2026-03-28-003`
- [ ] `kg_quality_metrics.py` Source Grounding計測バグ修正（優先度: 中）
  - `EXTRACTED_FROM`パスと`MAKES_CLAIM`パスを正しく計測するよう修正
  - `act-2026-03-28-005`
- [ ] entity_name長さ違反 109件の精査（優先度: 低）
  - 256文字超エンティティを手動レビューして短縮またはマージ
  - `act-2026-03-28-004`
- [ ] Probe B（間接接続パス）クエリタイムアウト解消（優先度: 低）
  - 4ホップMATCHをインデックス活用または段階的クエリに最適化
  - `act-2026-03-28-006`

## 次回の議論トピック

- Fact→Entity RELATES_TO補完のLLMバッチ処理設計（並列化・コスト見積もり）
- 決定論的修復スクリプトの自動化（定期メンテナンスcronジョブ化）
- discoverability スコア向上策（Insight・Stance・CrossDomainリンク強化）

## 参考情報

### 修復前後スコア比較

```
consistency:  16.7 → 83.3  (+66.6)
structural:   60.0 → 80.0  (+20.0)
completeness: 62.7 → ~80.0 (+~17.0)
```

### キーノード (note-neo4j)

- Discussion: `disc-2026-03-28-kg-quality-repair`
- Decisions: `dec-2026-03-28-kg-repair-deterministic`, `dec-2026-03-28-fact-type-keyword-classification`, `dec-2026-03-28-entity-type-normalization`
- ActionItems: `act-2026-03-28-001` ～ `act-2026-03-28-006`

### 生成ファイル

- `data/processed/kg_quality/accuracy_cache.json` — LLM-as-Judge評価結果（20件、平均0.428）
- `data/processed/kg_quality/discovery_report_20260328.json` — 創発的発見レポート（スコア0.666）
- `data/processed/kg_quality/report_20260328.md` — フル品質レポート
