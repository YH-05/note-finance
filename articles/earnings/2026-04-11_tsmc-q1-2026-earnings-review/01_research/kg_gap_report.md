# KGギャップ分析レポート — TSMC Q1 2026決算レビュー

**生成日**: 2026-04-11  
**対象銘柄**: TSM / 2330.TW  

---

## 既存データサマリー（research-neo4j）

| 項目 | 件数 |
|------|------|
| エンティティ（Company: TSMC） | 1件 |
| Fact（TSMCに関連） | 5件 |
| Claim（TSMCに関連） | 3件 |
| ソース | 未確認（published_at=null） |

### 既存Factの内容
1. 世界半導体売上が2026年に初めて$1Tを突破（AI需要集中型）
2. TSMC 2026 Capex見通し引き上げ。NVIDIA/AMDからのAIアクセラレーター需要。ASML時価総額5,000億ドル超
3. TSMC FY2025通期売上高$122B。AI accelerator 5年CAGRをmid-to-high 50%（2024-2029）に上方修正
4. TSMC FY2026通期売上高は前年比約30%増（USD建）を見込む。Q1 2026ガイダンス$34.6B-$35.8B（前年同期比+38%）
5. TSMC FY2026設備投資は$52B-$56B（70-80%が先端プロセス向け）。Arizonaフラブ2棟目は2026年ツール移設開始、2027年H2に高量産開始予定

### 既存Claimの内容
1. Stratechery 2026 TSMC Riskレポート（センチメント: -0.4 / bearish寄り）
2. Advanced PackagingおよびN3/N2の供給制約継続 → 価格決定力維持可能（bullish）
3. NVIDIA GTC 2026分析：推論専用チップとGroq技術が変えるAI半導体（neutral）

---

## ギャップ分析

### HIGH優先度

| ギャップ種別 | 詳細 | 推奨クエリ |
|------------|------|-----------|
| stale_data | 全FactのQ1 2026実績データが未投入 | "TSMC Q1 2026 revenue results April 2026" |
| no_coverage: Q1 actual | Q1 2026実績（売上・EPS・粗利益率）がKG未投入 | "TSMC Q1 2026 earnings actual NT dollar" |
| no_coverage: Iran war | イラン戦争サプライチェーン影響ファクトが不在 | "TSMC Iran war supply chain Taiwan 2026" |

### MEDIUM優先度

| ギャップ種別 | 詳細 | 推奨クエリ |
|------------|------|-----------|
| missing_bear_case | 1件のbearish claim（Stratechery）以外リスク論点が薄い | "TSMC risks geopolitical 2026 analyst" |
| missing_financials: Q1 2026 EPS | EPS実績・アナリスト予想が未投入 | "TSMC Q1 2026 EPS estimate analyst consensus" |
| open_questions: 60% CAGR | mid-to-high 50%→60%へのアップデート有無不明 | "TSMC AI accelerator CAGR 60% 2026 updated" |

---

## ギャップ解消状況

Webリサーチにより以下を解消:
- ✅ Q1 2026売上実績（NT$1,134.1B / +35.1% YoY）
- ✅ 60% CAGR vs "mid-to-high 50%"の実態把握
- ✅ Arizona Fab 21 Phase 2タイムライン
- ✅ Kumamoto（JASM Phase 2）タイムライン
- ✅ イラン戦争のサプライチェーン影響
- ⬜ Q1 2026 EPS実績（4/16発表待ち）
- ⬜ Q2 2026ガイダンス（4/16発表待ち）
