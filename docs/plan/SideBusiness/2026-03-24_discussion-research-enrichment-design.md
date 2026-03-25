# 議論メモ: research-enrichment スキル設計

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

creator-enrichment（creator-neo4j向け）のように、research-neo4jへ自動で情報投入するループ型スキルを構築したい。research-neo4j側は投入パイプライン（emit_research_queue.py → /save-to-research-graph）は構築済みだが、ギャップ分析→収集→投入を自動で繰り返すオーケストレーターが未構築。

### research-neo4j 現状（2026-03-24時点）

| ノード | 件数 |
|--------|------|
| Entity | 1,013 |
| Source | 1,710 |
| Fact | 1,518 |
| Claim | 1,000 |
| Topic | 227 |
| FinancialDataPoint | 453 |
| ConceptCategory | 8 |

### 主要課題

- **カテゴリ偏り**: WealthManagement Fact 0件、Technology Fact 34件
- **Entity空洞**: company 190件中、大半がFact 0件（AMD, Alphabet, Anthropic等）
- **鮮度**: 2026-01: 11件、2026-02: 32件と直近が薄い
- **財務データ**: FinancialDataPointがあるのはVerizonのみ
- **ソース偏り**: finance-news(683) + wealth-scrape(431)で8割

## 議論のサマリー

### 1. 情報収集手段の棚卸し

プロジェクトで利用可能な情報収集手段を網羅的に調査し、以下に分類した:

- **MCP ツール**: Tavily, Reddit, SEC EDGAR, alphaxiv, Wikipedia, Playwright, browser-use CLI
- **Python スクリプト**: collect_market_performance, prepare_news_session, prepare_ai_research_session, scrape_finance_news 等
- **コマンド**: /collect-finance-news, /ai-research-collect, /reddit-finance-topics 等

### 2. 2層アーキテクチャの提案・合意

全収集手段を一括実行すると長時間かかるため、以下の分離設計とした:

- **Layer 1（事前バッチ）**: Python スクリプトで自動化可能なもの → cron/手動で事前実行、JSON蓄積
- **Layer 2（リアルタイム）**: MCP ツール → スキル実行時にオンデマンド取得

Layer 1の実装は後回しにし、Gap分析ロジックとLayer 2の整備を先行する。

### 3. Gap分析の軸設計

当初5軸を提案:

1. カテゴリバランス
2. Entity カバレッジ
3. 鮮度
4. ソース多様性
5. 財務データ

議論の結果、**ソース多様性を軸から除外し4軸に整理**:

- ソース多様性は「何を集めるか」ではなく「どう集めるか」のメタ情報
- 独立軸としてではなく、複数ツール併用の運用ルールに組み込む

追加候補として検討・棄却したもの:
- リレーション密度 → 既存データからの推論で対応（収集軸ではない）
- 地理的偏り → Entity カバレッジの一変数
- Claim裏付け率 → 品質チェック軸（収集トリガーではない）

### 4. MCPツール選択方針

固定マッピング（Gap種別→ツール）ではなく、ターゲットの属性に基づく動的選択:

| ツール | 選択条件 |
|--------|---------|
| Tavily search | 常に使用 |
| Tavily research | カテゴリ不足時（深掘り） |
| SEC EDGAR | ticker/CIKあり |
| alphaxiv | Technology/EquityResearch系 |
| Reddit | InvestmentStrategy/MacroEconomics/WealthManagement系 |
| Wikipedia | description未登録Entity |
| browser-use CLI | フォールバック専用 |

### 5. フォールバックチェーン

creator-enrichmentの実績を踏襲:

| 用途 | Tier 1 | Tier 2 | Tier 3 |
|------|--------|--------|--------|
| Web検索 | Tavily search | WebSearch | スキップ |
| 本文抽出 | Tavily extract | WebFetch | browser-use CLI |
| 深掘り | Tavily research | Tavily search x複数 | WebSearch x複数 |

Tavilyはレート温存のため高付加価値検索に限定。Wikipedia等はWebFetchで。

browser-use CLI の特性:
- JSレンダリング対応（note.com, SPA等で有効）
- 1URL あたり5-10秒、セッション管理対応
- `~/.browser-use-env/` にインストール済み

## 決定事項

1. **2層アーキテクチャ**: Layer 1（事前バッチPython）+ Layer 2（リアルタイムMCP）で分離
2. **Gap分析4軸**: カテゴリバランス、Entityカバレッジ、鮮度、財務データ
3. **全軸毎サイクル実行**: --focusによる1軸フォーカスではなく全軸を回す
4. **収集量の上限なし**: APIレート制限以外の人為的上限は設けない
5. **フォールバックチェーン**: Tavily → WebSearch/WebFetch → browser-use CLI → スキップ
6. **Tavilyレート温存**: 高付加価値検索に限定、低付加価値はWebFetchで

## アクションアイテム

- [ ] Gap分析クエリ（4軸）の実装 + 優先度スコア算出ロジック (優先度: 高)
- [ ] Layer 2 収集フロー整備: ツール選択ロジック、フォールバック、JSON正規化 (優先度: 高)
- [ ] research-enrichment スキル（SKILL.md）作成: Phase 0-6 オーケストレーション (優先度: 中)
- [ ] Layer 1 統合ランナー作成（後回し） (優先度: 低)

## スキル実行フロー（設計案）

```
/research-enrichment --until HH:MM
    Phase 0: Init（Neo4j接続確認、設定読込）
    Phase 1: Gap Analysis（4軸クエリ実行→優先度スコア→ターゲット選定）
    Phase 2: Layer 1 読込（事前バッチ結果があれば活用）
    Phase 3: 収集（ターゲットごとにツール選択・実行）
    Phase 4: Transform → graph-queue JSON 生成
    Phase 5: 投入 → /save-to-research-graph
    Phase 6: Cycle Report + Time Check → ループ
```

## Gap分析Cypherクエリ（設計案）

### 軸1: カテゴリバランス

```cypher
MATCH (cc:ConceptCategory)<-[:IS_CATEGORY]-(t:Topic)
OPTIONAL MATCH (t)<-[:TAGGED]-(f:Fact)
WITH cc.name AS category, cc.name_ja AS category_ja,
     count(DISTINCT t) AS topics, count(DISTINCT f) AS facts
RETURN category, category_ja, topics, facts,
       CASE WHEN topics > 0 THEN round(toFloat(facts)/topics, 1) ELSE 0 END AS facts_per_topic
ORDER BY facts_per_topic ASC
```

判定: facts_per_topic < 5 → 優先カテゴリ

### 軸2: Entity カバレッジ

```cypher
MATCH (e:Entity)-[:IS_TYPE]->(et:EntityType {name: 'company'})
WHERE NOT exists { (f:Fact)-[:ABOUT]->(e) }
OPTIONAL MATCH (e)-[:IN_SECTOR]->(sec:Sector)
RETURN e.name, e.ticker, e.entity_key, sec.name AS sector
```

判定: ticker あり & Fact 0 → 優先収集

### 軸3: 鮮度

```cypher
MATCH (e:Entity)-[:IS_TYPE]->(et:EntityType {name: 'company'})
OPTIONAL MATCH (f:Fact)-[:ABOUT]->(e)
WITH e.name AS name, e.ticker AS ticker,
     max(f.as_of_date) AS latest, count(f) AS cnt
WHERE cnt > 0
RETURN name, ticker, latest, cnt
ORDER BY latest ASC
```

判定: latest < 今月 - 30日 → 更新優先

### 軸4: 財務データ

```cypher
MATCH (e:Entity)-[:IS_TYPE]->(et:EntityType {name: 'company'})
WHERE e.ticker IS NOT NULL AND e.ticker <> ''
AND NOT exists { (s:Source)-[:ABOUT]->(e) WHERE exists { (s)-[:HAS_DATAPOINT]->(:FinancialDataPoint) } }
RETURN e.name, e.ticker, e.sec_cik
```

判定: sec_cik あり → SEC EDGAR で即収集可能

## 参考情報

- creator-enrichment スキル: `.claude/skills/creator-enrichment/SKILL.md`
- save-to-research-graph スキル: `.claude/skills/save-to-research-graph/SKILL.md`
- emit_research_queue.py: `scripts/emit_research_queue.py`
- browser-use CLI: `~/.browser-use-env/bin/browser-use`
