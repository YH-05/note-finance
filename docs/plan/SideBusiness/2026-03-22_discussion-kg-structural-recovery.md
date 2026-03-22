# 議論メモ: KG構造品質回復・再発防止・情報ギャップ定義

**日付**: 2026-03-22
**参加**: ユーザー + AI

## 背景・コンテキスト

前日（3/21）に42本の論文を一括投入した結果、KG品質スコアが60.7→51.8に悪化。構造品質回復、根本原因分析、再発防止策の実装、および情報ギャップ判定の体系化を実施。

## 実施内容

### 1. 構造品質回復（3施策）

| 施策 | 結果 |
|------|------|
| Orphan Entity接続 | 342→254（-88）、+202 RELATES_TO |
| マルチタイプEntity統合 | 21ノード削除（FinBERT, Goldman Sachs, Bitcoin等19エンティティ） |
| 弱接続Source補強 | +977リレーション、94 Source改善 |

### 2. 根本原因分析

4つの原因を特定:
1. **save-to-graph Phase 3a で fact_entity RELATES_TO が欠落** — Entity MERGEは成功したがリレーション投入がスキップ/失敗（234件）
2. **academic-fetch と pdf-to-knowledge の Source 二重投入** — 同一論文に2つのSource、Author↔Fact断絶
3. **Person Entity（著者）64件の孤立** — Author ノードとは別にEntityとして作成
4. **直接MCP writeの20件** — リレーション未作成

### 3. 再発防止策（3つ実装完了）

| 再発防止策 | 修正内容 |
|-----------|---------|
| save-to-graph Phase 3c検証 | 期待値vs実績の3段階判定（OK/WARNING/ERROR）、E006エラー定義 |
| Source重複統合 | 既存2件統合 + academic-fetch.mdに推奨ワークフロー追記 |
| Orphanアラート | kg_quality_metrics.pyに閾値50(WARN)/200(CRIT)追加 |

### 4. 情報ギャップ定義

**議論**: 「何をもって情報ギャップを判断するか」

従来の判定方法（Insightノード、構造プローブ、定量指標）は**体系的でない**。「あるべき姿」の定義がなかった。

**決定**: L1（検出のみ）+ L2（YAML定義）を統合して1つの `entity-completeness-schema.yaml` を作成。
- equity-stock-research 7フェーズから共通必須データ17項目を導出
- セクター別KPI 7セクター（Telecom, SaaS, 半導体, 銀行, エネルギー, 小売, REIT）
- 重み付きスコアリング（high=3, medium=2, low=1）

**評価結果**:
- Indosat Ooredoo Hutchison: 0.52（14/24項目）
- 共通ギャップ: Revenue/EBITDA/ARPUはFact.contentに存在するが**FinancialDataPointとして未構造化**

### 5. NASデータ書き戻し

`/tmp/neo4j-research-data` → `/Volumes/NeoData/neo4j-research/data` にrsync完了（533MB）。NASマウント問題は未解決（Docker Desktop + APFS外部ボリューム）。

## 決定事項

1. **情報ギャップはentity-completeness-schema.yamlで体系的に判定** — L1(検出のみ)+L2(フェーズベース)の統合
2. **FinancialDataPoint構造化が次の本質的課題** — Fact→FinancialDataPoint抽出パイプラインが必要

## アクションアイテム

- [ ] **[High]** Fact→FinancialDataPoint自動抽出パイプライン実装 (act-2026-03-22-010)
- [ ] **[Medium]** kg_entity_completeness.pyをkg-quality-checkに統合 (act-2026-03-22-011)
- [x] **[High]** NASデータ書き戻し (act-2026-03-21-009) — 完了

## 次回の議論トピック

- Fact→FinancialDataPoint抽出パイプラインの設計方針
- entity-completeness-schema.yamlのセクター定義拡張（テレコム以外の実データ検証）
- 残留Orphan Entity 254件の対処（fuzzyマッチング or 手動レビュー）

## 作成ファイル

| ファイル | 説明 |
|---------|------|
| `data/config/entity-completeness-schema.yaml` | Entity完備性スキーマ（7フェーズ共通 + 7セクターKPI） |
| `scripts/kg_entity_completeness.py` | 完備性評価スクリプト（CLI対応） |
