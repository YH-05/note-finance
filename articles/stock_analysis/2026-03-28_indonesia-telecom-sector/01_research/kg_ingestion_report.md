# KG投入レポート

## セッション: article-research-indonesia-telecom-sector-20260328
## 投入日時: 2026-03-28T20:21:00+09:00

## 投入結果

| ノードタイプ | 件数 | 新規 | 既存更新 |
|------------|------|------|---------|
| Topic | 4 | 0 | 4 |
| Entity | 9 | 2 (InfraNexia, XLSmart) | 7 |
| Source | 18 | 18 | 0 |
| Fact | 20 | 20 | 0 |
| Claim | 0 | - | - |
| FinancialDataPoint | 0 | - | - |

| リレーションタイプ | 期待値 | 実績値 | 判定 |
|-------------------|--------|--------|------|
| STATES_FACT (Source→Fact) | 20 | 20 | OK |
| RELATES_TO (Fact→Entity) | 23 | 23 | OK |
| EXTRACTED_FROM (Fact→Source) | 20 | 20 | OK |
| TAGGED (Source→Topic) | 72 | 72 | OK |
| TAGGED (Fact→Topic) | 80 | 80 | OK |

**総合判定**: OK（全リレーション一致）

**注記**: entity_id/topic_id の不一致を entity_key/topic_key ベースのMERGEで解決
- Telkomsel: entity_id `ent-telkomsel`（既存）
- XLSmart: entity_id `ent-xlsmart`（既存）
- Indonesian Telecom: topic_id `3f4f0f03-...`（既存）
- ASEAN Telecom: topic_id `asean-telecom-sector`（既存）

## ギャップ解消状況

| ギャップ | 解消 | 備考 |
|---------|------|------|
| stale_data | ✓ | FY2024/FY2025/Q1 2025 財務データ投入 |
| no_coverage (FREN) | ✓ | XLSmart合併情報で補完 |
| missing_financials | △ | Factとして財務データ投入。FinancialDataPoint未作成 |
| missing_bear_case | △ | リサーチノートに6つのベア要因記載。Claimノード未作成 |
| no_coverage (EXCL) | ✓ | XLSmart/XL Axiata財務データ投入 |
| no_coverage (TOWR claims) | △ | TBIG Factのみ。TOWRの具体的財務データは残存ギャップ |
