# KG ギャップ分析レポート: BlackRock Q1 2026 決算レビュー

> 作成日: 2026-04-14 JST
> 対象: research-neo4j (bolt://localhost:7687)
> キーワード: BlackRock, BLK, AUM, 資産運用, Private Credit, iShares

## 1. 既存データサマリー

| 項目 | 件数 | 備考 |
|-----|-----|-----|
| Company (BlackRock) | 1 | ticker=BLK, entity_key=null |
| Fact (→BlackRock) | 2 | statement が null（旧スキーマ移行時の欠損） |
| Claim (→BlackRock) | 2 | sentiment: positive 1 / -0.4 数値 1（形式不統一） |
| Source (→BlackRock) | 3 | CNBC×2, Reddit×1、published_date 全て null |
| FinancialDataPoint | 0 | **決算数値の構造化データなし** |
| 関連 Topic | 5 | Asset Management Industry, Alternative Asset Managers, LLM in AM, 個人資産運用, BlackRock private credit 解約 |
| 未回答 Question | 0 | Question ノードに BLK 関連なし |

## 2. 特定されたギャップ

| # | ギャップ種別 | 優先度 | 詳細 |
|---|------------|-------|-----|
| G1 | stale_data | HIGH | Source 3件すべて published_date が null。実質的に鮮度判定不能。CNBC記事は URL から 2026-01 推定 |
| G2 | missing_financials | HIGH | FinancialDataPoint 0件。AUM/Revenue/EPS 等の時系列数値が未蓄積 |
| G3 | no_coverage | HIGH | Q1 2026 決算（本記事の対象期）に関するソース・ファクトが既存KGに皆無 |
| G4 | missing_claim_schema | MEDIUM | 既存 Claim の sentiment が "positive" と -0.4 で形式不統一。schema restructure が必要 |
| G5 | fact_content_missing | MEDIUM | Fact の statement フィールドが null。旧スキーマ移行の欠損データ |

## 3. ギャップ解消状況（Phase 2 リサーチ後）

| ギャップ | 解消状況 | 寄与ソース数 |
|---------|---------|-------------|
| G1 stale_data | ⚠ 部分解消（決算発表前のため最新情報は限定的） | 16件 |
| G2 missing_financials | ✅ 解消予定（Q4 2025 実績をKG投入） | official 3件（BlackRock IR PDF） |
| G3 no_coverage | ⚠ 発表待ち（21:30 JST 以降に Q1 実績を追加リサーチ） | — |
| G4 missing_claim_schema | ❌ 既存データの修正は本記事の範囲外 | — |
| G5 fact_content_missing | ❌ 既存データの修正は本記事の範囲外 | — |

## 4. 推奨検索クエリ（決算発表後）

21:30 JST 以降、以下のクエリで Q1 2026 実績をギャップ補完:

1. `"BlackRock" "Q1 2026" AUM results` — site:blackrock.com, site:reuters.com
2. `BLK Q1 2026 earnings beat miss EPS` — Bloomberg, WSJ, CNBC
3. `BlackRock HPS private credit redemption Q1 2026` — Bloomberg, FT
4. `site:sec.gov BlackRock 8-K 2026-04` — 実績 8-K
5. `BlackRock Larry Fink Q1 2026 commentary guidance` — 決算カンファレンスコメント

## 5. 本記事向けのKG投入方針

- **今回投入**: Q4 2025 実績（AUM $14.04T、EPS $13.16、純流入 $342B）＋ コンセンサス予想 4件を `Fact` として投入
- **発表後投入**: Q1 2026 実績・市場反応・経営陣コメントを別セッションで追加投入（session_id: `article-research-blk-earnings-review-2026q1-update-YYYYMMDD`）
- **authority_level 分布**: official 3, analyst 4, media 8, filing_index 1
