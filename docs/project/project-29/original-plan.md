# 議論メモ: research-neo4j Entity ノード廃止・全プロパティのラベル/ノード化

**日付**: 2026-04-02
**参加**: ユーザー + AI

## 背景・コンテキスト

research-neo4j の Entity ノード（1,658件）について以下の構造的問題が判明:

1. **Entity ラベルが汎用すぎる** — entity_type プロパティで型を区別するが、ラベルとして意味的クラスを表現していない
2. **プロパティの3層重複** — ticker/sector/country が Entity プロパティ・分類ノード・Entity ノードの3箇所に分散
3. **entity_key 複合キー** — `name::type` 形式の複合キーはNeo4jのアンチパターン
4. **リレーション3種混在** — Fact→Entity が RELATES_TO/ABOUT/MENTIONS に分裂（意味的区別なし）

## 議論のサマリー

### 論点1: Fact→Entity リレーション統一と ABOUT/MENTIONS 整理

データ調査により、Fact→Entity の ABOUT 909件・MENTIONS 876件はマッパー実装差異による偶発的なものであり意味的区別ではないことを確認。RELATES_TO 1本化を決定。

### 論点2: Entity ノードの見直し方針

当初は Entity ラベルを残しつつプロパティを正規化する案だったが、ユーザーの方針で Entity ラベル自体を廃止し、全 entity_type をファーストクラスのラベルにする方向に転換。

### 論点3: entity_key の扱い

3選択肢（A:現行維持、B:PascalCase変更、C:廃止してnameのみ）を検討。同ラベル同名重複19件・異ラベル同名55組の衝突リスクを調査した上で、Neo4j公式ベストプラクティスを確認:

- **「グラフでは複合キーを使うな」**（David Allen, Neo4j Developer Blog）
- **NODE KEY 制約**でラベル+プロパティの一意性をDB側で保証可能（Enterprise Edition）
- **ラベルチェックはプロパティフィルタより高速**

→ C案（entity_key 廃止）を採用。前提として重複の事前名寄せが必要。

### 論点4: Entity:Sector の再分類

Sector ラベルが90件あるが実態は2種:
- **正規 Sector（10件）**: GICS標準、IN_SECTOR で Company に接続
- **テーマ的ノード（79件）**: 「半導体」「AI銘柄」等、IN_SECTOR なし

テーマ的ノードは Topic にラベル変更。

### 論点5: Country の二重役割

Country は「分類属性」（IN_COUNTRY）と「分析対象」（RELATES_TO）を同一ノードで担う。役割の区別はリレーションで表現。

## 決定事項

1. **Entity ラベル廃止**: entity_type 15種を13個のファーストクラスラベル（Company, Technology, Indicator, Organization, Product, Person, MarketIndex, Concept, Instrument, Commodity, Broker + Sector, Country）に分解
2. **entity_key 廃止 + NODE KEY 制約**: ラベルごとに name を NODE KEY で一意性保証。同ラベル同名重複19件・異ラベル同名55組の事前名寄せが前提
3. **プロパティのノード分離**: ticker → Ticker, sector → Sector, country → Country, industry → Industry に正規化
4. **RELATES_TO 1本化**: ABOUT（5,343件）と MENTIONS（925件）を廃止、RELATES_TO にリネーム
5. **Entity:Sector テーマ的ノード → Topic**: GICS対応約10件は Sector にマージ、テーマ的約69件は Topic に変更
6. **Country 二重役割**: 属性（IN_COUNTRY）と分析対象（RELATES_TO）を同一ノードで

## アクションアイテム

- [ ] 同ラベル同名重複19件の名寄せ (優先度: 高)
- [ ] 異ラベル同名55組の精査・統合 (優先度: 高)
- [ ] 移行スクリプト設計・実装（Phase 1-4） (優先度: 高)
- [ ] ontology.yaml 更新 (優先度: 中)
- [ ] パイプライン更新（entity_linker, neo4j_loader, ontology_loader） (優先度: 中)
- [ ] スキル・スクリプトの MATCH (e:Entity) クエリ更新 (優先度: 中)
- [ ] Entity:Sector 79件の再分類 (優先度: 低)
- [ ] 孤立ノード処理（Entity 64件 + Fact 577件） (優先度: 低)

## 次回の議論トピック

- 移行スクリプトの Phase 分割の詳細設計（/plan-project 化）
- sector 名寄せマッピング表の確定（21種 → GICS 11種）
- country 英日名寄せマッピング表の確定
- 既存 Project #105 との関係整理（追加 Issue or 新規 Project）

## 参考情報

### Neo4j 公式ベストプラクティス（根拠）

| 出典 | 原則 | 今回の適用 |
|------|------|----------|
| David Allen "Graph Modeling: Labels" | ラベルで意味的クラスを表現、クエリユースケースのあるラベルのみ | Entity 廃止 → 個別ラベル |
| David Allen "Graph Data Modeling: Keys" | グラフでは複合キーを使うな、ノード分離で解決 | entity_key 廃止 → NODE KEY |
| Neo4j Community "Performance of Labels VS attributes" | ラベルチェックはプロパティフィルタより高速 | entity_type プロパティ → ラベル |
| Neo4j Cypher Manual "Constraints" | NODE KEY = 存在制約 + 一意制約の複合 | ラベルごとに name を NODE KEY |
| Neo4j "Transaction and Account Data Model" | Country は code を NODE KEY にする公式例 | Country.name を NODE KEY |

### データ規模（移行対象）

| 対象 | 件数 |
|------|------|
| Entity ノード（ラベル除去） | 1,658 |
| ABOUT リレーション（→ RELATES_TO） | 5,343 |
| MENTIONS リレーション（→ RELATES_TO） | 925 |
| Entity.ticker → Ticker ノード | 120 |
| Entity.sector → Sector 名寄せ | 139 |
| Entity.country → Country ノード | 68 |
| Identifier → Ticker 統合 | 144 |
| EntityType + IS_TYPE 廃止 | 1,597 |
| InstrumentClass + IS_INSTRUMENT_CLASS 廃止 | 106 |
| Entity:Sector → Topic 再分類 | ~69 |

### 保存先

- Neo4j: disc-2026-04-02-research-neo4j-entity-redesign (note-neo4j)
- Decision: dec-2026-04-02-entity-label-abolish 他5件
- ActionItem: act-2026-04-02-001 ~ act-2026-04-02-008
