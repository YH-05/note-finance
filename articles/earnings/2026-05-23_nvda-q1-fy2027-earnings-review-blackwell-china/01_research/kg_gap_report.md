# KGギャップ分析レポート

**対象トピック**: NVIDIA Q1 FY2027決算レビュー：Blackwellガイダンスと中国データセンターのゼロ前提を読み解く
**実行日**: 2026-05-23

## 既存KGデータサマリー

| 項目 | 件数 |
|------|------|
| NVIDIA関連 Entityノード | 5 (Company: NVIDIA/Nvidia, Technology: NVIDIA Blackwell/NVIDIA Kyber, Concept: Nvidia Earnings Article) |
| Fact (RELATES_TO Nvidia) | 30件以上（ほぼ全てが2026-01-28〜29の市場全体・M7関連） |
| Claim (statement有り) | 限定的（M7全体・Indonesia系・Open RAN系が中心、NVDA固有はほぼ無し） |
| FinancialDataPoint | 多数あるがmetric/period/fiscal_periodが全てnull（メタデータ欠落） |

## ギャップ一覧（優先度別）

### HIGH

1. **stale_data**: NVIDIA関連の最新Source published_atが**2026-01-29**で、本日(2026-05-23)時点で4ヶ月超のギャップ
2. **missing_q1_fy2027_actuals**: 2026-05-20発表のQ1 FY2027実績（売上・EPS・Data Center売上・Gaming/Auto売上・粗利益率）が全くKGに無い
3. **missing_china_data**: H20など中国向けデータセンター売上のゼロ前提シナリオに関するファクト無し
4. **missing_blackwell_ramp**: Blackwell（GB200/GB300）の出荷状況・顧客内訳・歩留まりに関する2026年5月時点の最新情報無し

### MEDIUM

5. **missing_q2_fy2027_guidance**: NVIDIAが発表したQ2 FY2027売上ガイダンス（中央値・レンジ）が無い
6. **fdp_metadata_gap**: 既存のFinancialDataPointは metric/period/fiscal_period が null で、活用しにくい
7. **missing_competitor_dynamics**: AMD MI350系・Broadcom ASIC事業の最新進捗 vs NVDAの相対ポジション

## ギャップ解消用の推奨検索クエリ

| クエリ | 目的 | 優先度 |
|--------|------|--------|
| "NVIDIA Q1 FY2027 earnings revenue data center" | 売上・セグメント別実績 | HIGH |
| "NVIDIA Q1 FY2027 EPS gross margin" | 収益性指標 | HIGH |
| "NVIDIA Q2 FY2027 guidance Blackwell" | 次四半期ガイダンス | HIGH |
| "NVIDIA China H20 revenue zero May 2026" | 中国ゼロ前提の影響 | HIGH |
| "Blackwell GB200 GB300 ramp customers May 2026" | Blackwell出荷状況 | MEDIUM |
| "NVIDIA conference call transcript May 20 2026" | 経営陣コメント | HIGH |
| "NVDA stock reaction after earnings May 2026" | 株価反応・アナリスト評価 | MEDIUM |
