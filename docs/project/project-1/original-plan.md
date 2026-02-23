# Reddit 金融トピック収集ワークフロー 実装プラン

## Context

note.com や X での記事作成において「何を書くか」のトピック発見が課題。Reddit の金融・投資コミュニティ（r/stocks, r/investing, r/wallstreetbets 等）には、個人投資家のリアルな議論や注目銘柄の情報が集まっており、記事ネタの宝庫となっている。

Reddit MCP サーバーを活用して、複数の金融系 subreddit からトレンドトピックを自動収集し、情報を整理した上で、既存の `/finance-full` ワークフローに接続して note.com 記事を作成する一気通貫のフローを構築する。

**スコープ**:
- センチメント分析（強気/弱気比率）は不要
- GitHub Issue 作成は不要（ターミナル出力 + Markdown ファイル）
- X 下書き生成は将来拡張（MVP 対象外）

---

## 全体アーキテクチャ

```
/reddit-finance-topics (スラッシュコマンド)
  |
  +-- Phase 1: Reddit トピック収集（Claude Code 内で完結）
  |     +-- Reddit MCP で 10+ subreddit から投稿取得（hot/top/rising）
  |     +-- エンゲージメント & 日付フィルタリング
  |     +-- AI カテゴリ分類 & 金融関連性判定
  |     +-- スコア順ソート → 上位 N 件選択
  |     → .tmp/reddit-topics/{timestamp}.json 出力
  |
  +-- Phase 2: トピック深掘り（reddit-topic-analyzer 並列実行）
  |     +-- get_post_content で投稿本文 + コメント取得
  |     +-- 主要論点の抽出・日本語要約
  |     +-- WebSearch で補足ニュース収集
  |     +-- 記事化の切り口提案 & カテゴリ推奨
  |     → .tmp/reddit-topics/analyzed-{timestamp}.json 出力
  |
  +-- Phase 3: 結果表示 & 記事化ブリッジ
        +-- トピック一覧をマークダウンテーブルで表示
        +-- 各トピックの /finance-full コマンド例を生成
        +-- ユーザーが選択したトピックで記事作成開始
```

---

## 新規作成ファイル一覧

| # | ファイル | 説明 |
|---|---------|------|
| 1 | `data/config/reddit-subreddits.json` | subreddit 設定 + フィルタ閾値 |
| 2 | `.claude/skills/reddit-finance-topics/SKILL.md` | スキル定義（オーケストレーター） |
| 3 | `.claude/agents/reddit-topic-analyzer.md` | トピック深掘りサブエージェント |
| 4 | `.claude/commands/reddit-finance-topics.md` | スラッシュコマンド定義 |

**既存ファイル変更**: `CLAUDE.md` にスキル・コマンドの記載追加のみ。

---

## Step 1: subreddit 設定ファイル作成

**ファイル**: `data/config/reddit-subreddits.json`

```json
{
  "version": "1.0",
  "subreddit_groups": {
    "general_investing": {
      "name_ja": "一般投資",
      "subreddits": ["investing", "stocks", "StockMarket"]
    },
    "trading": {
      "name_ja": "トレード",
      "subreddits": ["wallstreetbets", "options"]
    },
    "macro_economics": {
      "name_ja": "マクロ経済",
      "subreddits": ["economics", "finance"]
    },
    "deep_analysis": {
      "name_ja": "深層分析",
      "subreddits": ["SecurityAnalysis", "ValueInvesting"]
    },
    "sector_specific": {
      "name_ja": "セクター",
      "subreddits": ["technology", "RealEstate", "CryptoCurrency"]
    }
  },
  "filters": {
    "min_score": 50,
    "min_comments": 10,
    "posts_per_subreddit": 15,
    "post_types": ["hot", "top"],
    "top_time_filter": "week",
    "exclude_flairs": ["Meme", "YOLO", "Shitpost", "Loss"]
  },
  "categories": {
    "index": "株価指数・市場全体",
    "stock": "個別銘柄・企業分析",
    "sector": "セクター動向",
    "macro": "マクロ経済・金融政策",
    "ai": "AI・テクノロジー",
    "education": "投資教育・戦略"
  }
}
```

subreddit 合計: 12個（5グループ）。設定ファイルで管理するため、後から追加・削除が容易。

---

## Step 2: スラッシュコマンド作成

**ファイル**: `.claude/commands/reddit-finance-topics.md`

エントリポイント。パラメータを解析して `reddit-finance-topics` スキルに委譲する。

パラメータ:
- `--days N`: 対象期間（デフォルト 7）
- `--top-n N`: 表示するトピック数（デフォルト 10）
- `--groups "general_investing,trading"`: 対象グループ絞り込み（デフォルト all）
- `--deep`: Phase 2 の深掘り分析を実行（デフォルト off、Phase 1 のみ）

---

## Step 3: スキル定義（メイン）

**ファイル**: `.claude/skills/reddit-finance-topics/SKILL.md`

### Phase 1: Reddit トピック収集

スキル本体（オーケストレーター）が直接実行。Python CLI は使わない（Reddit MCP 呼び出しだけで完結するため）。

```
1. 設定ファイル読み込み（data/config/reddit-subreddits.json）
2. ToolSearch("reddit") で Reddit MCP ツールをロード
3. 各 subreddit に対して:
   a. get_subreddit_hot_posts(subreddit, limit=15)
   b. get_subreddit_top_posts(subreddit, limit=15, time="week")
   → 合計: 12 subreddit × 2 種 = 24 回の MCP 呼び出し
4. 結果をマージ、post_id で重複除去
5. フィルタリング:
   - score >= 50 && num_comments >= 10
   - flair が exclude_flairs に含まれない
   - 投稿日時が --days 以内
6. AI カテゴリ分類（タイトル + selftext から判定）
   - 金融と無関係な投稿を除外
   - 6 カテゴリに分類
7. engagement_score でソート → 上位 N 件選択
8. .tmp/reddit-topics/{timestamp}.json に出力
9. マークダウンテーブルで結果表示
```

**Phase 1 出力テーブル例**:
```markdown
## Reddit 金融トピック（2026-02-23）

| # | subreddit | タイトル | スコア | コメント | カテゴリ |
|---|-----------|---------|--------|---------|---------|
| 1 | r/stocks | NVDA earnings... | 5420 | 892 | stock |
| 2 | r/economics | Fed rate... | 3210 | 456 | macro |
| ...

`--deep` オプションで詳細分析を実行できます。
```

### Phase 2: トピック深掘り（`--deep` 指定時のみ）

`reddit-topic-analyzer` サブエージェントをカテゴリ別に並列呼び出し。

```
1. Phase 1 の結果をカテゴリ別に分割
2. 各カテゴリの投稿群を reddit-topic-analyzer に渡す（並列実行）
   - get_post_content で本文 + 上位コメント取得
   - 主要論点を日本語で要約
   - WebSearch で関連ニュース確認
   - 記事化の切り口を提案
3. 結果を集約 → .tmp/reddit-topics/analyzed-{timestamp}.json
```

### Phase 3: 結果表示 & 記事化ブリッジ

```
1. 分析結果を詳細テーブルで表示
2. 各トピックに対して /finance-full コマンド例を生成:

   ### 記事化推奨トピック

   1. **NVIDIA決算前の注目ポイント** (score: 5420, 892 comments)
      - 切り口: 個人投資家が注目するNVIDIA決算の3つのポイント
      - コマンド: `/finance-full "NVIDIA決算前の注目ポイント" --category stock_analysis`

   2. **Fed利下げ観測の変化** (score: 3210, 456 comments)
      - 切り口: Redditコミュニティが語る金融政策の行方
      - コマンド: `/finance-full "Fed利下げ観測の変化" --category economic_indicators`

3. ユーザーが番号を選択 → /finance-full を自動実行
```

---

## Step 4: サブエージェント定義

**ファイル**: `.claude/agents/reddit-topic-analyzer.md`

```yaml
model: sonnet
tools: Bash, Read, ToolSearch (Reddit MCP, WebSearch)
```

**入力**: カテゴリ別のトピック群（JSON）
```json
{
  "topics": [
    {
      "post_id": "1abc123",
      "subreddit": "wallstreetbets",
      "title": "NVDA earnings play",
      "selftext": "...",
      "url": "https://reddit.com/r/...",
      "score": 5420,
      "num_comments": 892,
      "category": "stock"
    }
  ],
  "analysis_config": {
    "comment_depth": 3,
    "comment_limit": 20,
    "enable_web_search": true
  }
}
```

**処理フロー**:
1. 各トピックに `get_post_content` で詳細取得
2. 投稿本文 + 上位コメントから主要論点を抽出・日本語要約
3. `WebSearch` で関連ニュースを 2-3 件確認
4. 記事化の切り口（タイトル案 + カテゴリ推奨）を提案

**出力**:
```json
{
  "analyzed_topics": [
    {
      "post_id": "1abc123",
      "title_ja": "NVIDIA決算前 - オプション取引量が急増",
      "category": "stock",
      "key_points": [
        "データセンター需要の持続性に注目が集まっている",
        "オプション市場でのボラティリティ上昇"
      ],
      "related_news": [
        {"title": "NVIDIA Q4 earnings preview", "source": "CNBC", "url": "..."}
      ],
      "article_suggestion": {
        "title": "NVIDIA決算前の注目ポイント - 個人投資家の視点",
        "category": "stock_analysis",
        "angle": "Redditコミュニティの議論から見える3つの注目点"
      }
    }
  ]
}
```

---

## Step 5: CLAUDE.md 更新

`CLAUDE.md` の Slash Commands テーブルに追加:

```markdown
| `/reddit-finance-topics` | Reddit金融コミュニティからトピック発見・記事化 |
```

---

## 実装順序

| 順番 | 内容 | 所要見込み |
|------|------|-----------|
| 1 | `data/config/reddit-subreddits.json` 作成 | 小 |
| 2 | `.claude/commands/reddit-finance-topics.md` 作成 | 小 |
| 3 | `.claude/skills/reddit-finance-topics/SKILL.md` 作成（Phase 1 + Phase 3） | 中 |
| 4 | `.claude/agents/reddit-topic-analyzer.md` 作成（Phase 2） | 中 |
| 5 | `CLAUDE.md` 更新 | 小 |
| 6 | 動作確認（Reddit MCP 実際に呼び出してテスト） | 小 |

---

## 検証方法

1. **Phase 1 テスト**: `/reddit-finance-topics --days 7 --top-n 5` を実行し、トピック一覧テーブルが表示されることを確認
2. **Phase 2 テスト**: `/reddit-finance-topics --days 7 --top-n 3 --deep` を実行し、深掘り分析結果と記事化提案が表示されることを確認
3. **記事化ブリッジテスト**: 表示された `/finance-full` コマンド例が正しいパラメータで構成されていることを目視確認
4. **設定変更テスト**: `reddit-subreddits.json` の subreddit を変更して再実行し、対象が変わることを確認

---

## 将来拡張（MVP 対象外）

- X（旧 Twitter）下書き生成機能
- GitHub Issue 作成 & Project 連携
- 定期実行パターン（週次スケジュール）
- Notion 連携（トピック候補 DB）
- センチメント分析（強気/弱気比率）の追加
