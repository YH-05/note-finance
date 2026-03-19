# ナレッジベース構築ガイド

本ドキュメントは、note-finance プロジェクトにおけるナレッジベース（Neo4j ナレッジグラフ + Claude Code スキル/エージェント基盤）の構築で得られたノウハウを体系的にまとめたものである。

---

## 目次

1. [アーキテクチャ全体像](#1-アーキテクチャ全体像)
2. [Neo4j ナレッジグラフ設計](#2-neo4j-ナレッジグラフ設計)
3. [スキーマ進化の軌跡と設計判断](#3-スキーマ進化の軌跡と設計判断)
4. [データパイプライン](#4-データパイプライン)
5. [Claude Code 基盤設計](#5-claude-code-基盤設計)
6. [ルール・ガバナンス体系](#6-ルールガバナンス体系)
7. [メモリシステム](#7-メモリシステム)
8. [実装パターン集](#8-実装パターン集)
9. [得られた教訓](#9-得られた教訓)

---

## 1. アーキテクチャ全体像

### システム構成図

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Code CLI                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ 64 Agents│  │ 58 Skills│  │37 Commands│  │10 Rules│ │
│  └────┬─────┘  └────┬─────┘  └────┬──────┘  └────────┘ │
│       │              │              │                    │
│       └──────────────┼──────────────┘                    │
│                      │                                   │
│  ┌───────────────────┼───────────────────────────┐      │
│  │           MCP Server Layer                     │      │
│  │  neo4j-research ┃ neo4j-note ┃ neo4j-modeling  │      │
│  │  rss ┃ tavily ┃ slack ┃ notion ┃ playwright    │      │
│  └───────────────────┼───────────────────────────┘      │
└──────────────────────┼──────────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
    ┌────▼────┐  ┌─────▼────┐  ┌────▼────┐
    │research │  │  GitHub   │  │  note   │
    │ Neo4j   │  │ Projects  │  │  .com   │
    │(port    │  │  #15,#19  │  │         │
    │ 7688)   │  │  etc.     │  │         │
    └─────────┘  └──────────┘  └─────────┘
```

### コンポーネント規模

| カテゴリ | 数量 | 詳細 |
|---------|------|------|
| Agents | 64 | 開発9, 金融コンテンツ33, ドキュメント10, PRレビュー7, 専門家4, その他1 |
| Skills | 58 | データパイプライン4, グラフ操作4, コンテンツ11, 品質8, 可視化3, 分析8, 計画6, ユーティリティ14 |
| Commands | 37 | 記事8, 金融5, PDF3, 開発5, グラフ3, その他13 |
| Rules | 10 | コーディング規約, Git運用, テスト戦略, 品質基準 等 |
| Python パッケージ | 10 | rss, news, pdf_pipeline, report_scraper, youtube_transcript 等 |
| Neo4j ノード型 | 12 | KG v2.3 スキーマ |
| Neo4j リレーション型 | 25+ | 抽出, 証拠, 時系列, 因果, スタンス, インサイト |

---

## 2. Neo4j ナレッジグラフ設計

### 2.1 インフラ構成

| DB | ポート | 用途 | ステータス |
|----|--------|------|----------|
| research-neo4j | 7688 (Bolt) / 7475 (Browser) | KG v2 統合DB（銘柄・マクロ・記事リサーチ全て） | **Active** |
| finance-neo4j (note-neo4j) | 7687 (Bolt) / 7474 (Browser) | Memory, Conversation, Discussion | 用途限定 |

- **データパス**: `/Volumes/NeoData/neo4j-research/`
- **接続**: `bolt://localhost:7688`, パスワード: `NEO4J_PASSWORD` 環境変数
- **MCP サーバー**: `mcp__neo4j-research__research-*` (KG v2), `mcp__neo4j-note__note-*` (Discussion/Memory)

**教訓**: Community Edition は DB 1つのみ。用途ごとにコンテナを分離した後、2026-03-18 に article-neo4j を research-neo4j に統合（+718ノード, +925リレーション, 500MB メモリ節約）。

### 2.2 スキーマ概要（v2.3）

**正規定義ファイル（SSoT）**: `data/config/knowledge-graph-schema.yaml` (853行)

#### ノード定義（12種）

| ノード | 説明 | 識別キー |
|--------|------|---------|
| **Source** | 情報ソース（web, news, pdf, original, blog） | source_id (SHA-256) |
| **Author** | 著者・発行主体 | author_id |
| **Chunk** | セクション単位のテキスト断片（Lexical Layer） | chunk_id |
| **Fact** | 検証済み過去の客観的情報**のみ** | fact_id |
| **Claim** | 主観的主張・予測・推奨・見通し全般 | claim_id |
| **Entity** | 名前付きエンティティ（企業, セクター, 指数, 国, 金融商品） | entity_id + entity_key |
| **FinancialDataPoint** | 構造化数値データ（is_estimate フラグ付き） | datapoint_id |
| **FiscalPeriod** | 時間的正規化（年次/四半期/月次） | period_id |
| **Topic** | テーマ・カテゴリタグ | topic_id + topic_key |
| **Stance** | 投資スタンススナップショット（Rating + TP + Sentiment） | stance_id (UUID5) |
| **Insight** | AI 生成の分析結果（synthesis, contradiction, gap, hypothesis, pattern） | insight_id |
| **Question** | 知識のギャップ（知りたいが不明な点） | question_id (SHA-256) |

#### 主要リレーション（25+種）

**抽出レイヤー**:
- `CONTAINS_CHUNK` (Source → Chunk) — ソースからチャンクを切り出す
- `EXTRACTED_FROM` (Fact/Claim/FDP → Chunk) — チャンクから抽出された情報

**証拠チェーン**:
- `SUPPORTED_BY` (Claim/Insight → Fact/FDP/Claim) — 根拠リンク（strength付き）
- `CONTRADICTS` (Claim → Claim) — 矛盾関係

**時系列**:
- `FOR_PERIOD` (FDP → FiscalPeriod) — 数値データの期間紐付け
- `NEXT_PERIOD` (FP → FP) — 期間順序（gap_months付き）
- `TREND` (FDP → FDP) — 数値トレンド（change_pct, direction, metric_id, source_hash）

**因果チェーン**:
- `CAUSES` (Fact/Claim/FDP → Fact/Claim/FDP) — 因果推論（mechanism, confidence）

**インサイト**:
- `DERIVED_FROM` (Insight → Fact/Claim/FDP/Insight) — 導出元
- `VALIDATES` / `CHALLENGES` (Insight → Claim/Insight) — 検証/挑戦

#### 名前空間（4つ）

| 名前空間 | ノードラベル | 用途 |
|---------|------------|------|
| kg_v2 | Source, Author, Chunk, Fact, Claim, Entity, FDP, FP, Topic, Stance, Insight, Question | ナレッジグラフ本体 |
| conversation | ConversationSession, ConversationTopic, Project | 会話履歴 |
| memory | Memory + 17サブラベル（Decision, SkillRun 等） | MCP Memory |
| archived | Archived | レガシーノード |

**重要ルール**: 全ノードラベルは **PascalCase** で統一。snake_case は禁止。

### 2.3 制約とインデックス

- **UNIQUE 制約**: 14個（全主キー + entity_key + topic_key + skill_run_id）
- **RANGE インデックス**: 23個（type フィールド, 日付, テキスト検索, ステータス追跡）

---

## 3. スキーマ進化の軌跡と設計判断

### 3.1 バージョン履歴

```
v1.0 (2026-03-11)  6 nodes, 9 rels     初期スキーマ
  │  要件: セルサイドレポートの知識抽出
  │  課題: Chunk未定義, 財務数値構造化なし, Claim型不足
  ▼
v2.0 (2026-03-12)  10 nodes, 15 rels    Claim-centric 再設計
  │  追加: Chunk, FDP, FiscalPeriod, Insight
  │  判断: Recommendation → Claim(recommendation) に統合
  │  判断: confidence プロパティ全削除（AI スコア不信頼）
  ▼
v2.1 (2026-03-17)  11 nodes, 18+ rels   因果+時系列+知識ギャップ
  │  追加: Question ノード, CAUSES リレーション
  │  追加: TREND の metric_id/source_hash スコープ
  │  追加: Stance ノード + HOLDS_STANCE/ON_ENTITY/SUPERSEDES
  ▼
v2.2 (2026-03-17)  同ノード数           スキーマ衛生 + 運用プロパティ
  │  追加: entity_key/topic_key 複合キー（MERGE 冪等性）
  │  追加: Source.command_source/domain（データ来歴）
  │  追加: Source.source_type += blog
  ▼
v2.3 (2026-03-18)  12 nodes             権威レベル + DB統合
     追加: Source.authority_level（6段階）
     統合: article-neo4j → research-neo4j
     追加: SkillRun サブラベル（実行トレーシング）
```

### 3.2 重要な設計判断とその理由

#### D1: Recommendation ノードの不採用 → Claim 統合

**背景**: v1.0 では投資推奨を独立ノードにする案があった。
**ユーザー指摘**: 「必ずしも銘柄に対する recommendation が書いてあるわけではない。セクターレポートやマクロ経済レポートを使うこともある」
**決定**: Claim(claim_type: recommendation) として統合。claim_type を10種に拡張。
**効果**: セクター・マクロレポートとの互換性を確保。ノード型の膨張を防止。

#### D2: Fact の厳密な定義

**背景**: バリュエーション前提（WACC, Beta等）を Fact に分類する案があった。
**ユーザー指摘**: 「バリュエーションは予想と実績値があるため、厳密には事実とは言えないのでは？」
**決定**: Fact = 検証済み過去の客観的情報**のみ**。予想・前提は Claim(assumption) に分類。
**効果**: Fact の信頼性が保証され、証拠チェーンの基盤として機能。

#### D3: confidence プロパティの全削除

**背景**: AI が抽出時に付与する確信度スコアを Fact/Claim/Insight に持たせる案があった。
**ユーザー指摘**: 「confidence はAIによるスコアであり、モデル間で結果が変わるため実装しない方がいい」
**決定**: 全ノードから confidence プロパティを削除。
**効果**: モデル依存の不安定なデータを排除。SUPPORTED_BY の strength（人間が判断可能な粒度）で代替。

#### D4: 複合キーによる MERGE 冪等性（v2.2）

**背景**: Entity/Topic の MERGE 時に name だけでは同名異種の衝突が発生。
**決定**: `entity_key = "{name}::{entity_type}"`, `topic_key = "{name}::{category}"` を導入。
**効果**: 同名でも entity_type/category が異なれば別ノードとして MERGE。完全な冪等性。

#### D5: Source.authority_level の6段階分類（v2.3）

**背景**: ソースの信頼性を重み付けして推論に活用したい。
**決定**: official（企業IR/SEC/中銀）> analyst（セルサイド/格付け）> media（報道機関）> blog（個人メディア）> social（Reddit/X）> academic（学術論文）
**効果**: 推論時にソースの信頼度を加味した判断が可能に。

#### D6: データ来歴の追跡（v2.2）

**背景**: どのコマンド・ワークフローがデータを生成したか不明だった。
**決定**: Source.command_source（生成コマンド名）+ Source.domain（ドメイン名）を追加。
**効果**: データの出自を追跡可能。重複排除やデバッグが容易に。

### 3.3 スキーマ設計のベストプラクティス

1. **SSoT（Single Source of Truth）**: スキーマ定義は `data/config/knowledge-graph-schema.yaml` が正。Neo4j の実態はここから適用。
2. **Wave ベースの漸進的拡張**: 一度に全機能を入れず、Wave 1（基盤）→ Wave 2（因果）→ Wave 3（時系列）→ Wave 4（知識ギャップ）と段階的に。
3. **MERGE ベースの冪等操作**: CREATE は禁止。同一データの再投入で重複しない設計。
4. **UNIQUE 制約先行**: ノード追加前に必ず制約を設定。制約なしの MERGE はパフォーマンス劣化。
5. **名前空間の分離**: KG v2, Memory, Conversation, Archived を混在させない。クエリ時に `WHERE NOT 'Memory' IN labels(n)` でフィルタ。

---

## 4. データパイプライン

### 4.1 PDF → ナレッジグラフ パイプライン

```
PDF ファイル
  │
  ▼  Phase 1: PDF → Markdown
  │  convert-pdf スキル / pdf_pipeline パッケージ
  │  出力: report.md, chunks.json, metadata.json
  │  冪等性: SHA-256 ハッシュでスキップ判定
  │
  ▼  Phase 2: 知識抽出
  │  uv run python -m pdf_pipeline.cli.helpers extract_knowledge
  │  出力: extraction.json (entities, facts, claims, datapoints)
  │
  ▼  Phase 3: グラフキュー生成
  │  scripts/emit_graph_queue.py --command pdf-extraction
  │  出力: .tmp/graph-queue/pdf-extraction/gq-{timestamp}-{hash4}.json
  │  フォーマット: v2 スキーマ準拠
  │
  ▼  Phase 4: Neo4j 投入
     save-to-graph スキル
     MERGE ノード → MERGE リレーション → クロスファイルリンク
```

**グレースフルデグラデーション**:
- Phase 1 失敗 → 全停止（出力なし）
- Phase 2 失敗 → Phase 1 成果物は保持、Phase 3-4 スキップ
- Phase 3 失敗 → Phase 1-2 成果物は保持、Phase 4 スキップ
- Phase 4 失敗 → キューファイル保持、手動リプレイ可能

### 4.2 RSS → ニュース → GitHub Issues パイプライン

```
RSS フィード (34 feeds, 6 categories)
  │
  ▼  rss MCP Server (7 tools)
  │  rss_list_feeds / rss_search_items / rss_fetch_feed
  │
  ▼  news.orchestrator.NewsWorkflowOrchestrator
  │  Collect → Extract (trafilatura/Playwright) → Summarize (LLM)
  │  → Group (11 themes) → Export (MD) → Publish
  │
  ▼  GitHub Issues (Project #15)
     URL 重複チェック, Status/Date フィールド設定
```

### 4.3 save-to-graph スキル（グラフ投入の中核）

**4フェーズ構成**:

1. **Phase 1: キュー検出と検証**
   - Neo4j 接続チェック
   - `.tmp/graph-queue/` 配下のファイル検出
   - JSON スキーマ検証（version: 1.0 | 2.0）

2. **Phase 2: ノード MERGE**（順序重要）
   ```
   Topic → Entity → Source → Author → Chunk
   → Fact → Claim → FDP → FiscalPeriod
   ```

3. **Phase 3a: ファイル内リレーション MERGE**
   - TAGGED, MAKES_CLAIM, ABOUT, CONTAINS_CHUNK, EXTRACTED_FROM 等

4. **Phase 3b: クロスファイルリンク**
   - 既存ノードとのカテゴリ/コンテンツマッチング

5. **Phase 4: 完了処理**
   - 処理済みファイルの削除/保持、統計出力

**パラメータ**: `--source`, `--file`, `--dry-run`, `--keep`, `--skip-cross-link`

### 4.4 オブザーバビリティ

`scripts/skill_run_tracer.py` によるスキル実行トレーシング:
- start/complete/error の3フェーズ追跡
- SkillRun ノード（Memory サブラベル）として Neo4j に保存
- エラー分類: 8カテゴリ（pdf_not_found, neo4j_connection, cypher_execution 等）
- Neo4j 未起動時はシンセティック ID で記録（グレースフルデグラデーション）

---

## 5. Claude Code 基盤設計

### 5.1 エージェント設計体系

#### カテゴリ別エージェント構成（64体）

| カテゴリ | 数 | 代表例 |
|---------|-----|-------|
| コア開発 | 9 | issue-implementer, test-writer, quality-checker |
| 金融コンテンツ | 33 | finance-news-collector, finance-article-writer, 8テーマ別収集 |
| ドキュメント | 10 | functional-design-writer, doc-reviewer |
| PR レビュー | 7 | pr-readability, pr-design, pr-security-code |
| 専門家 | 4 | workflow-designer, agent-creator, skill-creator |
| ガイド | 1 | claude-code-guide |

#### エージェント3タイプ

| タイプ | 色 | モデル | 役割 |
|--------|-----|-------|------|
| Orchestrator | Blue | Opus | 複数エージェントの統括。判断・分岐・統合。 |
| Specialist | Purple | Sonnet | 特定ドメインの専門処理。高速実行。 |
| Teammate | Green | 継承 | Agent Teams 内のチームメイト。 |

#### 金融ニュース収集のエージェント協調例

```
finance-news-orchestrator (Orchestrator/Opus)
  ├─ finance-news-ai (Specialist/Sonnet)
  ├─ finance-news-index (Specialist/Sonnet)
  ├─ finance-news-stock (Specialist/Sonnet)
  ├─ finance-news-sector (Specialist/Sonnet)
  ├─ finance-news-macro (Specialist/Sonnet)
  ├─ finance-news-finance (Specialist/Sonnet)
  └─ news-article-fetcher (Specialist/Sonnet)
```

### 5.2 スキル設計体系

#### スキル2タイプ

| タイプ | 説明 | 例 |
|--------|------|-----|
| NameKnowledgeBase | 読み取り専用のナレッジベース。ガイドライン・パターン・テンプレートを提供 | coding-standards, tdd-development, equity-stock-research |
| Workflow | アクション実行型。複数フェーズの処理を順次実行 | pdf-to-knowledge, save-to-graph, generate-market-report |

#### スキルの構成ファイル

```
.claude/skills/{skill-name}/
  ├── SKILL.md          # メイン定義（フロントマター + 処理フロー）
  ├── guide.md          # 詳細ガイド（任意）
  ├── templates/        # テンプレート集（任意）
  └── examples/         # 例示集（任意）
```

#### フロントマター必須項目

```yaml
---
name: スキル名
description: 1行説明（トリガー判定に使用）
type: knowledge_base | workflow
tools: [使用ツール一覧]
---
```

### 5.3 コマンド設計

#### 記事ワークフローチェーン

```
/article-init → /article-research → /article-draft
  → /article-critique → /article-publish
```

`/article-full` で全工程を一括実行可能。

#### 非推奨コマンドの移行

| 旧コマンド | 移行先 |
|-----------|-------|
| `/new-finance-article` | `/article-init` |
| `/finance-edit` | `/article-draft` + `/article-critique` |
| `/finance-full` | `/article-full` |
| `/publish-to-note` | `/article-publish` |

### 5.4 メタフレームワーク（自己拡張）

| スキル/エージェント | 役割 |
|-------------------|------|
| skill-expert | スキル設計・実装・検証のナレッジベース |
| agent-expert | エージェント設計・実装・検証のナレッジベース |
| skill-creator | スキル作成専門エージェント（skill-expert を参照） |
| agent-creator | エージェント作成専門エージェント（agent-expert を参照） |
| command-expert | コマンド設計・最適化エージェント |
| workflow-expert | ワークフロー設計・マルチエージェント連携のナレッジベース |
| skill-analytics | SkillRun トレーシングデータの分析 |

---

## 6. ルール・ガバナンス体系

### 6.1 ルールファイル一覧（10ファイル）

| ファイル | 要点 |
|---------|------|
| `coding-standards.md` | PEP 695型ヒント, NumPy Docstring, PascalCase/snake_case |
| `development-process.md` | format → lint → typecheck → test, TDD必須 |
| `testing-strategy.md` | Unit/Property/Integration, 日本語テスト名, Hypothesis |
| `git-rules.md` | Conventional Commits, feature/fix/refactor ブランチ |
| `common-instructions.md` | structlog ログ必須, template/ 参照パターン |
| `evidence-based.md` | 禁止語（best, optimal）→ 推奨語（measured X, reduces Y%） |
| `subagent-data-passing.md` | **完全なデータ構造必須**（URL省略禁止, JSON形式） |
| `article-quality-standards.md` | 表→画像化, ソースURL必須, チャート→画像化 |
| `neo4j-namespace-convention.md` | PascalCase統一, 名前空間分離 |
| `README.md` | ルールディレクトリの概要・参照方法 |

### 6.2 ルール設計のベストプラクティス

1. **具体的な失敗事例を記載**: `subagent-data-passing.md` には「省略時の実際の影響」テーブルがある。禁止理由が明確。
2. **チェックリスト形式**: 各ルールの末尾に `- [ ]` 形式のチェックリストを置き、批評・レビュー時に参照。
3. **参照パスの明示**: 「詳細はスキル `X` を参照」のように、ルール概要 → スキル詳細の2層構造。
4. **禁止語と推奨語の対比**: `evidence-based.md` のように「ダメな例」と「良い例」を並べる。

### 6.3 リポジトリ混同の防止

プロジェクトには2つのリポジトリが存在:

| リポジトリ | 用途 | Issue の種類 |
|-----------|------|-------------|
| `YH-05/note-finance` | コードベース（本リポジトリ） | 実装タスク・バグ修正 |
| `YH-05/finance` | 金融ニュース追跡 | ニュース記事・マーケットレポート |

**必須プロトコル**: Issue 作成前に `git remote get-url origin` で確認。リポジトリ名をハードコードしない。

---

## 7. メモリシステム

### 7.1 概要

Claude Code のファイルベースメモリ（`~/.claude/projects/{project}/memory/`）を使用。会話をまたいで持続する情報を保存。

### 7.2 メモリタイプ

| タイプ | 用途 | 例 |
|--------|------|-----|
| user | ユーザーの役割・目標・知識 | バイサイドアナリストとして FM 向け Initial Report を執筆 |
| feedback | アプローチの修正・確認 | Issue 作成時のリポジトリ混同、プランファイルの命名規則 |
| project | 進行中のプロジェクト情報 | research-neo4j の構成、KG v2.1 Phase 2 の進捗 |
| reference | 外部システムへのポインタ | Notion メインDB ID、最適アクセス方法 |

### 7.3 メモリに保存すべきでないもの

- コードパターン・アーキテクチャ・ファイルパス（コードから導出可能）
- Git 履歴・変更履歴（`git log` / `git blame` が権威）
- デバッグ解決策（修正はコードに、コンテキストはコミットメッセージに）
- CLAUDE.md に既に記載されている内容
- 一時的なタスク詳細（タスクツールを使用）

### 7.4 メモリのライフサイクル

1. **作成**: 非自明な情報を学習した時点で保存
2. **参照**: 関連タスク時に自動ロード（MEMORY.md がインデックス）
3. **更新**: 状況変化時に既存メモリを更新（重複作成しない）
4. **削除**: 陳腐化したメモリは削除（例: article-neo4j 廃止後の project_article_neo4j.md）

---

## 8. 実装パターン集

### 8.1 4フェーズワークフローパターン

pdf-to-knowledge, save-to-graph で共通する設計パターン:

```
Phase 1: 検出・検証
  │  前提条件チェック, 入力パース, 冪等性チェック
  ▼
Phase 2: 主処理
  │  コアロジック実行（PDF→MD, ノード MERGE 等）
  ▼
Phase 3: リンク
  │  関係性の確立（リレーション, クロスファイル参照）
  ▼
Phase 4: 完了
     クリーンアップ, 統計出力, オブザーバビリティ記録
```

**設計原則**: 各フェーズは前のフェーズの成功に依存するが、途中フェーズの失敗時はそれ以前の成果物を保持（グレースフルデグラデーション）。

### 8.2 冪等性パターン

| 手法 | 使用箇所 | 説明 |
|------|---------|------|
| SHA-256 ハッシュ | Source.source_id | 同一ソースの重複投入防止 |
| 複合キー MERGE | Entity.entity_key, Topic.topic_key | `"{name}::{type}"` で同名異種を区別 |
| 状態ファイル | pdf_pipeline StateManager | Phase 1 完了済みの PDF を再処理しない |
| UUID5 | Stance.stance_id | 決定論的 UUID で同一スタンスの重複防止 |

### 8.3 サブエージェントへのデータ受け渡し

**鉄則**: 完全なデータ構造を JSON 形式で渡す。省略・自然言語記述は禁止。

```json
{
  "articles": [
    {
      "url": "https://...",
      "title": "記事タイトル",
      "summary": "要約...",
      "feed_source": "CNBC - Markets",
      "published": "2026-01-19T12:00:00+00:00"
    }
  ],
  "issue_config": {
    "theme_key": "index",
    "theme_label": "株価指数",
    "project_id": "PVT_...",
    "repo": "YH-05/finance"
  }
}
```

### 8.4 エージェント協調パターン

**Orchestrator → Specialist 分散**:
- Orchestrator（Opus）がタスクを分配し、結果を統合
- Specialist（Sonnet）が個別ドメインを高速処理
- 並列実行で全体スループット向上

**Agent Teams（Teammate グリーン）**:
- test-lead → test-planner → (test-unit-writer & test-property-writer) → test-integration-writer
- weekly-report-lead → news-aggregator → data-aggregator → comment-generator → template-renderer

### 8.5 記事品質パターン

| ルール | 実装 |
|--------|------|
| マークダウン表 → 画像化 | `/generate-table-image` スキルで PNG 生成 |
| 根拠データ → ソースURL | `[数値](https://source.com)` 形式で埋め込み |
| データ可視化 → チャート画像 | `/generate-chart-image` スキルで matplotlib レンダリング |

---

## 9. 得られた教訓

### 9.1 スキーマ設計

| 教訓 | 詳細 |
|------|------|
| **Claim-centric が汎用性を生む** | 投資推奨もマクロ見通しも統一的に Claim として扱えるため、レポート種別を問わず対応可能 |
| **AI 生成スコアは保存しない** | confidence 等のモデル依存スコアは再現性がなく、バージョン間で矛盾を生む |
| **複合キーで冪等性を保証** | `name` だけの MERGE は同名異種で衝突する。`entity_key = "{name}::{type}"` が解 |
| **権威レベルは推論品質に直結** | SEC Filing と Reddit 投稿を同列に扱うと推論が劣化する |
| **SSoT を YAML で管理** | Neo4j 上のスキーマは `schema.yaml` から適用。手動変更は禁止 |

### 9.2 パイプライン設計

| 教訓 | 詳細 |
|------|------|
| **グレースフルデグラデーション必須** | Neo4j 停止中でも Phase 1-3 は完走。キューファイルで後から投入可能 |
| **MERGE 順序は制約依存** | Topic → Entity → Source の順で MERGE しないと参照先が未作成 |
| **ハッシュベースの冪等性** | 同一 PDF の再投入で重複ノードが生まれない設計が運用を楽にする |
| **Phase 分離でデバッグ容易** | 問題発生時に「Phase 2 の出力は正しいが Phase 3 で壊れている」と特定しやすい |

### 9.3 エージェント/スキル設計

| 教訓 | 詳細 |
|------|------|
| **メタフレームワークで自己拡張** | skill-expert / agent-expert が新スキル/エージェント作成を標準化 |
| **ルールは .claude/rules/ に集約** | 全エージェント・スキルが同一ルールを参照し、一貫性を保証 |
| **サブエージェントにはフルデータ** | URL や published を省略するとダウンストリームが機能不全に陥る |
| **Orchestrator/Specialist 分離** | 判断（Opus）と実行（Sonnet）を分離し、コスト効率と品質を両立 |

### 9.4 運用

| 教訓 | 詳細 |
|------|------|
| **リポジトリ混同は事故の元** | `git remote get-url origin` で毎回確認。ハードコード禁止 |
| **プランファイルは日付ベース** | ランダム名ではなく `YYYY-MM-DD_内容名.md` で命名。後から探しやすい |
| **メモリは陳腐化する** | 統合・廃止後のメモリは速やかに更新/削除。古いメモリは誤誘導の元 |
| **DB 統合は定期的に検討** | Community Edition の 1DB 制約下で、用途が重なる DB は統合してメモリ節約 |

---

## 関連リソース

| リソース | パス |
|---------|------|
| KG スキーマ定義（SSoT） | `data/config/knowledge-graph-schema.yaml` |
| プロジェクト共通指示 | `AGENTS.md` |
| Claude Code 固有設定 | `CLAUDE.md` |
| ルールディレクトリ | `.claude/rules/` |
| スキルディレクトリ | `.claude/skills/` |
| エージェントディレクトリ | `.claude/agents/` |
| コマンドディレクトリ | `.claude/commands/` |
| KG 議論メモ | `docs/plan/KnowledgeGraph/` |
| メモリディレクトリ | `~/.claude/projects/-Users-yukihata-Desktop-note-finance/memory/` |

---

*最終更新: 2026-03-19*
