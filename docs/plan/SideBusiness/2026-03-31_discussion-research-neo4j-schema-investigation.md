# 議論メモ: research-neo4j スキーマ調査・ontology.yaml SSoT 化

**日付**: 2026-03-31
**参加**: ユーザー + AI

## 背景・コンテキスト

KG v3.0 FIBO 準拠スキーマへの移行作業中、`data/config/knowledge-graph-schema.yaml` と
`data/lifecycle-state/research/ontology.yaml` の2ファイルが並存し、定義が矛盾していた。
Issue #279〜#293 の実装状況確認を起点に、データ品質問題（孤立 Fact、リレーション欠落）の
根本原因調査を実施した。

## 議論のサマリー

### Issue #279〜#293 実装状況確認

コードベースと DB の照合を実施。以下の状態を確認:
- **実装完了**: ontology.yaml 作成、neo4j-lifecycle スキル、スキーマ検証スクリプト群
- **DB 未反映**: neo4j-lifecycle Phase C（schema_version 設定）が未実行
- **設計課題**: EXTRACTED_FROM 欠落 377件、孤立 Fact 577件

### 孤立 Fact 問題の調査

当初「1,600件の孤立 Fact」と誤計測していた。原因は OPTIONAL MATCH の直積：
`1 Fact × N Entity × M Source` でカウントが膨らんでいた。EXISTS サブクエリに変更し
正確な値を確認:
- EXTRACTED_FROM 欠落: 377件（source_id/source_url 一致で 52件は決定論的に補完可能）
- Entity 接続なし（RELATES_TO 欠落）: 577件
- ABOUT 使用: 909件（Fact→Entity への不正使用含む）
- MENTIONS 使用: 876件（同上）

### RELATES_TO の設計上の位置付け

`RELATES_TO` は "catch-all" リレーションとして entity_linker が付与する。
ontology.yaml では `Fact|Claim → Entity` に限定定義されているが、DB では
ABOUT/MENTIONS/RELATES_TO の3種が混在している。

`ABOUT` の定義矛盾も発見:
- `ontology.yaml`: `Fact|Claim → Topic`
- `knowledge-graph-schema.yaml`: `Claim → Entity`
- DB 実態: Fact→Entity に使用されているケースあり（909件）

### 層分離設計の確認

ontology.yaml v3.0 で 6カテゴリに分類されていることを確認:
```
entity_classification_nodes → Person, Organization, Asset, Location, Concept, Event
source_classification_nodes → Academic, Report, News, Blog
temporal_nodes             → FiscalPeriod, DatePoint
analytical_nodes           → Fact, Claim, FinancialDataPoint, Insight
relational_nodes            → Topic, Tag
metadata_nodes             → Source, Author
```

### ontology.yaml SSoT 化の決定

`knowledge-graph-schema.yaml` の廃止を決定:
- Issue #295: ontology_loader.py 共通アダプター実装
- Issue #296: スクリプト7件（entity_linker.py, neo4j_loader.py 等）の参照先切替
- Issue #297: テスト8件のフィクスチャ更新
- Issue #298: スキル13件 + CLAUDE.md のパス参照更新 + 旧ファイル trash/ 移動

`/issue-implementation-serial 295 296 297 298` で連続実装 → PR #299 作成・CI 全パス確認済み。

## 決定事項

1. **ontology.yaml を SSoT として確立**: `data/lifecycle-state/research/ontology.yaml` を
   research-neo4j の唯一の真実のソースとし、`knowledge-graph-schema.yaml` を `trash/` に移動・廃止する
2. **ontology_loader.py アダプター採用**: 2ファイル間の構造非互換（ネスト深度・プロパティ名の差異）を
   `scripts/ontology_loader.py` の6関数で吸収。スクリプト・テスト・スキルが間接参照する設計
3. **Fact→Entity リレーション統一方針は未決**: RELATES_TO/ABOUT/MENTIONS の3種が混在する現状を
   RELATES_TO 1本に統一するか semantic distinction を維持するかは設計議論が必要

## アクションアイテム

- [x] PR #299 マージ（ontology_loader.py + 全参照切替）← **2026-03-31 マージ完了**（コンフリクト: main での kgs-yaml 変更を削除で上書き解消）
- [ ] 52件の EXTRACTED_FROM 補完（source_id/source_url 一致分、決定論的 Cypher MERGE）（高）
- [ ] RELATES_TO 欠落防止機構追加（entity_linker でバリデーション or NER 補完）（高）
- [ ] 577件の真の孤立 Fact 修復（LLM NER バッチ処理）（中）
- [ ] ABOUT/MENTIONS 整理（RELATES_TO 統一 or semantic 設計を確定してから実施）（中）
- [ ] neo4j-lifecycle Phase C 実行（schema_version 設定 + 最終品質検証）（中）

## 次回の議論トピック

- ABOUT/MENTIONS と RELATES_TO の意味的整理: 3種を維持するなら各リレーションの
  使用条件を ontology.yaml に明文化する必要がある
- RELATES_TO 欠落防止: entity_linker の入力バリデーション追加 or NER 自動補完の設計
- Phase C 実行タイミング: PR #299 マージ後すぐに実施するか、欠落修復を先に行うか

## 参考情報

- PR #299: ontology_loader.py アダプター実装 → **2026-03-31 マージ済み** (squash, feature/298-deprecate-kgs-yaml → main)
- `scripts/ontology_loader.py`: 6関数（load_consolidation_mapping, load_source_type_normalization,
  load_multilabel_types, load_constraints, load_indices, load_namespaces）
- `tests/scripts/test_ontology_loader.py`: 32件ユニットテスト
- 孤立 Fact 計測クエリ（正確版）:
  ```cypher
  MATCH (f:Fact)
  WHERE NOT EXISTS { (f)-[:EXTRACTED_FROM]->(:Source) }
  RETURN count(f) AS orphan_count
  // → 377件
  
  MATCH (f:Fact)
  WHERE NOT EXISTS { (f)-[:RELATES_TO|ABOUT|MENTIONS]->(:Entity) }
  RETURN count(f) AS no_entity_link
  // → 577件
  ```
