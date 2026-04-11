# KGギャップ分析レポート

**記事**: JPMorgan Chase Q1 2026決算プレビュー
**生成日**: 2026-04-11
**対象期間**: Q1 2026（2026-01-01 ～ 2026-03-31）

---

## 既存データサマリー（research-neo4j）

| 項目 | 件数 | 詳細 |
|------|------|------|
| Company ノード | 1件 | JPMorgan (ticker: JPM, sector: Financials) |
| Fact ノード | 3件 | FY2025財務サマリー、AI支出、調整予想 |
| Claim ノード | 3件 | JPST流入、アジア株IPO、Dimon不安発言 |
| Source ノード | 3件 | CNBC x2、Yahoo Finance x1 |
| 最新Source | 2026-01-29 | （約73日前） |

---

## 特定ギャップ一覧

| ギャップ種別 | 判定根拠 | 優先度 | 解消状況 |
|------------|---------|--------|---------|
| stale_data | 最新ソース2026-01-29（73日前） | HIGH | ✅ 解消済み |
| no_coverage | Q1 2026プレビューデータが0件 | HIGH | ✅ 解消済み |
| open_questions | NII/IBフィー/カード延滞/PCL/Dimonコメント | HIGH | ✅ 解消済み |
| missing_bear_case | bullish系のみ、bearish claim 1件のみ | MEDIUM | ✅ 部分解消 |
| missing_financials | Q1 2026四半期FDPが0件 | MEDIUM | ✅ 解消済み（予想値） |

---

## ギャップ解消状況

### 解消済み（HIGH優先度）
- **stale_data**: Reuters/CNN/CNBC/NYT等の直近2週間記事を取得（2026-04-06〜09）
- **no_coverage**: Q1 2026 EPSコンセンサス$5.44、NII成長率+8.54%等を取得
- **open_questions**:
  - NII: 2026通期ガイダンス$103B確認（Q4発表済み）
  - IBフィー: 2月に「strong growth」見通し確認
  - カード延滞: net charge-off ~3.4%（ガイダンス維持）
  - Dimon: イラン戦争→インフレ/金利上昇リスク警告（4/7株主書簡）

### 部分解消（MEDIUM優先度）
- **missing_bear_case**: Dimon警告・クレジット正常化・株価下落要因を追加取得
- **missing_financials**: Q1予想値（EPS $5.44、NII +8.54%）を追加。実績は4/14発表予定

---

## 残存ギャップ

| ギャップ | 内容 | 対処方針 |
|---------|------|---------|
| Q1 2026実績 | 4/14発表予定のため取得不可 | 記事はプレビューとして記述 |
| トレーディング収益詳細 | Q1のマーケット部門詳細 | 2月ガイダンス「strong growth」で代替 |
| PCL/引当金詳細 | Q1予想引当額 | カードCO率3.4%ガイダンスで代替 |
