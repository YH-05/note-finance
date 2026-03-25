# 議論メモ: research-enrichment 詳細設計（スコア重み・Config・Cypherクエリ確定）

**日付**: 2026-03-25
**参加**: ユーザー + AI
**前回議論**: `docs/plan/SideBusiness/2026-03-25_discussion-research-enrichment-skill-design.md`

## 背景・コンテキスト

前回議論でPhase構成・ターゲット選定方式・投入パイプライン・ソース選択が確定。今回は実データでGap分析クエリを検証し、統合スコアの重み・Config構造・Cypherクエリを最終確定する。

## 実データによるGap分析結果

### 軸1: カテゴリバランス（facts/topic）

| カテゴリ | topics | facts | facts/topic | 判定 |
|---------|--------|-------|-------------|------|
| WealthManagement | 7 | 0 | 0.0 | 深刻 |
| ContentPlanning | 40 | 77 | 1.9 | 低 |
| Technology | 13 | 34 | 2.6 | 低 |
| EquityResearch | 48 | 267 | 5.6 | 中 |
| MacroEconomics | 28 | 267 | 9.5 | 良 |
| Regulation | 9 | 87 | 9.7 | 良 |
| InvestmentStrategy | 12 | 140 | 11.7 | 良 |
| SectorAnalysis | 38 | 739 | 19.4 | 優 |

### 軸2: Entity空洞（ticker あり & Fact 0）

AMD, Samsung, SK Hynix, Broadcom, Boeing, BlackRock, Intel, Goldman Sachs, Advantest, Arista Networks, AppLovin, Coupang 等 20+件

### 軸3: 鮮度（latest_fact が古い順）

| Entity | ticker | latest_fact | fact_count |
|--------|--------|-------------|-----------|
| American Tower | AMT | 2024-09-12 | 1 |
| Google | GOOGL | 2025-03-01 | 4 |
| Microsoft | MSFT | 2025-03-01 | 6 |
| Maxis | MAXIS MK | 2025-03-01 | 3 |
| Amazon | AMZN | 2025-06-01 | 3 |

### 軸4: 財務データ欠損（sec_cik あり & FDP 0）

AMD(2488), AppLovin(1751008), Broadcom(1730168), Boeing(12927), BlackRock(2012383), Coupang(1834584), CoreWeave(1769628), DoorDash(1792789), Deutsche Bank(1159508), Intel(50863), JPMorgan(19617), Goldman Sachs(886982), Micron(723125), Nike(320187), Palantir(1321655) 等 20+件

## 決定事項

### 1. 統合スコアの重み

```
unified_score = 0.15 * category_gap + 0.35 * entity_gap + 0.30 * staleness + 0.20 * financial_gap
```

| 軸 | 重み | 理由 |
|----|------|------|
| w1 (category) | 0.15 | WealthManagementの穴は深刻だが銘柄分析への直接影響は限定的 |
| w2 (entity) | 0.35 | 銘柄分析に直結。AMD, Broadcom等の空洞は痛い |
| w3 (staleness) | 0.30 | Google/Microsoft 12ヶ月前は記事の信頼性に影響 |
| w4 (financial) | 0.20 | SEC EDGAR自動取得可能で効率が高い |

スコア算出例:
- AMD: 0 + 0.35 + 0 + 0.20 = **0.55**
- Google(stale 12mo): 0 + 0 + 0.30 + 0 = **0.30**
- WealthMgmt Topic: 0.15 + 0 + 0 + 0 = **0.15**

### 2. Config構造

```json
{
  "gap_analysis": {
    "weights": { "category": 0.15, "entity": 0.35, "staleness": 0.30, "financial": 0.20 },
    "max_targets_per_cycle": 5,
    "staleness_threshold_days": 90,
    "min_facts_per_topic": 5
  },
  "search": {
    "en_queries_per_target": 2,
    "ja_queries_per_target": 2,
    "reddit_subreddits": ["investing", "stocks", "SecurityAnalysis", "wallstreetbets"],
    "sec_edgar": { "filing_types": ["10-K", "10-Q", "8-K"] },
    "alphaxiv": { "max_papers": 3, "categories": ["Technology", "EquityResearch"] }
  },
  "fallback": { "browser_use_max_urls": 3 },
  "rawstore": { "enabled": true, "exclude_sources": ["sec_edgar", "alphaxiv"] }
}
```

### 3. Gap分析Cypherクエリ（確定版）

各クエリは候補リストを返し、スコアリングはLLM側で統合する。

#### Q1: カテゴリバランス

```cypher
MATCH (cc:ConceptCategory)<-[:IS_CATEGORY]-(t:Topic)
OPTIONAL MATCH (t)<-[:TAGGED]-(f:Fact)
WITH cc.name AS category, cc.name_ja AS category_ja,
     count(DISTINCT t) AS topics, count(DISTINCT f) AS facts
RETURN category, category_ja, topics, facts,
       CASE WHEN topics > 0 THEN round(toFloat(facts)/topics, 1) ELSE 0 END AS facts_per_topic
ORDER BY facts_per_topic ASC
```

判定: `facts_per_topic < min_facts_per_topic(5)` → 優先カテゴリ
スコア: `1.0 / (facts_per_topic + 1)`

#### Q2: Entity カバレッジ

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
AND NOT exists { (f:Fact)-[:ABOUT]->(e) }
AND NOT exists { (f:Fact)-[:RELATES_TO]->(e) }
OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)
RETURN e.name, e.ticker, e.entity_key, e.sec_cik, sec.name AS sector
LIMIT 30
```

スコア: Fact 0件 → 1.0、Fact 1-3件 → 0.5、Fact 4+件 → 0.0

#### Q3: 鮮度

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(e)
WITH e.name AS name, e.ticker AS ticker,
     max(f.as_of_date) AS latest_fact, count(f) AS fact_count
WHERE fact_count > 0
RETURN name, ticker, latest_fact, fact_count
ORDER BY latest_fact ASC
LIMIT 20
```

スコア: `min((today - latest_fact).days / staleness_threshold_days, 1.0)`

#### Q4: 財務データ

```cypher
MATCH (e:Entity)
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
AND e.sec_cik IS NOT NULL AND e.sec_cik <> ''
AND NOT exists { (fdp:FinancialDataPoint)-[:RELATES_TO]->(e) }
RETURN e.name, e.ticker, e.sec_cik
LIMIT 20
```

スコア: FDP 0件 & sec_cik あり → 1.0

## アクションアイテム

- [ ] SKILL.md 作成（全決定事項を統合） (優先度: 高)
- [ ] research-enrichment-config.json ファイル作成 (優先度: 高)
- [ ] references/gap-analysis-queries.md 作成 (優先度: 高)

## 次回の議論トピック

- Layer 1（事前バッチ）統合ランナー設計
- creator-enrichment との共通基底モジュール抽出
- 重みのチューニング方針（N回実行後のフィードバックループ）

## 参考情報

- 前回議論: `docs/plan/SideBusiness/2026-03-25_discussion-research-enrichment-skill-design.md`
- 初回議論: `docs/plan/SideBusiness/2026-03-24_discussion-research-enrichment-design.md`
- research-neo4j スキーマ: Entity 1013, Source 1710, Fact 1518, Claim 1000, Topic 227, FDP 453
