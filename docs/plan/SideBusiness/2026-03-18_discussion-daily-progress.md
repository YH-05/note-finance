# 議論メモ: 2026-03-18 日次進捗サマリー

**日付**: 2026-03-18
**参加**: ユーザー + AI

## 達成状況

- 完了率: **59/61 タスク (96.7%)**
- 未完了: 2件（明日以降に繰り越し）

## 主要成果（10項目）

### 1. KG v2.2 マイグレーション完了
- Phase 1: 制約・インデックス同期（entity_key UNIQUE, topic_key UNIQUE, Source インデックス）
- Phase 2: レガシーノード整理（Discussion/Decision/ActionItem → Archived ラベル付与）
- Phase 3: YAML 定義更新（`docker/article-neo4j/` 配下）
- Phase 4: emit_graph_queue.py のマッパー更新（command_source/domain/entity_key/topic_key 対応）

### 2. research-neo4j Wave 1-4 全実装・統合検証完了
- **Wave 1 (#143)**: Author=publisher 実体化 + Claim→Stance 遡及バッチ（`scripts/backfill_stance_from_claims.py`）
  - 9 Author / 9 Stance / 9 HOLDS_STANCE / 9 ON_ENTITY / 9 BASED_ON / 9 AUTHORED_BY
- **Wave 3 (#144)**: Metric.metric_id グルーピング + Temporal Chain 遡及バッチ（`scripts/backfill_temporal_chain.py`）
  - 16 FP / 152 MEASURES-linked DP / 13 NEXT_PERIOD / 106 TREND
- **Wave 4 (#145)**: consensus_divergence + prediction_test question_type 追加
  - extraction.py の Literal 型 + LLM プロンプトに実装済み
- **統合検証 (#146)**: 全ノード 3,282 / 全リレーション 5,310 確認

### 3. Project 13 #133/#134 クローズ
- #133: save-to-article-graph SKILL.md 新規作成
- #134: E2E dry-run 検証（topic-discovery + wealth-scrape の graph-queue JSON 生成確認）

### 4. LlamaParse スキル新設
- `.claude/skills/llamaparse-convert/` 新設
- LlamaParse REST API で PDF を高精度 Markdown に変換
- セルサイドレポート等の複雑レイアウト PDF 対応

### 5. NotebookLM CLI パッケージ新設
- `src/notebooklm/` に CLI パッケージ新設
- Playwright ベースのブラウザ自動化
- 質問自動送信・回答収集・バッチ処理

### 6. cognee スキル改善調査 & 計画作成
- cognee の eval/feedback loop アーキテクチャ調査
- 推奨度「中」：SkillRunログ + feedback構造化を優先アクション
- 計画: `docs/plan/2026-03-18_cognee-skill-improvement-adaptation.md`

### 7. JETRO スクレイパー実装計画策定
- JETRO HP の構造調査（RSS + AJAX カテゴリページ）
- 2層構成アーキテクチャ設計（RSS Layer + Playwright Crawler Layer）
- 計画: `docs/plan/2026-03-18_jetro-overseas-business-scraper.md`

### 8. AuraDB Free バックアップセットアップ
- データサイズ調査（Free Tier 上限の2%未満）
- 移行方式: MCP経由 Cypher ベース採用
- AuraDB Free インスタンス作成 + .mcp.json 設定追加済み

### 9. article-neo4j 廃止 → research-neo4j 統合
- article-neo4j (port 7689) を廃止
- research-neo4j (port 7688) に統合
- Docker Compose 定義・MCP 設定も更新済み

### 10. wealth スクレイピング改善 & RSS CLI 拡張
- wealth スクレイピングの精度改善
- RSS CLI 拡張
- Dependabot PR #116 マージ (dorny/paths-filter v4)

## 決定事項

1. **article-neo4j 廃止 → research-neo4j 統合** (dec-2026-03-18-006): 2インスタンス管理のオーバーヘッド解消
2. **LlamaParse スキル新設** (dec-2026-03-18-007): Claude Read 方式のアップグレードパス
3. **NotebookLM CLI パッケージ新設** (dec-2026-03-18-008): 銘柄リサーチ質問自動化
4. **entity_key/topic_key 複合キー導入** (dec-2026-03-18-001): MERGE 冪等化
5. **AuraDB Free バックアップ採用** (dec-2026-03-18-004): クラウドバックアップ確保
6. **MCP経由 Cypher ベース移行方式** (dec-2026-03-18-005): 既存 MCP インフラ活用

## アクションアイテム（明日以降）

- [ ] AuraDB Free 接続テスト + research-neo4j データ移行実行 (優先度: 高) — act-2026-03-18-009
- [ ] 日本株ニュース HTML スクレイパー実装 (優先度: 中) — act-2026-03-18-010
- [ ] cognee スキル改善適用: SkillRunログ + feedback構造化 (優先度: 中) — act-2026-03-18-011
- [ ] EXCL/XLSmart 財務時系列データ補完 (優先度: 中, deferred) — act-2026-03-18-005

## 次回の議論トピック

- AuraDB 移行完了後の運用フロー（定期同期の頻度・方法）
- JETRO スクレイパー実装着手のタイミング
- cognee スキル改善の具体的実装設計
- ISAT Initial Report 執筆開始に向けた残データ補完

## Neo4j 保存先

- Discussion: `disc-2026-03-18-daily-progress`
- Decisions: `dec-2026-03-18-006`, `dec-2026-03-18-007`, `dec-2026-03-18-008`
- ActionItems: `act-2026-03-18-009`, `act-2026-03-18-010`, `act-2026-03-18-011`
