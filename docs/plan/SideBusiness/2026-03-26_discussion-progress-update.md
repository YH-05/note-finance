# 議論メモ: 進捗更新・ActionItem状態同期・backfillバグ修正・pipelineリファクタリング

**日付**: 2026-03-26
**参加**: ユーザー + AI

## 背景・コンテキスト

未完了ActionItemの棚卸しとステータス同期、`backfill_creator_source_published_at.py` の実装・実行、およびfinance-news-workflowの廃止・スクレイピングパイプライン再構築。

## 議論のサマリー

### ActionItem ステータス更新

| ActionItem | 変更前 | 変更後 |
|-----------|-------|-------|
| act-2026-03-26-jetro-launchd-001（plist配置・launchctl load） | pending | completed |
| act-2026-03-26-jetro-launchd-002（launchctl start テスト実行） | pending | completed |
| act-2026-03-23-016（career_sister 投稿開始） | pending | completed |
| act-2026-03-25-publish-tue-evening（3/25夜スロット投稿） | pending | completed |
| act-2026-03-23-014（Post 2-5 順次投稿） | pending | in_progress |
| act-2026-03-26-backfill-run（Source.published_at埋め） | pending | completed |

### ASP登録（継続pending）

- act-2026-03-23-017: ASP登録（A8.net→afb→アクセストレード）
- act-2026-03-21-010: ASP登録実行（Threads/ブログ審査対応）
- ユーザー報告: 投稿は開始済みだがASP登録はまだ

### backfill_creator_source_published_at.py 実行

**dry-run結果（初回）**: candidates=793, updated=449, skipped=301, failed=43

**本番実行1回目**: 失敗
- エラー: `neo4j.exceptions.CypherSyntaxError: Text cannot be parsed to a DateTime "2026/03/26 10:00"`
- 原因: スラッシュ区切り日付（`YYYY/MM/DD HH:MM`）をCypherの `datetime()` が解析できない

**バグ修正1**: `_normalize_date()` 関数を追加
- `/` → `-` 置換
- 日付と時刻間のスペース → `T` 置換

**本番実行2回目**: 失敗
- エラー: `Text cannot be parsed to a DateTime "2026-01-20T09:44:30 +0900"`
- 原因: タイムゾーンオフセット前のスペース

**バグ修正2**: `_normalize_date()` を拡張
- タイムゾーン前スペース除去の正規表現を追加
- Python `datetime.fromisoformat()` でバリデーション
- RFC 2822 形式フォールバック（`email.utils.parsedate_to_datetime`）

**本番実行3回目**: 成功
- candidates=793, updated=440, skipped=311, failed=42
- 失敗42件は廃止ドメイン・404・403（データ上問題なし）

## finance-news-workflow 廃止・パイプライン再構築（コミット: 17d41d4）

### 廃止したもの
- `finance-news-workflow` スキル（`.agents/skills/`, `.claude/skills/` 両方）
- `collect_finance_news*.py` 6ファイル（旧フロー）

### 新設・変更したもの
- `scrape_finance_news.py` を大規模リファクタリング（単一エントリポイント）
- `ingest_graph_queue.py` 追加（graph-queue → Neo4j 投入）
- `backfill_creator_source_published_at.py` 追加（published_at 埋め）
- `kg-summary` / `topic-discovery` コマンド追加
- `creator-enrichment` バグ修正（gap_analysis, search, neo4j_writer）
- `data/raw/rss/feeds.json` 整理

### Mac Mini セットアップ（次フェーズ・pending）
- act-2026-03-26-finance-news-001: launchd plist 作成・登録（high）
- act-2026-03-26-finance-news-002: scrape_finance_news.py --skip-neo4j 動作確認（high）
- act-2026-03-26-finance-news-003: ingest_graph_queue.py --dry-run 確認（high）
- act-2026-03-26-finance-news-004: ingest_graph_queue.py launchd 設定（medium）

## 決定事項

なし（進捗記録のみ）

## アクションアイテム（継続中）

### creator-neo4j 関連
- [ ] act-2026-03-26-creator-monetization-001: Post/Account/Engagement/Conversionレイヤー設計（high）
- [ ] act-2026-03-25-020: creator-enrichment Story重点化（high）
- [ ] act-2026-03-24-001: creator-quality-check 実施（high）
- [ ] act-2026-03-21-012/013: emit_creator_queue.py / save-to-creator-neo4j スキル実装（blocked）

### career_sister 関連
- [ ] act-2026-03-23-017 / act-2026-03-21-010: ASP登録（A8.net→afb→アクセストレード）（high）
- [x] act-2026-03-23-014: Post 2-5 順次投稿（in_progress）

## 次回の議論トピック

- Mac Mini での finance-news pipeline セットアップ（launchd plist 配置）
- ASP登録の進め方（どのASPから着手するか）
- creator-enrichment Story収集重点化の具体的設定変更
- creator-quality-check の実施タイミング
- creator-neo4j Post/Account/Engagement/Conversion レイヤー設計

## 参考情報

- backfill修正箇所: `scripts/backfill_creator_source_published_at.py` の `_normalize_date()` 関数（L235付近）
- 修正内容: スラッシュ区切り・タイムゾーンスペース正規化 + Python datetime バリデーション + RFC 2822 フォールバック
