# 議論メモ: research-neo4j スキーマ定義と投入ロジック再設計

**日付**: 2026-03-30
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j (bolt://localhost:7688) のスキーマ定義が以下の3箇所に分散し保守困難な状態だった:
- `data/config/knowledge-graph-schema.yaml` (v2.4 現行SSOT)
- `data/lifecycle-state/research/ontology.yaml` (v3.0 設計)
- `data/lifecycle-state/research/schema.yaml` (v3.0 設計)

また投入パイプライン `scripts/emit_research_queue.py` が4,805行に肥大化。
v3.0 (FIBO準拠: 33ノード・59リレーション) が 2026-03-23 にマージ済みだが Migration 未実行。

議論動機: SSoT/定義が散在・投入パイプラインの整理・全体的に再設計したい

## 議論のサマリー

### 論点1: SSoT の統一先

knowledge-graph-schema.yaml を v3.0 に更新して唯一のSSoTとすることで合意。
範囲: スキーマ定義 + バリデーションルール（enum厳密化）。マッパー設定は Python 側で管理。
lifecycle-state/ は「設計履歴」として残すが参照元ではなくなる。

### 論点2: マッパー整理の方針

使用状況調査結果: 11マッパーのうち4マッパーが完全未使用、上位3マッパー (web_research 38%, finance_news 33%, wealth_scrape 20%) で91%を占める。

方針: 11マッパーは全て残しつつ共通ロジックを BaseMapper クラスに抽出、scripts/mappers/ 配下にプラグイン化。emit_research_queue.py は CLIエントリポイント+ルーティングのみに縮小。

### 論点3: パイプラインアーキテクチャ

ハイブリッド方式（役割分担）で合意:
```
[リサーチデータ入力]
        ↓
  ① emit_research_queue.py (Python) — データ変換
  ② entity_linker.py (Python・前処理) — entity_key 事前解決
  ③ neo4j_loader.py (Python・投入) — MERGE冪等投入
        ↓
  research-neo4j
```
Claude スキルはオーケストレーション専任（Python CLI を順次呼び出し）。
save-to-research-graph スキルは Cypher 直接実行をやめ Python CLI 呼出しに変更。

### 論点4: Entity スキーマ見直し

entity_type が 30種に散発的増加 → 14種に統合 + マルチラベル方式を採用。

**統合後 14種:**
Company, Technology, Organization, Person, MarketIndex, Indicator, Instrument,
Commodity, Country, Sector, Concept, Regulation, Broker, Product

**マルチラベル方式:**
```cypher
(e:Entity:Company {name: "Indosat", entity_key: "Indosat::company", sub_type: null})
(e:Entity:Organization {name: "Bank Indonesia", entity_key: "Bank Indonesia::organization", sub_type: "central_bank"})
```
- Entity ラベルは残す → `MATCH (e:Entity)` で横断クエリ（既存コード互換）
- タイプ別ラベル追加 → `MATCH (c:Company)` でタイプ別クエリ
- 統合前のサブタイプは `sub_type` プロパティで保持
- isin プロパティは削除（0%使用）
- EntityType 分類ノードはマルチラベル導入後に要否を再評価

### 論点5: データ品質

source_type 27種・entity_type 30種 → パイプライン整備（Phase 1-5）完了後に対処。
新規投入の品質担保が先決。

## 決定事項

1. **YAML SSoT 統一**: `data/config/knowledge-graph-schema.yaml` を v3.0 に更新して唯一の正とする
2. **マッパー共通化**: BaseMapper クラスに共通ロジックを抽出、scripts/mappers/ にプラグイン化（11マッパー維持）
3. **ハイブリッドパイプライン**: Python実行(emit→entity_linker→neo4j_loader) + Claudeオーケストレーション
4. **Python投入統一**: neo4j_loader.py に投入ロジックを統一、Cypher直書き廃止
5. **entity_linker 前処理化**: entity_key を投入前に事前解決
6. **Entity マルチラベル**: entity_type 30→14種統合 + マルチラベル方式 + sub_type プロパティ
7. **分類ノード段階評価**: EntityType 分類ノードはマルチラベル導入後に再評価

## アクションアイテム

- [ ] [Phase 1] knowledge-graph-schema.yaml を v3.0 に更新（Entityマルチラベル14タイプ定義、enum厳密化） (優先度: 高)
- [ ] [Phase 2] Entity マルチラベル移行（30→14種統合、sub_type追加、isin削除） (優先度: 高)
- [ ] [Phase 3] BaseMapper 抽出 + プラグイン化（scripts/mappers/） (優先度: 高)
- [ ] [Phase 4] neo4j_loader.py 強化（Cypher統合、マルチラベル対応、YAML SSoT自動適用） (優先度: 中)
- [ ] [Phase 5] save-to-research-graph スキル変更（Cypher→Python CLI呼出しに） (優先度: 中)
- [ ] [Phase 6] データ品質修正（source_type 5種正規化、NULL command_source 補完） (優先度: 低)
- [ ] [Phase 7] v3.0 Migration + 品質検証（/kg-quality-check） (優先度: 低)

## 次回の議論トピック

- Phase 1 完了後: entity_type 14種の enum バリデーションルール詳細確認
- Phase 2 後: EntityType 分類ノードの要否判断
- Phase 3 後: 未使用マッパー4種の削除検討

## 参考情報

### マッパー使用状況（2026-03-30 調査）

| マッパー | command_source | Source数 | 割合 |
|---------|---------------|---------|------|
| web_research | web-research | 794 | 38% |
| finance_news | finance-news-workflow | 683 | 33% |
| wealth_scrape | wealth-scrape | 411 | 20% |
| pdf_extraction | pdf-extraction + pdf-archive | 141 | 7% |
| academic_fetch | academic-fetch | 18 | 1% |
| reddit_topics | reddit-finance-topics | 10 | <1% |
| topic_discovery | topic-discovery | 2 | <1% |
| ai_research / market_report / asset_management / finance_full | (未使用) | 0 | - |

### entity_type 統合マッピング

| 新 entity_type | 統合元 | 推定件数 |
|---------------|--------|---------|
| technology | technology, system | 357 |
| company | company, fintech, subsidiary, digital_bank, it_services | 289 |
| indicator | indicator | 258 |
| organization | organization, central_bank, exchange, government, govt_agency, swf | 208 |
| product | product | 129 |
| person | person | 115 |
| sector | sector | 79 |
| index | index | 49 |
| concept | macro, theme, demographic | 44 |
| instrument | instrument, etf, bond, currency, currency_pair | 43 |
| country | country, region | 32 |
| commodity | commodity | 25 |
| broker | broker | 9 |
| regulation | (新規) | 0 |

### 保存先

- Neo4j ノード: `disc-2026-03-30-research-neo4j-redesign` (note-neo4j)
- Decision: `dec-2026-03-30-yaml-ssot` 他6件
- ActionItem: `act-2026-03-30-001` ~ `act-2026-03-30-007`
- プランファイル: `docs/plan/2026-03-30_research-neo4j-schema-pipeline-redesign.md`
