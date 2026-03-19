# 実装状況スナップショット (2026-03-19)

**日付**: 2026-03-19
**参加**: ユーザー + AI

## コードベース

| 項目 | 数値 |
|------|------|
| src/ パッケージ | 9個 |
| テスト | 7,020件 |
| スキル | 61個 |
| エージェント | 64個 |
| コマンド | 39個 |

### パッケージ一覧

| パッケージ | 説明 |
|-----------|------|
| `automation` | 自動化ユーティリティ |
| `data_paths` | データパス管理 |
| `news` | ニュース処理 |
| `news_scraper` | HTML スクレイパー (JETRO対応) |
| `notebooklm` | NotebookLM CLI自動化 |
| `pdf_pipeline` | PDF→Markdown変換パイプライン |
| `report_scraper` | セルサイドレポート処理 |
| `rss` | RSSフィード管理 |
| `youtube_transcript` | YouTube字幕収集 |

## 記事ステータス

| カテゴリ | revised_draft | first_draftのみ |
|---------|--------------|----------------|
| asset_management | 7本 | 1本 |
| macro_economy | 4本 | 0本 |
| stock_analysis | 1本 | 1本 |
| investment_education | 1本 | 0本 |
| side_business | 1本 | 0本 |
| market_report | 0本 | 0本 |
| **合計** | **16本** | **2本** |

## Neo4j / ナレッジグラフ

| DB | ノード | リレーション | 備考 |
|----|--------|------------|------|
| research-neo4j (port 7688) | 5,254 | 21,871 | AuraDB バックアップ済み |
| note-neo4j (port 7687) | 94 | — | Discussion/Decision/ActionItem |

### KG 品質スコア (kg_quality_metrics.py)

| カテゴリ | スコア |
|---------|-------|
| Overall | 53.6/100 (Rating C) |
| Consistency | 50.0 (最大改善: 16.7→50.0) |
| スキーマ | v2.4 (entity_type 14種追加, relationship 16種追加) |

### 残課題

- entity_id NULL 136件の補完
- レガシーリレーション名リネーム (RELATED_TO→RELATES_TO 72件, HAS_FACT→STATES_FACT 35件, TAGGED_WITH→TAGGED 3件)
- accuracy スコアが stub 実装

## GitHub Projects (アクティブ)

| # | プロジェクト | 状態 |
|---|------------|------|
| 92 | arXiv論文 著者・引用 自動取得パイプライン | 計画中 |
| 91 | news_scraper コードベース改善 | 計画中 |
| 90 | Neo4j書き込みパイプライン一本化 | 進行中 |
| 89 | KG品質ダッシュボード + Entity接続強化 | 完了近い |
| 88 | ASEAN銘柄データ取得基盤 | 計画中 |
| 87 | LlamaParse スキル新設 | 完了 |
| 86 | JETRO海外ビジネス情報スクレイパー | 完了 |
| 85 | YouTube Transcript Collector | 完了 |
| 84 | 日本株ニュース HTMLスクレイパー追加 | 完了 |
| 83 | KG v2.1: AI推論最適化スキーマ設計 | 完了 |

## 今日 (3/19) の成果

1. **Neo4j品質分析・改善**: P0-P2 の3段階改善 + パイプライン正規化ロジック組み込み
2. **research-neo4j大規模拡充**: MAG7 7社 (52facts/27sources)、G7マクロ (67facts/48sources)、ASEAN テレコム (25facts)
3. **KG品質ダッシュボード**: 初回計測実行、スキーマv2.4へ拡張、Overall 48.8→53.6
4. **article-research KG統合**: Phase 0 (KG照会+ギャップ分析) と Phase 5 (KG永続化) を追加
5. **topic-discovery KG統合**: Phase 0 (KG トピック発掘 8クエリ→4種候補生成) を追加
6. **generate-image-prompt スキル新設**: Nano Banana向け英語プロンプト、カテゴリ別スタイル対応
7. **ISAT競合企業分析**: Telkomsel/XLSmart/Telkom Indonesia のデータ拡充、パイプライン3問題修正
8. **KGパイプライン正規化**: emit_graph_queue.py に _normalize_entity_type()/_normalize_source_type() 追加

## 未完了 ActionItems

### 高優先度

- [ ] 記事ネタ候補7件から優先3本を選定し `/article-full` で執筆開始
- [ ] `/finance-suggest-topics` を実行し KG トピック発掘の動作確認
- [ ] 実際の記事で `/article-research` → KGギャップ分析 → Web検索 → KG永続化の一連フロー動作確認

### 中優先度

- [ ] entity_id NULL 136件を補完
- [ ] REVISED状態の記事をnote.comに投稿 (優先: macro_economy 3本, stock_analysis 1本)
- [ ] レガシーリレーション名をリネーム (110件)
- [ ] kg_quality_metrics.py の定期実行設定 (週次cron or GitHub Actions)
- [ ] emit_graph_queue.py に topic-discovery コマンドを追加するか検証
- [ ] 各カテゴリスキルへのKGギャップ分析統合を検討

## 参考情報

- AuraDB バックアップ: 2026-03-19 初回実行完了 (5,254ノード/21,871リレーション、42.5秒)
- Git コミット数: 20件/直近2週間
- 最新コミット: `43d6377` feat: KGパイプライン正規化 + スキル・記事更新
