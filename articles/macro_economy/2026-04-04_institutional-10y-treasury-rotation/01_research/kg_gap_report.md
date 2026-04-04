# KGギャップ分析レポート

**日時**: 2026-04-04  
**トピック**: 機関投資家が10年国債に大量シフト ─ COTデータが示す景気後退シグナルの読み方

## 既存データサマリー

| 項目 | 件数 |
|------|------|
| 関連Entityノード | 5件（US Treasury, 日本10年国債, 米国10年国債, 米10年国債金利 等） |
| 関連Factノード | 7件（米国債利回りスナップショット、2-10年スプレッド等） |
| 関連Claimノード | 10件（大半はBessent財務長官関連・SHY ETF等） |
| ソース数 | 不明（published_at = null が多数） |

## 特定ギャップ一覧

| 優先度 | ギャップ種別 | 内容 |
|--------|------------|------|
| HIGH | no_coverage | **COTデータ（Commitment of Traders）に関するFact/Claimが皆無**。機関投資家・ヘッジファンド・ディーラーのポジションデータなし |
| HIGH | no_coverage | **機関投資家の10年国債大量シフト**に関するファクト未収録 |
| HIGH | stale_data | 既存Factの `published_at` がすべてnull。データ鮮度が不明 |
| HIGH | open_questions | T10Y2Y（イールドカーブ逆転）の最新数値がKGに存在しない |
| MEDIUM | missing_bear_case | 景気後退シグナルとしてのCOT解釈のbearish/bullishバランスなし |
| MEDIUM | no_coverage | COT報告書の構造（Large Speculators/Commercial/Non-Commercial）の解説データなし |
| MEDIUM | missing_financials | FRED系列 DGS10, DGS2, T10Y2Y の最新数値未収録 |

## ギャップ解消用の推奨検索クエリ

1. `COT report 10-year Treasury 2025 2026 institutional positioning`
2. `Commitment of Traders Treasury futures net position recession signal`
3. `10-year Treasury yield institutional buying 2026 flight to safety`
4. `T10Y2Y yield curve inversion recession predictor historical`
5. `CFTC COT data bonds large speculators commercial hedgers`
6. `機関投資家 米国債 ポジション 2025 2026`
7. `フライトトゥクオリティ 10年債 景気後退`
8. `yield curve recession signal COT institutional flow 2026`
