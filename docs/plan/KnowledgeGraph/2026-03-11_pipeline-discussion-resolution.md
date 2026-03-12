# KnowledgeGraph議論ポイント完了 → 元プラン改訂

Created: 2026-03-11
Status: 合意済み（元プランに反映完了: 2026-03-11）

## Context

`docs/plan/KnowledgeGraph/` に3つのドキュメントがある:

1. `2026-03-11_first-memo.md` — ナレッジグラフ構築の上位設計
2. `2026-03-11_pdf-to-markdown-pipeline.md` — PDFパイプライン設計（元プラン）
3. `2026-03-11_pdf-pipeline-5-discussion-points.md` — 元プランへの5論点と改訂案

5論点（テーブルスキーマ、ノード拡張、MCP活用、検証方法、LLMプロバイダー）に加え、
追加3論点（Master Entity統合、抽出プロンプト戦略、グラフDB書き込み方式）を議論し、全8点で合意が得られた。

本プランは元プラン `2026-03-11_pdf-to-markdown-pipeline.md` を改訂する作業を定義する。

---

## 合意事項サマリー

### 既存5論点（pdf-pipeline-5-discussion-points.md）

| # | 論点 | 合意内容 |
|---|------|---------|
| 1 | Phase 3B テーブルスキーマ | 3層設計（RawTable → 型付きテーブル → ExtractedTables エンベロープ） |
| 2 | Phase 5 ノード/リレーション | FinancialDataPoint + FiscalPeriod追加、Phase 5A-5D分割 |
| 3 | mcp-neo4j-data-modeling | allowedTools追加 + パイプライン統合ポイント定義 |
| 4 | 検証方法 | グラウンドトゥルース方式（人手検証データ + 3軸検証） |
| 5 | LLMプロバイダー | LLMProvider Protocol + ProviderChain（Gemini優先、Claudeフォールバック） |

### 追加3論点（本セッション）

| # | 論点 | 合意内容 |
|---|------|---------|
| A | Doclingフォールバック | Docling MCPはGemini CLIで扱えることを確認しパス。代替パス設計はスキップ |
| B | Master Entity統合 | Entity拡張方式: 既存Entityノードにis_master/isin/official_name/sector追加。別ノード不要 |
| C | 抽出プロンプト戦略 | テキスト: 2パス（Pass1 Entity → Pass2 Fact/Claim）、テーブル: ルールベース変換 |
| D | コスト見積もり | 不要。1日あたりのGemini CLI限界で対処 |
| E | グラフDB書き込み | ハイブリッド: Python graph_writer.py新規作成、save-to-graphのMERGEパターン/ID生成を継承 |

---

## 改訂作業

### 対象ファイル

| ファイル | 変更内容 |
|---------|---------|
| `docs/plan/KnowledgeGraph/2026-03-11_pdf-to-markdown-pipeline.md` | 元プランの改訂（主要変更） |
| `docs/plan/KnowledgeGraph/2026-03-11_pdf-pipeline-5-discussion-points.md` | Status: 議論中 → 合意済み に更新 |

### 元プランへの具体的変更箇所

#### 1. Phase 3B: テーブルスキーマ差し替え

- 現行の `FinancialStatementTable` を3層設計に差し替え
- `schemas/tables.py` のコード例を5論点ドキュメントの Tier 1/2/3 に更新

#### 2. Phase 5: 分割 + 新規ノード/リレーション

- Phase 5 を 5A-5D に分割:
  - 5A: Fact + Claim + Entity抽出（テキストチャンク、2パスLLM）
  - 5B: FinancialDataPoint抽出（テーブルJSON、ルールベース変換）
  - 5C: FiscalPeriod生成 + PERTAINS_TOリンク
  - 5D: Entity間リレーション抽出（SUBSIDIARY_OF等）
- スキーマ拡張セクションに FinancialDataPoint, FiscalPeriod ノード追加
- 新規リレーション追加: HAS_DATAPOINT, PERTAINS_TO, MEASURES, SUBSIDIARY_OF

#### 3. Entity拡張（Master Entity統合）

- Entityノード定義に `isin`, `official_name`, `sector`, `is_master` プロパティ追加
- Phase 6 Entity名寄せの詳細追加:
  - `data/config/master-entities.yaml` 参照テーブル
  - 3段階照合: エイリアス完全一致 → ticker一致 → LLMベース判定

#### 4. 抽出プロンプト戦略セクション追加（新規）

- Track A（テキスト）: 2パス方式の概要
  - Pass 1: Entity抽出（既知Entity一覧参照）
  - Pass 2: Fact/Claim抽出（Pass 1のEntity参照付き）
- Track B（テーブル）: ルールベース変換
  - TimeSeriesTable/EstimateChangeTable → FinancialDataPoint[]のマッピングルール
  - RawTable（未分類）のみLLMフォールバック

#### 5. グラフDB書き込みセクション変更

- Phase 7-8 を改訂:
  - graph-queue JSON出力 → Python graph_writer.py による直接書き込み
  - save-to-graphスキルは使用せず、MERGEパターンとID生成ロジックを継承
- ファイル構成の `services/` セクション更新:
  ```
  services/
  ├── llm_provider.py         # LLMProvider Protocol
  ├── gemini_provider.py      # GeminiCLIProvider
  ├── claude_provider.py      # ClaudeCodeProvider
  ├── provider_chain.py       # フォールバック制御
  ├── graph_writer.py         # Neo4j書き込み（NEW: save-to-graphパターン継承）
  ├── id_generator.py         # UUID5/SHA256 ID生成（emit_graph_queue.pyから移植）
  ├── schema_validator.py     # スキーマバリデーション
  └── state_manager.py        # 処理状態管理
  ```

#### 6. mcp-neo4j-data-modeling活用セクション追加（新規）

- allowedTools設定の追加指示
- パイプライン統合ポイント（validate_data_model, validate_node等）

#### 7. 検証方法の差し替え

- AI出力ベースの検証 → グラウンドトゥルース方式
- `data/sample_report/ground_truth.json` の定義
- 3軸検証（数値抽出精度95%+、構造保持100%、ノイズ除去100%）

#### 8. LLMプロバイダーの変更

- `services/gemini_client.py` → `llm_provider.py` + `gemini_provider.py` + `claude_provider.py` + `provider_chain.py`
- 設定YAML `llm:` セクション追加

---

## 検証方法

改訂後のドキュメント整合性確認:

1. 元プランのPhase番号が連番になっているか
2. ファイル構成図が全変更を反映しているか
3. スキーマ拡張セクションが5論点ドキュメントと一致しているか
4. first-memoのDB構成（5層）と元プランのPhase/ノード定義が整合しているか
5. 依存ライブラリ一覧が更新されているか（neo4j driver追加の可能性）
