# research-neo4j オントロジー カスタマイズ計画

> 生成日: 2026-03-23
> ステータス: pending（ユーザーレビュー待ち）
> ベースライン: `ontology.yaml` (draft)

---

## 概要

既存データ（17ラベル, 39リレーション, 合計6,399ノード）から抽出したベースラインオントロジーに対し、
以下6項目のカスタマイズを計画する。各項目はユーザーの判断を待って実施する。

---

## ① Common Nodes (Source, Entity)

### 現状
- **Source** (1,709件): source_id, url, title, source_type, authority_level, category, command_source, collected_at, published_at
- **Entity** (1,013件): entity_key, entity_id, name, entity_type, ticker, sector, industry, sec_cik, sec_name, sic_code, sic_description, enriched_at

### カスタマイズ候補

| 項目 | 候補 | 影響範囲 |
|------|------|---------|
| Source に `language` プロパティ追加 | 多言語ソースの分類に有用 | 新規投入時に自動付与 |
| Source に `domain` プロパティ追加 | サイト別集計に有用 | URL からの自動抽出 |
| Entity の SEC 関連プロパティ整理 | sec_cik, sec_name, sic_code, sic_description は company 限定 | entity_type=company のみに適用 |
| Entity に `aliases` リストプロパティ追加 | 別名検索の高速化 | entity_linker と連携 |

### 判断ポイント
- [ ] Source の language / domain を required にするか optional にするか
- [ ] Entity の SEC プロパティを別ノード（SECRegistration）に分離するか

---

## ② Content Types (Fact, Claim, Chunk, FDP, Insight)

### 現状
5つの Content Type が存在。Fact と Claim が最多。

### カスタマイズ候補

| 項目 | 候補 | 影響範囲 |
|------|------|---------|
| Fact に `category` プロパティ追加 | 現在 null のみ。カテゴリ分類で検索性向上 | 既存1,518件のバックフィル |
| Fact に `confidence` プロパティ追加 | 情報の信頼度スコアリング | 新規投入時に自動付与 |
| Claim の `claim_type` 標準化 | 現在: earnings_beat, policy_hawkish 等。値の正規化 | 既存1,145件の再分類 |
| Insight のプロパティ拡充 | category, derived_from_count, created_at の追加 | 既存23件のバックフィル |
| Question を Content Type に昇格 | 3件のみだが、調査ワークフローで重要 | ラベル変更不要 |

### 判断ポイント
- [ ] Fact.category の値セットを ConceptCategory に合わせるか
- [ ] Claim.claim_type の標準値セットを定義するか
- [ ] Question を Content Type として正式に追加するか

---

## ③ Domain Nodes (Topic, Author, Stance, Metric, FiscalPeriod, Sector)

### 現状
6つの Domain Node が存在。Topic が最多（227件）。

### カスタマイズ候補

| 項目 | 候補 | 影響範囲 |
|------|------|---------|
| Topic.category の正規化 | 46種 → 8大分類（ConceptCategory）に統合 | 既存227件の category 更新 |
| Author にプロパティ追加 | affiliation（所属）, author_type（analyst/journalist/official） | 既存115件のバックフィル |
| Stance と Claim の関係整理 | Stance は Claim のサブタイプか独立ノードか | 設計判断 |
| Metric と indicator entity_type の関係整理 | Metric ノード vs Entity(indicator) の重複 | 統合 or 役割分離 |
| Sector ノード vs Entity(sector) の重複整理 | Sector(11件) と Entity(entity_type=sector, 13件) | 統合 or 役割分離 |
| FiscalPeriod のプロパティ拡充 | start_date, end_date の追加 | 既存25件のバックフィル |

### 判断ポイント
- [ ] Sector ノードと Entity(sector) を統合するか
- [ ] Metric ノードと Entity(indicator) を統合するか
- [ ] Author に所属情報を追加するか
- [ ] Stance を独立ノードとして維持するか

---

## ④ Entity Type 統合 (42種 → 14種)

### 統合マッピング

| 統合先 | 件数 | 統合元 |
|--------|------|--------|
| company | 205 | company, fintech, subsidiary, fintech_holding, digital_bank, it_services |
| technology | 275 | technology, system |
| organization | 142 | organization, central_bank, government, government_agency, institution, exchange |
| person | 89 | person |
| index | 39 | index |
| indicator | 38 | indicator, metric |
| instrument | 38 | instrument, etf, currency, currency_pair, fund, bond, asset |
| commodity | 16 | commodity |
| country | 16 | country, region |
| sector | 14 | sector, market |
| concept | 91 | concept, model, method, theme, article_proposal, event |
| regulation | 3 | regulation |
| broker | 9 | broker |
| product | 12 | product, dataset, data_center |

### カスタマイズ候補

| 項目 | 候補 | 理由 |
|------|------|------|
| broker を organization に統合 | broker はセルサイドの金融機関 | feedback_entity_multirole.md に注意 |
| concept を分割 | theme/article_proposal は Meta 層、model/method は What 層 | 粒度の違い |
| fintech を独立維持 | フィンテック企業は通常の company と投資視点が異なる | セクター分析で区別 |
| central_bank を独立維持 | 中央銀行はマクロ分析の主要アクター | マクロリサーチでの重要性 |

### 判断ポイント
- [ ] broker を organization に統合するか独立維持か（マルチロール考慮）
- [ ] concept の粒度をどうするか
- [ ] fintech, central_bank を独立 entity_type として維持するか

---

## ⑤ ConceptCategory (8大分類)

### 提案

| カテゴリ | 名前(JA) | Layer | 統合元 topic.category |
|---------|----------|-------|----------------------|
| MacroEconomics | マクロ経済 | What | macro, political, geopolitical |
| EquityResearch | 株式リサーチ | What | stock, earnings, valuation, equity_research |
| SectorAnalysis | セクター分析 | What | sector, sector_analysis, cross_sector |
| InvestmentStrategy | 投資戦略 | What | investment_strategy, investment_framework |
| Technology | テクノロジー | What | technology, ai, quantitative_finance |
| WealthManagement | 資産形成 | What | wealth, assets |
| Regulation | 規制 | What | regulatory, regulation, governance |
| ContentPlanning | コンテンツ企画 | Meta | content_planning, reddit, theme |

### カスタマイズ候補

| 項目 | 候補 | 理由 |
|------|------|------|
| Geopolitics を独立追加 | MacroEconomics から分離 | 地政学リスクは独立テーマ |
| CorporateStrategy を追加 | 企業戦略・M&A・経営判断 | EquityResearch とは視点が異なる |
| FixedIncome を追加 | 債券・金利・イールドカーブ | MacroEconomics とは資産クラスが異なる |
| finance（33件）の振り分け | 現在最大カテゴリだが曖昧 | 他カテゴリに分散すべき |
| null（28件）の対処 | カテゴリ未設定の Topic | バックフィルが必要 |

### 判断ポイント
- [ ] 8大分類で十分か、追加するか
- [ ] finance / null の topic をどう振り分けるか

---

## ⑥ Relation Types (39種)

### カテゴリ別整理

| カテゴリ | 件数 | リレーション |
|---------|------|-------------|
| コンテンツ接続 | 7 | TAGGED, STATES_FACT, MAKES_CLAIM, CONTAINS_CHUNK, EXTRACTED_FROM, HAS_DATAPOINT, ABOUT |
| エンティティ関連 | 4 | RELATES_TO, MENTIONS, IN_SECTOR, ON_ENTITY |
| 分析・推論 | 6 | SUPPORTED_BY, CONTRADICTS, INFLUENCES, CAUSES, DERIVED_FROM, SHARES_TOPIC |
| 時系列 | 3 | FOR_PERIOD, NEXT_PERIOD, TREND |
| エンティティ間 | 9 | COMPETES_WITH, CUSTOMER_OF, SUBSIDIARY_OF, PARTNERS_WITH, INVESTED_IN, GOVERNS, OPERATES_IN, SPUN_OFF_FROM, LED_BY |
| メタ・スタンス | 10 | AUTHORED_BY, COAUTHORED_WITH, CO_MENTIONED_WITH, MEASURES, FOR_METRIC, HOLDS_STANCE, BASED_ON, SOURCED_FROM, BELONGS_TO, ASKS_ABOUT |

### カスタマイズ候補

| 項目 | 候補 | 理由 |
|------|------|------|
| SOURCED_FROM と EXTRACTED_FROM の関係整理 | 16件 vs 1,411件。役割が重複？ | 明確な区別が必要 |
| BELONGS_TO の from/to ラベル明確化 | 24件。汎用的すぎる | 用途の特定が必要 |
| TREND の定義見直し | 108件。Entity→Entity だが意味が不明確 | プロパティ追加（metric_id, direction 等） |
| SUPPLIES_TO の追加 | サプライチェーン関係 | エンティティ間に不足 |
| REGULATES の追加 | 規制対象関係 | GOVERNS との区別 |
| MENTIONED_IN の追加 | Entity→Source の逆方向 | 検索パターンで有用 |

### 判断ポイント
- [ ] 低件数リレーション（LED_BY:1, SPUN_OFF_FROM:1, OPERATES_IN:2）を維持するか
- [ ] SOURCED_FROM を EXTRACTED_FROM に統合するか
- [ ] 新規リレーションタイプを追加するか

---

## 実行計画

### Phase 1: ユーザーレビュー
1. 本計画書の各項目の判断ポイントについてユーザーの決定を取得
2. ontology.yaml を更新

### Phase 2: スキーマ反映（Phase A-3）
1. 確定した ontology に基づき schema.yaml（制約・インデックス）を生成
2. 正規化ルールを更新

### Phase 3: データ整合性確認（Phase D で実施）
1. Entity Type 統合のマッピングテーブル作成
2. topic.category の再分類マッピング作成
3. 重複ノードの検出

---

## 参照ファイル

| ファイル | 説明 |
|---------|------|
| `ontology.yaml` | ベースラインオントロジー定義 |
| `schema.yaml` | 制約・インデックス定義（生成予定） |
| `lifecycle-state.json` | フェーズ進捗管理 |
| `../../config/neo4j-instances/research.yaml` | インスタンス設定 |
