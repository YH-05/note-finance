# ISAT IJ vs TLKM IJ — Neo4j グラフ分析メモ

> 作成日: 2026-03-16
> データソース: research-neo4j (bolt://localhost:7688)
> 分析手法: Metric マスターノード経由の横断比較

---

## 1. データ概要

| 項目 | ISAT IJ | TLKM IJ |
|------|---------|---------|
| Source | ISAT_IJ Research Memo (Phase 1-7) | TLKM_IJ Research Memo (Phase 1-7) |
| Entity | Indosat Ooredoo Hutchison | Telkom Indonesia |
| Claim 数 | 18 | 23 |
| Fact 数 | 17 | 40 |
| FinancialDataPoint 数 | 57 | 109 |
| 比較可能 Metric 数 | 12（Metric マスター経由） |

---

## 2. グラフから発見した比較ポイント

### 2-1. EBITDA マージン収斂（セルサイドが個別にしか言及しない）

| 期間 | ISAT | TLKM | Gap |
|------|------|------|-----|
| FY2021 | 44.0% | 52.9% | 8.9pp |
| FY2022 | 41.6% | 53.6% | 12.0pp |
| FY2023 | 46.7% | 52.0% | 5.3pp |
| FY2024 | 47.2% | 50.0% | **2.8pp** |

- **ISATはIOH合併シナジーでマージン急改善**（44→47%）
- **TLKMは逆にマージン低下トレンド**（53→50%）
- Gap は 12pp → 2.8pp に急縮小 → **FY2025-26で逆転の可能性**
- セルサイドは各社個別にマージン言及するが、このクロスカンパニー時系列を並べたレポートは見当たらない

### 2-2. Revenue 成長率の構造的格差

| 期間 | ISAT YoY | TLKM YoY |
|------|----------|----------|
| FY2022 | +48.9% | +2.9% |
| FY2023 | +9.6% | +1.3% |
| FY2024 | +9.1% | +0.5% |

- FY2022のISAT急伸はIOH合併効果（オーガニックではない）
- ただし**FY2023-24でも9%成長を維持**しているのに対し、**TLKMは1%未満に減速**
- TLKMの売上成長がほぼ停止 → 「インカム株化」の裏付け

### 2-3. バリュエーション前提（WACC）の非対称性

グラフ内のClaim（recommendation型）から抽出:

| ブローカー | ISAT WACC | TLKM WACC | 差 |
|-----------|-----------|-----------|-----|
| BofA | 14.3-15.3% | 10.0% | ~5pp |
| HSBC | 12.8% | 9.4% | 3.4pp |
| Citi | N/A | 9.4% | — |
| UBS | 12.4% | N/A | — |
| Goldman | N/A | 12.6% | — |
| Nomura | N/A | 8.6% | — |

- ISATに適用されるWACCはTLKMより**3-6pp高い**
- TLKMは国営企業プレミアム（低リスク＝低WACC）
- ISATのマージン改善・CF安定化が進むなら、このWACCギャップは過大評価の可能性
- **同一ハウスのWACCを横並びで見ることは通常のセルサイドレポートでは不可能**

### 2-4. Dividend Payout の方針差

| 期間 | ISAT | TLKM |
|------|------|------|
| FY2024 | 55% | 89% |

- TLKMは配当性向80-90%の「インカム株」
- ISATは55%→60%→70%（2026目標）の漸増方針
- ISATはFCFの余力をGPUaaS投資に振り向けている

### 2-5. 非対称カバレッジ（一方にしかないデータ）

**ISATにあってTLKMにない指標:**
- ROIC, ROE, EPS, EV/EBITDA, Blended ARPU, Subscribers, Revenue Market Share, DPS

**TLKMにあってISATにない指標:**
- CapEx/Revenue比率, Fiber Optic Length, D&A, O&M Cost, Personnel Cost, Analyst Target Price (9社分), Dividend Yield

→ ISATはプロフィタビリティ指標が充実、TLKMはコスト構造・インフラ指標が充実

---

## 3. グラフ構造から見えるが未構造化の繋がり

### 3-1. ゼロサム構造（テキスト内に存在、リンク未設定）

ISATのFact:
> "Indonesian telecom market: Telkomsel 47% revenue share (159M subs), Indosat 28% (96M subs), XLSmart 25% (83M subs)."

- このFactはISAT EntityにのみRELATES_TO
- TLKMのFact:
  > "Telkom Indonesia's mobile market share declined 180bps in 2024"
- **ISATのシェア拡大 = TLKMの浸食** というゼロサム構造がFactレベルで確認できるが、グラフ上では接続されていない

### 3-2. Golden Share 規制の対称性

- ISAT: `"Indonesian government holds Class A (Golden) share with veto rights"`
- TLKM: `"Government holds 'Dwi Warna' share granting veto rights"`
- **同一の規制フレームワーク**への暴露だが、別Factノードとして独立

### 3-3. インフラ資産の直接比較（セルサイドが明示比較しない）

| 項目 | ISAT | TLKM |
|------|------|------|
| ファイバー網 | 206,275 km | 179,000 km |
| BTS | 278,173 | N/A |
| 5G BTS | 6,872 | N/A |

- **ISATのファイバー網がTLKMより長い**（206K vs 179K km）という事実はセルサイドで明示比較されていない
- ISATの5G BTS 6,872局（FY2024の107局から急拡大）

### 3-4. J.P. Morgan の評価乖離

- ISAT: **Overweight**, TP 3,300 IDR（PER 13-15x、Telkom対比）
- TLKM: **Neutral**, TP 3,000 IDR（ROIC低下＋金利環境を懸念）
- 同一ハウスが「ISATはBuy、TLKMはHold」→ **バリューチェーン内でのシフトを示唆**

---

## 4. 使用した Cypher クエリ

### Metric 経由の横断比較（最も実用的）

```cypher
MATCH (met:Metric)<-[:MEASURES]-(dp_i)-[:RELATES_TO]->(isat:Entity {ticker: 'ISAT IJ'}),
      (met)<-[:MEASURES]-(dp_t)-[:RELATES_TO]->(tlkm:Entity {ticker: 'TLKM IJ'}),
      (dp_i)-[:FOR_PERIOD]->(fp:FiscalPeriod)<-[:FOR_PERIOD]-(dp_t)
RETURN met.display_name AS metric, fp.period_label AS period,
       dp_i.value AS ISAT, dp_t.value AS TLKM, met.unit_standard AS unit
ORDER BY met.category, met.canonical_name, fp.period_label;
```

### EBITDA マージン Gap 分析

```cypher
MATCH (met:Metric {canonical_name: 'ebitda_margin'})<-[:MEASURES]-(dp)-[:RELATES_TO]->(e:Entity),
      (dp)-[:FOR_PERIOD]->(fp:FiscalPeriod)
WHERE e.ticker IN ['ISAT IJ', 'TLKM IJ']
WITH fp.period_label AS period, e.ticker AS ticker, dp.value AS val
ORDER BY period, ticker
WITH period, collect({ticker: ticker, val: val}) AS data
WHERE size(data) = 2
RETURN period,
       [x IN data WHERE x.ticker = 'ISAT IJ'][0].val AS ISAT,
       [x IN data WHERE x.ticker = 'TLKM IJ'][0].val AS TLKM,
       [x IN data WHERE x.ticker = 'TLKM IJ'][0].val - [x IN data WHERE x.ticker = 'ISAT IJ'][0].val AS gap
ORDER BY period;
```

### 全クエリ集

→ `equity_research/cypher_queries/cross_company_comparison.cypher`

---

## 5. 今後のアクション

### 短期（リンク補強）
- [ ] 市場シェアFactを両Entity（ISAT + TLKM）にクロスリンク
- [ ] インフラ資産データ（fiber km, BTS数）をFinancialDataPoint化してMetricリンク
- [ ] Analyst Entity + AUTHORS リレーション追加

### 中期（データ追加）
- [ ] XL Axiata (EXCL IJ) のリサーチメモ投入 → 3社比較
- [ ] 四半期ARPU時系列の正規化（ISATに5期分、TLKMに7期分あるが別Metric名）
- [ ] マクロ感応度データ（金利・為替→各社への影響）の構造化

### スキーマ改善
- [ ] `(:Analyst)` ノード + `[:AUTHORS]` リレーション追加
- [ ] `[:COMPETES_WITH]` リレーション（ISAT ↔ TLKM ↔ EXCL）
- [ ] `[:CAUSES]` / `[:CORRELATES_WITH]` 因果リレーション

---

## 6. 技術メモ

- Metric マスター: `data/config/metric_master.json` (35指標, 102エイリアス)
- 適用スクリプト: `scripts/apply_metric_master.py`
- FiscalPeriod は重複統合済み（9ペア → 単一ノードに集約）
- 現在のカバレッジ: 166 FinancialDataPoint 中 152 (91.6%) がMetricリンク済み
