# KG Ingestion Report: US Telecom Sector

Generated: 2026-03-28

## 投入サマリー

| 項目 | 件数 |
|------|------|
| Source | 16 |
| Topic | 10 (8 new, 2 existing) |
| Entity | 10 (8 new, 2 existing) |
| Fact | 10 |
| TAGGED (Source->Topic) | 160 |
| TAGGED (Fact->Topic) | 100 |
| STATES_FACT | 10 |
| RELATES_TO (Fact->Entity) | 11 |
| EXTRACTED_FROM (Fact->Source) | 10 |

## 投入検証 (Phase 3c)

| リレーション | 期待値 | 実績値 | 判定 |
|-------------|--------|--------|------|
| STATES_FACT | 10 | 10 | OK |
| RELATES_TO | 11 | 11 | OK |
| TAGGED (Source->Topic) | 160 | 160 | OK |
| TAGGED (Fact->Topic) | 100 | 100 | OK |
| EXTRACTED_FROM | 10 | 10 | OK |

**総合判定**: OK (全リレーション100%一致)

## 新規 Entity (8社追加)

- Charter Communications (CHTR) — Cable/Broadband
- Lumen Technologies (LUMN) — Fiber/Enterprise
- Crown Castle (CCI) — Tower REIT
- SBA Communications (SBAC) — Tower REIT
- Frontier Communications (FYBR) — Fiber (now part of Verizon)
- EchoStar (SATS) — Satellite/Wireless
- SpaceX — Satellite
- FCC — Government Agency

## 新規 Topic (8追加)

- Fiber Broadband, Tower REIT, Telecom M&A, Fixed Wireless Access
- AI Infrastructure, Cable Broadband, BEAD Program, Spectrum Allocation (既存との重複チェック済み)

## ギャップ解消状況

| ギャップ | 解消 | 備考 |
|---------|------|------|
| G1: 6社の no_coverage | 部分的 | 6社のEntityとFactを追加。FinancialDataPointは未投入 |
| G2: AMT stale_data | 部分的 | Fact追加済み。詳細FDPは未投入 |
| G6: missing_relationships | 一部 | RELATES_TO 11件追加。COMPETES_WITH等は未追加 |
| G7: sector_overview | 解消 | セクター概観Fact+Topic投入済み |

## 未投入データ

- SEC Edgar 財務データ (FinancialDataPoint) — 別途投入が必要
- Claim ノード (12件のclaims.jsonデータ) — emit_research_queue で別途投入可能
- 競合/パートナー関係 (COMPETES_WITH等) — 手動またはenrichmentで補完
