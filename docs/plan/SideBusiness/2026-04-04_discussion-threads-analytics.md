# 議論メモ: Threadsインプレッション解析モジュール実装

**日付**: 2026-04-04
**参加**: ユーザー + AI

---

## 背景・コンテキスト

career_sisterアカウントの投稿パフォーマンスを可視化し、投稿戦略を最適化するため、Threads Insights APIを活用したanalyticsモジュールの設計・実装を行った。あわせて2026-04-05〜04-11の1週間分投稿ドラフトを生成した。

---

## 実施内容

### 1週間分ドラフト生成（career_sister）

- **期間**: 2026-04-05（土）〜 2026-04-11（金）
- **Threads**: 21本（有益15 / エンゲージメント4 / 収益化2）
- **Instagram**: 7本（カルーセル各7スライド）
- **保存先**: `creator/career_sister/drafts/week_2026-04-05/`
- `posting_state.json` 更新済み（cycle_position: 2→3, total_posts: 22→43）

### analyticsモジュール新規実装

| ファイル | 内容 |
|---------|------|
| `src/creator/insights.py` | ThreadsInsightsClient（get_media_insights / list_user_threads / resolve_media_ids） |
| `src/creator/analytics.py` | InsightsStore / EngagementAnalyzer / WeightRecommender |
| `scripts/insights_collector.py` | CLI: backfill / collect / followers |
| `scripts/engagement_analyzer.py` | CLI: matrix / report / recommend / apply / trend / compare |

### media_idバックフィル問題の解決

- `auto_poster.py` はmedia_idをログ出力するのみで `posting_state.json` に保存していなかった
- **対処**: `list_user_threads()` でpermalink→media_idマッピングを構築してバックフィル
- **今後**: `append_post_history()` に `threads_media_id` 引数を追加済み（`auto_poster.py` 修正完了）

### 実データ収集結果

- `posting_state.json` 記録分9件のmedia_id解決・インサイト取得成功
- Threads APIから直接取得した過去投稿37件のインサイトも収集
- 計46件の `creator/career_sister/analytics/insights/*.json` 生成
- 最高パフォーマンス投稿: `api_18004841801906393`（2026-03-26）views=482, ER=7.7%

---

## Threadsベストプラクティス調査結果

1. **Self-reply**: 投稿後すぐに補足リプライ → +42% ER（Buffer調査）
2. **画像添付**: テキスト単独より+60% views
3. **返信重視**: Mosseriが「返信が最も重要な指標」と明言
4. **投稿頻度**: 1日1〜2本が最適（毎日投稿 vs 隔日投稿で+12%）
5. **ポーリング**: 質問形式が返信を促進
6. **ハッシュタグ**: 効果薄（Threads固有アルゴリズム）

---

## 決定事項

1. **analyticsモジュール設計**: InsightsStore/EngagementAnalyzer/WeightRecommenderの3クラス分離、JSON永続化（DB不要）
2. **media_idバックフィル方式**: list_user_threads()経由のpermalink→media_idマッピング
3. **自動化スコープ**: App Review不要の4項目を優先実装対象として決定

---

## アクションアイテム

- [ ] self-replyボット実装（投稿後に自動補足リプライ送信）（優先度: 高）
- [ ] Threads画像添付機能実装（auto_poster.pyに画像添付オプション追加）（優先度: 高）
- [ ] IGS cross-promo自動化（Threads投稿後にIG Stories告知）（優先度: 中）
- [ ] insights_collector.py定期実行スケジュール設定（cron/launchd）（優先度: 中）
- [ ] インサイトデータ蓄積後（20-30件）にengagement_analyzer.pyでweight調整実行（優先度: 低）

---

## 次回の議論トピック

- 自動化実装の優先順位（self-reply vs 画像添付 どちらから？）
- インサイトデータがtheme/type/slot nullの46件をどう扱うか（matrix分析の精度向上）
- posting_state.jsonのpost_historyに記録されていない過去投稿の扱い

---

## 参考情報

- Threads API: `threads_basic` スコープで `/insights` 利用可能（App Review不要）
- Buffer調査: Self-reply +42% ER, 画像添付 +60% views
- Adam Mosseri: 「返信がThreadsで最も重要な指標」
- Neo4j: `disc-2026-04-04-threads-analytics-implementation`

## 実行コマンド一覧

```bash
# インサイト収集
uv run python scripts/insights_collector.py --account career_sister backfill
uv run python scripts/insights_collector.py --account career_sister collect
uv run python scripts/insights_collector.py --account career_sister followers

# 分析
uv run python scripts/engagement_analyzer.py --account career_sister matrix
uv run python scripts/engagement_analyzer.py --account career_sister report
uv run python scripts/engagement_analyzer.py --account career_sister recommend
uv run python scripts/engagement_analyzer.py --account career_sister apply --dry-run
uv run python scripts/engagement_analyzer.py --account career_sister trend
```
