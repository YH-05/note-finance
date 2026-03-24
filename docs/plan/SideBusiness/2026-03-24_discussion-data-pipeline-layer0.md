# 議論メモ: データ投入パイプライン統一 — 一気通貫パイプライン完成

**日付**: 2026-03-24
**参加**: ユーザー + AI

## 背景・コンテキスト

「全てのNeo4jデータベースはプロジェクトの知識そのもの」という根本原則に基づき、データ投入パイプラインの前段階を整備。2026-03-23の棚卸し（disc-2026-03-23-data-source-inventory）で特定されたNeo4j未接続ギャップへの対応として、パイプライン全体のアーキテクチャを設計し、Layer 0-2を段階的に実装した。

## 議論のサマリー

### Layer 0: ソースレジストリ
- 全27ソースをプロバイダー単位で統合インデックス（source_registry.json）に登録
- 収集方法はEnum固定ではなくcollection_methods.jsonに外部定義（6種: rss, scraping, api, web_search, pdf, manual）
- Pydanticモデルで型安全に管理、バリデーション機能付き

### Layer 1: RSSコレクター
- feedparser + trafilatura でRSSフィード収集 + 本文取得
- requests経由のHTTPタイムアウト（10秒/フィード）でハング防止
- User-Agentヘッダー追加でBot検知対策
- source_idフィルタでプリセットファイル重複参照を解消

### Layer 2: 原文保存 + アダプター
- RawStore: /Volumes/personal_folder/raw_texts にJSON保存、URLハッシュ重複排除
- save_text() / save_many_texts() ヘルパーで既存パイプラインから直接保存可能
- adapters.py: 6種のアダプター（news, news_scraper, rss_mcp, pdf, web_research, reddit）

### E2Eテスト結果
9ソースから99件の原文テキストを保存成功。各ソースが自分のフィードのみ取得することを確認。

### 問題と対応
1. **プリセット重複参照** → source_idフィルタで解消
2. **Bot検知** → The Verge/NASDAQ/Mr. Money Mustache無効化
3. **feedparserハング** → requests経由タイムアウト導入
4. **テキスト系 vs 数値系** → 別ルートに分離
5. **体験談DB** → 廃止

## 決定事項

1. **5層レイヤー構造** (dec-2026-03-24-pipeline-layer-architecture)
2. **Pythonコア + スキル/コマンド呼び出し** (dec-2026-03-24-python-core-with-skill-interface)
3. **原文保存先は /Volumes/personal_folder** (dec-2026-03-24-raw-text-storage-personal-folder)
4. **プロバイダー単位の粒度** (dec-2026-03-24-provider-level-granularity)
5. **収集方法の外部JSON定義** (dec-2026-03-24-collection-methods-external-json)
6. **テキスト系 vs 数値系の投入ルート分離** (dec-2026-03-24-text-vs-numeric-route)
7. **体験談DB廃止** (dec-2026-03-24-experience-db-deprecated)
8. **source_idフィルタによるプリセット重複解消** (dec-2026-03-24-source-id-filter)

## 実装成果物

### Layer 0: ソースレジストリ
| ファイル | 役割 |
|---|---|
| `src/data_pipeline/registry/models.py` | Pydanticモデル（DataSource, CollectionMethodDef等） |
| `src/data_pipeline/registry/loader.py` | ローダー + バリデーション + サマリー |
| `data/config/source_registry.json` | 統合インデックス（26ソース） |
| `data/config/collection_methods.json` | 収集方法定義（6種） |

### Layer 1: RSSコレクター
| ファイル | 役割 |
|---|---|
| `src/data_pipeline/collectors/base.py` | 共通プロトコル + CollectedItem + CollectionResult |
| `src/data_pipeline/collectors/rss.py` | RSSコレクター（feedparser + trafilatura + タイムアウト + source_idフィルタ） |
| `data/config/rss-presets.json` | source_idフィルタ対応（v1.1） |
| `data/config/rss-presets-jp.json` | source_idフィルタ対応（v1.1） |

### Layer 2: 原文保存 + アダプター
| ファイル | 役割 |
|---|---|
| `src/data_pipeline/storage/raw_store.py` | 原文保存ストア（save/save_text/save_many_texts） |
| `src/data_pipeline/storage/adapters.py` | 6種のアダプター（既存パイプライン→CollectedItem変換） |

### Layer 3: 構造化出力
| ファイル | 役割 |
|---|---|
| `src/data_pipeline/structurer/models.py` | StructuredOutput, SourceEntry, FactEntry, ClaimEntry, TopicEntry |
| `src/data_pipeline/structurer/converter.py` | CollectedItem → StructuredOutput 変換（minimal + LLM対応） |
| `src/data_pipeline/structurer/emitter.py` | JSON保存 + emit_research_queue.py 実行 |

**テスト**: 146件全パス（19秒）

## アクションアイテム

- [x] Layer 0（ソースレジストリ）設計・実装 (完了)
- [x] Layer 1（RSSコレクター）実装 (完了)
- [x] Layer 2（原文保存+アダプター）実装 (完了)
- [x] Layer 3（構造化出力）設計・実装 (完了)
- [x] 既存パイプラインとの統合ブリッジ (完了 — bridge.py 7種ワンライナー関数)
- [x] 全収集ルート原文保存統合 (完了 — Python直接フック3件 + emitフック + creator-neo4jフック + PostToolUse hook 4ツール)
- [x] リネーム: emit_graph_queue→emit_research_queue, save-to-graph→save-to-research-graph (完了 — 215+ファイル)
- [x] pyproject.tomlへのパッケージ登録 (完了)
- [x] LLM抽出ロジック: claude_agent_sdk経由のFact/Entity/Claim抽出 (完了)
- [x] 一気通貫オーケストレーター: run_pipeline() + neo4j_loader (完了)
- [ ] 日次バッチCLIの実装 (優先度: 中)
- [ ] CLIインターフェース（registry list/validate） (優先度: 低)

## 次回の議論トピック

- Layer 3: LLM抽出（Fact/Entity）とemit_research_queue.pyとの統合方法
- 日次バッチのスケジューリング設計（cronジョブ or スケジューラ）
- 既存パイプラインへのアダプター統合の優先順位
- 数値データ（yfinance/FRED）のFinancialDataPoint投入ルート設計
