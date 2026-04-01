# research-neo4j ナレッジグラフ — 設計思想・オントロジー・スキーマ全仕様

**生成日**: 2026-04-01
**DBバージョン**: KG v2.3（v3.0 移行計画中）
**接続先**: `bolt://localhost:7688`
**規模**: 14,589 ノード / 481,614 リレーション（2026-04-01 時点）

---

## 1. 設計思想

### 1.1 目的

research-neo4j はバイサイドアナリスト向け**投資リサーチ支援ナレッジグラフ（KG）**。

- AIエージェントが KG を参照しながら投資レポート（Initial Report）・投資仮説を自動生成
- 証券会社レポート・SEC Filing・ニュース・学術論文を統一スキーマで管理
- エンティティ間の因果・競合・依存関係を構造化し、人手では追えない間接影響を可視化

### 1.2 Single Source of Truth（SSOT）

```
research-neo4j = プロジェクト全体のSSOT
  ├── 銘柄・マクロ調査
  ├── アナリストレポート（セルサイド）
  ├── SEC EDGAR / XBRL 財務データ
  ├── Webリサーチ・ブログ
  └── 学術論文（arXiv）
```

記事執筆・投資仮説生成・週次レポートはすべて KG を出発点とする。
直接 Web 検索のみで執筆することは**禁止**（Neo4j 直書き禁止ルールと対称）。

### 1.3 コアデザイン原則

| 原則 | 説明 |
|------|------|
| **Provenance First** | 全 Fact/Claim は `Source` ノードに必ずトレースバック可能 |
| **Entity Disambiguation** | `entity_key = {name}::{entity_type}` で全エンティティを一意化 |
| **Claim vs Fact の分離** | 客観的事実（Fact）とアナリスト見解（Claim）を明確に区別 |
| **Source-scoped TREND** | セルサイドDPはレポート間でクロスオーバーしない（Source単位でスコーピング） |
| **Idempotent Ingestion** | 同一データを何度投入してもグラフが崩れない（MERGE + entity_key） |
| **Layered Architecture** | Source層 → Lexical層（Chunk） → Knowledge層（Fact/Claim） → Entity層の4階層 |

### 1.4 データパイプライン

全データ投入は **3段パイプライン経由**（直接 Cypher 書き込みは禁止）。

```
リサーチデータ
  → ① emit_research_queue.py   [graph-queue JSON 生成]
  → ② entity_linker.py          [4段階エンティティマッチング]
  → ③ neo4j_loader.py           [MERGE + 冪等投入]
  → research-neo4j
```

---

## 2. スキーマ進化履歴

| バージョン | 日付 | 主な変更 |
|-----------|------|---------|
| v1.0 | 2026-03-11 | 初期スキーマ（6ノード・9リレーション）—Source/Chunk/Claim/Entity/Organization/FiscalPeriod |
| v2.0 | 2026-03-12 | Claim 中心設計 — FinancialDataPoint/Insight 追加 |
| v2.1 | 2026-03-17 | Stance/CAUSES/Temporal/Question/AUTHORED_BY/TREND 追加 |
| v2.2 | 2026-03-17 | entity_key/topic_key 複合キー + Source.command_source/domain + blog source_type |
| v2.3 | 2026-03-18 | authority_level + article-neo4j → research-neo4j 統合（note記事データ統合） |
| **v3.0** | 計画中 | FIBO準拠・マルチラベル移行・BaseMapper + 11プラグイン・YAML SSoT 統一 |

---

## 3. オントロジー（概念層別設計）

### Layer 1: ソース・来歴層

```
Source ──AUTHORED_BY──> Author ──IS_AUTHOR_TYPE──> AuthorType
Source ──FROM_DOMAIN──> Domain
Source ──CONTAINS_CHUNK──> Chunk
Source ──IS_SOURCE_TYPE──> SourceType
Source ──IN_LANGUAGE──> Language
Source ──RATED_AS──> TrustLevel
Source ──INGESTED_VIA──> Pipeline
Source ──ABOUT──> [Entity/Company/Person/...]
```

**Source** は全データの起点。authority_level（一次/二次/三次）とsource_type（web/news/pdf/original/blog/sec_filing等）で信頼性を管理。

### Layer 2: レキシカル層

```
Source ──CONTAINS_CHUNK──> Chunk
Fact ──EXTRACTED_FROM──> Chunk
Claim ──EXTRACTED_FROM──> Chunk
```

**Chunk** は元文書を分割したテキスト断片。Fact/Claim の根拠（provenance）リンクを保持。

### Layer 3: ナレッジ抽出層

```
Source ──MAKES_CLAIM──> Claim ──IS_CLAIM_TYPE──> ClaimType
                              ──ABOUT──> [Entity系]
                              ──SUPPORTED_BY──> Fact
                              ──CONTRADICTS──> Claim
                              ──TAGGED──> Topic

Entity ──STATES_FACT──> Fact ──IS_FACT_TYPE──> FactType
                             ──ABOUT──> [Entity系]
                             ──EXTRACTED_FROM──> Source/Chunk
                             ──RELATES_TO──> [Entity系]
                             ──TAGGED──> Topic
```

**Fact（客観的事実）** と **Claim（アナリスト見解・主張）** を明確に分離。

- Claim の `claim_type` は議論的・予測的・評価的な主張（例: `bullish`, `target_price`, `risk_factor`）
- Fact の `fact_type` は確認済みの事実（例: `financial`, `event`, `regulatory`）

### Layer 4: エンティティ・マスターデータ層

**Entity（スーパーノード）** を中心に、特化型サブタイプが派生。

```
Entity (スーパーノード)
  ├── Company       (上場企業・非上場企業)
  ├── Organization  (機関・政府・NGO等)
  ├── Person        (経営者・政策立案者・研究者)
  ├── Instrument    (金融商品一般)
  ├── MarketIndex   (株価指数・市場インデックス)
  ├── Commodity     (コモディティ)
  ├── Indicator     (経済指標)
  ├── Technology    (テクノロジー・製品カテゴリ)
  ├── Product       (個別製品・サービス)
  ├── Concept       (抽象概念・トレンド)
  ├── Country       (国・地域)
  ├── Sector        (GICS/SICセクター)
  └── Broker        (証券会社)
```

`entity_key = "{name}::{entity_type}"` で MERGE 冪等性を保証。

### Layer 5: 財務定量データ層

```
Entity ──HAS_DATAPOINT──> FinancialDataPoint ──FOR_METRIC──> Metric ──IN_UNIT──> UnitOfMeasure
                                              ──FOR_PERIOD──> FiscalPeriod ──NEXT_PERIOD──> FiscalPeriod
                                              ──IS_DATAPOINT_TYPE──> DataPointType
                                              ──TREND──> FinancialDataPoint
```

**FinancialDataPoint** は XBRL/SEC EDGAR から取得した定量財務データ。
**TREND リレーション** は時系列変化を表現（source_hash でスコーピング）。

### Layer 6: セマンティック連携層

```
Entity ──RELATES_TO──> Entity          (汎用リレーション)
Entity ──SHARES_TOPIC──> Entity        (共通トピック経由の間接関連)
Entity ──CO_MENTIONED_WITH──> Entity   (同一文書内共起)
Entity ──INFLUENCES──> Entity          (影響関係)
Entity ──CAUSES──> Entity              (因果関係)
Topic ──TAGGED──> [全エンティティ]     (トピック付与: 427,326件)
```

**TAGGED** リレーションが最多（427,326件）。トピック分類が全エンティティ横断の索引として機能。

### Layer 7: アナリスト評価層

```
Author ──HOLDS_STANCE──> Stance ──ON_ENTITY──> Entity
                                ──BASED_ON──> Source
Author ──AFFILIATED_WITH──> [Organization/Broker]
Author ──COAUTHORED_WITH──> Author
```

**Stance** ノードはアナリスト個人のレーティング・目標株価を時点付きで管理。

### Layer 8: 分類・参照データ層

```
Entity ──IS_TYPE──> EntityType
Claim ──IS_CLAIM_TYPE──> ClaimType
Fact ──IS_FACT_TYPE──> FactType
Source ──IS_SOURCE_TYPE──> SourceType
Instrument ──IS_INSTRUMENT_CLASS──> InstrumentClass ──PARENT_CLASS──> InstrumentClass
Entity ──IN_SECTOR──> Sector ──IN_PARENT_SECTOR──> Industry
Concept ──IS_CATEGORY──> ConceptCategory
```

### Layer 9: 運用・メタデータ層

```
SkillRun         (スキル実行トレース)
QualitySnapshot  (KG品質スコア履歴)
Pipeline         (投入パイプライン定義)
Question         ──ASKS_ABOUT──> Entity (未解決問い)
Insight          ──DERIVED_FROM──> Fact/Claim (洞察)
Memory           (会話メモリ・設計決定記録)
```

---

## 4. 主要ノード詳細

### Source（3,451件）

全データの来歴ノード。information の provenance を保証。

| プロパティ | 型 | インデックス | 説明 |
|-----------|-----|------------|------|
| source_id | STRING | UNIQUE | UUID |
| title | STRING | FULLTEXT | タイトル |
| source_type | STRING | RANGE | web/news/pdf/original/blog/sec_filing等 |
| authority_level | STRING | RANGE | primary/secondary/tertiary |
| url | STRING | - | 元URL |
| published_at | STRING | RANGE | 発行日時（ISO 8601） |
| command_source | STRING | RANGE | 投入コマンド名 |
| domain | STRING | RANGE | ドメイン名 |
| source_hash | STRING | - | 重複検知用ハッシュ |
| language | STRING | - | 言語コード |
| organization | STRING | - | 発行組織名 |
| publisher | STRING | - | 出版社 |
| arxiv_id | STRING | - | arXiv論文ID |
| form_type | STRING | - | SEC Form種別（10-K, 10-Q等） |
| accession_number | STRING | - | SEC アクセッション番号 |
| feed_source | STRING | - | RSSフィード名 |
| batch_label | STRING | - | 一括投入バッチ識別子 |

### Fact（3,103件）

確認済み客観的事実。

| プロパティ | 型 | インデックス | 説明 |
|-----------|-----|------------|------|
| fact_id | STRING | UNIQUE | UUID |
| fact_type | STRING | RANGE | financial/event/regulatory/macro等 |
| content | STRING | FULLTEXT | 事実の内容（英語） |
| statement | STRING | - | 事実の命題形式 |
| as_of_date | STRING | RANGE | 情報基準日 |
| source_url | STRING | RANGE | 元ソースURL |
| confidence | FLOAT | - | 確信度（0.0〜1.0） |
| event_date | STRING | - | イベント発生日 |
| period | STRING | - | 対象期間 |
| value | STRING | - | 数値/定量データ |
| data_vintage | STRING | - | データビンテージ |
| phase | INTEGER | - | パイプラインフェーズ番号 |
| category | STRING | - | カテゴリ分類 |

### Claim（2,401件）

アナリスト・著者の見解・主張・評価。

| プロパティ | 型 | インデックス | 説明 |
|-----------|-----|------------|------|
| claim_id | STRING | UNIQUE | UUID |
| claim_type | STRING | RANGE | bullish/bearish/target_price/risk_factor等 |
| sentiment | FLOAT | RANGE | センチメントスコア（-1.0〜+1.0） |
| statement | STRING | - | 主張の命題形式 |
| summary | STRING | - | 要約 |
| confidence | FLOAT | - | 確信度 |
| target_price | FLOAT | - | 目標株価 |
| time_horizon | STRING | - | 時間軸（short/medium/long） |
| rating | STRING | - | レーティング（Buy/Hold/Sell等） |
| as_of_date | STRING | - | 情報基準日 |
| total_score | INTEGER | - | 品質スコア（複数指標の合計） |
| rank | INTEGER | - | 優先度ランク |
| magnitude | FLOAT | - | インパクト規模 |
| feasibility | INTEGER | - | 実現可能性スコア |
| uniqueness | INTEGER | - | 独自性スコア |
| timeliness | INTEGER | - | 時事性スコア |
| reader_interest | INTEGER | - | 読者関心スコア |
| information_availability | INTEGER | - | 情報入手可能性スコア |
| target_audience | STRING | - | 対象読者 |
| key_points | STRING | - | 主要ポイント（JSON配列文字列） |
| topic_title | STRING | - | 記事トピックタイトル候補 |

### Entity（1,647件） + サブタイプ

全エンティティの基底ノード。

| プロパティ | 型 | インデックス | 説明 |
|-----------|-----|------------|------|
| entity_id | STRING | UNIQUE | UUID |
| entity_key | STRING | UNIQUE | {name}::{entity_type} 複合キー |
| entity_type | STRING | RANGE | company/organization/person/etc |
| name | STRING | RANGE + FULLTEXT | 正規化名称 |
| ticker | STRING | UNIQUE | ティッカーシンボル |
| aliases | LIST | - | 別名リスト |
| description | STRING | - | 説明文 |
| country | STRING | - | 国コード |
| sector | STRING | - | セクター名 |
| industry | STRING | - | 業種名 |
| sub_type | STRING | - | サブタイプ |
| exchange | STRING | - | 取引所 |
| fiscal_year_end | STRING | - | 決算月 |
| sic_code | STRING | - | SICコード |
| sec_cik | STRING | - | SEC CIK番号 |
| enriched_at | STRING | - | エンリッチメント日時 |
| resolved | BOOLEAN | - | 名寄せ解決済みフラグ |
| match_layer | STRING | - | マッチングレイヤー（exact/fuzzy/vector等） |

**Entity vector index**: `entity_embedding_idx`（VECTOR型）— 類似エンティティ検索に使用。

### FinancialDataPoint（565件）

XBRL/SEC EDGAR 由来の定量財務データ。

| プロパティ | 型 | インデックス | 説明 |
|-----------|-----|------------|------|
| datapoint_id | STRING | UNIQUE | UUID |
| metric_name | STRING | RANGE | 指標名（EPS, Revenue等） |
| metric_id | STRING | - | Metric ノードへの参照ID |
| value | FLOAT | - | 数値 |
| unit | STRING | - | 単位 |
| currency | STRING | - | 通貨 |
| period_label | STRING | - | 期間ラベル（2024-Q3等） |
| period_end | STRING | - | 期末日 |
| as_of_date | STRING | - | 基準日 |
| is_estimate | BOOLEAN | RANGE | 予測値フラグ |
| xbrl_concept | STRING | - | XBRLコンセプト名 |
| sec_form_type | STRING | - | SEC Form種別 |
| filing_date | STRING | - | 提出日 |
| source_hash | STRING | - | Source単位スコーピング用ハッシュ |

### Topic（721件）

全エンティティ・Fact・Claim を横断するタグ分類。

| プロパティ | 型 | インデックス | 説明 |
|-----------|-----|------------|------|
| topic_id | STRING | UNIQUE | UUID |
| topic_key | STRING | UNIQUE | {name}::{category} 複合キー |
| name | STRING | RANGE + FULLTEXT | トピック名 |
| category | STRING | RANGE | macro/stock/asset/education/report/content_planning等 |
| description | STRING | - | 説明文 |

---

## 5. 主要リレーション詳細

| リレーション | 件数 | from → to | 説明 |
|------------|------|-----------|------|
| TAGGED | 427,326 | [全ノード] → Topic | トピック付与（最多） |
| ABOUT | 5,343 | Fact/Claim/FinancialDataPoint → [Entity系] | 対象エンティティ |
| SUPPORTED_BY | 5,150 | Claim → Fact | ClaimをFactで裏付け |
| RELATES_TO | 4,433 | [Entity系] → [Entity系] | 汎用関連（bridge型） |
| STATES_FACT | 4,057 | Entity/Organization/Country → Fact | 事実を述べる |
| EXTRACTED_FROM | 3,699 | Fact/Claim → Source/Chunk | 抽出元 |
| FROM_DOMAIN | 3,014 | Source → Domain | ドメイン帰属 |
| SHARES_TOPIC | 3,088 | [Entity系] → [Entity系] | 共通トピック経由の間接関連 |
| IS_FACT_TYPE | 2,923 | Fact → FactType | 事実タイプ分類 |
| RATED_AS | 2,821 | Source → TrustLevel | 信頼度評価 |
| MAKES_CLAIM | 2,211 | Source → Claim | ソースがClaimを含む |
| IS_SOURCE_TYPE | 1,823 | Source → SourceType | ソース種別分類 |
| IS_TYPE | 1,593 | [Entity系] → EntityType | エンティティ種別 |
| DERIVED_FROM | 1,666 | Insight/Claim → Fact/Claim | 派生元 |
| INFLUENCES | 1,637 | Entity/Person → Entity | 影響関係 |
| CONTAINS_CHUNK | 1,532 | Source → Chunk | チャンク分割 |
| IS_CLAIM_TYPE | 1,023 | Claim → ClaimType | Claim種別分類 |
| MENTIONS | 925 | Fact → [Entity系] | 言及（弱い関連） |
| IS_CATEGORY | 217 | Concept/Metric → Category | カテゴリ分類 |
| IS_AUTHOR_TYPE | 115 | Author → AuthorType | 著者種別 |
| IN_SECTOR | 143 | [Entity系] → Sector | セクター帰属 |
| IN_INDUSTRY | 91 | [Entity系] → Industry | 業種帰属 |
| IN_PARENT_SECTOR | 16 | Industry → Sector | 親セクター |
| FOR_METRIC | 180 | FinancialDataPoint → Metric | 指標参照 |
| FOR_PERIOD | 537 | FinancialDataPoint → FiscalPeriod | 期間参照 |
| IN_UNIT | 453 | FinancialDataPoint → UnitOfMeasure | 単位参照 |
| IS_DATAPOINT_TYPE | 272 | FinancialDataPoint → DataPointType | データポイント種別 |
| HAS_DATAPOINT | 463 | Entity → FinancialDataPoint | 財務データ保有 |
| MEASURES | 336 | FinancialDataPoint → Metric | 計測指標 |
| TREND | 114 | FinancialDataPoint → FinancialDataPoint | 時系列変化 |
| NEXT_PERIOD | 15 | FiscalPeriod → FiscalPeriod | 次期間リンク |
| AUTHORED_BY | 192 | Source → Author | 著者帰属 |
| AFFILIATED_WITH | 21 | Author → [Organization/Broker] | 所属機関 |
| HOLDS_STANCE | 74 | Author → Stance | スタンス表明 |
| ON_ENTITY | 74 | Stance → Entity | スタンス対象エンティティ |
| BASED_ON | 74 | Stance → Source | スタンスの根拠ソース |
| COAUTHORED_WITH | 259 | Author → Author | 共著関係 |
| CO_MENTIONED_WITH | 171 | [Entity系] → [Entity系] | 共起関連 |
| SUBSIDIARY_OF | 18 | Company/Entity → Company | 子会社関係 |
| COMPETES_WITH | 82 | Company/Entity → Company | 競合関係 |
| PARTNERS_WITH | 23 | Company/Entity → Company | パートナーシップ |
| CUSTOMER_OF | 30 | Company/Entity → Company | 顧客関係 |
| INVESTED_IN | 9 | Company/Entity → Company | 投資関係 |
| LED_BY | 1 | Company/Entity → Person | 経営者 |
| GOVERNS | 6 | Entity/Organization/Person → Entity/Country | 管轄・統治 |
| OPERATES_IN | 2 | Company/Organization → Country | 事業展開国 |
| CAUSES | 46 | Commodity/Concept/Entity → Entity | 因果関係 |
| CONTRADICTS | 159 | Claim → Claim | 矛盾するClaim |
| SPUN_OFF_FROM | 1 | Company → Company | スピンオフ元 |
| HAS_IDENTIFIER | 145 | [Entity系] → Identifier | 識別子（ISIN/CIK等） |
| ASKS_ABOUT | 7 | Question → [Entity系] | 未解決質問 |
| INGESTED_VIA | 2,733 | Source → Pipeline | 投入パイプライン |
| SOURCED_FROM | 16 | Fact → Source | 直接ソース参照 |
| BELONGS_TO | 24 | Entity → Topic | カテゴリ帰属 |
| IN_LANGUAGE | 128 | Source → Language | 言語属性 |
| PARENT_CLASS | 6 | InstrumentClass → InstrumentClass | 親クラス |
| IS_INSTRUMENT_CLASS | 93 | [Instrument系] → InstrumentClass | 商品クラス分類 |
| IS_ENTITY_TYPE | 4 | Company → EntityType | レガシー種別リンク |

---

## 6. 制約・インデックス一覧

### UNIQUENESS 制約（16件）

| 対象 | プロパティ | 説明 |
|------|-----------|------|
| Author | author_id | 著者ID |
| Chunk | chunk_id | チャンクID |
| Claim | claim_id | ClaimID |
| Entity | entity_id | エンティティID |
| Entity | entity_key | 複合キー（name::entity_type） |
| Entity | ticker | ティッカー |
| Fact | fact_id | FactID |
| FinancialDataPoint | datapoint_id | データポイントID |
| FiscalPeriod | period_id | 期間ID |
| Insight | insight_id | InsightID |
| Metric | canonical_name | 正規化名称 |
| Metric | metric_id | MetricID |
| Source | source_id | SourceID |
| Stance | stance_id | StanceID |
| Topic | topic_id | TopicID |
| Topic | topic_key | 複合キー（name::category） |

### RANGE インデックス（追加）

| 対象 | プロパティ |
|------|-----------|
| Claim | claim_type, sentiment |
| Entity | entity_type, name |
| Fact | as_of_date, fact_type, source_url |
| FinancialDataPoint | is_estimate, metric_name |
| FiscalPeriod | period_label |
| Insight | insight_type |
| Metric | canonical_name, category |
| RELATES_TO（rel） | hops, path_weight |
| Source | authority_level, command_source, domain, published_at, source_type, title |
| Topic | category |

### FULLTEXT インデックス（5件）

| 名称 | 対象 | プロパティ |
|------|------|-----------|
| research_alias_fulltext | Alias | name, value |
| research_entity_fulltext | Entity | name |
| research_entity_fulltext_v2 | Entity | name, entity_key |
| research_fact_fulltext | Fact | content |
| research_source_fulltext | Source | title |
| research_topic_fulltext | Topic | name |

### VECTOR インデックス（1件）

| 名称 | 対象 | プロパティ | 用途 |
|------|------|-----------|------|
| entity_embedding_idx | Entity | embedding | 類似エンティティ検索 |

---

## 7. 参照データノード（マスターデータ）

### EntityType（42件）
エンティティの詳細種別定義。`name_ja` で日本語名を保持。

### ClaimType（14件）
Claim の意味的分類（bullish/bearish/target_price/risk_factor/catalyst/headwind/tailwind等）。
`direction` プロパティで positive/negative/neutral を表現。

### FactType（10件）
Fact の事実種別（financial/event/regulatory/macro/company/research等）。

### SourceType（17件）
情報ソースの種別（web/news/pdf/sec_filing/original/blog/report/paper等）。

### InstrumentClass（13件）
金融商品クラス階層（FIBO準拠）。`fibo_domain` で FIBO オントロジードメインを管理。

### TrustLevel（20件）
ソース信頼度レベル。`rank` で順序付き評価を管理。

### ConceptCategory（8件）
Concept ノードのカテゴリ分類。`layer` で階層を表現。

### UnitOfMeasure（38件）
`name`, `symbol`, `dimension` で物理量・通貨・割合等を標準化。

---

## 8. 運用ノード

### SkillRun（20件）
各スキル実行のトレースログ。実行時刻・入出力サマリ・ステータスを記録。

### QualitySnapshot（7件）
KG品質計測の履歴スナップショット。8次元スコア（accuracy/completeness/consistency/timeliness/structural/discoverability/finance_specific/overall）。

### Memory（20件）
設計判断・会話セッションの永続化。スキル実行との関連を管理。

### Pipeline（10件）
データ投入パイプラインの定義ノード。`category` でデータ種別を管理。

---

## 9. 今後の計画（KG v3.0）

GitHub Project #105（Issue #278〜#293）として管理中。

| Wave | 内容 | Issue |
|------|------|-------|
| 1 | YAML SSoT 整備（knowledge-graph-schema.yaml v3.0統一） | #278, #279 |
| 2 | Entity マルチラベル移行（30種→14種統合） | #280 |
| 3 | BaseMapper + 11プラグイン化（emit_research_queue.py分割） | #281〜#287 |
| 4 | neo4j_loader.py 強化（APOC マルチラベル MERGE） | #288 |
| 5 | save-to-research-graph Python CLI化 | #289, #290 |
| 6 | データ品質修正（source_type正規化・NULL command_source補完） | #291 |
| 7 | v3.0 完全適用 + 品質検証 | #292, #293 |

---

## 10. 関連ファイル

| ファイル | 説明 |
|---------|------|
| `scripts/emit_research_queue.py` | graph-queue JSON 生成（Step 1） |
| `scripts/entity_linker.py` | エンティティリンキング（Step 2） |
| `src/data_pipeline/neo4j_loader.py` | グラフ投入（Step 3） |
| `data/config/knowledge-graph-schema.yaml` | YAML SSoT（v2.4 → v3.0移行中） |
| `docs/project/project-28/project.md` | KG v3.0 設計書 |
| `.claude/rules/neo4j-write-rules.md` | 直書き禁止ルール |
| `.claude/rules/neo4j-query-construction.md` | Cypher クエリ構築ルール |
