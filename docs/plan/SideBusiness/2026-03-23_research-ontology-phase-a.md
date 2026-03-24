# 議論メモ: research-neo4j オントロジー Phase A

**日付**: 2026-03-23
**参加**: ユーザー + AI
**スキル**: neo4j-lifecycle --instance research

## 背景・コンテキスト

research-neo4j (bolt://localhost:7688) の KG v2 スキーマを neo4j-lifecycle Phase A で正式にドキュメント化し、
FIBO (Financial Industry Business Ontology) を参考にオントロジーを再設計した。

既存データ: 17ラベル, 39リレーション, 6,399ノード

## 議論のサマリー

### 設計方針

「可能な限りプロパティをリレーションに変換し、薄いハブノード設計に移行」が基本方針として確定。

### 6項目カスタマイズ

1. **① Common Nodes**: Source/Entity の大幅リレーション化
   - Source: category, domain, authority_level, language, command_source → リレーション化
   - Entity: entity_type, ticker, sec_*, sector, industry → リレーション化
2. **② Content Types**: Fact.fact_type, Claim.claim_type, FDP.unit/currency/metric_name → リレーション化
3. **③ Domain Nodes**: Topic.category, Author.organization/author_type → リレーション化
4. **④ Entity Type統合**: 42種→14種に正規化
5. **⑤ ConceptCategory**: topic.category 46種→8大分類
6. **⑥ Relation Types**: 既存39種 + 新設16種 = 55種

### FIBO準拠アップデート

- **Identifier統一**: TickerSymbol + SECRegistration → Identifier ノード（FIBO: SecuritiesIdentification パターン）
- **InstrumentClass階層化**: FIBO SEC domain の Equity/Debt/Fund/Derivative 階層（A案: EntityType の下位分類として追加）

## 決定事項

1. Source は薄いハブノード: {source_id, url, title, source_type, collected_at, published_at} のみ
2. Entity は薄いハブノード: {entity_key, entity_id, name, enriched_at, updated_at} のみ
3. 新設ノード15種: Domain, TrustLevel, Language, Pipeline, EntityType, Identifier, Industry, Alias, FactType, ClaimType, UnitOfMeasure, Currency, ConceptCategory, AuthorType, InstrumentClass
4. 新設リレーション18種: FROM_DOMAIN, RATED_AS, IN_LANGUAGE, INGESTED_VIA, IS_TYPE, HAS_IDENTIFIER, IN_INDUSTRY, ALIAS_OF, IS_FACT_TYPE, IS_CLAIM_TYPE, IN_UNIT, IN_CURRENCY, IS_CATEGORY, AFFILIATED_WITH, IS_AUTHOR_TYPE, IS_INSTRUMENT_CLASS, PARENT_CLASS
5. FIBO Identifier パターン: type(ticker/ISIN/LEI/CIK/SIC/FIGI), value, issuing_authority
6. FIBO InstrumentClass 階層: L1(equity/debt/fund/derivative/currency/commodity/index_basket) + L2サブクラス
7. FIBO残りの提案（Exchange, HAS_CONSTITUENT, CorporateAction, Ownership強化, HAS_JURISDICTION）は見送り

## 成果物

| ファイル | パス |
|---------|------|
| ontology.yaml | `data/lifecycle-state/research/ontology.yaml` |
| schema.yaml | `data/lifecycle-state/research/schema.yaml` |
| customization-plan.md | `data/lifecycle-state/research/customization-plan.md` |
| lifecycle-state.json | `data/lifecycle-state/research/lifecycle-state.json` |

## アクションアイテム

- [ ] **Phase B 実行**: Pipeline コンポーネント生成（抽出プロンプト、Entity Linker設定、Emit Queue設定、MERGEガイド） (優先度: 高)
- [ ] **emit_research_queue.py 更新**: 新オントロジー対応（15新設ノード、Identifier統一、InstrumentClass階層） (優先度: 高)
- [ ] **entity_linker.py 更新**: EntityType ノード + Identifier パターン対応 (優先度: 高)
- [ ] **移行計画策定**: Phase C 追加実行の判断。既存6,399ノードへのプロパティ→リレーション変換適用 (優先度: 中)

## 最終ノード・リレーション数

- **34ノードラベル** (既存17 + 新設15 + 運用系4 - 統合2)
- **62リレーションタイプ** (既存39 + 新設18 + FIBO追加2 + 統合-2 + PARENT_CLASS)
