# KG Ingestion Report: インドネシアBUMN分析

## 投入サマリー

| 項目 | 件数 |
|------|------|
| graph-queue | gq-20260328115031-1b2a15cd.json (v3.0) |
| Source ノード | 16 (15新規, 1既存) |
| Topic ノード | 5 (5新規) |
| Entity ノード | 13 (9新規, 4既存) |
| Fact ノード | 16 (16新規) |
| STATES_FACT | 16 |
| RELATES_TO (fact_entity) | 16 |
| EXTRACTED_FROM (fact→source) | 16 |
| TAGGED (source→topic) | 80 |
| **リレーション合計** | **128** |

## 新規投入 Entity

| Entity | Type |
|--------|------|
| BBRI (Bank Rakyat Indonesia) | company |
| BMRI (Bank Mandiri) | company |
| BBNI (Bank Negara Indonesia) | company |
| JSMR (Jasa Marga) | company |
| SMGR (Semen Indonesia) | company |
| WSKT (Waskita Karya) | company |
| ANTM (Aneka Tambang) | company |
| PTBA (Bukit Asam) | company |
| TINS (Timah) | company |

## 新規投入 Topic

| Topic | Category |
|-------|----------|
| Indonesia BUMN Analysis | equity_research |
| Indonesia SOE Reform | political |
| Indonesia Banking Sector | sector |
| Indonesia Mining Sector | sector |
| Indonesia Infrastructure | sector |

## ギャップ解消状況

| ギャップ | ステータス |
|---------|----------|
| 銀行BUMN (BBRI,BMRI,BBNI) | ✓ Entity + Fact 投入済み |
| 建設BUMN (WIKA,WSKT,PTPP) | ✓ Entity + Fact 投入済み |
| 資源BUMN (ANTM,PTBA,TINS) | ✓ Entity + Fact 投入済み |
| JSMR, SMGR | ✓ Entity + Fact 投入済み |
| Danantara | ✓ Fact 追加投入済み |
| BBTN, PGAS, KAEF, ELSA | 残存（個社Fact未投入） |
| FinancialDataPoint | 残存（全社0件） |

Generated: 2026-03-28
