# Threads / Instagram インプレッション解析モジュール

## Context

career_sister / mitsuki アカウントの投稿パフォーマンスを可視化し、投稿戦略を最適化する。
`posting_algorithm.md` Section 11 で設計済みのフィードバックループ（テーマ×型×スロットの3次元マトリクス）を実装する。
Threads API の `/insights` エンドポイントは `threads_basic` スコープで利用可能（App Review 不要）。

## 分析内容

### 1. 投稿単位パフォーマンス
- views（インプレッション）、likes、replies、reposts、quotes
- エンゲージメント率 = (likes + replies + reposts + quotes) / views

### 2. 3次元マトリクス分析
- **テーマ別** (T1-T10): どのトピックが最も反応を得ているか
- **型別** (型1-5, 型1-A/B): どのフォーマットが効果的か
- **スロット別** (朝/昼/夜): どの時間帯が最も届くか
- **クロス**: テーマ×型、テーマ×スロット、型×スロットの組み合わせ

### 3. トレンド分析
- 週次エンゲージメント推移（今週 vs 先週）
- フォロワー数推移

### 4. アクション提案
- テーマの weight 調整推奨（posting_state.json の themes[].weight に反映）
- 高エンゲージメント組み合わせ Top5 / 低エンゲージメント Bottom5

### 5. Instagram 比較
- 同一コンテンツの Threads vs Instagram パフォーマンス比較

---

## 重要な発見: media_id 未保存

`auto_poster.py` は `result.media_id` をログに出力するが、`posting_state.json` の `post_history` には保存していない。Insights API は media_id を必須とするため、以下で対応:

1. **バックフィル**: `GET /{user_id}/threads?fields=id,permalink` で permalink → media_id マッピングを構築
2. **今後**: `append_post_history()` に `threads_media_id` / `instagram_media_id` パラメータを追加

---

## ファイル構成

### 新規作成

| ファイル | 目的 |
|---------|------|
| `src/creator/insights.py` | API クライアント（ThreadsInsightsClient / InstagramInsightsClient） |
| `src/creator/analytics.py` | 分析ロジック（InsightsStore / EngagementAnalyzer / WeightRecommender） |
| `scripts/insights_collector.py` | CLI: API からインサイト収集 |
| `scripts/engagement_analyzer.py` | CLI: 分析・レポート・重み調整推奨 |

### 修正

| ファイル | 変更内容 |
|---------|---------|
| `scripts/auto_poster.py` L1268-1319 | `append_post_history()` に `threads_media_id` / `instagram_media_id` を追加 |
| `scripts/auto_poster.py` L1650-1657 | 呼び出し側で `result.media_id` / `ig_result.media_id` を渡す |

### データ保存先（実行時に自動生成）

```
creator/{account}/analytics/
  insights/{post_id}.json        # 投稿ごとの生インサイト
  user_insights/{date}.json      # ユーザー集計
  engagement_matrix.json         # 3次元マトリクス
  weight_history.json            # 重み調整履歴
  followers.json                 # フォロワー推移
```

---

## データモデル

### 投稿インサイト: `insights/{post_id}.json`
```json
{
  "post_id": "2026-03-31_001",
  "threads_media_id": "17841400123456789",
  "date": "2026-03-31",
  "slot": "朝",
  "category": "有益",
  "type": "型2",
  "theme": "T2",
  "threads_insights": {
    "views": 1250,
    "likes": 45,
    "replies": 12,
    "reposts": 5,
    "quotes": 2,
    "engagement_rate": 0.0512,
    "fetched_at": "2026-04-01T09:00:00+09:00"
  },
  "instagram_insights": null
}
```

### エンゲージメントマトリクス: `engagement_matrix.json`
```json
{
  "generated_at": "2026-04-04T10:00:00+09:00",
  "total_posts_analyzed": 43,
  "by_theme": {"T1": {"posts": 4, "avg_views": 1100, "avg_engagement_rate": 0.045}},
  "by_type": {"型1": {"posts": 8, "avg_views": 1200, "avg_engagement_rate": 0.052}},
  "by_slot": {"朝": {"posts": 15, "avg_views": 800, "avg_engagement_rate": 0.035}},
  "cross_dimensional": {
    "theme_x_type": {"T7_型1": {"posts": 2, "avg_engagement_rate": 0.058}},
    "theme_x_slot": {},
    "type_x_slot": {}
  },
  "top_combinations": [],
  "bottom_combinations": []
}
```

---

## CLI インターフェース

### insights_collector.py
```bash
uv run python scripts/insights_collector.py --account career_sister backfill   # 初回: media_id解決 + 全投稿インサイト取得
uv run python scripts/insights_collector.py --account career_sister collect    # 日次: 24h経過した新投稿のインサイト取得
uv run python scripts/insights_collector.py --account career_sister followers  # フォロワー数記録
```

### engagement_analyzer.py
```bash
uv run python scripts/engagement_analyzer.py --account career_sister matrix    # マトリクス構築
uv run python scripts/engagement_analyzer.py --account career_sister report    # レポート表示
uv run python scripts/engagement_analyzer.py --account career_sister recommend # 重み調整提案
uv run python scripts/engagement_analyzer.py --account career_sister apply     # 重み反映（確認あり）
uv run python scripts/engagement_analyzer.py --account career_sister trend     # トレンド表示
uv run python scripts/engagement_analyzer.py --account career_sister compare   # Threads vs IG 比較
```

---

## 実装順序

### Wave 1: 基盤（インサイト収集）
1. `src/creator/insights.py` — ThreadsInsightsClient（get_media_insights / list_user_threads / resolve_media_ids）
2. `src/creator/analytics.py` — InsightsStore（JSON read/write）
3. `scripts/insights_collector.py` — `backfill` コマンド
4. テスト: 既存43投稿の media_id 解決 + インサイト取得

### Wave 2: 前方統合
5. `scripts/auto_poster.py` — append_post_history() に media_id 追加（L1268-1319, L1650-1657）

### Wave 3: 分析
6. `src/creator/analytics.py` — EngagementAnalyzer（build_matrix / top/bottom_combinations / trend_analysis）
7. `scripts/engagement_analyzer.py` — matrix / report / trend / compare コマンド

### Wave 4: フィードバックループ
8. `src/creator/analytics.py` — WeightRecommender（recommend / apply_to_posting_state）
9. `scripts/engagement_analyzer.py` — recommend / apply コマンド
10. weight_history.json ロギング

---

## 参照ファイル

| ファイル | 用途 |
|---------|------|
| `src/creator/poster.py` | API クライアントパターン（ThreadsConfig, httpx, PostResult） |
| `scripts/auto_poster.py` L1268-1657 | StateUpdater + 投稿フロー（media_id 追加箇所） |
| `creator/career_sister/posting_state.json` | post_history スキーマ + themes[].weight |
| `creator/career_sister/posting_algorithm.md` Section 11 | フィードバックループ仕様 |
| `creator/career_sister/posting_algorithm.md` Section 4.2 | テーマ選択アルゴリズム（weight 使用箇所） |

---

## 検証方法

1. **Wave 1 検証**: `uv run python scripts/insights_collector.py --account career_sister backfill --dry-run` で media_id 解決を確認 → `--dry-run` 外して実行 → `analytics/insights/` にJSONファイルが生成されることを確認
2. **Wave 2 検証**: テスト投稿して `posting_state.json` の `post_history` に `threads_media_id` が記録されることを確認
3. **Wave 3 検証**: `uv run python scripts/engagement_analyzer.py --account career_sister report` でレポートが表示されることを確認
4. **Wave 4 検証**: `uv run python scripts/engagement_analyzer.py --account career_sister recommend --dry-run` で重み調整案が表示されることを確認
5. **E2E**: backfill → matrix → report → recommend → apply（dry-run）の一連フローを通す
