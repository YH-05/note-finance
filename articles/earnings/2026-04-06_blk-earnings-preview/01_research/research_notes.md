# BLK 決算プレビュー リサーチノート

## データソース一覧

### ヘルパースクリプト出力
- `blk_reaction.json`: 直近8四半期のEPSサプライズ + 株価反応 + リターン
- `blk_8k.json`: 直近6四半期の8-K EX-99.1 ハイライト

### quants SQLite DB
- nc_earnings_calendar: 4/14 BMO, EPS予想 $12.16, FQ Mar/2026
- av_company_overview: 時価総額 $150.3B, PER 27.4, Forward PE 18.02, EPS $35.28, 配当 $20.84 (2.18%), Beta 1.493
- se_financial_statements: FY2025 Revenue $24.2B, NI $5.9B / Q3 2025 Revenue $6.5B, NI $1.5B

### Web検索結果

**カタリスト:**
- Q1 2025実績: Adjusted EPS $11.30 (Zacks $10.43をビート), Revenue $5.3B (+12% YoY)
- FY2025: 記録的AUM $14T, 純流入 $698B
- GIP/HPS/Preqin統合による統一プラットフォーム化（2026年が初の通年）
- 暗号資産ETFモメンタム（Bitcoin ETF $123B, XRP ETFの投機的関心）
- BofA目標株価 $1,467、Deutsche Bank $1,380

**アナリストコンセンサス (2026年3月時点):**
- 90%のカバーアナリストが強気
- コンセンサス目標株価 $1,300
- Argus: 強気維持、EPS予想引き上げ
- Morningstar: 中立、目標株価引き上げ

**リスク要因:**
- 関税政策の市場影響
- 市場のボラティリティ・集中リスク
- 地政学的不確実性
- 2月に株価 -4.89%下落

**乖離パターン（blk_reaction.jsonから）:**
- 2025 Q3: EPS -21.4%ミス → 株価 +4.1% → 原因: GAAP EPS $8.43 vs Adjusted $11.55（GIP/HPS非現金費用）
- 2025 Q2: EPS +11.5%ビート → 株価 -2.6% → 原因: 要Web検索補完
- 2024 Q1: EPS +4.5%ビート → 株価 -2.9% → 原因: 要Web検索補完
