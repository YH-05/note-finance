# KG Gap Report: US Telecom Sector

Generated: 2026-03-28

## 既存データサマリー

| Entity | Ticker | Fact | Claim | Source | FDP | 最新Source | 状態 |
|--------|--------|------|-------|--------|-----|-----------|------|
| AT&T | T | 15 | 8 | 2 | 23 | 2026-01-28 | stale (59日) |
| Verizon | VZ | 15 | 7 | 2 | 22 | 2026-03-07 | OK (21日) |
| T-Mobile US | TMUS | 15 | 7 | 1 | 19 | 2026-02-11 | stale (45日) |
| Comcast | CMCSA | 12 | 7 | 0 | 25 | N/A | stale |
| American Tower | AMT | 1 | 0 | 2 | 0 | 2025-03-01 | stale (1年超) |
| Charter | CHTR | 0 | 0 | 0 | 0 | N/A | no_coverage |
| Lumen | LUMN | 0 | 0 | 0 | 0 | N/A | no_coverage |
| Crown Castle | CCI | 0 | 0 | 0 | 0 | N/A | no_coverage |
| SBA Comm | SBAC | 0 | 0 | 0 | 0 | N/A | no_coverage |
| Frontier | FYBR | 0 | 0 | 0 | 0 | N/A | no_coverage |
| EchoStar | SATS | 0 | 0 | 0 | 0 | N/A | no_coverage |

### Claimセンチメント分布

| Entity | Bullish | Bearish | Neutral |
|--------|---------|---------|---------|
| AT&T | 5 | 2 | 0 |
| Verizon | 5 | 2 | 0 |
| Comcast | 0 | 0 | 7 |
| T-Mobile US | 0 | 0 | 0 (未分類) |

### 既存リレーション

- AT&T ↔ Comcast: COMPETES_WITH (broadband, fiber deployment)
- Comcast ↔ Disney: COMPETES_WITH (streaming)
- Comcast ↔ Netflix: COMPETES_WITH (streaming)

## 特定されたギャップ

### HIGH Priority

| # | 種別 | 対象 | 詳細 |
|---|------|------|------|
| G1 | no_coverage | CHTR, LUMN, CCI, SBAC, FYBR, SATS | 6社が完全未登録 |
| G2 | stale_data | AMT | 最新ソース1年超前 |
| G3 | missing_financials | AMT, CHTR, LUMN, CCI, SBAC, FYBR, SATS | 7社のFDPが0件 |

### MEDIUM Priority

| # | 種別 | 対象 | 詳細 |
|---|------|------|------|
| G4 | missing_sentiment | TMUS, CMCSA | Claim未分類 or 全neutral |
| G5 | stale_data | T, TMUS | 30日超経過 |
| G6 | missing_relationships | 全社 | COMPETES_WITH が AT&T↔CMCSA のみ。タワーREIT↔キャリア関係なし |
| G7 | sector_overview | US Telecom | セクター全体のトレンド・規制・5G進捗の体系的データ不足 |

## 推奨検索クエリ（ギャップ解消用）

### Priority 1: 未登録6社の基本プロファイル + 財務
1. "Charter Communications CHTR 2025 2026 earnings revenue subscribers"
2. "Lumen Technologies LUMN fiber enterprise 2025 2026 restructuring"
3. "Crown Castle CCI tower REIT 2025 2026 earnings fiber small cells"
4. "SBA Communications SBAC tower REIT 2025 2026 revenue"
5. "Frontier Communications FYBR fiber conversion 2025 2026 subscribers"
6. "EchoStar SATS DISH wireless spectrum 5G 2025 2026"

### Priority 2: AMT更新 + セクター概観
7. "American Tower AMT 2025 2026 earnings data center CoreSite"
8. "US telecom sector 2026 outlook 5G fiber broadband trends"
9. "US wireless market share 2025 2026 T-Mobile Verizon AT&T"

### Priority 3: 競争関係 + バリューチェーン
10. "US tower REIT comparison AMT CCI SBAC lease revenue"
11. "US cable broadband vs fiber competition 2025 2026"
12. "FCC spectrum auction 2025 2026 C-band CBRS"
