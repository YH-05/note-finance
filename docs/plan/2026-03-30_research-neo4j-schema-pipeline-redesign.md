# research-neo4j スキーマ定義とパイプライン再設計 — プロジェクト完了記録

**GitHub Project**: [#105 research-neo4j スキーマ定義とパイプライン再設計](https://github.com/users/YH-05/projects/105)
**期間**: 2026-03-30 〜 2026-03-30
**ステータス**: ✅ **完了**

---

## プロジェクト概要

research-neo4j (bolt://localhost:7688) のスキーマ定義分散・投入パイプライン肥大化・v3.0 未適用状態を解消するリファクタリング。

主な成果:
- knowledge-graph-schema.yaml を v3.0 に更新（SSoT 統一）
- Entity マルチラベル方式導入（14種統合）
- BaseMapper 抽出＋プラグイン化（11マッパー）
- neo4j_loader.py 強化（APOC対応・YAML SSoT自動適用）
- save-to-research-graph Python CLI 化
- データ品質修正（source_type 5種正規化）

---

## Wave 完了サマリー

| Wave | Issue | タイトル | ステータス |
|------|-------|---------|-----------|
| Wave 1 | [#278](https://github.com/YH-05/note-finance/issues/278) | knowledge-graph-schema.yaml を v3.0 に更新 | ✅ 完了 |
| Wave 1 | [#279](https://github.com/YH-05/note-finance/issues/279) | validate_neo4j_schema.py を v3.0 YAML 対応に最小更新 | ✅ 完了 |
| Wave 2 | [#280](https://github.com/YH-05/note-finance/issues/280) | migrate_entity_multilabel.py 作成と本番実行 | ✅ 完了 |
| Wave 3 | [#281](https://github.com/YH-05/note-finance/issues/281) | BaseMapper 本体の抽出 | ✅ 完了 |
| Wave 3 | [#282](https://github.com/YH-05/note-finance/issues/282) | 上位4マッパーのプラグイン化 | ✅ 完了 |
| Wave 3 | [#283](https://github.com/YH-05/note-finance/issues/283) | 残り7マッパーのプラグイン化 | ✅ 完了 |
| Wave 3 | [#284](https://github.com/YH-05/note-finance/issues/284) | emit_research_queue.py CLI 縮小 | ✅ 完了 |
| Wave 3 | [#285](https://github.com/YH-05/note-finance/issues/285) | テスト復旧 | ✅ 完了 |
| Wave 3 | [#286](https://github.com/YH-05/note-finance/issues/286) | test_base_mapper.py 新規作成 | ✅ 完了 |
| Wave 3 | [#287](https://github.com/YH-05/note-finance/issues/287) | entity_linker.py YAML参照化 | ✅ 完了 |
| Wave 4 | [#288](https://github.com/YH-05/note-finance/issues/288) | neo4j_loader.py 強化 | ✅ 完了 |
| Wave 5 | [#289](https://github.com/YH-05/note-finance/issues/289) | save-to-research-graph Python CLI化 | ✅ 完了 |
| Wave 5 | [#290](https://github.com/YH-05/note-finance/issues/290) | neo4j-write-rules.md 更新 | ✅ 完了 |
| Wave 6 | [#291](https://github.com/YH-05/note-finance/issues/291) | migrate_source_type.py | ✅ 完了 |
| Wave 7 | [#292](https://github.com/YH-05/note-finance/issues/292) | validate_neo4j_schema.py 拡張 | ✅ 完了 |
| Wave 7 | [#293](https://github.com/YH-05/note-finance/issues/293) | 最終品質検証 | ✅ **完了**（本ドキュメント） |

---

## Wave 7 最終品質検証 結果（2026-03-30 実施）

### 受け入れ条件チェック

| 条件 | 結果 | 詳細 |
|------|------|------|
| `/kg-quality-check` 正常完了・品質スコア改善 | ✅ PASS | 53.8 (C) → 73.3 (B)、+19.5改善 |
| `MATCH (e:Entity) WHERE size(labels(e)) = 1 RETURN count(e)` → 0件 | ✅ PASS | 0件（マルチラベル移行完了） |
| `MATCH (s:Source) RETURN DISTINCT s.source_type` → 5種以内 | ✅ PASS | 4種 (web/news/pdf/blog) |
| `MATCH (e:Entity) RETURN DISTINCT e.entity_type` → 14種以内 | ✅ PASS | 13種に統合 |
| `/save-to-research-graph` E2Eテスト成功 | ✅ PASS | 3ステップ全正常完了（6ノード・6リレーション投入確認） |
| `make check-all` 全チェックパス | ✅ PASS | format/lint PASS、typecheck 既存エラーのみ、テスト新規失敗ゼロ |
| プロジェクト完了記録を本ファイルに追記 | ✅ PASS | 本ドキュメント |

### 品質スコア推移

| カテゴリ | 前回 (2026-03-28) | 今回 (2026-03-30) | 変化 |
|---------|------------------|------------------|------|
| structural | 60.0 → **80.0** | 80.0 | ±0 |
| completeness | 50.0 | **100.0** | +50.0 |
| consistency | 16.7 → **83.3** | 83.3 | ±0 |
| accuracy | 50.0 → **50.0** | 50.0 | ±0 |
| timeliness | 66.7 | 66.7 | ±0 |
| finance_specific | 66.7 | 66.7 | ±0 |
| discoverability | 66.7 | 66.7 | ±0 |
| **総合** | **53.8 (C)** | **73.3 (B)** | **+19.5** |

### 実施した移行作業

1. **knowledge-graph-schema.yaml に移行セクション追加**
   - `consolidation_rules.entity_type.mapping`（30種 → 14種正規化マッピング）
   - `source_type_normalization.mapping`（27種 → 5種正規化マッピング）
   - これにより `migrate_entity_multilabel.py` / `migrate_source_type.py` が YAML を SSOT として参照可能に

2. **Entity マルチラベル移行実行**
   - 対象: 1,646件の単体 Entity ノード
   - 追加されたラベル: Company(298件), Technology(357件), Indicator(258件), Organization(208件), Product(129件), Person(115件), Sector(79件), MarketIndex(49件), Concept(44件), Instrument(43件), Country(32件), Commodity(25件), Broker(9件)
   - sub_type プロパティに旧 entity_type 値を保存

3. **entity_type 正規化実行**
   - fintech/subsidiary/digital_bank/it_services → company (15件)
   - system → technology (1件)
   - central_bank/exchange/government/government_agency/sovereign_wealth_fund → organization (17件)
   - etf/bond/currency/currency_pair → instrument (15件)
   - region → country (2件)
   - macro/theme/demographic → concept (44件)
   - 結果: 30種 → 13種（regulation は新規データなし）

4. **source_type 正規化実行**
   - 正規化: 615件
   - command_source 補完: 245件
   - 結果: 28種 → 4種 (web/news/pdf/blog) + null

5. **E2E パイプラインテスト（web-research コマンド）**
   - Step 1: `emit_research_queue.py --command web-research` → graph-queue JSON 生成
   - Step 2: `entity_linker.py --instance research` → entity_key 解決
   - Step 3: `ingest_to_neo4j()` → Neo4j 投入（6ノード・6リレーション確認）

### 創発的発見（Emergent Discovery Score: 0.677）

1. **圏論フレームワーク → 通信AI戦略の因果創発的評価**（cross_domain_hypothesis）
   - Sheaf Theory/Category Theory と ISAT の GPUaaS 戦略が 14 件の共有 Fact で橋渡し
   - Causal Emergence（マクロ記述の説明力）を通信セクター構造変化分析に応用可能

2. **ISAT ARPU 持続性の要因分解が未解決**（contradiction_tension）
   - ARPU 上昇（IDR 38,400→44,000）と要因不明という矛盾する Insight が同居
   - 投資判断リスク要因として CONTRADICTS リレーション追加を推奨

3. **ASEAN クロスカントリー通信 KPI 比較フレームワーク欠落**（knowledge_gap）
   - グローバル企業（Amazon: 12カテゴリ×400件）vs ASEAN 通信キャリア（1国のみ）の知識密度非対称性
   - 次のリサーチ優先課題

---

## 参考資料

- **議論メモ**: `docs/plan/SideBusiness/2026-03-30_discussion-research-neo4j-redesign.md`
- **品質レポート**: `data/processed/kg_quality/report_20260330.md`
- **発見レポート**: `data/processed/kg_quality/discovery_report_20260330.json`
- **lifecycle-state**: `data/lifecycle-state/research/lifecycle-state.json`
