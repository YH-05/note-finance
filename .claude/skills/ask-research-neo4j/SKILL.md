---
name: ask-research-neo4j
description: |
  research-neo4j（bolt://localhost:7688）に蓄積されたナレッジグラフのデータのみに基づいてユーザーの質問に回答するスキル。
  外部検索やLLMの事前学習知識を使わず、グラフ内のFact・Claim・Entity・Source・FinancialDataPointから
  エビデンス付きの回答を生成する。回答不能な場合は正直にKGに情報がないことを伝える。
  Use PROACTIVELY when ユーザーが「KGに聞いて」「research-neo4jから」「グラフの情報で」
  「蓄積データで回答して」「ナレッジグラフベースで」と言った場合、
  または投資テーマ・銘柄・マクロ経済について既存データのみで回答を求められた場合。
  「ask-research」「KGに質問」「neo4jで調べて」「グラフDB検索」と言われても使うこと。
allowed-tools: Read, Bash, Glob, Grep, ToolSearch
argument-hint: <質問文>
---

# ask-research-neo4j スキル

research-neo4j に蓄積されたナレッジグラフのデータ**のみ**に基づいてユーザーの質問に回答する。
LLMの事前学習知識や外部Web検索は一切使用しない。

## 鉄則

1. **回答はグラフ内のデータのみ**から構成する。KGに存在しない情報を補完・推測してはならない
2. **根拠を明示**する。回答に使った Fact/Claim/Source を引用として提示する
3. **情報不足は正直に伝える**。KGにデータがなければ「KGにこの情報はありません」と回答し、`/investment-research` や `/research-enrichment` での補充を提案する
4. **鮮度を示す**。引用データの日付（Source.published_at, Fact.as_of_date 等）を必ず表示する

## 処理フロー

```
Step 0: Neo4j接続確認 + スキーマ取得
Step 1: 質問解析 → キーワード・エンティティ抽出
Step 2: 適応的Cypherクエリ実行（最大6クエリ）
Step 3: 回答合成 + 根拠引用
Step 4: 補足情報（ギャップ・推奨アクション）
```

### Step 0: Neo4j接続確認 + スキーマ取得

`mcp__neo4j-research__research-get_neo4j_schema` を ToolSearch でロードして実行する。

**接続失敗時**: 以下を表示して終了する。

```
research-neo4j（bolt://localhost:7688）に接続できません。
Docker起動: cd docker/research-neo4j && docker compose up -d
```

スキーマから現在のラベル・プロパティ・リレーションを確認する。
このスキーマ情報に基づいてStep 2のクエリを構築する（静的なクエリテンプレートに依存しない）。

### Step 1: 質問解析

ユーザーの質問から以下を抽出する:

| 抽出項目 | 説明 | 例 |
|---------|------|----|
| keywords | 検索キーワード（2-5語） | "NVIDIA", "AI", "GPU" |
| question_type | 質問の種類 | fact_lookup / sentiment / comparison / timeline / overview |
| time_scope | 時間的スコープ | recent（30日）/ quarter / year / all |

**question_type による検索戦略**:

| タイプ | 主要クエリ | 説明 |
|--------|-----------|------|
| fact_lookup | Q1 + Q2 | 特定の事実・数値を知りたい |
| sentiment | Q1 + Q4 | ある銘柄/テーマへの見方を知りたい |
| comparison | Q1 + Q2（複数Entity） | 2つ以上の対象を比較したい |
| timeline | Q2 + Q3 | 時系列的な変化を知りたい |
| overview | Q1 + Q2 + Q3 + Q4 | テーマの全体像を把握したい |

### Step 2: 適応的Cypherクエリ実行

`mcp__neo4j-research__research-read_neo4j_cypher` を ToolSearch でロードして使用する。
質問の種類に応じてクエリを選択的に実行する（全クエリを毎回実行しない）。

> **注意**: 以下のクエリテンプレートは参考例。Step 0 で取得したスキーマに基づき、
> 実際のラベル・プロパティ・リレーションが一致することを確認してから実行すること。

**Q1: 関連Entity検索**

```cypher
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e.name CONTAINS $keyword
   OR any(a IN coalesce(e.aliases, []) WHERE a CONTAINS $keyword)
   OR e.ticker = $keyword
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:RELATES_TO]->(e)
RETURN e.name AS entity, e.entity_type AS type, e.ticker AS ticker,
       e.description AS description,
       count(DISTINCT f) AS facts, count(DISTINCT c) AS claims
ORDER BY facts + claims DESC
LIMIT 10
```

各キーワードで実行し、ヒットしたEntityを以降のクエリで使用する。

**Q2: 関連Fact取得**

Fact → Source の接続パスは複数ある（EXTRACTED_FROM → Chunk → Source、SOURCED_FROM → Source、STATES_FACT の逆方向）。
OPTIONAL MATCH で複数パスを試み、いずれかで Source 情報を取得する。

```cypher
MATCH (f:Fact)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e.name IN $entity_names
OPTIONAL MATCH (s1:Source)-[:STATES_FACT]->(f)
OPTIONAL MATCH (f)-[:SOURCED_FROM]->(s2:Source)
OPTIONAL MATCH (f)-[:EXTRACTED_FROM]->(ch:Chunk)<-[:CONTAINS_CHUNK]-(s3:Source)
WITH f, coalesce(s1, s2, s3) AS s
RETURN f.content AS fact, f.confidence AS confidence,
       f.as_of_date AS fact_date, f.fact_type AS fact_type,
       s.title AS source_title, s.published_at AS source_date, s.url AS source_url
ORDER BY coalesce(f.as_of_date, s.published_at) DESC
LIMIT 30
```

**Q3: ソース一覧（時系列）**

```cypher
MATCH (s:Source)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e.name IN $entity_names
RETURN s.title AS title, s.url AS url, s.published_at AS published,
       s.authority_level AS authority, s.source_type AS type
ORDER BY s.published_at DESC
LIMIT 15
```

**Q4: Claim取得（センチメント付き）**

> Claim.sentiment は **FLOAT**（正値=bullish方向、負値=bearish方向、0付近=neutral）。
> Claim.magnitude は影響の大きさを示す FLOAT。

```cypher
MATCH (c:Claim)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e.name IN $entity_names
OPTIONAL MATCH (s:Source)-[:MAKES_CLAIM]->(c)
RETURN c.content AS claim, c.claim_type AS type,
       c.sentiment AS sentiment, c.magnitude AS magnitude,
       s.title AS source_title, s.published_at AS source_date, s.url AS source_url
ORDER BY s.published_at DESC
LIMIT 20
```

**センチメント解釈ガイド**:
- 文字列の場合: そのまま使用（"bullish", "bearish", "neutral" 等）
- 数値の場合: > 0.3 → bullish、< -0.3 → bearish、その間 → neutral

**Q5: FinancialDataPoint（数値データ）**

> Metric への接続は `MEASURES` リレーションが主。`FOR_METRIC` も存在するが補助的。

```cypher
MATCH (fdp:FinancialDataPoint)-[:RELATES_TO]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e.name IN $entity_names
OPTIONAL MATCH (fdp)-[:FOR_PERIOD]->(fp:FiscalPeriod)
OPTIONAL MATCH (fdp)-[:MEASURES]->(m:Metric)
RETURN coalesce(m.display_name, m.canonical_name, fdp.metric_name) AS metric,
       fdp.value AS value, fdp.unit AS unit,
       fdp.as_of_date AS date, fp.period_label AS period,
       fdp.is_estimate AS is_estimate
ORDER BY fp.period_label DESC, m.canonical_name ASC
LIMIT 20
```

**Q6: 関連Topic・タグ構造**

```cypher
MATCH (e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)<-[:RELATES_TO]-(f:Fact)-[:TAGGED]->(t:Topic)
WHERE e.name IN $entity_names
RETURN t.name AS topic, count(DISTINCT f) AS fact_count
ORDER BY fact_count DESC
LIMIT 10
```

**Q7: Stance（アナリスト評価・投資スタンス）**

質問がセンチメントや投資判断に関する場合に実行する。

```cypher
MATCH (st:Stance)-[:ON_ENTITY]->(e:Company|Technology|Organization|Person|MarketIndex|Indicator|Instrument|Commodity|Country|Concept|Regulation|Broker|Product)
WHERE e.name IN $entity_names
OPTIONAL MATCH (a:Author)-[:HOLDS_STANCE]->(st)
OPTIONAL MATCH (st)-[:BASED_ON]->(s:Source)
RETURN st.rating AS rating, st.sentiment AS sentiment,
       st.target_price AS target_price, st.target_price_currency AS currency,
       st.as_of_date AS date, st.summary AS summary,
       a.name AS analyst, a.organization AS org
ORDER BY st.as_of_date DESC
LIMIT 10
```

### Step 3: 回答合成

取得したデータから回答を構成する。以下のフォーマットで出力する。

```markdown
## 回答: {質問の要約}

{Fact・Claim・FinancialDataPointに基づく回答本文}

### 根拠データ

#### Fact（{n}件）
- {fact_content}（{source_date}, [出典]({source_url})）
- ...

#### Claim（{n}件）
| 内容 | 方向 | 出典 | 日付 |
|------|------|------|------|
| {claim} | {bullish/bearish/neutral} | {source} | {date} |

> sentiment > 0.3 → bullish、< -0.3 → bearish、その間 → neutral として表示

#### 数値データ（{n}件）※ FinancialDataPointがある場合のみ
| 指標 | 値 | 単位 | 基準日 | 期間 |
|------|-----|------|--------|------|
| {metric} | {value} | {unit} | {date} | {period} |

#### アナリスト評価 ※ Stanceがある場合のみ
| アナリスト | 評価 | ターゲット | 日付 | 概要 |
|-----------|------|-----------|------|------|
| {analyst} | {rating} | {target_price} | {date} | {summary} |

### データ鮮度
- 最新ソース: {date}（{N}日前）
- 使用Fact数: {n}件 / 使用Claim数: {n}件
- 対象Entity: {entity_names}

{KG情報の限界・不足があれば記載}
```

### Step 4: 補足情報

回答後、以下を評価して補足する:

| 状況 | 補足内容 |
|------|---------|
| Fact + Claim < 3件 | "KGカバレッジが薄いです。`/investment-research --theme {keyword}` で情報を追加できます" |
| 最新ソース > 30日前 | "データが {N}日前と古いです。`/research-enrichment` で最新情報を取得できます" |
| センチメントが一方向のみ | "bullish/bearishの一方のみです。反対意見のリサーチを推奨します" |
| Entity ヒット0件 | "KGに該当するEntityがありません。`/investment-research --theme {keyword}` で新規リサーチを開始できます" |

## 回答の原則

- **「KGによると」「蓄積データでは」**等の前置きで、データソースがKGであることを明示する
- 複数のFactやClaimが矛盾する場合は、**両方を提示**して判断はユーザーに委ねる
- 数値データには必ず**基準日（as_of_date / published_at）**を付記する
- Source.url が存在する場合は**マークダウンリンク**で埋め込む
- KGにない情報を聞かれた場合に、LLMの知識で回答を**補完しない**

## 使用例

```bash
# 銘柄について聞く
/ask-research-neo4j NVIDIAの最新の業績はどうなっている？

# マクロテーマについて聞く
/ask-research-neo4j 日銀の金融政策について蓄積されている情報は？

# 比較
/ask-research-neo4j テスラとBYDの競争状況についてKGに何がある？

# センチメント
/ask-research-neo4j S&P500に対するbullish/bearishの見方は？

# 概要
/ask-research-neo4j AIセクターについてKGにどんな情報がある？
```

## 関連スキル

| スキル | 関係 |
|--------|------|
| `/kg-summary` | KGアセットの定量サマリー（LLM不使用、数値のみ） |
| `/investment-research` | KG照会 + 外部検索でギャップを埋める |
| `/research-enrichment` | KGの知識ギャップを自動拡充する |
| `/topic-discovery` | KGデータからトピック候補を発掘する |
