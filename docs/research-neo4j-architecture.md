# research-neo4j アーキテクチャドキュメント

> **最終更新**: 2026-04-01
> **対象DB**: research-neo4j (bolt://localhost:7688, Browser: http://localhost:7475)
> **スキーマバージョン**: v3.0 (FIBO準拠)
> **SSoT**: `data/lifecycle-state/research/ontology.yaml`

---

## 1. 設計思想

### 1.1 存在意義

research-neo4j は、本プロジェクトにおける **金融リサーチ知識の Single Source of Truth (SSoT)** である。RSS、Web検索、PDF変換、Reddit、SEC Edgar 等あらゆるソースから収集された情報は、標準パイプラインを通じてこのグラフDBに集約される。記事執筆・分析・各種SNS投稿はすべて research-neo4j のデータをベースに行う。

```
データ収集（任意の方法）→ パイプライン経由で投入 → research-neo4j → 分析・執筆・投稿
```

### 1.2 設計原則

| 原則 | 説明 |
|------|------|
| **Claim-centric** | Recommendation 等の独立ノードを設けず、Claim の claim_type で統一。セクター・マクロレポートとの互換性を確保 |
| **Fact の厳密性** | Fact = 検証済み過去の客観的情報のみ。バリュエーション前提（WACC, Beta等）は Claim(assumption) に分類 |
| **confidence 非採用** | AI が出力する確信度スコアはモデル依存で再現性がないため、Fact/Claim/Insight すべてから confidence を排除 |
| **薄いハブノード** | FIBO準拠の分類ノード（EntityType, SourceType, FactType 等）を導入し、プロパティの enum 値をノード化。クエリの柔軟性と拡張性を確保 |
| **マルチラベル Entity** | Entity は共通ラベル `Entity` に加え、タイプ別ラベル（`Company`, `Technology` 等）を持つ。`MATCH (e:Entity)` で横断クエリ、`MATCH (c:Company)` でタイプ別クエリの両方が可能 |
| **パイプライン投入必須** | Cypher 直書きによるノード・リレーション作成は禁止。全データ投入は `emit_research_queue.py → entity_linker.py → neo4j_loader.py` の3段パイプライン経由 |

### 1.3 スキーマ進化の経緯

```
v1.0 (2026-03-09)  6ノード・9リレーション — 基盤データ層のみ
  ↓ PDFパイプライン対応、Claim品質強化
v2.0 (2026-03-12)  10ノード・15リレーション — Claim-centric、Insight/FDP/FiscalPeriod 追加
  ↓ Stance/Question/CAUSES/Temporal Chain 追加
v2.1 (2026-03-17)  12ノード・20リレーション — AI推論最適化
  ↓ entity_key/topic_key 複合キー、Source運用プロパティ
v2.2 (2026-03-22)  複合キー・運用プロパティ強化
  ↓ FIBO準拠再設計（薄いハブノード）
v3.0 (2026-03-23)  33ノード・59リレーション — FIBO準拠オントロジー
  ↓ SSoT統一、マルチラベル移行、パイプラインリファクタ
v3.0 完全適用 (2026-03-30)  ontology.yaml SSoT 確立、品質スコア 73.3 (B)
```

### 1.4 他インスタンスとの関係

| インスタンス | ポート | 用途 | 関係 |
|-------------|--------|------|------|
| **research-neo4j** | 7688 | 金融リサーチ知識 | 本ドキュメントの対象 |
| note-neo4j | 7687 | 会話履歴・議論メモ | Memory/Conversation/Discussion |
| creator-neo4j | 7689 | クリエイター運用 | Fact/Tip/Story/Entity (SNS投稿素材) |

research-neo4j は銘柄調査・マクロ分析専用。article-neo4j（旧称）は research-neo4j に統合済みで廃止。

---

## 2. オントロジー設計

### 2.1 ノード概観（44ラベル、現行DB）

ontology.yaml で定義されたスキーマ上は33ラベル・59リレーションだが、マルチラベル方式により実DB上は44ラベルが存在する（Entity のサブタイプラベル14種が追加されるため）。

### 2.2 ノード分類体系

ontology.yaml v3.0 では、ノードを以下の6カテゴリに分類している。

#### Common Nodes（2）— 全インスタンス共通の基盤

| ラベル | キープロパティ | 説明 | 現行件数 |
|--------|-------------|------|---------|
| **Source** | `source_id` | データの出典元（ニュース、論文、レポート等） | 3,451 |
| **Entity** | `entity_key` | 固有名詞。`entity_key` は `"Name::type"` 形式 | 1,647 |

Entity はマルチラベル方式を採用しており、以下の14種のサブタイプラベルを持つ:

| サブタイプラベル | 件数 | 統合元の旧 entity_type |
|---------------|------|----------------------|
| Technology | 357 | technology, system |
| Company | 298 | company, fintech, subsidiary, digital_bank, it_services |
| Indicator | 258 | indicator, metric |
| Organization | 208 | organization, central_bank, government, government_agency, institution, exchange |
| Product | 129 | product, dataset, data_center |
| Person | 115 | person |
| Sector | 90 | sector, market |
| MarketIndex | 49 | index |
| Concept | 44 | concept, model, method, theme, article_proposal, event |
| Instrument | 43 | instrument, etf, currency, currency_pair, fund, bond, asset |
| Country | 32 | country, region |
| Commodity | 25 | commodity |
| Broker | 9 | broker |
| Regulation | 0 | regulation (新規、データ未投入) |

```cypher
-- 横断クエリ（全Entity）
MATCH (e:Entity) RETURN e.name, labels(e)

-- タイプ別クエリ
MATCH (c:Company) RETURN c.name, c.ticker

-- サブタイプ確認
MATCH (e:Entity) WHERE e.sub_type IS NOT NULL RETURN e.sub_type, count(e)
```

#### Content Types（5）— ナレッジの種類

| ラベル | キープロパティ | 説明 | 現行件数 |
|--------|-------------|------|---------|
| **Fact** | `fact_id` | 検証済みの事実・データ・統計 | 3,103 |
| **Claim** | `claim_id` | 主張・意見・予測・アナリストの見解 | 2,401 |
| **Chunk** | `chunk_id` | ソースドキュメントの断片・セクション | 1,532 |
| **FinancialDataPoint** | `datapoint_id` | 定量的な財務・経済データポイント | 565 |
| **Insight** | `insight_id` | 分析から導出された洞察・知見 | 23 |

**Fact vs Claim の境界:**
- **Fact**: 「トヨタの2025年度売上高は37兆円」— 検証済み過去の客観的情報
- **Claim**: 「WACC 8.5% を前提とするとフェアバリューは…」— 前提を含む主張

**Insight の5タイプ**: synthesis（統合）, contradiction（矛盾）, gap（欠落）, hypothesis（仮説）, pattern（パターン）

#### Domain Nodes（9）— ドメイン固有の構造ノード

| ラベル | キープロパティ | 説明 | 現行件数 |
|--------|-------------|------|---------|
| **Topic** | `topic_key` | トピック分類。`"Name::category"` 形式 | 721 |
| **Author** | `author_id` | ソースの著者・アナリスト | 115 |
| **Stance** | `stance_id` | アナリストのスタンス・投資判断 | 74 |
| **Metric** | `metric_id` | 財務指標の定義（Revenue, EBITDA等） | 55 |
| **FiscalPeriod** | `period_id` | 会計期間（年度・四半期） | 47 |
| **Sector** | `sector_id` | 産業セクター（GICS準拠） | 90 |
| **ConceptCategory** | `concept_category_id` | 上位概念カテゴリ（8大分類） | 8 |
| **AuthorType** | `author_type_id` | 著者の種類分類 | 4 |
| **InstrumentClass** | `instrument_class_id` | 金融商品種類（FIBO SEC階層） | 13 |

#### Source Classification Nodes（5）— ソース分類の薄いハブ

| ラベル | キープロパティ | 説明 | 現行件数 |
|--------|-------------|------|---------|
| **SourceType** | `source_type_id` | ソース種類（news, blog, web, pdf 等） | 17 |
| **Domain** | `domain_id` | Webドメイン（サイト単位の集約） | 439 |
| **TrustLevel** | `trust_level_id` | 信頼度分類（10段階: official〜social） | 20 |
| **Language** | `language_id` | 言語コード（ISO 639-1） | 3 |
| **Pipeline** | `pipeline_id` | 投入パイプライン（コマンドソース） | 10 |

**TrustLevel 階層（信頼度順）:**
1. official（公的機関）→ 2. academic（学術）→ 3. company（企業公式）→ 4. institutional（機関投資家）→ 5. analyst（アナリスト）→ 6. industry（業界）→ 7. media（メディア）→ 8. primary（一次データ）→ 9. blog → 10. social

#### Entity Classification Nodes（4）— エンティティ分類

| ラベル | キープロパティ | 説明 | 現行件数 |
|--------|-------------|------|---------|
| **EntityType** | `entity_type_id` | Entity のサブタイプ分類（14種） | 42 |
| **Identifier** | `identifier_id` | 識別子（ticker, ISIN, LEI, CIK 等） | 144 |
| **Industry** | `industry_id` | 産業分類（Sector の下位） | 48 |
| **Alias** | `alias_id` | Entity/Topic の別名・略称 | (未集計) |

#### Content Classification Nodes（4）— コンテンツ分類

| ラベル | キープロパティ | 説明 | 現行件数 |
|--------|-------------|------|---------|
| **FactType** | `fact_type_id` | 事実の種類（10種） | 10 |
| **ClaimType** | `claim_type_id` | 主張の種類（10種） | 14 |
| **UnitOfMeasure** | `unit_id` | 数値の単位（通貨含む） | 38 |
| **DataPointType** | `datapoint_type_id` | actual/estimate/forecast/consensus | 4 |

#### Operational Nodes（4）— ドメインモデル外

| ラベル | 説明 | 現行件数 |
|--------|------|---------|
| **Memory** | MCP Memory（設計・技術判断のサブラベル付き） | 20 |
| **SkillRun** | スキル実行トレース | 20 |
| **QualitySnapshot** | KG品質計測スナップショット | 7 |
| **Question** | 調査質問 | 3 |

---

## 3. リレーション体系

### 3.1 全リレーション一覧（59種定義、58種実データ）

#### コンテンツ接続（7）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `TAGGED` | Source → Topic | 427,326 | ソースのトピック分類 |
| `STATES_FACT` | Source → Fact | 4,057 | ソースが述べる事実 |
| `MAKES_CLAIM` | Source → Claim | 2,211 | ソースが主張する内容 |
| `CONTAINS_CHUNK` | Source → Chunk | 1,532 | ソースの断片化 |
| `EXTRACTED_FROM` | Fact\|Claim → Chunk | 3,699 | Chunk からの抽出元 |
| `HAS_DATAPOINT` | Source → FDP | 463 | ソースの定量データ |
| `ABOUT` | Fact\|Claim → Topic | 5,343 | コンテンツのトピック |

#### エンティティ関連（4）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `RELATES_TO` | Fact\|FDP → Entity | 4,433 | データが言及するエンティティ |
| `MENTIONS` | Fact\|Claim\|Chunk → Entity | 925 | エンティティへの言及 |
| `IN_SECTOR` | Entity → Sector | 143 | エンティティのセクター |
| `ON_ENTITY` | Stance → Entity | 74 | スタンスの対象 |

#### 分析・推論（6）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `SUPPORTED_BY` | Claim → Fact | 5,150 | 主張を裏付ける事実 |
| `CONTRADICTS` | Claim → Claim | 159 | 矛盾する主張 |
| `INFLUENCES` | Entity → Entity | 1,637 | 影響関係 |
| `CAUSES` | Entity → Entity | 46 | 因果関係 |
| `DERIVED_FROM` | Insight → Fact | 1,666 | 洞察の導出元 |
| `SHARES_TOPIC` | Source → Source | 3,088 | 同一トピック共有 |

#### 時系列（3）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `FOR_PERIOD` | FDP → FiscalPeriod | 537 | データの対象期間 |
| `NEXT_PERIOD` | FiscalPeriod → FiscalPeriod | 15 | 次の会計期間 |
| `TREND` | FDP → FDP | 114 | 時系列チェーン（metric_id付き） |

#### エンティティ間（9）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `COMPETES_WITH` | Entity → Entity | 82 | 競合関係 |
| `CUSTOMER_OF` | Entity → Entity | 30 | 顧客関係 |
| `SUBSIDIARY_OF` | Entity → Entity | 18 | 子会社関係 |
| `PARTNERS_WITH` | Entity → Entity | 23 | パートナーシップ |
| `INVESTED_IN` | Entity → Entity | 9 | 投資関係 |
| `GOVERNS` | Entity → Entity | 6 | 規制・監督関係 |
| `OPERATES_IN` | Entity → Entity | 2 | 事業展開先 |
| `SPUN_OFF_FROM` | Entity → Entity | 1 | スピンオフ元 |
| `LED_BY` | Entity → Entity | 1 | 経営リーダー |

#### メタ・スタンス（8）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `AUTHORED_BY` | Source → Author | 192 | ソースの著者 |
| `COAUTHORED_WITH` | Author → Author | 259 | 共著関係 |
| `CO_MENTIONED_WITH` | Entity → Entity | 171 | 共起関係 |
| `MEASURES` | Metric → Entity | 336 | 指標の計測対象 |
| `FOR_METRIC` | FDP → Metric | 180 | データの指標種別 |
| `HOLDS_STANCE` | Source → Stance | 74 | ソースが示すスタンス |
| `BASED_ON` | Stance → Source | 74 | スタンスの根拠 |
| `SOURCED_FROM` | Fact\|Claim → Source | 16 | コンテンツの出典 |

#### Source 分類（5）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `IS_SOURCE_TYPE` | Source → SourceType | 1,823 | ソース種類 |
| `FROM_DOMAIN` | Source → Domain | 3,014 | Webドメイン |
| `RATED_AS` | Source → TrustLevel | 2,821 | 信頼度評価 |
| `IN_LANGUAGE` | Source → Language | 128 | 言語 |
| `INGESTED_VIA` | Source → Pipeline | 2,733 | 投入パイプライン |

#### Entity 分類（5）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `IS_TYPE` | Entity → EntityType | 1,593 | サブタイプ分類 |
| `HAS_IDENTIFIER` | Entity → Identifier | 145 | 識別子 |
| `IN_INDUSTRY` | Entity → Industry | 91 | 産業分類 |
| `IS_INSTRUMENT_CLASS` | Entity → InstrumentClass | 93 | 金融商品種類 |
| `ALIAS_OF` | Alias → Entity\|Topic | — | 別名の正規化 |

#### Content 分類（4）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `IS_FACT_TYPE` | Fact → FactType | 2,923 | 事実の種類 |
| `IS_CLAIM_TYPE` | Claim → ClaimType | 1,023 | 主張の種類 |
| `IN_UNIT` | FDP\|Stance → UnitOfMeasure | 453 | 単位 |
| `IS_DATAPOINT_TYPE` | FDP → DataPointType | 272 | 実績/予想/予測 |

#### Domain 分類（3）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `IS_CATEGORY` | Topic → ConceptCategory | 217 | 上位概念カテゴリ |
| `AFFILIATED_WITH` | Author → Entity | 21 | 著者の所属組織 |
| `IS_AUTHOR_TYPE` | Author → AuthorType | 115 | 著者の種類 |

#### 階層・参照（3）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `PARENT_CLASS` | InstrumentClass → InstrumentClass | 6 | L2→L1 階層 |
| `IN_PARENT_SECTOR` | Industry → Sector | 16 | 親セクター |
| `ISSUED_BY` | Identifier → Entity | — | 識別子の発行機関 |

#### レガシー（2）

| リレーション | From → To | 件数 | 説明 |
|-------------|-----------|------|------|
| `BELONGS_TO` | Entity\|Topic → Sector\|Topic | 24 | 旧所属関係 |
| `ASKS_ABOUT` | Question → Topic | 7 | 調査質問のトピック |

---

## 4. FIBO準拠設計の詳細

### 4.1 FIBO（Financial Industry Business Ontology）からの借用

KG v3.0 では以下の FIBO コンセプトを採用:

| FIBO コンセプト | 対応ノード/リレーション | 適用 |
|---------------|----------------------|------|
| `Securities/Identification` | Identifier ノード + HAS_IDENTIFIER | ticker, ISIN, LEI, CIK, FIGI |
| `SEC/Equities`, `SEC/Debt`, `SEC/Funds`, `DER` | InstrumentClass 階層 | 金融商品の2階層分類 |
| `hasIdentifier` パターン | HAS_IDENTIFIER リレーション | Entity→Identifier |
| `isClassifiedBy` パターン | IS_TYPE, IS_SOURCE_TYPE 等 | 分類ノードへのリレーション |

### 4.2 InstrumentClass 階層（FIBO SEC domain 準拠）

```
equity (株式)
  ├── common_share
  ├── preferred_share
  └── depositary_receipt
debt (債券)
  ├── government_bond
  ├── corporate_bond
  └── convertible
fund (ファンド)
  ├── etf
  ├── mutual_fund
  └── money_market
derivative (デリバティブ)
  ├── option
  ├── future
  └── swap
currency (通貨)
  ├── fiat
  ├── crypto
  └── currency_pair
commodity (コモディティ)
  ├── energy
  ├── metal
  └── agricultural
index_basket (指数・バスケット)
  ├── equity_index
  ├── bond_index
  └── commodity_index
```

### 4.3 ConceptCategory（8大分類）

Topic ノードを上位概念で分類する。

| カテゴリ | 日本語 | Layer | 含まれる旧 category |
|---------|--------|-------|-------------------|
| MacroEconomics | マクロ経済 | What | macro, political, geopolitical |
| EquityResearch | 株式リサーチ | What | stock, earnings, valuation, competition, kpi |
| SectorAnalysis | セクター分析 | What | sector, cross_sector, industry-trend |
| InvestmentStrategy | 投資戦略 | What | investment_strategy, investment, capital-allocation |
| Technology | テクノロジー | What | technology, ai, quantitative_finance |
| WealthManagement | 資産形成 | What | wealth, assets |
| Regulation | 規制 | What | regulatory, governance, corporate-action |
| ContentPlanning | コンテンツ企画 | Meta | content_planning, reddit, theme |

---

## 5. データ投入パイプライン

### 5.1 アーキテクチャ

```
[リサーチデータ入力 (JSON)]
        │
        ▼
  ① emit_research_queue.py (Python)
     └─ 11マッパーのいずれかでデータ変換
     └─ graph-queue JSON を出力
        │
        ▼
  ② entity_linker.py (Python)
     └─ entity_key の事前解決（既存Entity照合）
     └─ linked JSON を出力
        │
        ▼
  ③ neo4j_loader.py (Python)
     └─ MERGE 冪等投入（APOC対応）
     └─ YAML SSoT から制約・インデックス自動適用
        │
        ▼
  research-neo4j
```

Claude Code スキル（`/save-to-research-graph`）はオーケストレーション専任で、上記 Python CLI を順次呼び出す。

### 5.2 マッパー一覧（11種）

| マッパー | コマンドソース | 用途 | 使用割合 |
|---------|---------------|------|---------|
| web_research | web-research | Web検索結果の投入 | 38% |
| finance_news | finance-news-workflow | ニュースRSS記事 | 33% |
| wealth_scrape | wealth-scrape | 資産形成ブログ | 20% |
| pdf_extraction | pdf-extraction, pdf-archive | PDFレポート | 7% |
| academic_fetch | academic-fetch | arXiv論文 | 1% |
| reddit_topics | reddit-finance-topics | Reddit投稿 | <1% |
| topic_discovery | topic-discovery | トピック提案結果 | <1% |
| ai_research | — | AI投資リサーチ | 未使用 |
| market_report | — | マーケットレポート | 未使用 |
| asset_management | — | 資産形成 | 未使用 |
| finance_full | — | 記事全工程 | 未使用 |

全マッパーは `scripts/mappers/` 配下にプラグインとして配置され、共通ロジックは `BaseMapper` クラスに抽出されている。

### 5.3 禁止事項

`mcp__neo4j-research__research-write_neo4j_cypher` による直接のノード・リレーション作成（CREATE/MERGE）は禁止。

**例外:**
- スキーマ操作（`CREATE CONSTRAINT`, `CREATE INDEX`）
- ユーザーの明示的承認がある修復作業（`SET`, `DELETE`）

**読み取り** (`mcp__neo4j-research__research-read_neo4j_cypher`) は制限なし。

### 5.4 ontology_loader.py アダプター

ontology.yaml と旧 knowledge-graph-schema.yaml の構造非互換を吸収する共通アダプター。

| 関数 | 説明 |
|------|------|
| `load_consolidation_mapping()` | entity_type 統合マッピング (42種→14種) |
| `load_source_type_normalization()` | source_type 正規化マッピング (27種→5種) |
| `load_multilabel_types()` | マルチラベル entity_type キー一覧 |
| `load_constraints()` | Neo4j UNIQUE 制約定義 |
| `load_indices()` | Neo4j インデックス定義 |
| `load_namespaces()` | 名前空間定義 |

---

## 6. 知識発見パターン

### 6.1 AI創発的発見の設計意図

research-neo4j の中核的な価値は、蓄積されたデータからAIが創発的な考察を行えることにある:

- **特定の主張を裏付ける情報の特定** — `SUPPORTED_BY` チェーンの探索
- **矛盾する主張の発見** — `CONTRADICTS` リレーションの検出
- **欠落情報の推測** — `Question` ノードと知識ギャップ分析
- **クロスドメイン仮説の生成** — `INFLUENCES`/`CAUSES` を跨ぐパス探索

### 6.2 代表的なクエリパターン

```cypher
-- 特定銘柄の全Fact/Claimを取得（銘柄レポート執筆用）
MATCH (e:Company {name: "Indosat"})
OPTIONAL MATCH (f:Fact)-[:RELATES_TO]->(e)
OPTIONAL MATCH (c:Claim)-[:MENTIONS]->(e)
RETURN e.name, collect(DISTINCT f.content) AS facts, collect(DISTINCT c.content) AS claims

-- 矛盾する主張の発見
MATCH (c1:Claim)-[:CONTRADICTS]->(c2:Claim)
RETURN c1.content, c2.content, c1.sentiment, c2.sentiment

-- 時系列トレンド（特定指標）
MATCH (dp1:FinancialDataPoint)-[t:TREND]->(dp2:FinancialDataPoint)
WHERE t.metric_id = "revenue"
MATCH (dp1)-[:FOR_PERIOD]->(fp1:FiscalPeriod)
MATCH (dp2)-[:FOR_PERIOD]->(fp2:FiscalPeriod)
RETURN fp1.period_id, dp1.value, fp2.period_id, dp2.value, t.change_pct

-- ソースの信頼度分布
MATCH (s:Source)-[:RATED_AS]->(tl:TrustLevel)
RETURN tl.name, tl.rank, count(s) AS source_count
ORDER BY tl.rank

-- クロスドメイン影響パス
MATCH path = (e1:Entity)-[:INFLUENCES*1..3]->(e2:Entity)
WHERE e1.name = "Federal Reserve" AND e2 <> e1
RETURN [n IN nodes(path) | n.name] AS influence_chain
```

---

## 7. データ品質

### 7.1 品質スコア推移

| 日付 | 総合 | structural | completeness | consistency | accuracy |
|------|------|-----------|-------------|------------|---------|
| 2026-03-28 | 53.8 (C) | 60.0 | 50.0 | 16.7 | 50.0 |
| 2026-03-30 | 73.3 (B) | 80.0 | 100.0 | 83.3 | 50.0 |

### 7.2 既知の品質課題

| 課題 | 件数 | ステータス |
|------|------|----------|
| EXTRACTED_FROM 欠落 Fact | 377件 | 52件は決定論的に補完可能 |
| Entity 未接続 Fact（RELATES_TO 欠落） | 577件 | LLM NER バッチ処理で修復予定 |
| ABOUT/MENTIONS/RELATES_TO の3種混在 | — | 設計議論中（統一 or semantic 維持） |

### 7.3 正規化ステータス

| 項目 | 正規化前 | 正規化後 |
|------|---------|---------|
| entity_type | 30種 | 14種（マルチラベル） |
| source_type | 28種 | 4種 (web/news/pdf/blog) + null |

---

## 8. インフラ構成

| 項目 | 値 |
|------|-----|
| コンテナ | Docker (docker-compose.yml の neo4j-research サービス) |
| Bolt | bolt://localhost:7688 |
| Browser | http://localhost:7475 |
| データ保存先 | /Volumes/NeoData/neo4j-research/ (外付けSSD) |
| バックアップ | AuraDB Free（初回 2026-03-19, `/backup-auradb` スキル） |
| パスワード | NEO4J_PASSWORD 環境変数 |
| Edition | Community Edition（単一DB制約あり） |

---

## 9. 関連ファイル一覧

| ファイル | 説明 |
|---------|------|
| `data/lifecycle-state/research/ontology.yaml` | **SSoT** — v3.0 FIBO準拠スキーマ定義 |
| `scripts/ontology_loader.py` | ontology.yaml アダプター（6関数） |
| `scripts/emit_research_queue.py` | graph-queue JSON 生成（CLIエントリポイント） |
| `scripts/entity_linker.py` | エンティティリンキング（entity_key 事前解決） |
| `src/data_pipeline/neo4j_loader.py` | Neo4j 投入（MERGE冪等） |
| `scripts/mappers/` | 11マッパープラグイン |
| `.claude/rules/neo4j-write-rules.md` | 直書き禁止ルール |
| `.claude/rules/neo4j-query-construction.md` | Cypher クエリ構築ルール |
| `.claude/rules/neo4j-namespace-convention.md` | 名前空間・命名規約 |
| `docs/plan/KnowledgeGraph/2026-03-12_discussion-kg-schema-v2.md` | v2.0 設計議論 |
| `docs/plan/2026-03-17_kg-v2.1-reasoning-schema-research.md` | v2.1 AI推論最適化設計 |
| `docs/plan/SideBusiness/2026-03-23_discussion-kg-v30-merge.md` | v3.0 マージ記録 |
| `docs/plan/SideBusiness/2026-03-30_discussion-research-neo4j-redesign.md` | v3.0 完全適用議論 |
| `docs/plan/2026-03-30_research-neo4j-schema-pipeline-redesign.md` | プロジェクト完了記録 |
| `docs/plan/SideBusiness/2026-03-31_discussion-research-neo4j-schema-investigation.md` | ontology.yaml SSoT化決定 |

---

## 10. グラフ規模サマリー（2026-04-01 時点）

| メトリクス | 値 |
|-----------|-----|
| ノードラベル数 | 44（ontology定義33 + マルチラベル14 - 重複3） |
| リレーションタイプ数 | 58 |
| 総ノード数 | 約 16,000 |
| 総リレーション数 | 約 490,000 |
| 最大ノード | Source: 3,451 |
| 最大リレーション | TAGGED: 427,326 |
| 品質スコア | 73.3 (B) |
