# KG Gap Report: インドネシアBUMN分析

## 既存データサマリー

| Entity | Type | Facts | Claims | Sources | FDP |
|--------|------|-------|--------|---------|-----|
| Indonesia | country | 93 | 60 | 15 | 0 |
| Telkom Indonesia | company | 48 | 91 | 66 | 0 |
| Telkomsel | company | 27 | 132 | 19 | 0 |
| Government of Indonesia | government | 7 | 34 | 0 | 0 |
| Bank Indonesia | central_bank | 2 | 0 | 0 | 0 |
| BBRI (Bank Rakyat Indonesia) | company | 0 | 0 | 0 | 0 |
| BMRI (Bank Mandiri) | company | 0 | 0 | 0 | 0 |
| BBNI (Bank Negara Indonesia) | company | 0 | 0 | 0 | 0 |
| TLKM (Telkom Indonesia) | company | 0 | 0 | 0 | 0 |

### 関連トピック（Tagged Facts）

| Topic | Category | Tagged Facts |
|-------|----------|-------------|
| Indonesian Telecom | sector | 144 |
| ASEAN Telecom | sector | 120 |
| Indonesia Equity Strategy | equity_research | 109 |
| Emerging Markets | macro | 109 |
| Indonesia Danantara | political | 45 |

## 特定されたギャップ

### HIGH Priority

| # | ギャップ種別 | 対象 | 詳細 |
|---|------------|------|------|
| 1 | no_coverage | 銀行BUMN (BBRI, BMRI, BBNI, BBTN) | Entity存在するが Fact/Claim/Source 全て0件 |
| 2 | no_coverage | 建設BUMN (WIKA, WSKT, PTPP, ADHI, JSMR) | Entity未登録 |
| 3 | no_coverage | 資源BUMN (PGAS, PTBA, ANTM, TINS) | Entity未登録 |
| 4 | no_coverage | その他BUMN (SMGR, KAEF, ELSA) | Entity未登録 |
| 5 | missing_financials | 全17銘柄 | FinancialDataPoint 0件 |

### MEDIUM Priority

| # | ギャップ種別 | 対象 | 詳細 |
|---|------------|------|------|
| 6 | stale_data | Telkom Indonesia | Source published_date が NULL（鮮度不明） |
| 7 | missing_bear_case | Indonesia macro | Claim偏り: bullish 80 vs bearish 13 |
| 8 | no_coverage | BUMN改革/Danantara | Topic存在(45 facts)だが個社への影響分析なし |

## 推奨検索クエリ（ギャップ解消用）

1. "Indonesia BUMN state-owned enterprises 2025 2026 financial performance"
2. "BBRI BMRI BBNI Indonesia banking sector earnings 2025"
3. "Indonesia construction BUMN WIKA WSKT infrastructure spending"
4. "PTBA ANTM TINS Indonesia mining resources commodity"
5. "Danantara BUMN reform holding company impact"
6. "Indonesia SOE privatization dividend policy"
7. "JSMR toll road SMGR cement Indonesia infrastructure"
8. "Bank Indonesia monetary policy 2026 rupiah"

Generated: 2026-03-28
