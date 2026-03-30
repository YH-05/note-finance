# research-neo4j スキーマ定義と投入ロジック再設計

**日付**: 2026-03-30
**種別**: project-discuss → 実装計画

## Context

research-neo4j のスキーマ定義が3箇所に分散し、投入パイプラインが肥大化（4,805行）。
v3.0（FIBO準拠）が 2026-03-23 にマージ済みだが Migration 未実行。
SSoT統一・パイプライン整理・全体再設計の3点について議論し、以下の方針に合意。

## 合意事項（2026-03-30 議論結果）

### 1. YAML SSoT 統一

- **SSoT**: `data/config/knowledge-graph-schema.yaml` を v3.0 に更新して唯一の正とする
- **範囲**: スキーマ定義（ノード/リレーション/制約/インデックス）+ バリデーションルール（enum厳密化）
- **マッパー設定**: YAML には含めない（Python BaseMapper 側で管理）
- **lifecycle-state/**: 設計履歴として残すが、参照元ではなくなる
- **自動生成ターゲット**: Cypher制約/インデックス、テスト期待値

### 2. マッパー共通化（emit_research_queue.py）

- **方針**: 11マッパーは全て残す（削除しない）
- **共通化**: BaseMapper クラスに共通ロジックを抽出
- **プラグイン化**: 各マッパーを独立ファイルに分割（scripts/mappers/）
- **BaseMapper の責務**:
  - Source/Entity/Topic ノード生成（entity_key/topic_key 自動付与）
  - Fact/Claim ノード生成
  - 標準リレーション構築（STATES_FACT, RELATES_TO, ABOUT, EXTRACTED_FROM, TAGGED）
  - v3.0 分類ポストプロセッサ
  - YAML SSoT 読み込み・バリデーション
- **各マッパーは差分のみ**: 入力パース、フィールドマッピング、コマンド固有処理

### 3. パイプラインアーキテクチャ（ハイブリッド）

```
[リサーチデータ入力]
        ↓
  ① emit_research_queue.py (Python)
     BaseMapper + 11個のプラグインマッパー
     YAML SSoT を読んでバリデーション
        ↓
  graph-queue JSON (.tmp/graph-queue/)
        ↓
  ② entity_linker.py (Python・前処理)
     4段階マッチング → entity_key 事前解決
        ↓
  ③ neo4j_loader.py (Python・投入)
     MERGE ベース冪等投入 + トランザクション制御
        ↓
  research-neo4j (bolt://localhost:7688)
```

- **Python**: データ変換(①)、エンティティ解決(②)、DB投入(③)
- **Claude スキル**: オーケストレーション（①②③のPython CLIを順次呼出し）
- **save-to-research-graph**: Cypher直接実行をやめ、Python CLI呼び出しのオーケストレーターに変更
- **PostToolUse フック**: `.tmp/research-input/*.json` 検出 → 自動トリガー

### 4. Entity スキーマ再設計

#### entity_type 統合（30種→14種）

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

- 統合前のサブタイプは `sub_type` プロパティで保持（例: sub_type="central_bank"）

#### マルチラベル方式

Entity ラベルは残し、タイプ別ラベルを **追加** する:
```
(e:Entity:Company {name: "Indosat", entity_key: "Indosat::company", sub_type: null})
(e:Entity:Organization {name: "Bank Indonesia", entity_key: "Bank Indonesia::organization", sub_type: "central_bank"})
```

14タイプの新ラベル:
Company, Technology, Organization, Person, MarketIndex, Indicator, Instrument, Commodity, Country, Sector, Concept, Regulation, Broker, Product

- `MATCH (c:Company)` でタイプ別クエリ
- `MATCH (e:Entity)` で横断クエリ（既存コード互換）
- entity_type プロパティは当面残す（クエリ便宜用）
- EntityType 分類ノードはマルチラベル導入後に再評価

#### プロパティ整理
- `isin`: 削除（0%使用）
- `ticker`: 残す → Identifier ノードへも展開
- `aliases`: 残す（entity_linker で使用）
- `description`: 残す
- `sub_type`: 新規追加（統合前の細分類）

#### 分類ノード展開（Entity 関連優先）
- EntityType: 42種→14種に整理（マルチラベル導入後に要否再評価）
- Identifier: ticker 値の正規化（name/type/value を設定）
- Industry / Sector / InstrumentClass: 現状維持・改善
- Source/Fact/Claim 関連の分類ノード: 現状維持（後回し）

### 5. データ品質（パイプライン整備後に対処）

- source_type 27種 → YAML enum で5種に正規化（新規投入の品質担保が先）
- command_source NULL 1,302件 → 既存データは後から修正
- entity_type 30種 → 14種マルチラベル統合
- 実施タイミング: BaseMapper + YAML SSoT 整備完了後

### 6. マッパー使用状況（調査結果）

| マッパー | command_source | Source数 | 割合 |
|---------|---------------|---------|------|
| web_research | web-research | 794 | 38% |
| finance_news | finance-news-workflow | 683 | 33% |
| wealth_scrape | wealth-scrape | 411 | 20% |
| pdf_extraction | pdf-extraction + pdf-archive | 141 | 7% |
| academic_fetch | academic-fetch | 18 | 1% |
| reddit_topics | reddit-finance-topics | 10 | <1% |
| topic_discovery | topic-discovery | 2 | <1% |
| ai_research | (未使用) | 0 | - |
| market_report | (未使用) | 0 | - |
| asset_management | (未使用) | 0 | - |
| finance_full | (未使用) | 0 | - |

## 実装フェーズ

### Phase 1: YAML SSoT 整備
- `data/config/knowledge-graph-schema.yaml` を v3.0 に更新
- Entity マルチラベル（14タイプ）の定義を追加
- v3.0 分類ノード/リレーション定義を追加
- enum バリデーションルールを厳密化（source_type 5種、entity_type 14種等）
- lifecycle-state/ の設計内容を YAML に統合

### Phase 2: Entity マルチラベル移行
- entity_type 30種→14種の統合マッピングテーブル作成
- マルチラベル追加 Cypher 実行（Entity:Company, Entity:Person 等）
- sub_type プロパティ追加（統合前の細分類を保持）
- isin プロパティ削除
- EntityType 42種→14種に整理

### Phase 3: BaseMapper 抽出 + プラグイン化
- `scripts/mappers/base.py` に共通ロジック抽出
- 11マッパーを `scripts/mappers/*.py` に分割
- BaseMapper が YAML SSoT を読んでバリデーション
- emit_research_queue.py は CLI エントリポイント + ルーティングのみに
- BaseMapper にマルチラベル生成ロジックを組み込み

### Phase 4: neo4j_loader.py 強化
- save-to-research-graph のCypherテンプレートのロジックを neo4j_loader.py に移植
- マルチラベル付きノード投入対応
- YAML SSoT から制約/インデックスを自動適用
- トランザクション制御・エラーハンドリング強化

### Phase 5: save-to-research-graph スキル変更
- Cypher直接実行をやめ、Python CLI呼び出しのオーケストレーターに変更
- `uv run python scripts/emit_research_queue.py` → `uv run python scripts/entity_linker.py` → `uv run python src/data_pipeline/neo4j_loader.py`

### Phase 6: データ品質修正
- source_type 正規化（27種→5種）
- NULL command_source の補完
- Entity Identifier ノードの正規化（ticker 展開）

### Phase 7: v3.0 Migration + 品質検証
- neo4j-lifecycle --instance research --phase C（残りの移行タスク）
- 品質検証: /kg-quality-check

## 重要ファイル

| ファイル | 役割 | 変更内容 |
|---------|------|---------|
| `data/config/knowledge-graph-schema.yaml` | SSoT | v2.4→v3.0 更新 + マルチラベル定義 |
| `scripts/emit_research_queue.py` | CLI エントリポイント | ルーティングのみに縮小 |
| `scripts/mappers/base.py` | 共通ロジック | **新規作成**（マルチラベル対応） |
| `scripts/mappers/*.py` | 各マッパー | **新規作成**（既存から分割） |
| `scripts/entity_linker.py` | エンティティ解決 | パイプライン位置の明確化 |
| `src/data_pipeline/neo4j_loader.py` | Neo4j投入 | Cypher統合 + マルチラベル対応 |
| `.claude/skills/save-to-research-graph/SKILL.md` | オーケストレーター | Cypher→Python CLI呼出しに変更 |
| `.claude/rules/neo4j-write-rules.md` | 直書き禁止ルール | パイプライン定義の更新 |
| `data/lifecycle-state/research/` | 設計履歴 | 参照元ではなくなる |

## 検証方法

1. **Phase 1 検証**: `uv run python scripts/validate_neo4j_schema.py` でYAML↔DB整合性チェック
2. **Phase 2 検証**: `MATCH (e:Entity) RETURN labels(e), count(e)` でマルチラベル適用確認 + `MATCH (e:Company) RETURN count(e)` で274件前後
3. **Phase 3 検証**: `make test` で既存テスト全パス + 新規BaseMapperテスト
4. **Phase 4 検証**: graph-queue JSON → neo4j_loader.py → DB投入 → MATCHで件数確認
5. **Phase 5 検証**: `/save-to-research-graph` スキルの動作確認（テスト用JSON投入）
6. **Phase 6 検証**: `MATCH (s:Source) RETURN s.source_type, count(s)` で5種に収束確認
7. **Phase 7 検証**: `/kg-quality-check` で品質スコア確認

## 議論保存（実装開始前に実行）

プランモード終了後に以下を実行:

1. **note-neo4j に保存**: Discussion/Decision/ActionItem ノードを MERGE
   - Discussion: `disc-2026-03-30-research-neo4j-redesign`
   - Decision: 7件（YAML SSoT、マッパー共通化、ハイブリッドパイプライン、Python投入統一、entity_linker前処理、Entity マルチラベル、分類ノード段階評価）
   - ActionItem: 7フェーズに対応する7件

2. **議論メモ作成**: `docs/plan/SideBusiness/2026-03-30_discussion-research-neo4j-redesign.md`

3. **メモリ更新**: project_kg_v30_schema.md をマルチラベル方式の合意で更新
